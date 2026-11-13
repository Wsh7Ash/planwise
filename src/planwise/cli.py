"""Command line interface for planwise."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

from . import PlanError, analyze, at_or_above, render_json, render_text

DEMO_SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, age INTEGER, city TEXT);
CREATE INDEX users_email ON users(email);
"""


def _read_query(value: str) -> str:
    if os.path.isfile(value):
        with open(value, "r", encoding="utf-8") as handle:
            return handle.read()
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="planwise",
        description="Explain a SQLite statement and report full scans / temp B-trees.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="analyse a statement against a database")
    check.add_argument("database", help="path to a SQLite database file")
    check.add_argument("query", help="SQL text or path to a .sql file")
    check.add_argument("--json", action="store_true", help="emit JSON")
    check.add_argument("--row-threshold", type=int, default=1000,
                       help="table size at which a full scan becomes high severity (default 1000)")
    check.add_argument("--fail-on", choices=["none", "low", "medium", "high"], default="medium")
    check.add_argument("--out", help="also write the report to this path")

    sub.add_parser("demo", help="run against a throwaway demo database")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "demo":
        conn = sqlite3.connect(":memory:")
        conn.executescript(DEMO_SCHEMA)
        conn.executemany(
            "INSERT INTO users (email, age, city) VALUES (?, ?, ?)",
            [(f"user{i}@example.com", 20 + i % 40, "Cairo") for i in range(1, 2001)],
        )
        conn.commit()
        for statement in (
            "SELECT * FROM users WHERE email = 'user7@example.com'",
            "SELECT id FROM users WHERE city = 'Cairo'",
            "SELECT id FROM users ORDER BY age",
        ):
            analysis = analyze(conn, statement, 1000)
            print(render_text(analysis, statement))
            print()
        conn.close()
        return 0

    if not os.path.isfile(args.database):
        print(f"planwise: database not found: {args.database}", file=sys.stderr)
        return 2

    try:
        statement = _read_query(args.query)
    except OSError as exc:
        print(f"planwise: cannot read query: {exc}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.database)
    try:
        analysis = analyze(conn, statement, args.row_threshold)
    except PlanError as exc:
        print(f"planwise: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()

    report = render_json(analysis, args.database) if args.json else render_text(analysis, args.database)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(report + "\n")

    if args.fail_on != "none" and at_or_above(analysis.findings, args.fail_on):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
