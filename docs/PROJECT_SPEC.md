# PROJECT_SPEC — planwise

- **Name:** planwise
- **Category:** database-tooling
- **Target user:** developers and DBAs shipping SQLite-backed services
- **Problem:** `EXPLAIN QUERY PLAN` output is unreadable during review, so full
  scans and temp B-trees reach production unnoticed.
- **Solution:** a CLI that converts plan rows into severity-ranked findings,
  measures table sizes, and drafts candidate indexes.
- **Core workflow:** `planwise check <db> <sql>` → warnings + suggestions →
  exit code gates CI.
- **Must-have features:** full-scan and temp B-tree detection, row counts,
  threshold severity, index suggestions, text/JSON, demo mode.
- **Nice-to-have features:** before/after plan comparison, join-order advice.
- **Stack:** Python 3.10+ standard library (`sqlite3`).
- **Test strategy:** in-memory databases with known plans; indexed vs unindexed
  lookups; severity threshold; CLI exit codes and file inputs.
- **Demo/result strategy:** `planwise demo` plus a checked-in example query.
- **Safety considerations:** never executes the analyzed statement, no writes,
  database opened only to read.
- **Definition of done:** tests pass, install works, demo output recorded, docs
  accurate, no secrets.
