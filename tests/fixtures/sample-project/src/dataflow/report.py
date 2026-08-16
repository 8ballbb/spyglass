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


class ReportBuilder:
    """Accumulates records and derives figures from them.

    This class is deliberately close to the size limit the design process
    enforces. A plan that adds several more aggregations to it should notice
    that it would push the class past that limit, and say so before any code is
    written rather than after.

    Parameters
    ----------
    records : list of dict
        The records to report on.
    """

    def __init__(self, records: list[dict]) -> None:
        self._records = list(records)

    def _total_where(self, status: str) -> float:
        """Total of the amounts whose status matches.

        Parameters
        ----------
        status : str
            The status to filter on.

        Returns
        -------
        float
            The filtered total.
        """
        return sum(r.get("amount", 0.0) for r in self._records
                   if r.get("status") == status)

    def total(self) -> float:
        """Total of every amount.

        Returns
        -------
        float
            The computed value.
        """
        return sum(r.get('amount', 0.0) for r in self._records)

    def count(self) -> float:
        """Number of records held.

        Returns
        -------
        float
            The computed value.
        """
        return len(self._records)

    def mean(self) -> float:
        """Mean amount, or 0.0 when empty.

        Returns
        -------
        float
            The computed value.
        """
        return self.total() / self.count() if self._records else 0.0

    def minimum(self) -> float:
        """Smallest amount seen.

        Returns
        -------
        float
            The computed value.
        """
        return min((r.get('amount', 0.0) for r in self._records), default=0.0)

    def maximum(self) -> float:
        """Largest amount seen.

        Returns
        -------
        float
            The computed value.
        """
        return max((r.get('amount', 0.0) for r in self._records), default=0.0)

    def spread(self) -> float:
        """Difference between largest and smallest.

        Returns
        -------
        float
            The computed value.
        """
        return self.maximum() - self.minimum()

    def open_total(self) -> float:
        """Total of records still open.

        Returns
        -------
        float
            The computed value.
        """
        return self._total_where('open')

    def closed_total(self) -> float:
        """Total of records already closed.

        Returns
        -------
        float
            The computed value.
        """
        return self._total_where('closed')

    def format_total(self) -> str:
        """Render total for display.

        Returns
        -------
        str
            A formatted, human-readable line.
        """
        return f"total: {self.total():,.2f}"

    def format_count(self) -> str:
        """Render count for display.

        Returns
        -------
        str
            A formatted, human-readable line.
        """
        return f"count: {self.count():,.2f}"

    def format_mean(self) -> str:
        """Render mean for display.

        Returns
        -------
        str
            A formatted, human-readable line.
        """
        return f"mean: {self.mean():,.2f}"

    def format_minimum(self) -> str:
        """Render minimum for display.

        Returns
        -------
        str
            A formatted, human-readable line.
        """
        return f"minimum: {self.minimum():,.2f}"

    def format_maximum(self) -> str:
        """Render maximum for display.

        Returns
        -------
        str
            A formatted, human-readable line.
        """
        return f"maximum: {self.maximum():,.2f}"

    def format_spread(self) -> str:
        """Render spread for display.

        Returns
        -------
        str
            A formatted, human-readable line.
        """
        return f"spread: {self.spread():,.2f}"

    def format_open_total(self) -> str:
        """Render open_total for display.

        Returns
        -------
        str
            A formatted, human-readable line.
        """
        return f"open_total: {self.open_total():,.2f}"

    def format_closed_total(self) -> str:
        """Render closed_total for display.

        Returns
        -------
        str
            A formatted, human-readable line.
        """
        return f"closed_total: {self.closed_total():,.2f}"
