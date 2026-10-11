from app.graph.workflow import collect_pricing_evidence

def make_report():
    expected_line = {
        "invoice_id": "INV-001",
        "customer_id": "CUS-001",
        "billing_period": "2026-07",
        "pricing_version_id": "PRICE-V2",
        "quantity": "100",
        "unit_price": "0.0120",
        "amount": "1.20",
        "currency": "USD",
        "calculation_method": "authoritative_usage_x_effective_unit_price",
        "source_event_ids": ["EVT-001", "EVT-002"],
    }

    return {
        "findings": {
            "invoice_mismatches": [
                {"evidence": {"expected_line": expected_line}}
            ],
            "calculation_mismatches": [
                {"evidence": {"expected_line": expected_line}}
            ],
            "pricing_errors": [],
        }
    }


def test_pricing_evidence_contains_reconstructed_amount():
    evidence = collect_pricing_evidence(make_report())

    assert len(evidence) == 1
    assert evidence[0].evidence_id == (
        "pricing-reconstruction:CUS-001:2026-07:PRICE-V2"
    )
    assert "expected_amount=1.20" in evidence[0].description
    assert "EVT-001" in evidence[0].description


def test_duplicate_findings_produce_one_evidence_reference():
    evidence = collect_pricing_evidence(make_report())

    assert len(evidence) == 1


def test_missing_expected_line_is_ignored():
    report = {
        "findings": {
            "invoice_mismatches": [
                {"evidence": {"actual_line": {"amount": "1.20"}}}
            ],
            "calculation_mismatches": [],
        }
    }

    assert collect_pricing_evidence(report) == []

def test_reads_complete_expected_invoice_lines():
    report = {
        "expected_invoice_lines": [
            {
                "customer_id": "CUS-2001",
                "billing_period": "2026-07",
                "pricing_version_id": "PRICE-GROWTH-V1",
                "quantity": "500",
                "unit_price": "0.0200",
                "amount": "10.00",
                "currency": "USD",
                "calculation_method": (
                    "authoritative_usage_x_effective_unit_price"
                ),
                "source_event_ids": ["EVT-2001-001"],
            }
        ],
        "findings": {},
    }

    evidence = collect_pricing_evidence(report)

    assert len(evidence) == 1
    assert evidence[0].evidence_id == (
        "pricing-reconstruction:CUS-2001:2026-07:PRICE-GROWTH-V1"
    )
    assert "expected_amount=10.00" in evidence[0].description


def test_clean_invoice_line_is_included_without_discrepancy():
    report = {
        "expected_invoice_lines": [
            {
                "customer_id": "CUS-3001",
                "billing_period": "2026-07",
                "pricing_version_id": "PRICE-PRO-V1",
                "quantity": "100",
                "unit_price": "0.0500",
                "amount": "5.00",
                "currency": "USD",
                "calculation_method": (
                    "authoritative_usage_x_effective_unit_price"
                ),
                "source_event_ids": ["EVT-3001-001"],
            }
        ],
        "findings": {
            "invoice_mismatches": [],
            "calculation_mismatches": [],
        },
    }

    evidence = collect_pricing_evidence(report)

    assert len(evidence) == 1
    assert "expected_amount=5.00" in evidence[0].description