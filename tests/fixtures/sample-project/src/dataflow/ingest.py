"""Record ingestion."""

import csv
from pathlib import Path


def load_records(path: Path, strict: bool = False, skip_blank: bool = True) -> list[dict]:
    """Load records from a CSV file."""
    records = []
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if skip_blank and not any(row.values()):
                continue
            if "id" not in row or not row["id"]:
                if strict:
                    raise ValueError("missing id")
                else:
                    continue
            if "amount" in row and row["amount"]:
                try:
                    row["amount"] = float(row["amount"])
                except ValueError:
                    if strict:
                        raise
                    row["amount"] = 0.0
            else:
                row["amount"] = 0.0
            if "status" in row and row["status"] not in ("open", "closed"):
                if strict:
                    raise ValueError("bad status")
                row["status"] = "open"
            records.append(row)
    return records
