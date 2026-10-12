
from app.services.billing_policy_rag import load_policy_documents
from app.tools import billing_policy_tools


def test_loads_all_three_billing_policy_documents():
    documents = load_policy_documents()

    document_ids = {
        document.metadata["document_id"]
        for document in documents
    }

    assert {
        "BILLING-POLICY-001",
        "BILLING-POLICY-002",
        "BILLING-POLICY-003",
    }.issubset(document_ids)


def test_policy_documents_preserve_source_metadata():
    documents = load_policy_documents()

    pricing_documents = [
        document
        for document in documents
        if document.metadata["document_id"] == "BILLING-POLICY-001"
    ]

    assert pricing_documents

    document = pricing_documents[0]

    assert document.metadata["title"] == "Usage-Based Billing and Pricing"
    assert document.metadata["effective_from"] == "2026-01-01"
    assert document.metadata["source_file"] == "usage_billing.md"
    assert "retroactively" in document.page_content.lower()


def test_policy_tool_returns_retrieved_source_evidence(monkeypatch):
    def fake_retrieve(query, k=3):
        assert "retroactive" in query.lower()
        assert k == 3

        return [
            {
                "document_id": "BILLING-POLICY-001",
                "title": "Usage-Based Billing and Pricing",
                "effective_from": "2026-01-01",
                "source_file": "usage_billing.md",
                "content": "A later pricing version must not automatically be applied retroactively.",
                "chunk_index": 0,
                "distance": 0.5,
            }
        ]

    monkeypatch.setattr(
        billing_policy_tools,
        "retrieve_policy_context",
        fake_retrieve,
    )

    result = billing_policy_tools.search_billing_policies.invoke(
        {"query": "Can pricing be applied retroactively?"}
    )

    assert "BILLING-POLICY-001" in result
    assert "usage_billing.md" in result
    assert "must not automatically be applied retroactively" in result


def test_policy_tool_reports_retrieval_failure(monkeypatch):
    def fake_retrieve(query, k=3):
        raise RuntimeError("Simulated retrieval failure")

    monkeypatch.setattr(
        billing_policy_tools,
        "retrieve_policy_context",
        fake_retrieve,
    )

    result = billing_policy_tools.search_billing_policies.invoke(
        {"query": "pricing effective dates"}
    )

    assert "POLICY RETRIEVAL FAILED" in result
    assert "RuntimeError" in result
