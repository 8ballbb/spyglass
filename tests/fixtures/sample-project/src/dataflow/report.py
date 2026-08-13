"""Reporting helpers."""


def summarise(records: list[dict]) -> dict:
    """Summarise a list of records.

    Parameters
    ----------
    records : list of dict
        Records to summarise.

    Returns
    -------
    dict
        Totals keyed by status.
    """
    totals: dict[str, float] = {}
    for record in records:
        status = record.get("status", "open")
        totals[status] = totals.get(status, 0.0) + record.get("amount", 0.0)
    return totals
