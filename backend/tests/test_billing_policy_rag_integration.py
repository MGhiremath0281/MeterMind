
import pytest

from app.services.billing_policy_rag import (
    rebuild_policy_index,
    retrieve_policy_context,
)


@pytest.mark.integration
def test_retrieves_retroactive_pricing_policy():
    rebuild_policy_index()

    results = retrieve_policy_context(
        "Can a new pricing version be applied retroactively?",
        k=3,
    )

    assert results

    top_result = results[0]

    assert top_result["document_id"] == "BILLING-POLICY-001"
    assert top_result["source_file"] == "usage_billing.md"
    assert "retroactively" in top_result["content"].lower()
