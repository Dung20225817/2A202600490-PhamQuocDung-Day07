from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str], score_threshold: float | None = None) -> None:
        self.store = store
        self.llm_fn = llm_fn
        self.score_threshold = score_threshold

    def answer(self, question: str, top_k: int = 3) -> str:
        retrieved = self.store.search(question, top_k=top_k, min_score=self.score_threshold)
        if not retrieved:
            return self.llm_fn(
                f"Question: {question}\n\nNo context was retrieved from the knowledge base. "
                "State that the answer cannot be grounded from available data."
            )

        context_blocks = []
        for idx, item in enumerate(retrieved, start=1):
            source = item.get("metadata", {}).get("doc_id", "unknown")
            context_blocks.append(
                f"[{idx}] source={source} score={item.get('score', 0.0):.4f}\n{item.get('content', '')}"
            )

        context = "\n\n".join(context_blocks)
        prompt = (
            "You are a helpful assistant. Use only the provided context to answer.\n"
            "If the context is insufficient, say what is missing.\n\n"
            f"Question:\n{question}\n\n"
            f"Context:\n{context}\n\n"
            "Answer:"
        )
        return self.llm_fn(prompt)
