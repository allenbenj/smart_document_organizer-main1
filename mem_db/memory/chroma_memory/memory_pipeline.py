"""
Module: memory_pipeline.py

This pipeline consolidates functionality from the following scripts:
  • embed_and_store.py
  • bootstrap_reasoning_memory.py

The following modules remain as standalone dependencies and should stay in the folder:
  • collective_intelligence_review_system.py    (defines ReviewableMemory)
  • unified_memory_manager_canonical.py       (defines MemoryBridge)
  • memory_bridge.py                          (bridge logic, if separate)

Merged and removed:
  • embed_and_store.py
  • bootstrap_reasoning_memory.py
"""

import asyncio
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

# Import review system and memory bridge
from collective_intelligence_review_system import ReviewableMemory  # noqa: E402
from langchain.docstore.document import Document  # noqa: E402
from langchain.embeddings import HuggingFaceEmbeddings  # noqa: E402
from langchain.text_splitter import RecursiveCharacterTextSplitter  # noqa: E402
from langchain.vectorstores import Chroma  # noqa: E402
from unified_memory_manager_canonical import MemoryBridge  # noqa: E402


def create_reviewable_memory(config=None):
    """
    Instantiate ReviewableMemory with an optional MemoryBridge configuration.
    """
    bridge = MemoryBridge(config or {})
    return ReviewableMemory(memory_bridge=bridge)


def process_document(doc):
    """
    Placeholder for document extraction logic.
    Should return a dict with 'entities' and 'relationships'.
    """
    # TODO: implement actual entity and relationship extraction
    return {"entities": [], "relationships": []}


def get_review_decision(review_item):
    """
    Placeholder for obtaining review decisions (e.g., via human UI).
    Returns a dict matching review_item.item_id and decision metadata.
    """
    # TODO: integrate with human-in-the-loop or automated decision system
    return {
        "item_id": review_item.item_id,
        "decision": "APPROVED",
        "reviewer_id": "reviewer1",
        "reviewer_notes": "Approved after review",
    }


async def process_documents(config):
    """
    Load, split, and embed documents into Chroma vectorstore.
    Returns a list of Document objects for review.
    """
    # Initialize embeddings
    embedding_model = config.get(
        "embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
    )
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model)

    # Text splitter configuration
    splitter_conf = config.get("chunking", {})
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=splitter_conf.get("chunk_size", 1000),
        chunk_overlap=splitter_conf.get("chunk_overlap", 100),
        separators=["\n\n", "\n", " ", ""],
    )

    # Prepare Chroma vectorstore
    vs_conf = config.get("vectorstore", {})
    persist_dir = vs_conf.get("persist_directory", "./chroma_db")
    collection_name = vs_conf.get("collection_prefix", "embedded_rag_memory")
    db = Chroma(
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_function=embeddings,
    )

    # Load and chunk documents
    docs = []
    loader_conf = config.get("document_loader", {})
    source_dir = Path(loader_conf.get("source_directory", "./documents"))
    accepted_exts = loader_conf.get("accepted_extensions", [])
    for file_path in source_dir.rglob("*"):
        if file_path.suffix.lower() in accepted_exts:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            chunks = text_splitter.split_text(text)
            docs_chunked = [
                Document(
                    page_content=chunk,
                    metadata={"source": str(file_path), "chunk_index": idx},
                )
                for idx, chunk in enumerate(chunks)
            ]
            docs.extend(docs_chunked)
            db.add_documents(docs_chunked)

    db.persist()
    return docs


async def process_and_review_documents(docs, review_memory):
    """
    Enqueue extraction results for review, retrieve pending items, and submit decisions.
    """
    # Enqueue each extraction result
    for doc in docs:
        extraction_result = process_document(doc)
        await review_memory.process_extraction_result(
            extraction_result, doc.metadata["source"]
        )

    # Handle pending reviews
    pending = await review_memory.get_pending_reviews()
    for review_item in pending:
        decision = get_review_decision(review_item)
        await review_memory.submit_review_decision(decision)


def print_context7_library_ids(config):
    """
    Print the context7 library names and their IDs from the config.
    """
    libraries = config.get("libraries", {})
    if not libraries:
        print("No libraries configured in config.")
        return
    print("Context7-Compatible Library IDs:")
    for name, lib in libraries.items():
        lib_id = lib.get("id")
        print(f"  {name}: {lib_id}")


def main():
    # Load configuration
    cfg_file = Path("config.yaml")
    if not cfg_file.exists():
        print("Error: config.yaml not found.")
        return
    config = yaml.safe_load(cfg_file.read_text())

    # Embed documents and queue for review
    docs = asyncio.run(process_documents(config))
    review_memory = create_reviewable_memory(config.get("review_memory", {}))
    asyncio.run(process_and_review_documents(docs, review_memory))

    # Output Context7 library identifiers
    print_context7_library_ids(config)


if __name__ == "__main__":
    main()
