from datetime import date
from decimal import Decimal

import pytest

from app.services.reconciliation import (
    reconstruct_expected_invoice_lines,
    select_pricing_version,
)

from decimal import Decimal

from app.services.reconciliation import (
    reconstruct_expected_invoice_lines,
)
from app.tools.billing_tools import load_fixture


def test_selects_july_starter_pricing():
    versions = [
        {
            "pricing_version_id": "V1",
            "plan_id": "STARTER",
            "unit_price": "0.0100",
            "effective_from": "2026-01-01",
            "effective_to": "2026-06-30",
        },
        {
            "pricing_version_id": "V2",
            "plan_id": "STARTER",
            "unit_price": "0.0120",
            "effective_from": "2026-07-01",
            "effective_to": None,
        },
    ]

    result = select_pricing_version(
        "STARTER",
        "2026-07-03T09:00:00+00:00",
        versions,
    )

    assert result["pricing_version_id"] == "V2"
    assert Decimal(result["unit_price"]) == Decimal("0.0120")


def test_rejects_ambiguous_pricing():
    versions = [
        {
            "pricing_version_id": "V1",
            "plan_id": "STARTER",
            "unit_price": "0.0100",
            "effective_from": "2026-01-01",
            "effective_to": None,
        },
        {
            "pricing_version_id": "V2",
            "plan_id": "STARTER",
            "unit_price": "0.0120",
            "effective_from": "2026-07-01",
            "effective_to": None,
        },
    ]

    with pytest.raises(ValueError, match="Ambiguous pricing"):
        select_pricing_version(
            "STARTER",
            "2026-07-03T09:00:00+00:00",
            versions,
        )

def test_reconstructs_cus1001_july_invoice_from_source_events():
    fixture = load_fixture()

    expected_lines, errors = reconstruct_expected_invoice_lines(fixture)

    assert errors == []

    line = next(
        item for item in expected_lines
        if item["customer_id"] == "CUS-1001"
    )

    assert line["billing_period"] == "2026-07"
    assert line["pricing_version_id"] == "PRICE-STARTER-V2"
    assert Decimal(line["quantity"]) == Decimal("2979")
    assert Decimal(line["unit_price"]) == Decimal("0.0120")
    assert Decimal(line["amount"]) == Decimal("35.75")
