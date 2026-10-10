from typing import Any

from langgraph.graph import StateGraph, START, END

from app.agents.event_agent import event_agent
from app.agents.pricing_agent import pricing_agent
from app.agents.invoice_agent import invoice_agent
from app.agents.audit_agent import audit_agent

from app.graph.state import MeterMindState


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
        "messages": [
            {"role": "user", "content": task}
        ]
    })

    return extract_response(result)


def run_specialist(
    state: MeterMindState,
    agent,
    agent_name: str,
    task: str,
) -> dict[str, Any]:
    outputs = dict(state.get("agent_outputs", {}))
    errors = list(state.get("errors", []))

    try:
        output = invoke_agent(agent, task)

        outputs[agent_name] = {
            "status": "completed",
            "output": output,
        }

    except Exception as exc:
        errors.append(f"{agent_name}: {type(exc).__name__}: {exc}")

        outputs[agent_name] = {
            "status": "failed",
            "output": "",
            "error": f"{type(exc).__name__}: {exc}",
        }

    return {
        "agent_outputs": outputs,
        "errors": errors,
    }


def event_node(state: MeterMindState) -> dict[str, Any]:
    return run_specialist(
        state,
        event_agent,
        "event_agent",
        """
Investigate duplicate and missing usage events.

Use the event inspection tool. Report the exact event IDs and evidence
when available. Clearly distinguish confirmed issues from hypotheses.
""",
    )


def pricing_node(state: MeterMindState) -> dict[str, Any]:
    return run_specialist(
        state,
        pricing_agent,
        "pricing_agent",
        """
Investigate customer plans and pricing versions.

Use the pricing inspection tool. Examine effective dates and identify
what evidence is missing before declaring a pricing error.
""",
    )


def invoice_node(state: MeterMindState) -> dict[str, Any]:
    return run_specialist(
        state,
        invoice_agent,
        "invoice_agent",
        """
Investigate expected versus recorded invoice amounts.

Use the invoice inspection and arithmetic tools where appropriate.
Use deterministic values as the financial source of truth.
""",
    )


def audit_node(state: MeterMindState) -> dict[str, Any]:
    outputs = dict(state.get("agent_outputs", {}))
    errors = list(state.get("errors", []))

    # Do not treat the case as audited if a specialist failed.
    failed_agents = [
        name
        for name in (
            "event_agent",
            "pricing_agent",
            "invoice_agent",
        )
        if outputs.get(name, {}).get("status") != "completed"
    ]

    if failed_agents:
        outputs["audit_agent"] = {
            "status": "blocked",
            "output": (
                "Audit blocked because specialist agents failed: "
                + ", ".join(failed_agents)
            ),
        }

        return {
            "agent_outputs": outputs,
            "audit_status": "unresolved",
        }

    try:
        # The audit receives the other agents' findings explicitly.
        audit_task = (
            "Independently audit this MeterMind case.\n\n"
            f"Case ID: {state.get('case_id', 'RECON-DEMO-001')}\n\n"
            "Specialist outputs:\n"
            + str({
                name: outputs[name]
                for name in (
                    "event_agent",
                    "pricing_agent",
                    "invoice_agent",
                )
            })
            + "\n\nRetrieve the deterministic evidence report. "
            "Verify relevant arithmetic. Identify unsupported claims, "
            "contradictions, and unresolved evidence. "
            "Return one final decision: verified, disputed, or unresolved."
        )

        audit_output = invoke_agent(audit_agent, audit_task)

        outputs["audit_agent"] = {
            "status": "completed",
            "output": audit_output,
        }

        # Keep this conservative. The audit model's prose is not a
        # machine-validated approval decision.
        audit_status = "review_required"

    except Exception as exc:
        errors.append(
            f"audit_agent: {type(exc).__name__}: {exc}"
        )

        outputs["audit_agent"] = {
            "status": "failed",
            "output": "",
            "error": f"{type(exc).__name__}: {exc}",
        }

        audit_status = "unresolved"

    return {
        "agent_outputs": outputs,
        "errors": errors,
        "audit_status": audit_status,
    }


def build_workflow():
    graph = StateGraph(MeterMindState)

    graph.add_node("event_agent", event_node)
    graph.add_node("pricing_agent", pricing_node)
    graph.add_node("invoice_agent", invoice_node)
    graph.add_node("audit_agent", audit_node)

    graph.add_edge(START, "event_agent")
    graph.add_edge("event_agent", "pricing_agent")
    graph.add_edge("pricing_agent", "invoice_agent")
    graph.add_edge("invoice_agent", "audit_agent")
    graph.add_edge("audit_agent", END)

    return graph.compile()


meter_mind_workflow = build_workflow()


def run_investigation(
    case_id: str = "RECON-DEMO-001",
) -> dict[str, Any]:
    result = meter_mind_workflow.invoke({
        "case_id": case_id,
        "agent_outputs": {},
        "errors": [],
    })

    return {
        "case_id": result.get("case_id", case_id),
        "audit_status": result.get("audit_status", "unresolved"),
        "agent_outputs": result.get("agent_outputs", {}),
        "errors": result.get("errors", []),
    }