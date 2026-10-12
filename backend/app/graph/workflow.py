from typing import Any

from langgraph.graph import StateGraph, START, END

from app.agents.event_agent import event_agent
from app.agents.pricing_agent import pricing_agent
from app.agents.invoice_agent import invoice_agent
from app.agents.audit_agent import audit_agent
from app.graph.supervisor import decide_next_step
from app.graph.state import MeterMindState
from app.schemas.agent_result import AgentResult, AgentStatus
from app.services.agent_result_adapter import build_agent_result
from app.tools.billing_tools import get_report
from app.schemas.agent_result import (
    AgentResult,
    AgentStatus,
    EvidenceReference,
)
from app.services.billing_policy_rag import (
    clear_policy_retrieval_audit,
    get_policy_retrieval_audit,
    retrieve_policy_context,
)
from app.services.investigation_grouper import (
    group_investigation_findings,
)

SPECIALISTS = {
    "event_agent": event_agent,
    "pricing_agent": pricing_agent,
    "invoice_agent": invoice_agent,
}


TASKS = {
    "event_agent": """
Investigate duplicate and missing usage events.

Use the event inspection tool. Identify exact event IDs and explain
what the deterministic evidence establishes. Do not invent findings.
""",
    "pricing_agent": """
Investigate customer plans and pricing versions.

Use the pricing inspection tool. Examine effective dates and explain
what additional evidence is needed to verify actual billed prices.
Do not declare a pricing mismatch without sufficient evidence.
""",
    "invoice_agent": """
Investigate expected versus recorded invoice amounts.

Use invoice inspection and arithmetic tools where appropriate.
Treat deterministic financial calculations as authoritative.
Do not infer root cause from an amount mismatch alone.
""",
}


def extract_response(result: dict[str, Any]) -> str:
    messages = result.get("messages", [])

    for message in reversed(messages):
        if getattr(message, "type", "") == "ai":
            content = getattr(message, "content", "")
            if isinstance(content, str):
                return content
            return str(content)

    return "Agent returned no final AI response."


def invoke_agent(agent, task: str) -> str:
    result = agent.invoke({
        "messages": [{"role": "user", "content": task}]
    })
    return extract_response(result)


def failed_result(
    agent_name: str,
    case_id: str,
    error: str,
) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        case_id=case_id,
        status=AgentStatus.FAILED,
        summary=f"Agent execution failed: {error}",
        limitations=["No successful investigation result was produced."],
    )

def collect_pricing_evidence(
    report: dict[str, Any],
) -> list[EvidenceReference]:
    """Collect all reconstructed pricing lines, deduplicating by identity."""
    evidence_by_id: dict[str, EvidenceReference] = {}

    def add_line(expected_line: dict[str, Any]) -> None:
        customer_id = expected_line.get("customer_id")
        billing_period = expected_line.get("billing_period")
        pricing_version_id = expected_line.get("pricing_version_id")

        if not all((customer_id, billing_period, pricing_version_id)):
            return

        evidence_id = (
            f"pricing-reconstruction:{customer_id}:"
            f"{billing_period}:{pricing_version_id}"
        )

        description = (
            f"Reconstructed invoice line for customer {customer_id}; "
            f"period={billing_period}; "
            f"pricing_version={pricing_version_id}; "
            f"quantity={expected_line.get('quantity')}; "
            f"unit_price={expected_line.get('unit_price')}; "
            f"expected_amount={expected_line.get('amount')}; "
            f"currency={expected_line.get('currency')}; "
            f"calculation_method="
            f"{expected_line.get('calculation_method')}; "
            f"source_events={expected_line.get('source_event_ids', [])}"
        )

        evidence_by_id[evidence_id] = EvidenceReference(
            evidence_id=evidence_id,
            source="deterministic_pricing_reconstruction",
            description=description,
        )

    # Preferred source: the complete reconstruction output.
    expected_lines = report.get("expected_invoice_lines", [])

    if isinstance(expected_lines, list):
        for line in expected_lines:
            if isinstance(line, dict):
                add_line(line)

    # Backward-compatible fallback for older report structures.
    findings = report.get("findings", {})

    for group_name in ("invoice_mismatches", "calculation_mismatches"):
        group = findings.get(group_name, [])

        if not isinstance(group, list):
            continue

        for finding in group:
            if not isinstance(finding, dict):
                continue

            evidence = finding.get("evidence", {})
            if not isinstance(evidence, dict):
                continue

            expected_line = evidence.get("expected_line")
            if isinstance(expected_line, dict):
                add_line(expected_line)

    return list(evidence_by_id.values())


