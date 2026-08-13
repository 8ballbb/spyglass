from dataflow.timeutils import normalise_date


def test_normalise_date_iso_passthrough():
    assert normalise_date("2026-01-15").startswith("2026-01-15")
