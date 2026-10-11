import pytest

from app.schemas.agent_result import AgentStatus, FindingStatus
from app.services.agent_result_adapter import build_agent_result


@pytest.fixture
def sample_report():
    return {
        "case_id": "RECON-TEST-001",
        "status": "review_required",
        "finding_count": 2,
        "findings": {
            "duplicate_events": [
                {
                    "finding_type": "duplicate_event",
                    "severity": "high",
                    "event_id": "EVT-001",
                    "occurrences": 2,
                    "duplicate_copies": 1,
                    "customer_ids": ["CUS-001"],
                    "evidence": {
                        "records": [
                            {"event_id": "EVT-001"},
                            {"event_id": "EVT-001"},
                        ]
                    },
                    "requires_review": True,
                }
            ],
            "missing_events": [],
            "invoice_mismatches": [
                {
                    "finding_type": "invoice_amount_mismatch",
                    "severity": "high",
                    "customer_id": "CUS-001",
                    "expected_amount": "35.75",
                    "actual_amount": "30.75",
                    "difference": "-5.00",
                    "direction": "undercharge",
                    "evidence": {
                        "expected_line": {
                            "invoice_line_id": "LINE-001",
                        },
                        "actual_line": {
                            "invoice_line_id": "LINE-001",
                        },
                    },
                    "requires_review": True,
                }
            ],
            "calculation_mismatches": [],
        },
        "limitations": ["Synthetic fixture only."],
    }


def test_event_agent_receives_only_event_findings(sample_report):
    result = build_agent_result(sample_report, "event_agent")

    assert isinstance(result.status, AgentStatus)
    assert result.status == AgentStatus.COMPLETED
    assert len(result.findings) == 1
    assert result.findings[0].category == "duplicate_event"
    assert result.findings[0].affected_event_ids == ["EVT-001"]


def test_invoice_agent_receives_invoice_findings(sample_report):
    result = build_agent_result(sample_report, "invoice_agent")

    assert len(result.findings) == 1
    finding = result.findings[0]

    assert finding.category == "invoice_discrepancy"
    assert finding.affected_customer_id == "CUS-001"
    assert finding.affected_invoice_line_ids == ["LINE-001"]
    assert finding.status == FindingStatus.CONFIRMED


def test_findings_include_evidence_references(sample_report):
    result = build_agent_result(sample_report, "event_agent")

    finding = result.findings[0]

    assert len(finding.evidence) == 1
    assert finding.evidence[0].source == (
        "deterministic_reconciliation_report"
    )
    assert finding.evidence[0].evidence_id == "duplicate_events:0"


def test_pricing_agent_does_not_invent_findings(sample_report):
    result = build_agent_result(sample_report, "pricing_agent")

    assert result.findings == []
    assert result.status == AgentStatus.COMPLETED


def test_empty_report_groups_produce_empty_result():
    report = {
        "case_id": "RECON-CLEAN-001",
        "findings": {
            "duplicate_events": [],
            "missing_events": [],
            "invoice_mismatches": [],
            "calculation_mismatches": [],
        },
    }

    result = build_agent_result(report, "event_agent")

    assert result.findings == []
    assert "no findings" in result.summary


def test_unknown_agent_is_rejected(sample_report):
    with pytest.raises(ValueError, match="Unsupported agent name"):
        build_agent_result(sample_report, "unknown_agent")


def test_missing_findings_dictionary_is_rejected():
    with pytest.raises(ValueError, match="no findings dictionary"):
        build_agent_result({"case_id": "RECON-001"}, "event_agent")


def test_missing_case_id_is_rejected():
    report = {"findings": {}}

    with pytest.raises(ValueError, match="case_id"):
        build_agent_result(report, "event_agent")