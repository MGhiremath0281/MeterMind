
from collections import defaultdict
from typing import Iterable

from app.schemas.agent_result import AgentFinding


def _invoice_line_key(finding: AgentFinding) -> str | None:
    """Return a grouping key only when a concrete invoice-line ID exists."""
    if not finding.affected_invoice_line_ids:
        return None

    # One finding may refer to multiple lines. Do not guess which line
    # is the primary one; only group unambiguous single-line findings.
    if len(finding.affected_invoice_line_ids) != 1:
        return None

    line_id = finding.affected_invoice_line_ids[0].strip()
    if not line_id:
        return None

    return f"{finding.affected_customer_id or 'unknown'}:{line_id}"


def group_investigation_findings(
    findings: Iterable[AgentFinding],
) -> list[dict]:
    """
    Group findings that identify the same customer and invoice line.

    Original findings and evidence are retained. Findings without an
    unambiguous invoice-line identity remain in separate investigation cases.
    """
    groups: dict[str, list[AgentFinding]] = defaultdict(list)
    standalone: list[AgentFinding] = []

    for finding in findings:
        key = _invoice_line_key(finding)

        if key is None:
            standalone.append(finding)
        else:
            groups[key].append(finding)

    cases: list[dict] = []

    for key, grouped_findings in groups.items():
        cases.append(
            {
                "group_key": key,
                "finding_ids": [
                    finding.finding_id for finding in grouped_findings
                ],
                "categories": sorted(
                    {finding.category for finding in grouped_findings}
                ),
                "affected_customer_id": grouped_findings[0].affected_customer_id,
                "affected_invoice_line_ids": sorted(
                    {
                        line_id
                        for finding in grouped_findings
                        for line_id in finding.affected_invoice_line_ids
                    }
                ),
                "evidence": [
                    evidence.model_dump(mode="json")
                    for finding in grouped_findings
                    for evidence in finding.evidence
                ],
                "findings": [
                    finding.model_dump(mode="json")
                    for finding in grouped_findings
                ],
                "requires_review": True,
            }
        )

    for finding in standalone:
        cases.append(
            {
                "group_key": f"finding:{finding.finding_id}",
                "finding_ids": [finding.finding_id],
                "categories": [finding.category],
                "affected_customer_id": finding.affected_customer_id,
                "affected_invoice_line_ids": (
                    finding.affected_invoice_line_ids
                ),
                "evidence": [
                    evidence.model_dump(mode="json")
                    for evidence in finding.evidence
                ],
                "findings": [finding.model_dump(mode="json")],
                "requires_review": True,
            }
        )

    return cases
