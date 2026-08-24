# Decisions

| Date | Decision | Because | From |
|------|----------|---------|------|
| 2026-08-24 | Not adopting `python-dateutil` for date normalisation | Declared in `pyproject.toml` but not actually installed; even if installed, its loose format-guessing parser would accept a broader grammar than `normalise_date`'s fixed three `strptime` formats, silently widening accepted input | batch-normalise-dates |
