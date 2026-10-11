
from app.schemas.agent_result import (
    AgentFinding,
    EvidenceReference,
    FindingSeverity,
    FindingStatus,
)
from app.services.investigation_grouper import group_investigation_findings


def make_finding(
    finding_id: str,
    category: str,
    line_ids: list[str] | None = None,
    customer_id: str = "CUS-1001",
) -> AgentFinding:
    return AgentFinding(
        finding_id=finding_id,
        category=category,
        title=category.replace("_", " ").title(),
        description="Deterministic test finding.",
        status=FindingStatus.CONFIRMED,
        severity=FindingSeverity.HIGH,
        evidence=[
            EvidenceReference(
                evidence_id=f"evidence:{finding_id}",
                source="test",
                description="Test evidence.",
            )
        ],
        affected_customer_id=customer_id,
        affected_invoice_line_ids=line_ids or [],
        recommended_action="Review the evidence.",
    )


def test_related_invoice_findings_are_grouped():
    findings = [
        make_finding(
            "invoice_mismatches:0",
            "invoice_discrepancy",
            ["LINE-0001"],
        ),
        make_finding(
            "calculation_mismatches:0",
            "calculation_mismatch",
            ["LINE-0001"],
        ),
    ]

    cases = group_investigation_findings(findings)

    assert len(cases) == 1
    assert set(cases[0]["finding_ids"]) == {
        "invoice_mismatches:0",
        "calculation_mismatches:0",
    }
    assert len(cases[0]["evidence"]) == 2
    assert cases[0]["requires_review"] is True


def test_different_invoice_lines_remain_separate():
    findings = [
        make_finding("F-1", "invoice_discrepancy", ["LINE-0001"]),
        make_finding("F-2", "calculation_mismatch", ["LINE-0002"]),
    ]

    cases = group_investigation_findings(findings)

    assert len(cases) == 2


def test_findings_without_line_identity_remain_separate():
    findings = [
        make_finding("F-1", "duplicate_event"),
        make_finding("F-2", "missing_event"),
    ]

    cases = group_investigation_findings(findings)

    assert len(cases) == 2


def test_same_line_for_different_customers_is_not_grouped():
    findings = [
        make_finding(
            "F-1", "invoice_discrepancy", ["LINE-0001"], "CUS-1001"
        ),
        make_finding(
            "F-2", "calculation_mismatch", ["LINE-0001"], "CUS-1002"
        ),
    ]

    cases = group_investigation_findings(findings)

    assert len(cases) == 2
