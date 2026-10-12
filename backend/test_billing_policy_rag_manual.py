
from app.services.billing_policy_rag import (
    rebuild_policy_index,
    retrieve_policy_context,
)


if __name__ == "__main__":
    count = rebuild_policy_index()
    print(f"\nIndexed {count} policy chunks.")

    query = "Can a new pricing version be applied retroactively?"

    results = retrieve_policy_context(query, k=3)

    print(f"\nQuery: {query}")
    print("\nRetrieved policy passages:\n")

    for result in results:
        print("=" * 70)
        print(f"Document ID: {result['document_id']}")
        print(f"Title: {result['title']}")
        print(f"Effective from: {result['effective_from']}")
        print(f"Source file: {result['source_file']}")
        print(f"Distance: {result['distance']:.4f}")
        print(f"\n{result['content']}")
        print()
