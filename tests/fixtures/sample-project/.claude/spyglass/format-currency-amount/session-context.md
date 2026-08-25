# Session context — format-currency-amount

## Decisions

- Implement `format_currency` with plain stdlib string formatting (`f"{amount:,.2f} {currency_code.upper()}"`). No existing code, stdlib module, or installed package covers it directly; `locale.currency()` was considered and rejected (global, non-thread-safe locale state; formats with the locale's own symbol rather than an appended code). No new dependency needed.
- Currency code is uppercased but not otherwise validated (length/content) — deliberate, not an oversight.

## Interface

```python
def format_currency(amount: float, currency_code: str) -> str:
    """Format an amount as '1,234.50 EUR'."""
```

Module: `dataflow.report`, alongside the existing `summarise` function. `ReportBuilder` is unchanged.

## Scope

Single-session. No sub-tasks remaining. No refactors proposed or declined.