def collect_policy_evidence(
    policy_results: list[dict[str, Any]] | None = None,
) -> list[EvidenceReference]:
    """Convert retrieved policy metadata into traceable evidence references."""
    if policy_results is None:
        policy_results = get_policy_retrieval_audit()

    evidence_by_id: dict[str, EvidenceReference] = {}

    for item in policy_results:
        document_id = item.get("document_id")
        chunk_index = item.get("chunk_index")

        if document_id is None or chunk_index is None:
            continue

        evidence_id = f"{document_id}:chunk-{chunk_index}"

        description = (
            f"Retrieved billing policy: {item.get('title')}; "
            f"effective_from={item.get('effective_from')}; "
            f"source_file={item.get('source_file')}; "
            f"retrieval_query={item.get('query', 'pricing investigation')}"
        )

        evidence_by_id[evidence_id] = EvidenceReference(
            evidence_id=evidence_id,
            source="billing_policy_rag",
            description=description[:1000],
        )

    return list(evidence_by_id.values())


def result_for_agent(
    agent_name: str,
    report: dict[str, Any],
    case_id: str,
) -> AgentResult:
    result = build_agent_result(
        report=report,
        agent_name=agent_name,
        case_id=case_id,
    )

    if agent_name == "pricing_agent":
        findings = report.get("findings", {})
        pricing_errors = findings.get("pricing_errors", [])
        pricing_evidence = collect_pricing_evidence(report)

        if pricing_errors:
            return result.model_copy(
                update={
                    "status": AgentStatus.NEEDS_MORE_EVIDENCE,
                    "summary": (
                        "Effective-dated pricing reconstruction could not "
                        "be fully completed because pricing errors were found."
                    ),
                    "evidence_reviewed": pricing_evidence,
                    "limitations": [
                        *result.limitations,
                        *[str(error) for error in pricing_errors],
                    ],
                    "recommended_next_steps": [
                        "Resolve the pricing errors.",
                        "Rerun effective-dated pricing reconstruction.",
                    ],
                }
            )

        return result.model_copy(
            update={
                "status": AgentStatus.COMPLETED,
                "summary": (
                    "Effective-dated pricing reconstruction completed. "
                    "Evidence from all reconstructed invoice lines was "
                    "attached for review."
                ),
                "evidence_reviewed": pricing_evidence,
                "limitations": [
                    *result.limitations,
                    "Pricing reconstruction uses the currently "
                    "implemented flat per-unit pricing model.",
                    "Pricing evidence includes all reconstructed invoice "
                    "lines available in the reconciliation report.",
                ],
                "recommended_next_steps": [
                    "Review reconstructed charges alongside invoice "
                    "discrepancies and event anomalies."
                ],
            }
        )

    return result



def run_specialist(
    state: MeterMindState,
    agent,
    agent_name: str,
    task: str,
) -> dict[str, Any]:
    case_id = state.get("case_id", "RECON-DEMO-001")
    outputs = dict(state.get("agent_outputs", {}))
    results = dict(state.get("agent_results", {}))
    errors = list(state.get("errors", []))

    try:
        policy_evidence: list[EvidenceReference] = []

        if agent_name == "pricing_agent":
            # Explicit retrieval guarantees that policy evidence capture
            # does not depend on whether the LLM calls its policy tool.
            policy_query = (
                "effective-dated pricing versions, pricing effective dates, "
                "retroactive pricing changes, and deterministic billing "
                "reconstruction rules"
            )

            policy_results = retrieve_policy_context(
                policy_query,
                k=3,
            )

            policy_evidence = collect_policy_evidence(policy_results)

        commentary = invoke_agent(agent, task)

        # Structured findings and pricing evidence come from deterministic
        # reconciliation data, not from the LLM's commentary.
        report = get_report()
        structured = result_for_agent(agent_name, report, case_id)

        # Merge policy references with deterministic evidence without
        # replacing either source.
        if agent_name == "pricing_agent" and policy_evidence:
            existing_evidence = {
                item.evidence_id: item
                for item in structured.evidence_reviewed
            }

            for item in policy_evidence:
                existing_evidence[item.evidence_id] = item

            structured = structured.model_copy(
                update={
                    "evidence_reviewed": list(existing_evidence.values())
                }
            )

        results[agent_name] = structured
        outputs[agent_name] = {
            "status": "completed",
            "output": commentary,
            "result": structured.model_dump(mode="json"),
        }

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        errors.append(f"{agent_name}: {error}")

        structured = failed_result(agent_name, case_id, error)
        results[agent_name] = structured

        outputs[agent_name] = {
            "status": "failed",
            "output": "",
            "error": error,
            "result": structured.model_dump(mode="json"),
        }

    return {
        "agent_outputs": outputs,
        "agent_results": results,
        "errors": errors,
    }


