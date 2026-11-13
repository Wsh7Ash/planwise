# Changelog

## [1.0.0] - 2026-11-13

### Added

- `planwise check` for SQLite `EXPLAIN QUERY PLAN` analysis.
- Findings for full table scans and temporary B-trees (ORDER BY / GROUP BY).
- Row counts for scanned tables and size-aware severity.
- Index suggestions from comparison predicates and ordering.
- `--fail-on` CI gate, JSON output, `--out` report writing.
- `planwise demo` with an in-memory dataset.
- pytest suite covering plan parsing, thresholds and CLI exit codes.
