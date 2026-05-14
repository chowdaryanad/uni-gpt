import os
os.environ["TRANSFORMERS_NO_TF"] = "1"

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from .config import QDRANT_COLLECTION, EMBED_MODEL

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF_DIR = os.path.join(BASE_DIR, "core", "rag", "data")

print(f"📂 Loading PDFs from: {PDF_DIR}")

_embeddings = None
_vector_store = None
_retriever = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            encode_kwargs={"normalize_embeddings": False},
        )
    return _embeddings


def load_pdf_documents():
    """Load all PDFs from PDF_DIR and return Document objects with metadata."""
    pdf_dir = Path(PDF_DIR)
    docs = []

    if not pdf_dir.exists():
        print(f"⚠️ PDF directory not found: {pdf_dir}")
        return docs

    pdf_files = list(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        print(f"⚠️ No PDF files found in: {pdf_dir}")
        return docs

    for pdf_path in pdf_files:
        file_name = pdf_path.name
        print(f"📄 Loading: {file_name}")

        try:
            loader = PyPDFLoader(str(pdf_path))
            pages = loader.load()

            for p in pages:
                docs.append(
                    Document(
                        page_content=p.page_content,
                        metadata={
                            "source": file_name,
                            "page": p.metadata.get("page", 0),
                        },
                    )
                )
        except Exception as e:
            print(f"❌ Error loading {file_name}: {e}")

    print(f"✅ Total documents loaded: {len(docs)}")
    return docs


def get_retriever():
    global _retriever, _vector_store

    if _retriever is not None:
        return _retriever

    # ✅ In-memory Qdrant (no Docker needed)
    client = QdrantClient(":memory:")

    # ✅ Create collection if not exists
    collections = [c.name for c in client.get_collections().collections]

    if QDRANT_COLLECTION not in collections:
        client.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=768,  # must match embedding model
                distance=Distance.COSINE,
            ),
        )

    embeddings = get_embeddings()

    _vector_store = QdrantVectorStore(
        client=client,
        collection_name=QDRANT_COLLECTION,
        embedding=embeddings,
    )

    # ✅ LOAD REAL PDFs from PDF_DIR
    docs = load_pdf_documents()

    if docs:
        _vector_store.add_documents(docs)
        print(f"📚 {len(docs)} document chunks added to vector store")
    else:
        print("⚠️ No documents loaded — vector store is empty")

    _retriever = _vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4},
    )

    return _retriever