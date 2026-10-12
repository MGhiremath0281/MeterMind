
from app.agents.pricing_agent import pricing_agent

query = """
Investigate this question:
Can a new pricing version be applied retroactively?

Use the available tools to inspect pricing data and search billing
policies before drawing a conclusion. Cite the policy document ID
and explain what the evidence establishes and what remains unknown.
"""

result = pricing_agent.invoke(
    {
        "messages": [
            {"role": "user", "content": query}
        ]
    }
)

print("\n=== AGENT RESPONSE ===")

for message in result["messages"]:
    message_type = type(message).__name__
    content = getattr(message, "content", "")
    tool_calls = getattr(message, "tool_calls", [])

    if tool_calls:
        print(f"\n[{message_type}] TOOL CALLS:")
        for call in tool_calls:
            print(f"  Tool: {call.get('name')}")
            print(f"  Arguments: {call.get('args')}")

    if content:
        print(f"\n[{message_type}]")
        print(content)
