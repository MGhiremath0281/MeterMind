from typing import Any
from datetime import date
from collections import defaultdict
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP


def first_present(record: dict[str, Any], *keys: str, default=None):
    for key in keys:
        if key in record:
            return record[key]
    return default


def records(fixture: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = fixture.get(key)
        if isinstance(value, list):
            return value
    raise ValueError(
        f"Missing expected fixture list. Tried {keys}. Available keys: {list(fixture.keys())}"
    )


def get_event_id(event: dict[str, Any]) -> str:
    value = first_present(event, "event_id", "id", "usage_event_id")
    if value is None:
        raise ValueError(f"Event is missing its ID: {event}")
    return str(value)


def decimal_value(value: Any) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def money(value: Any) -> Decimal:
    return decimal_value(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def line_amount(line: dict[str, Any]) -> Decimal:
    amount = first_present(line, "amount", "line_amount", "total")
    if amount is not None:
        return money(amount)
    quantity = decimal_value(first_present(line, "quantity", default=0))
    price = decimal_value(first_present(line, "unit_price", "price_per_unit", default=0))
    return money(quantity * price)



def line_key(line: dict[str, Any]) -> tuple:
    customer_id = first_present(line, "customer_id")
    billing_period = first_present(
        line, "billing_period", "period"
    )
    pricing_version_id = first_present(
        line, "pricing_version_id"
    )

    if (
        customer_id is not None
        and billing_period is not None
        and pricing_version_id is not None
    ):
        return (
            "billing",
            str(customer_id),
            str(billing_period),
            str(pricing_version_id),
        )

    line_id = first_present(
        line, "invoice_line_id", "line_id"
    )
    if line_id is not None:
        return ("id", str(line_id))

    raise ValueError(
        f"Cannot establish invoice line identity: {line}"
    )


def detect_duplicates(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(get_event_id(event) for event in events)
    findings = []
    for event_id, count in sorted(counts.items()):
        if count > 1:
            matching = [event for event in events if get_event_id(event) == event_id]
            findings.append({
                "finding_type": "duplicate_event",
                "severity": "high",
                "event_id": event_id,
                "occurrences": count,
                "duplicate_copies": count - 1,
                "customer_ids": sorted({
                    str(first_present(event, "customer_id", default="unknown"))
                    for event in matching
                }),
                "evidence": {"records": matching},
                "requires_review": True,
            })
    return findings


def detect_missing(
    source_events: list[dict[str, Any]],
    observed_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_counts = Counter(get_event_id(event) for event in source_events)
    observed_counts = Counter(get_event_id(event) for event in observed_events)
    source_by_id = {get_event_id(event): event for event in source_events}
    findings = []
    for event_id, expected_count in sorted(source_counts.items()):
        actual_count = observed_counts.get(event_id, 0)
        if actual_count < expected_count:
            source = source_by_id[event_id]
            findings.append({
                "finding_type": "missing_event",
                "severity": "high",
                "event_id": event_id,
                "expected_occurrences": expected_count,
                "observed_occurrences": actual_count,
                "missing_copies": expected_count - actual_count,
                "customer_id": str(first_present(source, "customer_id", default="unknown")),
                "evidence": {"authoritative_event": source},
                "requires_review": True,
            })
    return findings


def compare_invoice_lines(
    expected_lines: list[dict[str, Any]],
    actual_lines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected = {line_key(line): line for line in expected_lines}
    actual = {line_key(line): line for line in actual_lines}
    findings = []
    for key in sorted(set(expected) | set(actual), key=str):
        exp = expected.get(key)
        act = actual.get(key)
        if exp is None:
            amount = line_amount(act)
            findings.append({
                "finding_type": "unexpected_invoice_line",
                "severity": "medium",
                "line_key": key,
                "expected_amount": "0.00",
                "actual_amount": str(amount),
                "difference": str(amount),
                "requires_review": True,
            })
            continue
        if act is None:
            amount = line_amount(exp)
            findings.append({
                "finding_type": "missing_invoice_line",
                "severity": "high",
                "line_key": key,
                "expected_amount": str(amount),
                "actual_amount": "0.00",
                "difference": str(-amount),
                "requires_review": True,
            })
            continue

        exp_amount, act_amount = line_amount(exp), line_amount(act)
        diff = money(act_amount - exp_amount)
        if diff != Decimal("0.00"):
            findings.append({
                "finding_type": "invoice_amount_mismatch",
                "severity": "high" if abs(diff) >= Decimal("5.00") else "medium",
                "line_key": key,
                "customer_id": str(first_present(act, "customer_id", default=first_present(exp, "customer_id", default="unknown"))),
                "expected_amount": str(exp_amount),
                "actual_amount": str(act_amount),
                "difference": str(diff),
                "direction": "overcharge" if diff > 0 else "undercharge",
                "evidence": {"expected_line": exp, "actual_line": act},
                "requires_review": True,
            })
    return findings


def verify_calculations(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for line in lines:
        quantity = decimal_value(first_present(line, "quantity", default=0))
        unit_price = decimal_value(first_present(line, "unit_price", "price_per_unit", default=0))
        recorded = line_amount(line)
        calculated = money(quantity * unit_price)
        if recorded != calculated:
            findings.append({
                "finding_type": "calculation_mismatch",
                "severity": "high",
                "invoice_line_id": str(first_present(line, "invoice_line_id", "line_id", "id", default="unknown")),
                "quantity": str(quantity),
                "unit_price": str(unit_price),
                "recorded_amount": str(recorded),
                "calculated_amount": str(calculated),
                "difference": str(money(recorded - calculated)),
                "requires_review": True,
            })
    return findings

def select_pricing_version(
    plan_id: str,
    occurred_at: str,
    pricing_versions: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Select exactly one pricing version effective on the
    usage event's calendar date.

    effective_from and effective_to are treated as inclusive
    calendar dates. An absent effective_to means no end date.
    """
    event_date = date.fromisoformat(occurred_at[:10])

    matches = []

    for version in pricing_versions:
        if str(version.get("plan_id")) != str(plan_id):
            continue

        effective_from = date.fromisoformat(
            str(version["effective_from"])
        )

        effective_to_value = version.get("effective_to")
        effective_to = (
            date.fromisoformat(str(effective_to_value))
            if effective_to_value
            else None
        )

        if event_date < effective_from:
            continue

        if effective_to is not None and event_date > effective_to:
            continue

        matches.append(version)

    if not matches:
        raise ValueError(
            f"No effective pricing version for plan={plan_id}, "
            f"date={event_date}"
        )

    if len(matches) > 1:
        version_ids = [
            str(item.get("pricing_version_id"))
            for item in matches
        ]
        raise ValueError(
            f"Ambiguous pricing for plan={plan_id}, "
            f"date={event_date}: {version_ids}"
        )

    return matches[0]


def reconstruct_expected_invoice_lines(
    fixture: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Independently reconstruct expected invoice lines from
    authoritative usage events, customer plans, and pricing.

    Returns:
        (expected_lines, pricing_errors)

    This implementation assumes:
    - Pricing is per usage unit.
    - The fixture's pricing applies to its usage metric.
    - Billing is grouped by customer, month, and pricing version.
    - Each reconstructed line is rounded to cents using
      ROUND_HALF_UP.
    """
    source_events = records(
        fixture, "clean_events", "source_events", "original_events"
    )
    customers = records(fixture, "customers")
    pricing_versions = records(fixture, "pricing_versions")

    customers_by_id = {
        str(customer["customer_id"]): customer
        for customer in customers
    }

    # group_key -> accumulated quantity and pricing metadata
    groups: dict[tuple, dict[str, Any]] = {}
    pricing_errors: list[dict[str, Any]] = []

    for event in source_events:
        event_id = get_event_id(event)
        customer_id = str(
            first_present(event, "customer_id", default="")
        )
        occurred_at = first_present(event, "occurred_at")

        try:
            if not occurred_at:
                raise ValueError("Usage event has no occurred_at")

            customer = customers_by_id.get(customer_id)
            if customer is None:
                raise ValueError(
                    f"Unknown customer_id={customer_id}"
                )

            plan_id = str(customer["plan_id"])

            version = select_pricing_version(
                plan_id=plan_id,
                occurred_at=str(occurred_at),
                pricing_versions=pricing_versions,
            )

            quantity = decimal_value(
                first_present(event, "quantity")
            )
            if quantity < 0:
                raise ValueError(
                    f"Negative usage quantity for event {event_id}"
                )

            unit_price = decimal_value(version["unit_price"])
            if unit_price < 0:
                raise ValueError(
                    f"Negative unit price in "
                    f"{version['pricing_version_id']}"
                )

            period = str(occurred_at)[:7]
            version_id = str(version["pricing_version_id"])

            group_key = (
                customer_id,
                period,
                version_id,
            )

            if group_key not in groups:
                groups[group_key] = {
                    "customer_id": customer_id,
                    "plan_id": plan_id,
                    "billing_period": period,
                    "pricing_version_id": version_id,
                    "unit_price": unit_price,
                    "currency": str(
                        customer.get("currency", "USD")
                    ),
                    "quantity": Decimal("0"),
                    "event_ids": [],
                }

            group = groups[group_key]

            # Defensive check: one pricing version must not
            # resolve to inconsistent prices.
            if group["unit_price"] != unit_price:
                raise ValueError(
                    f"Inconsistent unit price for {version_id}"
                )

            group["quantity"] += quantity
            group["event_ids"].append(event_id)

        except (KeyError, TypeError, ValueError) as exc:
            pricing_errors.append({
                "finding_type": "pricing_reconstruction_error",
                "severity": "high",
                "event_id": event_id,
                "customer_id": customer_id,
                "occurred_at": occurred_at,
                "description": str(exc),
                "requires_review": True,
            })

    expected_lines = []

    # Only produce complete expected lines. A pricing error
    # must never silently turn into a zero-dollar charge.
    if pricing_errors:
        return [], pricing_errors

    for group_key in sorted(groups):
        group = groups[group_key]

        quantity = group["quantity"]
        unit_price = group["unit_price"]
        expected_amount = money(quantity * unit_price)

        expected_lines.append({
            "invoice_id": next(
                (
                    str(line["invoice_id"])
                    for line in records(
                        fixture,
                        "baseline_invoice_lines",
                        "correct_invoice_lines",
                        "expected_invoice_lines",
                    )
                    if (
                        str(line.get("customer_id"))
                        == group["customer_id"]
                        and str(
                            first_present(
                                line, "billing_period", "period", default=""
                            )
                        ) == group["billing_period"]
                    )
                ),
                "",
            ),
            "customer_id": group["customer_id"],
            "billing_period": group["billing_period"],
            "plan_id": group["plan_id"],
            "pricing_version_id": group["pricing_version_id"],
            "quantity": str(quantity),
            "unit_price": str(unit_price),
            "amount": str(expected_amount),
            "currency": group["currency"],
            "source_event_ids": group["event_ids"],
            "calculation_method": (
                "authoritative_usage_x_effective_unit_price"
            ),
        })

    return expected_lines, pricing_errors

def run_reconciliation(
    fixture: dict[str, Any],
) -> dict[str, Any]:
    source_events = records(
        fixture, "clean_events", "source_events", "original_events"
    )
    observed_events = records(
        fixture, "observed_events", "processed_events", "ingested_events"
    )
    actual_lines = records(
        fixture, "observed_invoice_lines",
        "actual_invoice_lines", "invoice_lines"
    )

    # Reconstruct expected charges instead of trusting the
    # fixture's precomputed invoice baseline.
    expected_lines, pricing_errors = (
        reconstruct_expected_invoice_lines(fixture)
    )

    findings = {
        "duplicate_events": detect_duplicates(observed_events),
        "missing_events": detect_missing(
            source_events, observed_events
        ),
        "invoice_mismatches": (
            compare_invoice_lines(expected_lines, actual_lines)
            if not pricing_errors
            else []
        ),
        "calculation_mismatches": verify_calculations(actual_lines),
        "pricing_errors": pricing_errors,
    }

    total = sum(len(items) for items in findings.values())

    return {
        "case_id": fixture.get(
            "case_id", "RECON-DEMO-001"
        ),
        "status": (
            "review_required"
            if total
            else "no_discrepancy_detected"
        ),
        "finding_count": total,
        "findings": findings,
        "expected_invoice_lines": expected_lines,
        "limitations": [
            "Expected charges are reconstructed from the authoritative "
            "source ledger and effective-dated pricing.",
            "Duplicate and missing observed events are assessed separately "
            "from the authoritative usage used for expected billing.",
            "Invoice amount mismatches and arithmetic mismatches can "
            "describe the same underlying financial incident.",
            "This API is read-only and does not modify invoices or payments.",
        ],
    }