"""Date and time helpers."""

from datetime import datetime, timezone


def normalise_date(value: str, assume_utc: bool = True) -> str:
    """Convert a loose date string into an ISO-8601 timestamp.

    Args:
        value: A date string in one of several accepted formats.
        assume_utc: Treat naive inputs as UTC rather than local time.

    Returns:
        An ISO-8601 formatted timestamp string.

    Raises:
        ValueError: If the value matches none of the accepted formats.
    """
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if assume_utc and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    raise ValueError(f"unrecognised date format: {value!r}")
