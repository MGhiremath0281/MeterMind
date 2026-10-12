
from app.tools.billing_tools import inspect_pricing_data
from app.tools.billing_policy_tools import search_billing_policies


def test_pricing_fixture_selects_starter_v2_for_july():
    import json

    fixture = json.loads(inspect_pricing_data.invoke({}))

    customer = next(
        item for item in fixture["customers"]
        if item["customer_id"] == "CUS-1001"
    )

    assert customer["plan_id"] == "STARTER"

    versions = [
        item for item in fixture["pricing_versions"]
        if item["plan_id"] == customer["plan_id"]
    ]

    july_versions = [
        item for item in versions
        if item["effective_from"] <= "2026-07-01"
        and (
            item["effective_to"] is None
            or item["effective_to"] >= "2026-07-01"
        )
    ]

    assert len(july_versions) == 1
    assert july_versions[0]["pricing_version_id"] == "PRICE-STARTER-V2"
    assert july_versions[0]["unit_price"] == "0.0120"


def test_policy_tool_returns_retroactive_pricing_rule(monkeypatch):
    from app.tools import billing_policy_tools

    def fake_retrieve(query, k=3):
        return [
            {
                "document_id": "BILLING-POLICY-001",
                "title": "Usage-Based Billing and Pricing",
                "effective_from": "2026-01-01",
                "source_file": "usage_billing.md",
                "content": (
                    "A later pricing version must not automatically "
                    "be applied retroactively."
                ),
                "chunk_index": 0,
                "distance": 0.5,
            }
        ]

    monkeypatch.setattr(
        billing_policy_tools,
        "retrieve_policy_context",
        fake_retrieve,
    )

    result = search_billing_policies.invoke(
        {"query": "pricing effective dates and retroactive pricing"}
    )

    assert "BILLING-POLICY-001" in result
    assert "usage_billing.md" in result
    assert "retroactively" in result.lower()
