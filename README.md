# planwise

**Read a SQLite query plan and get told, in plain language, which scan will
hurt and which index would fix it.**

## Why

SQLite happily answers a query by scanning an entire table. Nothing warns you
until the table grows and the endpoint slows down. `EXPLAIN QUERY PLAN` has the
answer, but its rows are terse (`SCAN orders`, `USE TEMP B-TREE FOR ORDER BY`)
and reviewers rarely read them. `planwise` converts those rows into severity
ranked findings, counts the rows involved, and drafts the `CREATE INDEX`
statement you probably want.

## Features

- Full-scan detection with row counts, so severity reflects real size
- Temporary B-tree detection for `ORDER BY` / `GROUP BY`
- Index suggestions derived from equality/comparison predicates and ordering
- Severity gate for CI (`--fail-on`), text and JSON output
- In-memory demo database so the tool can be tried without your own data
- Standard library only (`sqlite3`), no database writes

## Example output

Output from `planwise demo` (reproduced in `RESULTS.md`):

```text
planwise - SELECT id FROM users WHERE city = 'Cairo'
==============================================
[HIGH  ] full-scan        full table scan of users (~2000 rows)

Suggested indexes:
  CREATE INDEX IF NOT EXISTS idx_users_city ON "users"("city");

1 warning(s), worst severity: high

planwise - SELECT id FROM users ORDER BY age
==============================================
[HIGH  ] full-scan        full table scan of users (~2000 rows)
[MEDIUM] temp-btree-order use temp b-tree for order by

Suggested indexes:
  CREATE INDEX IF NOT EXISTS idx_users_age ON "users"("age");

2 warning(s), worst severity: high
```

## Architecture

```text
src/planwise/__init__.py   plan parsing, severity model, index heuristics
src/planwise/cli.py        check / demo commands, exit codes
tests/test_planwise.py     plan behaviour, thresholds, CLI
```

`analyze(conn, sql)` is the single entry point: it calls
`EXPLAIN QUERY PLAN`, groups plan rows into findings, counts rows for scanned
tables via `SELECT COUNT(*)`, and extracts candidate columns with lightweight
regexes. The CLI only renders and maps findings to exit codes.

## Requirements

- Python 3.10+
- A SQLite database file (or use `planwise demo`)

## Installation

```shell
git clone https://github.com/Wsh7Ash/planwise.git
cd planwise
python -m pip install -e .
```

## Quick start

```shell
planwise demo
planwise check ./app.db "SELECT * FROM orders WHERE customer_id = 42"
```

## Usage

```shell
# Write a JSON report and fail CI on medium findings
planwise check ./app.db queries/slow.sql --json --out results/plan.json

# Report only
planwise check ./app.db "SELECT id FROM orders ORDER BY created_at" --fail-on none

# Treat tables above 50k rows as high severity
planwise check ./app.db "SELECT * FROM events WHERE kind = 'click'" --row-threshold 50000
```

Exit codes: `0` clean/below threshold, `1` findings at or above threshold,
`2` missing database or invalid SQL.

## Configuration

Only flags: `--row-threshold`, `--fail-on`, `--json`, `--out`.

## Testing

```shell
python -m pip install -e . pytest
python -m pytest tests -q
```

## Project structure

```text
planwise/
├─ src/planwise/         analysis + CLI
├─ tests/                pytest suite
├─ examples/             sample schema and query
├─ docs/                 architecture, usage, spec
├─ results/              generated reports
└─ .github/workflows/    CI
```

## Limitations

- Index suggestions are heuristics from simple `col op value` patterns; they can
  miss joins, composite predicates and expression indexes.
- Plans reflect the current statistics. Run `ANALYZE` on the database for more
  representative plans.
- Only SQLite is supported; PostgreSQL/MySQL plans use different formats.
- Row counts are approximate planning inputs, not exact measurements under load.

## Roadmap

- Parse `EXPLAIN` bytecode for join-order advice
- Compare plans before/after a candidate index
- Emit a patch file of suggested migrations

## Security notes

The tool explains SQL against a database you supply and does not execute the
statement, so it is safe to point at production copies. Statements are still
passed to SQLite's planner; avoid pasting SQL from untrusted sources that
reference attached databases.

## License

MIT — see `LICENSE`.
