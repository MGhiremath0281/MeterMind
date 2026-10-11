from app.graph.supervisor import decide_next_step
from app.schemas.agent_result import (
    AgentResult,
    AgentStatus,
    FindingSeverity,
    FindingStatus,
    AgentFinding,
    EvidenceReference,
)


def make_result(
    agent_name: str,
    status: AgentStatus = AgentStatus.COMPLETED,
    findings=None,
) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        case_id="RECON-TEST-001",
        status=status,
        summary="Test investigation result.",
        findings=findings or [],
        limitations=(
            ["Additional evidence is required."]
            if status == AgentStatus.NEEDS_MORE_EVIDENCE
            else []
        ),
        recommended_next_steps=(
            ["Obtain the missing evidence."]
            if status == AgentStatus.NEEDS_MORE_EVIDENCE
            else []
        ),
    )


def all_completed():
    return {
        "event_agent": make_result("event_agent"),
        "pricing_agent": make_result("pricing_agent"),
        "invoice_agent": make_result("invoice_agent"),
    }


def test_missing_specialist_result_is_unresolved():
    results = all_completed()
    del results["pricing_agent"]

    decision = decide_next_step(results, [], retry_count=0)

    assert decision["decision"] == "unresolved"
    assert decision["retry_allowed"] is True


def test_agent_execution_error_is_unresolved():
    decision = decide_next_step(
        all_completed(),
        ["invoice_agent: timeout"],
        retry_count=0,
    )

    assert decision["decision"] == "unresolved"


def test_more_evidence_triggers_bounded_reinvestigation():
    results = all_completed()
    results["pricing_agent"] = make_result(
        "pricing_agent",
        AgentStatus.NEEDS_MORE_EVIDENCE,
    )

    decision = decide_next_step(results, [], retry_count=0, max_retries=2)

    assert decision["decision"] == "reinvestigate"
    assert decision["retry_allowed"] is True


def test_retry_limit_prevents_infinite_reinvestigation():
    results = all_completed()
    results["pricing_agent"] = make_result(
        "pricing_agent",
        AgentStatus.NEEDS_MORE_EVIDENCE,
    )

    decision = decide_next_step(results, [], retry_count=2, max_retries=2)

    assert decision["decision"] == "unresolved"
    assert decision["retry_allowed"] is False


def test_completed_results_with_findings_require_review():
    results = all_completed()

    finding = AgentFinding(
        finding_id="duplicate_events:0",
        category="duplicate_event",
        title="Duplicate event",
        description="A duplicate event was detected.",
        status=FindingStatus.CONFIRMED,
        severity=FindingSeverity.HIGH,
        evidence=[
            EvidenceReference(
                evidence_id="duplicate_events:0",
                source="deterministic_reconciliation_report",
                description="Duplicate detected by the reconciliation engine.",
            )
        ],
        recommended_action="Review the event before correcting billing.",
    )

    results["event_agent"] = make_result(
        "event_agent",
        findings=[finding],
    )

    decision = decide_next_step(results, [], retry_count=0)

    assert decision["decision"] == "review_required"
    assert decision["retry_allowed"] is False


def test_clean_results_do_not_automatically_approve_case():
    decision = decide_next_step(all_completed(), [], retry_count=0)

    assert decision["decision"] == "review_required"