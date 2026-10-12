
from app.graph.workflow import collect_policy_evidence
from app.schemas.agent_result import EvidenceReference
from app.services.billing_policy_rag import (
    clear_policy_retrieval_audit,
    get_policy_retrieval_audit,
)
from app.graph.workflow import run_specialist
from app.schemas.agent_result import AgentResult, AgentStatus

def test_policy_retrieval_audit_converts_to_evidence_references():
    clear_policy_retrieval_audit()

    # Simulate the metadata recorded by a successful policy retrieval.
    from app.services import billing_policy_rag

    with billing_policy_rag._retrieval_audit_lock:
        billing_policy_rag._retrieval_audit.append(
            {
                "query": "July 2026 STARTER pricing",
                "document_id": "BILLING-POLICY-001",
                "title": "Usage-Based Billing and Pricing",
                "effective_from": "2026-01-01",
                "source_file": "usage_billing.md",
                "chunk_index": 0,
                "distance": 0.9,
            }
        )

    evidence = collect_policy_evidence()

    assert len(evidence) == 1
    assert isinstance(evidence[0], EvidenceReference)
    assert evidence[0].evidence_id == "BILLING-POLICY-001:chunk-0"
    assert evidence[0].source == "billing_policy_rag"
    assert "usage_billing.md" in evidence[0].description

    clear_policy_retrieval_audit()


def test_pricing_specialist_includes_policy_and_deterministic_evidence(
    monkeypatch,
):
    from app.graph import workflow
    from app.services import billing_policy_rag

    clear_policy_retrieval_audit()

    # Simulate the policy retrieval that occurs during agent invocation.
    def fake_invoke_agent(agent, task):
        with billing_policy_rag._retrieval_audit_lock:
            billing_policy_rag._retrieval_audit.append(
                {
                    "query": "July 2026 STARTER pricing",
                    "document_id": "BILLING-POLICY-001",
                    "title": "Usage-Based Billing and Pricing",
                    "effective_from": "2026-01-01",
                    "source_file": "usage_billing.md",
                    "chunk_index": 0,
                    "distance": 0.9,
                }
            )
        return "Policy retrieved."

    # Keep the test independent of the real LLM and database.
    monkeypatch.setattr(workflow, "invoke_agent", fake_invoke_agent)
    monkeypatch.setattr(workflow, "get_report", lambda: {})
    monkeypatch.setattr(
        workflow,
        "result_for_agent",
        lambda agent_name, report, case_id: AgentResult(
            agent_name=agent_name,
            case_id=case_id,
            status=AgentStatus.COMPLETED,
            summary="Pricing reconstruction completed.",
            evidence_reviewed=[
                EvidenceReference(
                    evidence_id="pricing-reconstruction:CUS-1001:2026-07:PRICE-STARTER-V2",
                    source="deterministic_pricing_reconstruction",
                    description="Deterministic pricing reconstruction.",
                )
            ],
        ),
    )

    result = run_specialist(
        state={"case_id": "TEST-CASE"},
        agent=object(),
        agent_name="pricing_agent",
        task="Investigate July pricing.",
    )

    pricing_result = result["agent_results"]["pricing_agent"]
    sources = {item.source for item in pricing_result.evidence_reviewed}

    assert "billing_policy_rag" in sources
    assert "deterministic_pricing_reconstruction" in sources

    policy_refs = [
        item for item in pricing_result.evidence_reviewed
        if item.source == "billing_policy_rag"
    ]
    assert policy_refs[0].evidence_id == "BILLING-POLICY-001:chunk-0"

    clear_policy_retrieval_audit()
