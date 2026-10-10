from typing import Any
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
    line_id = first_present(line, "invoice_line_id", "line_id")
    if line_id is not None:
        return ("id", str(line_id))
    return (
        "composite",
        str(first_present(line, "invoice_id", default="")),
        str(first_present(line, "customer_id", default="")),
        str(first_present(line, "billing_period", "period", default="")),
        str(first_present(line, "pricing_version_id", default="")),
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


def run_reconciliation(fixture: dict[str, Any]) -> dict[str, Any]:
    source_events = records(fixture, "clean_events", "source_events", "original_events")
    observed_events = records(fixture, "observed_events", "processed_events", "ingested_events")
    expected_lines = records(fixture, "baseline_invoice_lines", "correct_invoice_lines", "expected_invoice_lines")
    actual_lines = records(fixture, "observed_invoice_lines", "actual_invoice_lines", "invoice_lines")

    findings = {
        "duplicate_events": detect_duplicates(observed_events),
        "missing_events": detect_missing(source_events, observed_events),
        "invoice_mismatches": compare_invoice_lines(expected_lines, actual_lines),
        "calculation_mismatches": verify_calculations(actual_lines),
    }
    total = sum(len(items) for items in findings.values())
    return {
        "case_id": "RECON-DEMO-001",
        "status": "review_required" if total else "no_discrepancy_detected",
        "finding_count": total,
        "findings": findings,
        "limitations": [
            "Missing events are proven against the authoritative source ledger in this synthetic fixture.",
            "Expected invoice lines currently come from the fixture baseline; effective-dated pricing reconstruction is a later step.",
            "This API is read-only and does not modify invoices or payments.",
        ],
    }
