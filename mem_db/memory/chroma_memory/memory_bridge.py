from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter  # noqa: E402
from langchain_community.vectorstores import Chroma  # noqa: E402
from langchain_huggingface import HuggingFaceEmbeddings  # noqa: E402
from unified_memory_manager_canonical import create_reviewable_memory  # noqa: E402

# Step 1: Set Up Chroma for Document Storage

CHROMA_PATH = "./chroma_db"
SOURCE_DIR = Path("./seed_documents")
embedding_model = "sentence-transformers/all-MiniLM-L6-v2"

# Initialize the embedding model
embedding_function = HuggingFaceEmbeddings(
    model_name=embedding_model, model_kwargs={"device": "cpu"}
)

# Load and split documents
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
docs = []

# Load documents from the source directory
files = list(SOURCE_DIR.glob("*.*"))
for file in files:
    content = file.read_text(encoding="utf-8", errors="ignore")
    name = file.name
    split_docs = splitter.create_documents([content], metadatas=[{"source": name}])
    docs.extend(split_docs)

# Store documents in Chroma
vectorstore = Chroma.from_documents(
    documents=docs, embedding=embedding_function, persist_directory=CHROMA_PATH
)
print(f"✅ {len(docs)} reasoning chunks saved to {CHROMA_PATH}")

# Step 2: Set Up Reviewable Memory for Human Review

# Create a ReviewableMemory instance
review_memory = create_reviewable_memory()

# Step 3: Integrate Chroma with Reviewable Memory


async def process_and_review_documents():
    # Process documents and add items to the review queue
    for doc in docs:
        # Extract entities and relationships from the document
        extraction_result = process_document(doc)  # Implement this function

        # Add extraction results to the review queue
        await review_memory.process_extraction_result(
            extraction_result, doc.metadata["source"]
        )

    # Retrieve pending reviews and handle review decisions
    pending_reviews = await review_memory.get_pending_reviews()
    for review_item in pending_reviews:
        # Get review decisions (e.g., from a human reviewer)
        decision = get_review_decision(review_item)  # Implement this function

        # Submit review decisions
        await review_memory.submit_review_decision(decision)


# Example function to process a document and extract entities and relationships
def process_document(doc):
    # Implement your document processing logic here
    # This function should return an extraction result with entities and relationships
    return {"entities": [], "relationships": []}


# Example function to get review decisions
def get_review_decision(review_item):
    # Implement your logic to get review decisions here
    # This function should return a review decision for the given review item
    return {
        "item_id": review_item.item_id,
        "decision": "APPROVED",  # Example decision
        "reviewer_id": "reviewer1",
        "reviewer_notes": "Approved after review",
    }


# Run the integration
import asyncio  # noqa: E402

asyncio.run(process_and_review_documents())
