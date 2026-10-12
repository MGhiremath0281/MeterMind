
from langchain.tools import tool

from app.services.billing_policy_rag import retrieve_policy_context


@tool
def search_billing_policies(query: str) -> str:
    """Search MeterMind's indexed billing policies for relevant supporting
    passages about pricing rules, effective dates, usage events, and
    invoice discrepancy investigations. Use the returned source metadata
    when explaining policy evidence.
    """
    try:
        results = retrieve_policy_context(query, k=3)

        if not results:
            return "No relevant billing policy passages were retrieved."

        sections = []

        for item in results:
            sections.append(
                f"Document ID: {item['document_id']}\n"
                f"Title: {item['title']}\n"
                f"Effective from: {item['effective_from']}\n"
                f"Source: {item['source_file']}\n"
                f"Passage:\n{item['content']}"
            )

        return "\n\n---\n\n".join(sections)

    except Exception as exc:
        # Do not silently convert a retrieval failure into policy evidence.
        return (
            "POLICY RETRIEVAL FAILED. No policy evidence was established. "
            f"Error: {type(exc).__name__}: {exc}"
        )