def event_node(state: MeterMindState) -> dict[str, Any]:
    return run_specialist(
        state,
        event_agent,
        "event_agent",
        TASKS["event_agent"],
    )


def pricing_node(state: MeterMindState) -> dict[str, Any]:
    return run_specialist(
        state,
        pricing_agent,
        "pricing_agent",
        TASKS["pricing_agent"],
    )


def invoice_node(state: MeterMindState) -> dict[str, Any]:
    return run_specialist(
        state,
        invoice_agent,
        "invoice_agent",
        TASKS["invoice_agent"],
    )


def collect_investigation_cases(
    agent_results: dict[str, AgentResult],
) -> list[dict[str, Any]]:
    """Group specialist findings while preserving their source records."""
    findings = []

    for agent_name in (
        "event_agent",
        "pricing_agent",
        "invoice_agent",
    ):
        result = agent_results.get(agent_name)

        if result is None:
            continue

        findings.extend(result.findings)

    return group_investigation_findings(findings)


def supervisor_node(state: MeterMindState) -> dict[str, Any]:
    agent_results = state.get("agent_results", {})

    investigation_cases = collect_investigation_cases(agent_results)

    decision = decide_next_step(
        agent_results=agent_results,
        errors=state.get("errors", []),
        retry_count=state.get("retry_count", 0),
        max_retries=2,
    )

    return {
        "investigation_cases": investigation_cases,
        "supervisor_decision": decision["decision"],
        "supervisor_reason": decision["reason"],
    }

def route_after_supervisor(state: MeterMindState) -> str:
    decision = state.get("supervisor_decision", "unresolved")

    if decision == "reinvestigate":
        return "reinvestigate"

    if decision == "review_required":
        return "audit"

    return "finish_unresolved"


def reinvestigation_node(
    state: MeterMindState,
) -> dict[str, Any]:
    """
    Retry only agents whose structured results request more evidence.

    Retries are bounded. This does not claim that repeating an unchanged
    tool call creates new evidence.
    """
    retry_count = state.get("retry_count", 0)

    if retry_count >= 2:
        return {
            "supervisor_decision": "unresolved",
            "supervisor_reason": "Maximum re-investigation attempts reached.",
        }

    results = dict(state.get("agent_results", {}))
    outputs = dict(state.get("agent_outputs", {}))
    errors = list(state.get("errors", []))
    case_id = state.get("case_id", "RECON-DEMO-001")

    retry_count += 1

    # Remove previous errors for agents being retried so a successful
    # retry is not permanently treated as a failed execution.
    retry_names = [
        name
        for name, result in results.items()
        if result.status == AgentStatus.NEEDS_MORE_EVIDENCE
    ]

    for name in retry_names:
        errors = [
            error for error in errors
            if not error.startswith(f"{name}:")
        ]

    retry_tasks = {
        "pricing_agent": (
            TASKS["pricing_agent"]
            + "\nRe-investigation: explicitly identify which required "
            "pricing evidence is unavailable. Do not claim that missing "
            "deterministic reconstruction has been performed."
        ),
        "event_agent": TASKS["event_agent"],
        "invoice_agent": TASKS["invoice_agent"],
    }

    for name in retry_names:
        agent = SPECIALISTS.get(name)

        if agent is None:
            continue

        retry_state: MeterMindState = {
            **state,
            "agent_outputs": outputs,
            "agent_results": results,
            "errors": errors,
        }

        updated = run_specialist(
            retry_state,
            agent,
            name,
            retry_tasks[name],
        )

        outputs = updated["agent_outputs"]
        results = updated["agent_results"]
        errors = updated["errors"]

    return {
        "agent_outputs": outputs,
        "agent_results": results,
        "errors": errors,
        "retry_count": retry_count,
    }


def finish_unresolved_node(
    state: MeterMindState,
) -> dict[str, Any]:
    return {
        "audit_status": "unresolved",
        "supervisor_decision": "unresolved",
        "supervisor_reason": state.get(
            "supervisor_reason",
            "The investigation could not establish sufficient evidence.",
        ),
    }


