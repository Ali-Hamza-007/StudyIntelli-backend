import os
import json
import logging
import numpy as np
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional sentence-transformers import. If the package is not installed we
# fall back to a simple TF-IDF-style bag-of-words similarity so the system
# still works (just less accurately).  Install with:
#   pip install sentence-transformers
# ---------------------------------------------------------------------------
try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False
    logger.warning(
        "sentence-transformers not installed. RAG will use keyword overlap similarity. "
        "Install with: pip install sentence-transformers"
    )


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

_MODEL = None  # Lazy-loaded singleton

def _get_model():
    global _MODEL
    if _MODEL is None and _ST_AVAILABLE:
        logger.info("Loading sentence-transformer model (first call)…")
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Model loaded.")
    return _MODEL


def _embed(texts: list[str]) -> list[list[float]]:
    """Return a list of embedding vectors (one per text)."""
    model = _get_model()
    if model is not None:
        return model.encode(texts, convert_to_numpy=True, show_progress_bar=False).tolist()
    # Fallback: character-level unigram bag-of-words on 1000 most common chars
    return _bow_embed(texts)


def _bow_embed(texts: list[str]) -> list[list[float]]:
    """Minimal bag-of-words fallback when sentence-transformers is missing."""
    vocab = {}
    for text in texts:
        for ch in set(text.lower()):
            if ch not in vocab:
                vocab[ch] = len(vocab)
    dim = max(len(vocab), 1)
    embeddings = []
    for text in texts:
        vec = [0.0] * dim
        for ch in text.lower():
            if ch in vocab:
                vec[vocab[ch]] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        embeddings.append([v / norm for v in vec])
    return embeddings


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


# ---------------------------------------------------------------------------
# RAGService
# ---------------------------------------------------------------------------

class RAGService:
    """Builds and queries a simple in-DB vector index for a Document."""

    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 100

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.CHUNK_SIZE,
            chunk_overlap=self.CHUNK_OVERLAP,
        )
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model="openai/gpt-oss-20b",
            temperature=0.4,
        )

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def build_index(self, document) -> int:
        """
        Chunk `document.extracted_text`, embed each chunk, and persist them
        as `DocumentChunk` rows.  Returns the number of chunks created.

        Must be called AFTER document.extracted_text has been populated.
        Deletes any existing chunks for the document first (idempotent).
        """
        from api.models import DocumentChunk  # lazy import to avoid circular

        text = document.extracted_text or ""
        if not text.strip():
            logger.warning(f"Document {document.id}: no text to index.")
            return 0

        # Remove stale chunks
        DocumentChunk.objects.filter(document=document).delete()

        chunks = self.splitter.split_text(text)
        if not chunks:
            return 0

        logger.info(f"Embedding {len(chunks)} chunks for document {document.id}…")
        embeddings = _embed(chunks)

        chunk_objects = [
            DocumentChunk(
                document=document,
                chunk_index=i,
                text=chunks[i],
                embedding=embeddings[i],   # stored as JSON list of floats
            )
            for i in range(len(chunks))
        ]
        DocumentChunk.objects.bulk_create(chunk_objects)
        logger.info(f"Indexed {len(chunk_objects)} chunks for document {document.id}.")
        return len(chunk_objects)

    # ------------------------------------------------------------------
    # Query / chat
    # ------------------------------------------------------------------

    def query(self, document, question: str, top_k: int = 5) -> str:
        """
        Retrieve the top-k most relevant chunks for `question` from the
        document's stored index, then ask Groq to answer based on those chunks.

        Returns the answer string.
        """
        from api.models import DocumentChunk  # lazy import

        chunks = DocumentChunk.objects.filter(document=document).order_by("chunk_index")

        if not chunks.exists():
            # Fallback: rebuild the index on the fly if somehow missing
            logger.warning(
                f"No chunks found for document {document.id}. Rebuilding index…"
            )
            self.build_index(document)
            chunks = DocumentChunk.objects.filter(document=document).order_by("chunk_index")

        if not chunks.exists():
            return "I couldn't find any content in this document to answer your question."

        # Embed the question and compute similarity against all stored chunks
        question_embedding = _embed([question])[0]

        scored = []
        for chunk in chunks:
            sim = _cosine_similarity(question_embedding, chunk.embedding)
            scored.append((sim, chunk.text))

        # Sort descending by similarity, take top-k
        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [text for _, text in scored[:top_k]]

        context = "\n\n---\n\n".join(top_chunks)

        prompt = (
            "You are a helpful academic tutor. Use ONLY the provided context to answer "
            "the student's question. If the answer is not in the context, say so clearly.\n\n"
            f"Context:\n{context}\n\n"
            f"Student's Question: {question}\n\n"
            "Answer:"
        )

        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"RAG query error for document {document.id}: {e}", exc_info=True)
            return f"Sorry, I encountered an error while processing your question: {str(e)}"
