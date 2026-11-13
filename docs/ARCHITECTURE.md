# Architecture

## Data flow

```text
SQL text ──► EXPLAIN QUERY PLAN ──► plan rows ──► findings
                                                   │
database ──► COUNT(*) per scanned table ───────────┤
                                                   ▼
SQL text ──► predicate/order extraction ──► index suggestions
                                                   ▼
                                    render_text / render_json
```

## Findings

| Kind | Trigger | Severity |
|---|---|---|
| `full-scan` | `SCAN <table>` without `USING` | high when rows ≥ threshold, else medium |
| `temp-btree-order` | plan mentions a temp B-tree for ORDER BY | medium |
| `temp-btree-group` | plan mentions a temp B-tree for GROUP BY | medium |

`SEVERITY_ORDER` in `planwise/__init__.py` is the single source of truth for
`--fail-on` comparisons.

## Why `SCAN ... USING ...` is not flagged

SQLite prints `SCAN t USING INDEX i` when the whole index is read in order.
That is linear but index-only, and usually intentional for small reference
tables. Only a bare `SCAN t` means a full row-by-row read, so that is the only
case that produces `full-scan`.

## Row counting

`_count_rows` runs `SELECT COUNT(*) FROM "table"`. The table name comes from the
plan row, which SQLite controls, and is quoted defensively. A failure degrades
to `None`, in which case severity stays `medium`.

## Index heuristics

Two regexes over the statement (string literals stripped, comments removed):
one for `column op ?|number` predicates, one for `ORDER BY` column lists.
Names are de-duplicated, keywords filtered, and the resulting suggestion is
`CREATE INDEX IF NOT EXISTS idx_<table>_<cols> ON "<table>"(<cols>);`.
Suggestions are advisory; they are never executed.

## Error handling

`PlanError` wraps `sqlite3.Error` from the planner and empty statements, and the
CLI maps it to exit code 2 so CI can distinguish "bad query" from "slow query".