def audit_node(state: MeterMindState) -> dict[str, Any]:
    case_id = state.get("case_id", "RECON-DEMO-001")
    outputs = dict(state.get("agent_outputs", {}))
    results = dict(state.get("agent_results", {}))
    errors = list(state.get("errors", []))

    specialist_names = (
        "event_agent",
        "pricing_agent",
        "invoice_agent",
    )

    failed_agents = [
        name
        for name in specialist_names
        if outputs.get(name, {}).get("status") != "completed"
    ]

    if failed_agents:
        message = (
            "Audit blocked because specialist execution failed: "
            + ", ".join(failed_agents)
        )

        audit_result = AgentResult(
            agent_name="audit_agent",
            case_id=case_id,
            status=AgentStatus.NEEDS_MORE_EVIDENCE,
            summary=message,
            limitations=["One or more specialist investigations failed."],
            recommended_next_steps=[
                "Resolve specialist failures and rerun the investigation."
            ],
        )

        outputs["audit_agent"] = {
            "status": "blocked",
            "output": message,
            "result": audit_result.model_dump(mode="json"),
        }
        results["audit_agent"] = audit_result

        return {
            "agent_outputs": outputs,
            "agent_results": results,
            "errors": errors,
            "audit_status": "unresolved",
        }

    try:
        report = get_report()

        audit_task = (
            "Independently audit this MeterMind case.\n"
            f"Case ID: {case_id}\n\n"
            "Specialist commentary:\n"
            + str({
                name: outputs[name].get("output", "")
                for name in specialist_names
            })
            + "\n\nRetrieve the deterministic evidence report. "
            "Check the evidence, calculations, contradictions, and "
            "limitations. Do not approve financial corrections. "
            "Explain what remains unresolved."
        )

        commentary = invoke_agent(audit_agent, audit_task)

        # The structured audit record reflects deterministic findings.
        # The LLM commentary is retained separately for human review.
        structured = build_agent_result(
            report=report,
            agent_name="audit_agent",
            case_id=case_id,
        )

        results["audit_agent"] = structured
        outputs["audit_agent"] = {
            "status": "completed",
            "output": commentary,
            "result": structured.model_dump(mode="json"),
        }

        # Deliberately conservative: no automated approval yet.
        audit_status = "review_required"

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        errors.append(f"audit_agent: {error}")

        structured = failed_result("audit_agent", case_id, error)
        results["audit_agent"] = structured

        outputs["audit_agent"] = {
            "status": "failed",
            "output": "",
            "error": error,
            "result": structured.model_dump(mode="json"),
        }
        audit_status = "unresolved"

    return {
        "agent_outputs": outputs,
        "agent_results": results,
        "errors": errors,
        "audit_status": audit_status,
    }


def build_workflow():
    graph = StateGraph(MeterMindState)

    graph.add_node("event_agent", event_node)
    graph.add_node("pricing_agent", pricing_node)
    graph.add_node("invoice_agent", invoice_node)
    graph.add_node("audit_agent", audit_node)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("reinvestigate", reinvestigation_node)
    graph.add_node("finish_unresolved", finish_unresolved_node)

    graph.add_edge(START, "event_agent")
    graph.add_edge("event_agent", "pricing_agent")
    graph.add_edge("pricing_agent", "invoice_agent")
    graph.add_edge("invoice_agent", "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "reinvestigate": "reinvestigate",
            "audit": "audit_agent",
            "finish_unresolved": "finish_unresolved",
        },
    )

    graph.add_edge("reinvestigate", "supervisor")
    graph.add_edge("audit_agent", END)
    graph.add_edge("finish_unresolved", END)

    return graph.compile()

meter_mind_workflow = build_workflow()

def run_investigation(
    case_id: str = "RECON-DEMO-001",
) -> dict[str, Any]:
    result = meter_mind_workflow.invoke({
        "case_id": case_id,
        "agent_outputs": {},
        "agent_results": {},
        "errors": [],
        "retry_count": 0,
        "supervisor_decision": "pending",
        "supervisor_reason": "",
    })

    return {
        "case_id": result.get("case_id", case_id),
        "audit_status": result.get("audit_status", "unresolved"),
        "supervisor_decision": result.get(
            "supervisor_decision", "unresolved"
        ),
        "supervisor_reason": result.get("supervisor_reason", ""),
        "retry_count": result.get("retry_count", 0),
        "agent_outputs": result.get("agent_outputs", {}),
        "investigation_cases": result.get("investigation_cases", []),
        "agent_results": {
            name: (
                agent_result.model_dump(mode="json")
                if isinstance(agent_result, AgentResult)
                else agent_result
            )
            for name, agent_result in result.get(
                "agent_results", {}
            ).items()
        },
        "errors": result.get("errors", []),
    }