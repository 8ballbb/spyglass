# format-currency-amount

## Module design

- `src/dataflow/report.py` — modified. Add one module-level function, `format_currency`, alongside the existing module-level `summarise` function. No new files; no changes to `ReportBuilder`.
- No new imports required (uses only built-in string formatting).

## Contracts

### `format_currency`
- Module: `dataflow.report`
- Preconditions: `amount` is a float; `currency_code` is a three-letter currency code string (any case).
- Postconditions: returns a string of the form `"<amount formatted with thousands separator and 2 decimals>", "<currency_code uppercased>"` joined by a space, e.g. `"1,234.50 EUR"`.
- Edge cases:
  - Negative amounts: sign stays attached to the digits, e.g. `-1234.5, "eur"` → `"-1,234.50 EUR"`.
  - Lowercase or mixed-case currency code: uppercased in the output.
  - No validation of the currency code's length or characters — used as given (uppercased) rather than rejected.
- Algorithm: format `amount` with Python's `,.2f` format spec, uppercase `currency_code`, join with a space.

## Signatures

```python
def format_currency(amount: float, currency_code: str) -> str:
    """Format an amount as '1,234.50 EUR'."""
```

Complexity budget: well under 15 (single formatting expression).
