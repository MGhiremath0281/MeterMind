from app.graph.workflow import run_investigation


def test_workflow_runs_all_specialists():
    result = run_investigation()

    outputs = result["agent_outputs"]

    expected_agents = {
        "event_agent",
        "pricing_agent",
        "invoice_agent",
        "audit_agent",
    }

    assert expected_agents.issubset(outputs.keys())

    for agent_name in expected_agents:
        assert outputs[agent_name]["status"] in {
            "completed",
            "failed",
            "blocked",
        }

    print(result)


if __name__ == "__main__":
    print(run_investigation())