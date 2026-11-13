# Contributing

## Setup

```shell
python -m pip install -e . pytest
python -m pytest tests -q
```

## Adding a plan rule

1. Detect the plan detail in `analyze()` and emit `add(kind, severity, ...)`.
2. Keep deduplication by `(kind, table)` so repeated plan rows do not duplicate.
3. Add a test that provokes the plan (in-memory DB is enough) and one that must
   stay clean.
4. Document the kind in `docs/ARCHITECTURE.md`.

## Style

- Standard library only.
- Do not execute analysed statements; planning only.
- Suggestions must remain advisory strings, never applied automatically.

## Pull requests

Explain the plan shape you are targeting, include the query that produces it,
and confirm the test suite passes.
