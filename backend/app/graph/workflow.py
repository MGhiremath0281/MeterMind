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

    # Pricing data is currently available, but deterministic,
    # effective-dated pricing reconstruction is not implemented yet.
    if agent_name == "pricing_agent":
        return result.model_copy(update={
            "status": AgentStatus.NEEDS_MORE_EVIDENCE,
            "summary": (
                "Pricing metadata is available, but the current "
                "reconciliation engine does not independently reconstruct "
                "charges from effective-dated pricing rules."
            ),
            "limitations": [
                *result.limitations,
                "Effective-dated pricing reconstruction is not implemented.",
            ],
            "recommended_next_steps": [
                "Reconstruct expected charges from usage, customer plan, "
                "and the pricing version effective at the usage timestamp.",
                "Compare reconstructed charges with the invoice lines.",
            ],
        })

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
        commentary = invoke_agent(agent, task)

        # Findings come from deterministic evidence, not model prose.
        report = get_report()
        structured = result_for_agent(agent_name, report, case_id)

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

def supervisor_node(state: MeterMindState) -> dict[str, Any]:
    decision = decide_next_step(
        agent_results=state.get("agent_results", {}),
        errors=state.get("errors", []),
        retry_count=state.get("retry_count", 0),
        max_retries=2,
    )

    return {
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