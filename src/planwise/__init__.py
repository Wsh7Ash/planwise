"""planwise - read SQLite query plans and point out the expensive parts.

``analyze()`` runs ``EXPLAIN QUERY PLAN`` for a statement, turns the plan rows
into findings (full table scans, temporary B-trees) and proposes indexes based
on simple predicate/ordering extraction. It never modifies the database.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Iterable, Sequence

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}

_KEYWORDS = {
    "select", "from", "where", "and", "or", "not", "in", "is", "null", "like",
    "glob", "between", "order", "group", "by", "having", "limit", "offset",
    "join", "inner", "left", "right", "outer", "cross", "on", "as", "case",
    "when", "then", "else", "end", "distinct", "union", "all", "exists",
}


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    detail: str
    table: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Analysis:
    sql: str
    findings: list[Finding] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)

    @property
    def worst(self) -> str:
        for severity in ("high", "medium", "low"):
            if any(f.severity == severity for f in self.findings):
                return severity
        return "none"

    def to_dict(self) -> dict:
        return {
            "sql": self.sql,
            "worst": self.worst,
            "findings": [f.to_dict() for f in self.findings],
            "suggestions": list(self.suggestions),
            "row_counts": dict(self.row_counts),
        }


class PlanError(ValueError):
    """Raised when SQLite cannot explain the supplied statement."""


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _scan_table(detail: str) -> str:
    rest = detail[len("SCAN "):]
    return rest.split(" USING ")[0].strip().strip('"')


def _count_rows(conn: sqlite3.Connection, table: str) -> int | None:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {_quote(table)}").fetchone()
        return int(row[0]) if row else None
    except sqlite3.Error:
        return None


def _clean_sql(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def _columns_from_sql(sql: str) -> tuple[list[str], list[str]]:
    """Return (equality/comparison columns, order-by columns) in first-seen order."""
    text = re.sub(r"'[^']*'", "?", sql)
    text = re.sub(r"--[^\n]*", " ", text)

    where_columns: list[str] = []
    for match in re.finditer(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|>=|<=|>|<)\s*(?:\?|\d+)", text
    ):
        column = match.group(1)
        if column.lower() not in _KEYWORDS:
            where_columns.append(column.split(".")[-1])

    order_columns: list[str] = []
    for match in re.finditer(r"ORDER\s+BY\s+(.+?)(?:\s+LIMIT\b|\s*$)", text, re.IGNORECASE | re.DOTALL):
        for part in match.group(1).split(","):
            token = part.strip().split()[0] if part.strip() else ""
            token = token.split(".")[-1]
            if token and token.lower() not in _KEYWORDS:
                order_columns.append(token)

    def unique(items: Iterable[str]) -> list[str]:
        seen: list[str] = []
        for item in items:
            if item not in seen:
                seen.append(item)
        return seen

    return unique(where_columns), unique(order_columns)


def _index_name(table: str, columns: Sequence[str]) -> str:
    raw = f"idx_{table}_{'_'.join(columns)}"
    return re.sub(r"[^A-Za-z0-9_]", "_", raw)


def analyze(conn: sqlite3.Connection, sql: str, row_threshold: int = 1000) -> Analysis:
    """Explain ``sql`` and return findings plus suggested indexes."""
    statement = _clean_sql(sql)
    if not statement:
        raise PlanError("empty SQL statement")

    try:
        plan_rows = conn.execute("EXPLAIN QUERY PLAN " + statement).fetchall()
    except sqlite3.Error as exc:
        raise PlanError(f"SQLite could not explain the statement: {exc}") from exc

    result = Analysis(sql=statement)
    seen: set[tuple[str, str | None]] = set()

    def add(kind: str, severity: str, detail: str, table: str | None) -> None:
        key = (kind, table)
        if key in seen:
            return
        seen.add(key)
        result.findings.append(Finding(kind, severity, detail, table))

    for row in plan_rows:
        detail = str(row[-1])
        upper = detail.upper()

        if upper.startswith("SCAN ") and "CONSTANT ROW" not in upper:
            if " USING " in upper:
                continue  # index-assisted scan; not a full table scan
            table = _scan_table(detail)
            count = _count_rows(conn, table)
            if count is not None:
                result.row_counts[table] = count
            severity = "high" if (count or 0) >= row_threshold else "medium"
            note = f"full table scan of {table}"
            if count is not None:
                note += f" (~{count} rows)"
            add("full-scan", severity, note, table)
        elif "TEMP B-TREE" in upper:
            kind = "temp-btree-order" if "ORDER BY" in upper else "temp-btree-group"
            add(kind, "medium", detail.lower(), None)

    where_columns, order_columns = _columns_from_sql(statement)
    scanned = sorted({f.table for f in result.findings if f.table})
    for table in scanned:
        columns = where_columns or order_columns
        # If ORDER BY brings its own columns, prefer a covering suggestion.
        if order_columns and set(where_columns) != set(order_columns):
            combined = list(dict.fromkeys(where_columns + order_columns))
            columns = combined
        if columns:
            cols = ", ".join(_quote(c) for c in columns)
            result.suggestions.append(
                f"CREATE INDEX IF NOT EXISTS {_index_name(table, columns)} "
                f"ON {_quote(table)}({cols});"
            )
    return result


def render_text(analysis: Analysis, target: str = "") -> str:
    lines = [f"planwise{f' - {target}' if target else ''}", "=" * 46]
    if not analysis.findings:
        lines.append("No plan warnings. SQLite used indexes for this statement.")
        return "\n".join(lines)
    for finding in analysis.findings:
        lines.append(f"[{finding.severity.upper():6}] {finding.kind:16} {finding.detail}")
    if analysis.suggestions:
        lines.append("")
        lines.append("Suggested indexes:")
        lines.extend(f"  {s}" for s in analysis.suggestions)
    lines.append("")
    lines.append(f"{len(analysis.findings)} warning(s), worst severity: {analysis.worst}")
    return "\n".join(lines)


def render_json(analysis: Analysis, target: str = "") -> str:
    payload = analysis.to_dict()
    payload = {"target": target, **payload}
    return json.dumps(payload, indent=2)


def at_or_above(findings: Sequence[Finding], threshold: str) -> list[Finding]:
    if threshold == "none":
        return []
    limit = SEVERITY_ORDER[threshold]
    return [f for f in findings if SEVERITY_ORDER[f.severity] >= limit]
