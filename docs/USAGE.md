# Usage

## Try it without a database

```shell
planwise demo
```

Three statements run against an in-memory 2,000-row table: an indexed lookup
(clean), an unindexed filter (full scan) and an unordered sort (temp B-tree).

## Check the query behind a slow endpoint

```shell
sqlite3 app.db "EXPLAIN QUERY PLAN SELECT * FROM orders WHERE customer_id = 42"
planwise check app.db "SELECT * FROM orders WHERE customer_id = 42"
```

If the first command prints `SCAN orders`, planwise reports it, counts the rows
and suggests `CREATE INDEX ... ON "orders"("customer_id")`.

## Gate CI

```shell
planwise check app.db queries/report.sql --fail-on high --out results/plan.json
```

`--fail-on high` only fails on large-table scans, which keeps adoption low
friction. Tighten to `medium` once existing scans are fixed.

## Choosing a row threshold

The default `1000` works for request-path queries. For nightly reports run with
`--row-threshold 500000` so only genuinely large scans are marked high.

## Reading suggestions safely

The emitted `CREATE INDEX IF NOT EXISTS` statements are starting points. Check
write amplification and storage before applying them to a busy database; an
index that speeds one report can slow every insert.

## Library use

```python
import sqlite3
from planwise import analyze

conn = sqlite3.connect("app.db")
analysis = analyze(conn, "SELECT * FROM orders WHERE customer_id = 42")
for finding in analysis.findings:
    print(finding.severity, finding.kind, finding.detail)
print(analysis.suggestions)
```
