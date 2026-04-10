from __future__ import annotations

from typing import Any, Callable

from .chunking import _dot
from .embeddings import _mock_embed
from .models import Document


class EmbeddingStore:
    """
    A vector store for text chunks.

    Tries to use ChromaDB if available; falls back to an in-memory store.
    The embedding_fn parameter allows injection of mock embeddings for tests.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        embedding_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._embedding_fn = embedding_fn or _mock_embed
        self._collection_name = collection_name
        self._use_chroma = False
        self._store: list[dict[str, Any]] = []
        self._collection = None
        self._next_index = 0

        try:
            import chromadb

            client = chromadb.Client()
            self._collection = client.get_or_create_collection(name=self._collection_name)
            self._use_chroma = True
        except Exception:
            self._use_chroma = False
            self._collection = None

    def _make_record(self, doc: Document) -> dict[str, Any]:
        metadata = dict(doc.metadata or {})
        metadata.setdefault("doc_id", doc.id)
        record_id = f"{doc.id}::{self._next_index}"
        self._next_index += 1
        return {
            "id": record_id,
            "content": doc.content,
            "metadata": metadata,
            "embedding": self._embedding_fn(doc.content),
        }

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a batch of texts.

        Uses OpenAI batch API when available; otherwise falls back to one-by-one embedding.
        """
        if not texts:
            return []

        client = getattr(self._embedding_fn, "client", None)
        model_name = getattr(self._embedding_fn, "model_name", None)
        if client is not None and model_name:
            batch_size = 128
            vectors: list[list[float]] = []
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                response = client.embeddings.create(model=model_name, input=batch)
                vectors.extend([[float(value) for value in item.embedding] for item in response.data])
            return vectors

        return [self._embedding_fn(text) for text in texts]

    def _search_records(
        self,
        query: str,
        records: list[dict[str, Any]],
        top_k: int,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        if not records:
            return []

        query_embedding = self._embedding_fn(query)
        scored: list[dict[str, Any]] = []
        for record in records:
            score = _dot(query_embedding, record["embedding"])
            scored.append(
                {
                    "id": record["id"],
                    "content": record["content"],
                    "metadata": record["metadata"],
                    "score": float(score),
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        if min_score is not None:
            scored = [item for item in scored if item["score"] >= min_score]
        return scored[: max(0, top_k)]

    def add_documents(self, docs: list[Document]) -> None:
        """
        Embed each document's content and store it.

        For ChromaDB: use collection.add(ids=[...], documents=[...], embeddings=[...])
        For in-memory: append dicts to self._store
        """
        if not docs:
            return

        # Batch embed for better performance on large corpora.
        vectors = self._embed_texts([doc.content for doc in docs])

        for doc, vector in zip(docs, vectors):
            metadata = dict(doc.metadata or {})
            metadata.setdefault("doc_id", doc.id)
            record_id = f"{doc.id}::{self._next_index}"
            self._next_index += 1
            record = {
                "id": record_id,
                "content": doc.content,
                "metadata": metadata,
                "embedding": vector,
            }

            if self._use_chroma and self._collection is not None:
                self._collection.add(
                    ids=[record["id"]],
                    documents=[record["content"]],
                    embeddings=[record["embedding"]],
                    metadatas=[record["metadata"]],
                )
            else:
                self._store.append(record)

    def search(self, query: str, top_k: int = 5, min_score: float | None = None) -> list[dict[str, Any]]:
        """
        Find the top_k most similar documents to query.

        For in-memory: compute dot product of query embedding vs all stored embeddings.
        """
        if top_k <= 0:
            return []

        if self._use_chroma and self._collection is not None:
            query_embedding = self._embedding_fn(query)
            response = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
            ids = response.get("ids", [[]])[0]
            docs = response.get("documents", [[]])[0]
            metadatas = response.get("metadatas", [[]])[0]
            distances = response.get("distances", [[]])[0]

            results: list[dict[str, Any]] = []
            for idx, content, metadata, distance in zip(ids, docs, metadatas, distances):
                results.append(
                    {
                        "id": idx,
                        "content": content,
                        "metadata": metadata or {},
                        "score": float(-distance),
                    }
                )
            results.sort(key=lambda item: item["score"], reverse=True)
            if min_score is not None:
                results = [item for item in results if item["score"] >= min_score]
            return results[: max(0, top_k)]

        return self._search_records(query=query, records=self._store, top_k=top_k, min_score=min_score)

    def get_collection_size(self) -> int:
        """Return the total number of stored chunks."""
        if self._use_chroma and self._collection is not None:
            return int(self._collection.count())
        return len(self._store)

    def search_with_filter(
        self,
        query: str,
        top_k: int = 3,
        metadata_filter: dict = None,
        min_score: float | None = None,
    ) -> list[dict]:
        """
        Search with optional metadata pre-filtering.

        First filter stored chunks by metadata_filter, then run similarity search.
        """
        if not metadata_filter:
            return self.search(query=query, top_k=top_k, min_score=min_score)

        if self._use_chroma and self._collection is not None:
            query_embedding = self._embedding_fn(query)
            response = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=metadata_filter,
            )
            ids = response.get("ids", [[]])[0]
            docs = response.get("documents", [[]])[0]
            metadatas = response.get("metadatas", [[]])[0]
            distances = response.get("distances", [[]])[0]

            results: list[dict[str, Any]] = []
            for idx, content, metadata, distance in zip(ids, docs, metadatas, distances):
                results.append(
                    {
                        "id": idx,
                        "content": content,
                        "metadata": metadata or {},
                        "score": float(-distance),
                    }
                )
            results.sort(key=lambda item: item["score"], reverse=True)
            if min_score is not None:
                results = [item for item in results if item["score"] >= min_score]
            return results[: max(0, top_k)]

        filtered_records = [
            record
            for record in self._store
            if all(record.get("metadata", {}).get(key) == value for key, value in metadata_filter.items())
        ]
        return self._search_records(query=query, records=filtered_records, top_k=top_k, min_score=min_score)

    def delete_document(self, doc_id: str) -> bool:
        """
        Remove all chunks belonging to a document.

        Returns True if any chunks were removed, False otherwise.
        """
        if self._use_chroma and self._collection is not None:
            response = self._collection.get(where={"doc_id": doc_id})
            ids = response.get("ids", [])
            if not ids:
                return False
            self._collection.delete(ids=ids)
            return True

        before = len(self._store)
        self._store = [r for r in self._store if r.get("metadata", {}).get("doc_id") != doc_id]
        return len(self._store) < before
