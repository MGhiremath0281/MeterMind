from typing import Any

from app.schemas.agent_result import AgentResult, AgentStatus


REQUIRED_SPECIALISTS = (
    "event_agent",
    "pricing_agent",
    "invoice_agent",
)


def decide_next_step(
    agent_results: dict[str, AgentResult],
    errors: list[str],
    retry_count: int,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    Deterministic supervisor policy.

    This function never interprets LLM prose as an approval.
    It returns a routing decision, not authorization to change billing.
    """

    if retry_count < 0 or max_retries < 0:
        raise ValueError("Retry counts cannot be negative.")

    if errors:
        return {
            "decision": "unresolved",
            "reason": "One or more agent executions failed.",
            "retry_allowed": retry_count < max_retries,
            "retry_count": retry_count,
        }

    missing = [
        name
        for name in REQUIRED_SPECIALISTS
        if name not in agent_results
    ]

    if missing:
        return {
            "decision": "unresolved",
            "reason": f"Missing specialist results: {', '.join(missing)}.",
            "retry_allowed": retry_count < max_retries,
            "retry_count": retry_count,
        }

    failed = [
        name
        for name in REQUIRED_SPECIALISTS
        if agent_results[name].status == AgentStatus.FAILED
    ]

    if failed:
        return {
            "decision": "unresolved",
            "reason": f"Failed specialist results: {', '.join(failed)}.",
            "retry_allowed": retry_count < max_retries,
            "retry_count": retry_count,
        }

    needs_evidence = [
        name
        for name in REQUIRED_SPECIALISTS
        if agent_results[name].status == AgentStatus.NEEDS_MORE_EVIDENCE
    ]

    if needs_evidence:
        return {
            "decision": (
                "reinvestigate"
                if retry_count < max_retries
                else "unresolved"
            ),
            "reason": (
                "More evidence is required from: "
                + ", ".join(needs_evidence)
            ),
            "retry_allowed": retry_count < max_retries,
            "retry_count": retry_count,
        }

    # A completed investigation may still contain discrepancies.
    # Completion is not the same as approval.
    has_findings = any(
        result.findings
        for name, result in agent_results.items()
        if name in REQUIRED_SPECIALISTS
    )

    if has_findings:
        return {
            "decision": "review_required",
            "reason": (
                "Deterministic findings exist and require review. "
                "No financial correction is authorized."
            ),
            "retry_allowed": False,
            "retry_count": retry_count,
        }

    return {
        "decision": "review_required",
        "reason": (
            "No findings were reported, but the current evidence checks "
            "do not establish that the entire billing case is correct."
        ),
        "retry_allowed": False,
        "retry_count": retry_count,
    }