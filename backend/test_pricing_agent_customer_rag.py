
from app.agents.pricing_agent import pricing_agent

query = """
Investigate Acme AI, customer ID CUS-1001, on the STARTER plan
for the July 2026 billing period.

You must use BOTH tools before reaching a conclusion:
1. Call inspect_pricing_data to inspect customer plans and pricing versions.
2. Call search_billing_policies to retrieve the relevant effective-dated
   pricing policy.

Explain which pricing version is applicable in July 2026, why the
effective dates matter, and what evidence would be needed to establish
whether the recorded invoice is incorrect.

Cite the pricing version IDs and policy document ID.
Do not invent invoice amounts or authorize financial corrections.
"""

result = pricing_agent.invoke(
    {
        "messages": [
            {"role": "user", "content": query}
        ]
    }
)

print("\n=== TOOL CALL AUDIT ===")

called_tools = []

for message in result["messages"]:
    for call in getattr(message, "tool_calls", []):
        name = call.get("name")
        called_tools.append(name)
        print(f"Tool called: {name}")
        print(f"Arguments: {call.get('args')}")

print("\n=== REQUIRED TOOL CHECK ===")

for required in (
    "inspect_pricing_data",
    "search_billing_policies",
):
    print(f"{required}: {'CALLED' if required in called_tools else 'NOT CALLED'}")

print("\n=== FINAL AGENT RESPONSE ===")
print(result["messages"][-1].content)
