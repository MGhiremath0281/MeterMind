
from pathlib import Path
import re

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma


# backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]

POLICY_DIR = BACKEND_DIR / "data" / "billing_policies"
VECTOR_DIR = BACKEND_DIR / "data" / "chroma_billing_policies"

COLLECTION_NAME = "metermind_billing_policies"
EMBEDDING_MODEL = "embeddinggemma:latest"


def load_policy_documents() -> list[Document]:
    """Load policy files and split them into traceable text chunks."""

    if not POLICY_DIR.exists():
        raise FileNotFoundError(
            f"Billing policy directory not found: {POLICY_DIR}"
        )

    documents: list[Document] = []

    for path in sorted(POLICY_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")

        # Read the simple YAML-style frontmatter used by our demo files.
        metadata: dict[str, str] = {}

        if content.startswith("---"):
            parts = content.split("---", 2)

            if len(parts) == 3:
                for line in parts[1].splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip()

                content = parts[2].strip()

        document_id = metadata.get("document_id", path.stem)
        title = metadata.get("title", path.stem)
        effective_from = metadata.get("effective_from", "")

        # Keep paragraphs intact where possible.
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", content)
            if paragraph.strip()
        ]

        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip()

            if current and len(candidate) > 700:
                chunks.append(current)
                current = paragraph
            else:
                current = candidate

        if current:
            chunks.append(current)

        for index, chunk in enumerate(chunks):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "document_id": document_id,
                        "title": title,
                        "effective_from": effective_from,
                        "source_file": path.name,
                        "chunk_index": index,
                    },
                )
            )

    if not documents:
        raise ValueError(f"No Markdown policy documents found in {POLICY_DIR}")

    return documents


def rebuild_policy_index() -> int:
    """Rebuild the local Chroma index from the current policy files."""

    documents = load_policy_documents()

    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

    # Remove the previous collection so deleted or edited documents
    # cannot leave stale chunks in the index.
    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(VECTOR_DIR),
    )

    vector_store.delete_collection()

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(VECTOR_DIR),
    )

    ids = [
        f"{doc.metadata['document_id']}-chunk-{doc.metadata['chunk_index']}"
        for doc in documents
    ]

    vector_store.add_documents(documents=documents, ids=ids)

    return len(documents)


def retrieve_policy_context(
    query: str,
    k: int = 3,
) -> list[dict]:
    """Retrieve relevant policy passages with source metadata."""

    if not query.strip():
        raise ValueError("Query must not be empty.")

    if k < 1:
        raise ValueError("k must be at least 1.")

    if not VECTOR_DIR.exists():
        raise RuntimeError(
            "Policy index does not exist. Run rebuild_policy_index() first."
        )

    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(VECTOR_DIR),
    )

    matches = vector_store.similarity_search_with_score(query, k=k)

    results = []

    for document, distance in matches:
        results.append(
            {
                "content": document.page_content,
                "document_id": document.metadata.get("document_id"),
                "title": document.metadata.get("title"),
                "effective_from": document.metadata.get("effective_from"),
                "source_file": document.metadata.get("source_file"),
                "chunk_index": document.metadata.get("chunk_index"),
                # Chroma returns a distance here, not a probability.
                "distance": float(distance),
            }
        )

    return results
