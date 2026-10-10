import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from langchain.tools import tool

from app.services.reconciliation import run_reconciliation


FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "metermind_synthetic_fixture.json"
)


def load_fixture() -> dict[str, Any]:
    if not FIXTURE_PATH.exists():
        raise FileNotFoundError(
            f"MeterMind fixture not found: {FIXTURE_PATH}"
        )

    with FIXTURE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_report() -> dict[str, Any]:
    return run_reconciliation(load_fixture())


def get_findings(*groups: str) -> list[dict[str, Any]]:
    report = get_report()
    all_findings = report.get("findings", {})

    return [
        finding
        for group in groups
        for finding in all_findings.get(group, [])
    ]


def serialize(data: Any) -> str:
    return json.dumps(data, default=str, indent=2)


@tool
def inspect_event_anomalies() -> str:
    """Find duplicate and missing usage events using deterministic checks.
    Return event IDs, affected customers, and supporting evidence.
    """
    return serialize({
        "duplicate_events": get_findings("duplicate_events"),
        "missing_events": get_findings("missing_events"),
    })


@tool
def inspect_pricing_data() -> str:
    """Retrieve customer plans and pricing versions from the fixture.
    Use the returned data to investigate pricing questions. Do not assume
    that the newest price applies to older usage.
    """
    fixture = load_fixture()

    return serialize({
        "customers": fixture.get("customers", []),
        "pricing_versions": fixture.get(
            "pricing_versions",
            fixture.get("pricing", []),
        ),
        "available_fixture_keys": list(fixture.keys()),
    })


@tool
def inspect_invoice_discrepancies() -> str:
    """Retrieve deterministic invoice mismatches and arithmetic findings,
    including expected amounts, recorded amounts, and differences.
    """
    return serialize({
        "invoice_mismatches": get_findings("invoice_mismatches"),
        "calculation_mismatches": get_findings(
            "calculation_mismatches"
        ),
    })


@tool
def retrieve_audit_evidence() -> str:
    """Retrieve the complete deterministic reconciliation report for
    independent audit. Includes all findings and known limitations.
    """
    return serialize(get_report())


@tool
def verify_invoice_arithmetic(
    quantity: float,
    unit_price: float,
    recorded_amount: float,
) -> str:
    """Independently verify quantity multiplied by unit price against
    a recorded invoice amount. This checks arithmetic only.
    """
    expected = (
        Decimal(str(quantity)) * Decimal(str(unit_price))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    recorded = Decimal(str(recorded_amount)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    return serialize({
        "quantity": str(quantity),
        "unit_price": str(unit_price),
        "expected_amount": str(expected),
        "recorded_amount": str(recorded),
        "difference": str(recorded - expected),
        "matches": expected == recorded,
    })