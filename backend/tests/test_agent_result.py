from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.agent_result import (
    AgentFinding,
    AgentResult,
    AgentStatus,
    EvidenceReference,
    FindingSeverity,
    FindingStatus,
)


def make_evidence() -> EvidenceReference:
    return EvidenceReference(
        evidence_id="EVT-1001-003",
        source="inspect_event_anomalies",
        description="The event ID appears more than once in the observed event stream.",
    )


def make_finding(**overrides) -> AgentFinding:
    data = {
        "finding_id": "FINDING-001",
        "category": "duplicate_event",
        "title": "Duplicate usage event",
        "description": "The same event ID appears multiple times.",
        "status": FindingStatus.CONFIRMED,
        "severity": FindingSeverity.HIGH,
        "evidence": [make_evidence()],
        "affected_customer_id": "CUS-1001",
        "affected_event_ids": ["EVT-1001-003"],
        "recommended_action": "Review the duplicate before adjusting billing.",
    }
    data.update(overrides)
    return AgentFinding(**data)


def test_valid_confirmed_finding_requires_and_accepts_evidence():
    finding = make_finding()

    assert finding.status == FindingStatus.CONFIRMED
    assert finding.evidence[0].evidence_id == "EVT-1001-003"


def test_confirmed_finding_without_evidence_is_rejected():
    with pytest.raises(ValidationError):
        make_finding(evidence=[])


def test_financial_impact_requires_currency():
    with pytest.raises(ValidationError):
        make_finding(financial_impact=Decimal("-5.00"))


def test_financial_impact_accepts_decimal_and_currency():
    finding = make_finding(
        financial_impact=Decimal("-5.00"),
        currency="USD",
    )

    assert finding.financial_impact == Decimal("-5.00")
    assert finding.currency == "USD"


def test_non_finite_financial_impact_is_rejected():
    with pytest.raises(ValidationError):
        make_finding(
            financial_impact=Decimal("NaN"),
            currency="USD",
        )


def test_unexpected_fields_are_rejected():
    with pytest.raises(ValidationError):
        make_finding(unverified_claim="this should not be accepted")


def test_failed_agent_cannot_report_findings():
    with pytest.raises(ValidationError):
        AgentResult(
            agent_name="event_agent",
            case_id="RECON-001",
            status=AgentStatus.FAILED,
            summary="The investigation failed.",
            findings=[make_finding()],
        )


def test_needs_more_evidence_must_explain_what_is_missing():
    with pytest.raises(ValidationError):
        AgentResult(
            agent_name="pricing_agent",
            case_id="RECON-001",
            status=AgentStatus.NEEDS_MORE_EVIDENCE,
            summary="Pricing cannot yet be verified.",
        )


def test_valid_result_can_be_serialized():
    result = AgentResult(
        agent_name="event_agent",
        case_id="RECON-001",
        status=AgentStatus.COMPLETED,
        summary="One duplicate event was identified.",
        findings=[make_finding()],
        evidence_reviewed=[make_evidence()],
    )

    payload = result.model_dump(mode="json")

    assert payload["case_id"] == "RECON-001"
    assert payload["findings"][0]["status"] == "confirmed"
    assert payload["findings"][0]["evidence"][0]["evidence_id"] == (
        "EVT-1001-003"
    )