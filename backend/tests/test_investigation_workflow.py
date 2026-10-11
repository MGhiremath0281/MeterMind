
from app.graph.workflow import collect_investigation_cases
from app.schemas.agent_result import (
    AgentFinding,
    AgentResult,
    AgentStatus,
    EvidenceReference,
    FindingSeverity,
    FindingStatus,
)


def make_finding(
    finding_id: str,
    category: str,
    line_id: str | None,
) -> AgentFinding:
    return AgentFinding(
        finding_id=finding_id,
        category=category,
        title=category.replace("_", " ").title(),
        description="Deterministic finding for integration testing.",
        status=FindingStatus.CONFIRMED,
        severity=FindingSeverity.HIGH,
        evidence=[
            EvidenceReference(
                evidence_id=f"evidence:{finding_id}",
                source="test",
                description="Test evidence reference.",
            )
        ],
        affected_customer_id="CUS-1001",
        affected_invoice_line_ids=[line_id] if line_id else [],
        recommended_action="Review the evidence.",
    )


def make_result(
    agent_name: str,
    findings: list[AgentFinding],
) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        case_id="TEST-CASE",
        status=AgentStatus.COMPLETED,
        summary="Test result.",
        findings=findings,
    )


def test_invoice_findings_are_grouped_from_agent_results():
    results = {
        "invoice_agent": make_result(
            "invoice_agent",
            [
                make_finding(
                    "invoice_mismatches:0",
                    "invoice_discrepancy",
                    "LINE-0001",
                ),
                make_finding(
                    "calculation_mismatches:0",
                    "calculation_mismatch",
                    "LINE-0001",
                ),
            ],
        )
    }

    cases = collect_investigation_cases(results)

    assert len(cases) == 1
    assert len(cases[0]["finding_ids"]) == 2
    assert len(cases[0]["evidence"]) == 2
    assert cases[0]["requires_review"] is True


def test_event_findings_without_invoice_lines_stay_separate():
    results = {
        "event_agent": make_result(
            "event_agent",
            [
                make_finding("duplicate_events:0", "duplicate_event", None),
                make_finding("missing_events:0", "missing_event", None),
            ],
        )
    }

    cases = collect_investigation_cases(results)

    assert len(cases) == 2


def test_missing_specialist_results_produce_no_cases():
    assert collect_investigation_cases({}) == []
