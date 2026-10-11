from typing import Any

from app.schemas.agent_result import (
    AgentFinding,
    AgentResult,
    AgentStatus,
    EvidenceReference,
    FindingSeverity,
    FindingStatus,
)


GROUP_CATEGORIES = {
    "duplicate_events": "duplicate_event",
    "missing_events": "missing_event",
    "invoice_mismatches": "invoice_discrepancy",
    "calculation_mismatches": "calculation_mismatch",
}

AGENT_GROUPS = {
    "event_agent": ("duplicate_events", "missing_events"),
    "pricing_agent": (),
    "invoice_agent": ("invoice_mismatches", "calculation_mismatches"),
    "audit_agent": (
        "duplicate_events",
        "missing_events",
        "invoice_mismatches",
        "calculation_mismatches",
    ),
}


def _severity(value: Any) -> FindingSeverity:
    try:
        return FindingSeverity(str(value).lower())
    except ValueError:
        return FindingSeverity.MEDIUM


def _describe_finding(group: str, finding: dict[str, Any]) -> str:
    """Build a description from deterministic report fields."""

    finding_type = finding.get("finding_type", group)

    if group == "duplicate_events":
        return (
            f"Event {finding.get('event_id', 'unknown')} appears "
            f"{finding.get('occurrences', 'an unknown number of times')} "
            "in the observed event stream. This is a detected duplicate; "
            "its billing impact must be assessed separately."
        )

    if group == "missing_events":
        return (
            f"Event {finding.get('event_id', 'unknown')} has "
            f"{finding.get('missing_copies', 'an unknown number of')} "
            "missing occurrence(s) when comparing the observed stream "
            "with the fixture's authoritative source ledger."
        )

    if group == "invoice_mismatches":
        return (
            f"{finding_type}: expected amount "
            f"{finding.get('expected_amount', 'unknown')}, recorded amount "
            f"{finding.get('actual_amount', 'unknown')}, difference "
            f"{finding.get('difference', 'unknown')}. "
            "The discrepancy is detected; its root cause is not established "
            "by this comparison alone."
        )

    if group == "calculation_mismatches":
        return (
            f"Invoice line {finding.get('invoice_line_id', 'unknown')} has "
            f"recorded amount {finding.get('recorded_amount', 'unknown')} "
            f"but quantity-times-unit-price calculates to "
            f"{finding.get('calculated_amount', 'unknown')}."
        )

    return f"Deterministic reconciliation finding: {finding_type}."


def _evidence_for(
    group: str,
    index: int,
    finding: dict[str, Any],
) -> list[EvidenceReference]:
    """
    Create references to report records.

    These references identify evidence in the deterministic report.
    They are not cryptographic proofs or database foreign keys.
    """

    report_id = f"{group}:{index}"
    details = finding.get("evidence")

    if details is not None:
        description = (
            f"Evidence payload from reconciliation group {group}: "
            f"{_describe_finding(group, finding)}"
        )
    else:
        # Some deterministic checks encode their evidence directly in
        # the finding fields rather than under an 'evidence' key.
        description = (
            f"Deterministic report record from group {group}: "
            f"{_describe_finding(group, finding)}"
        )

    return [
        EvidenceReference(
            evidence_id=report_id,
            source="deterministic_reconciliation_report",
            description=description,
        )
    ]


def _affected_event_ids(finding: dict[str, Any]) -> list[str]:
    event_id = finding.get("event_id")
    return [str(event_id)] if event_id is not None else []


def _affected_invoice_line_ids(
    group: str,
    finding: dict[str, Any],
) -> list[str]:
    line_id = finding.get("invoice_line_id")

    if line_id is None and group == "invoice_mismatches":
        evidence = finding.get("evidence", {})
        if isinstance(evidence, dict):
            for key in ("actual_line", "expected_line"):
                line = evidence.get(key)
                if isinstance(line, dict):
                    line_id = line.get("invoice_line_id", line.get("line_id"))
                    if line_id is not None:
                        break

    return [str(line_id)] if line_id is not None else []


def _to_agent_finding(
    group: str,
    index: int,
    finding: dict[str, Any],
) -> AgentFinding:
    evidence = _evidence_for(group, index, finding)

    customer_id = finding.get("customer_id")
    if customer_id is None:
        customer_ids = finding.get("customer_ids", [])
        if customer_ids:
            customer_id = customer_ids[0]

    return AgentFinding(
        finding_id=f"{group}:{index}",
        category=GROUP_CATEGORIES[group],
        title=finding.get("finding_type", GROUP_CATEGORIES[group]).replace(
            "_", " "
        ).title(),
        description=_describe_finding(group, finding),
        # The deterministic engine establishes the discrepancy detected
        # by its rules. It does not automatically establish root cause.
        status=FindingStatus.CONFIRMED,
        severity=_severity(finding.get("severity")),
        evidence=evidence,
        affected_customer_id=(
            str(customer_id) if customer_id is not None else None
        ),
        affected_event_ids=_affected_event_ids(finding),
        affected_invoice_line_ids=_affected_invoice_line_ids(
            group, finding
        ),
        limitations=[
            "This finding confirms the deterministic rule's detected "
            "condition, not necessarily its root cause."
        ],
        recommended_action=(
            "Review the referenced evidence before making any financial "
            "correction."
        ),
    )


def build_agent_result(
    report: dict[str, Any],
    agent_name: str,
    case_id: str | None = None,
) -> AgentResult:
    """
    Build a validated result from deterministic findings.

    This function does not consume or trust LLM-generated findings.
    """

    if agent_name not in AGENT_GROUPS:
        raise ValueError(f"Unsupported agent name: {agent_name}")

    groups = report.get("findings")
    if not isinstance(groups, dict):
        raise ValueError("Reconciliation report has no findings dictionary.")

    result_findings: list[AgentFinding] = []
    reviewed_evidence: list[EvidenceReference] = []

    for group in AGENT_GROUPS[agent_name]:
        items = groups.get(group, [])

        if not isinstance(items, list):
            raise ValueError(f"Report group {group} must be a list.")

        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Report entry {group}[{index}] must be an object."
                )

            finding = _to_agent_finding(group, index, item)
            result_findings.append(finding)
            reviewed_evidence.extend(finding.evidence)

    effective_case_id = case_id or report.get("case_id")
    if not effective_case_id:
        raise ValueError("A case_id must be provided by the report or caller.")

    summary = (
        f"{agent_name} mapped {len(result_findings)} deterministic finding(s)."
        if result_findings
        else f"{agent_name} found no findings in its assigned report groups."
    )

    return AgentResult(
        agent_name=agent_name,
        case_id=str(effective_case_id),
        status=AgentStatus.COMPLETED,
        summary=summary,
        findings=result_findings,
        evidence_reviewed=reviewed_evidence,
        limitations=[
            "Results are derived from the deterministic reconciliation "
            "report, not independently verified LLM conclusions.",
            *report.get("limitations", []),
        ],
    )