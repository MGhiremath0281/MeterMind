from app.graph.state import MeterMindState
from app.schemas.agent_result import AgentResult, AgentStatus


def test_state_supports_structured_agent_results():
    result = AgentResult(
        agent_name="event_agent",
        case_id="RECON-TEST-001",
        status=AgentStatus.COMPLETED,
        summary="No confirmed anomalies were reported.",
    )

    state: MeterMindState = {
        "case_id": "RECON-TEST-001",
        "agent_outputs": {},
        "agent_results": {
            "event_agent": result,
        },
        "errors": [],
        "retry_count": 0,
        "supervisor_decision": "pending",
    }

    assert state["agent_results"]["event_agent"].case_id == (
        "RECON-TEST-001"
    )
    assert state["retry_count"] == 0