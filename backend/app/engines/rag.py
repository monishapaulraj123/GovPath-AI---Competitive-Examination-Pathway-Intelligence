"""
Retrieval-Augmented Generation (RAG) Engine.
Handles document ingestion, overlapping chunking, metadata indexing,
TF-IDF + cosine vector retrieval (with optional external LLM embeddings), and source attribution.
"""

from typing import Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session
from app.models import RAGChunk, RAGDocument


def chunk_text(text: str, chunk_size: int = 550, overlap: int = 100) -> list[str]:
    clean = " ".join(text.split())
    if len(clean) <= chunk_size:
        return [clean] if clean else []

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        if end < len(clean):
            last_space = clean.rfind(" ", start, end)
            if last_space > start + chunk_size // 2:
                end = last_space
        piece = clean[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(clean):
            break
        start = max(end - overlap, start + 1)
    return chunks


class RAGEngine:
    def __init__(self, db: Session):
        self.db = db

    def ingest_document(
        self,
        title: str,
        content: str,
        source_name: str,
        exam_id: Optional[str] = None,
        doc_type: str = "Curated Reference",
        source_url: str = "",
        verified_status: str = "Verified Reference",
    ) -> RAGDocument:
        doc = RAGDocument(
            title=title.strip(),
            exam_id=exam_id,
            doc_type=doc_type,
            source_name=source_name.strip(),
            source_url=source_url.strip(),
            verified_status=verified_status,
            raw_text=content.strip(),
        )
        self.db.add(doc)
        self.db.flush()

        pieces = chunk_text(content)
        for idx, piece in enumerate(pieces):
            self.db.add(
                RAGChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    content=piece,
                    chunk_metadata={
                        "title": doc.title,
                        "exam_id": exam_id,
                        "doc_type": doc_type,
                        "source_name": doc.source_name,
                        "source_url": doc.source_url,
                        "verified_status": doc.verified_status,
                    },
                )
            )
        doc.chunk_count = len(pieces)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def retrieve(
        self,
        query: str,
        exam_id: Optional[str] = None,
        top_k: int = 4,
    ) -> list[dict[str, Any]]:
        chunks = self.db.query(RAGChunk).all()
        if not chunks:
            return []

        filtered = chunks
        if exam_id:
            exam_matches = [
                c for c in chunks if (c.chunk_metadata or {}).get("exam_id") in (exam_id, None)
            ]
            if exam_matches:
                filtered = exam_matches

        corpus = [c.content + " " + str((c.chunk_metadata or {}).get("title", "")) for c in filtered]
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(corpus + [query])
        doc_vecs = matrix[:-1]
        query_vec = matrix[-1]
        scores = cosine_similarity(query_vec, doc_vecs).flatten()

        ranked_indices = scores.argsort()[::-1][:top_k]
        results: list[dict[str, Any]] = []
        for idx in ranked_indices:
            score = float(scores[idx])
            if score <= 0.02 and results:
                continue
            chunk = filtered[int(idx)]
            meta = chunk.chunk_metadata or {}
            results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "score": round(score, 3),
                "content": chunk.content,
                "title": meta.get("title", "Reference Document"),
                "exam_id": meta.get("exam_id"),
                "doc_type": meta.get("doc_type", "Reference"),
                "source_name": meta.get("source_name", "GovPath Knowledge Base"),
                "source_url": meta.get("source_url", ""),
                "verified_status": meta.get("verified_status", "Verified Reference"),
            })
        return results
