from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from src import (
    EMBEDDING_PROVIDER_ENV,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    Document,
    EmbeddingStore,
    KnowledgeBaseAgent,
    LocalEmbedder,
    OpenAIEmbedder,
    SentenceChunker,
    _mock_embed,
)

GROUP_QUERIES = [
    "Quy tắc cốt lõi của The Mom Test để tránh nhận lời nói dối là gì?",
    "Tại sao compliments lại được coi là fool's gold trong học hỏi khách hàng?",
    "Làm thế nào để anchor những thông tin fluff từ khách hàng?",
    "Dấu hiệu nào cho thấy một cuộc gặp khách hàng đã thành công (Advancement)?",
    "Bạn nên làm gì khi lỡ tay pitching ý tưởng của mình quá sớm?",
]

QUERY_NORMALIZATION = {
    GROUP_QUERIES[0]: "What are the core rules of The Mom Test to avoid being lied to?",
    GROUP_QUERIES[1]: "Why are compliments considered fool's gold in customer learning?",
    GROUP_QUERIES[2]: "How do you anchor fluffy customer answers to concrete past behavior?",
    GROUP_QUERIES[3]: "What signals show that a customer meeting has truly advanced?",
    GROUP_QUERIES[4]: "What should you do if you accidentally start pitching too early?",
}


def _pick_embedder():
    load_dotenv(override=False)
    provider = os.getenv(EMBEDDING_PROVIDER_ENV, "openai").strip().lower()

    if provider == "openai":
        try:
            return OpenAIEmbedder(model_name=os.getenv("OPENAI_EMBEDDING_MODEL", OPENAI_EMBEDDING_MODEL))
        except Exception:
            return _mock_embed
    if provider == "local":
        try:
            return LocalEmbedder(model_name=os.getenv("LOCAL_EMBEDDING_MODEL", LOCAL_EMBEDDING_MODEL))
        except Exception:
            return _mock_embed
    return _mock_embed


def _infer_content_type(text: str) -> str:
    lower = text.lower()
    if "rule of thumb" in lower or "the mom test" in lower:
        return "rule"
    if "advancement" in lower or "commitment" in lower:
        return "advancement"
    if "good question" in lower:
        return "good_question"
    if "bad question" in lower:
        return "bad_question"
    if "compliment" in lower or "fluff" in lower:
        return "signal"
    return "general"


def _build_member2_documents() -> list[Document]:
    text = (PROJECT_ROOT / "The Mom Test.md").read_text(encoding="utf-8")

    # Member #2 strategy: granular sentence chunks.
    chunks = SentenceChunker(max_sentences_per_chunk=1).chunk(text)

    docs: list[Document] = []
    for idx, chunk in enumerate(chunks):
        docs.append(
            Document(
                id=f"momtest_s{idx}",
                content=chunk,
                metadata={
                    "doc_id": "TheMomTest",
                    "chapter": "unknown",
                    "content_type": _infer_content_type(chunk),
                    "strategy": "member2_sentence_granular",
                },
            )
        )
    return docs


def build_member2_store() -> EmbeddingStore:
    docs = _build_member2_documents()

    store = EmbeddingStore(collection_name="member2_eval", embedding_fn=_pick_embedder())
    store.add_documents(docs)
    return store


def export_member2_chunks(output_path: Path) -> Path:
    docs = _build_member2_documents()
    payload = {
        "strategy": "member2_sentence_granular",
        "chunker": "SentenceChunker(max_sentences_per_chunk=1)",
        "chunk_count": len(docs),
        "chunks": [
            {
                "id": doc.id,
                "content": doc.content,
                "metadata": doc.metadata,
                "char_len": len(doc.content),
            }
            for doc in docs
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def run_benchmark(top_k: int = 3, score_threshold: float = 0.7) -> None:
    store = build_member2_store()
    backend = getattr(store._embedding_fn, "_backend_name", "mock embeddings fallback")

    print("=== Member #2 Benchmark (Granular SentenceChunker) ===")
    print(f"Collection size: {store.get_collection_size()}")
    print(f"Embedding backend: {backend}")
    print(f"Top-k: {top_k} | Score threshold: {score_threshold}")

    no_hit_count = 0

    for i, query in enumerate(GROUP_QUERIES, start=1):
        candidates = [query]
        normalized = QUERY_NORMALIZATION.get(query)
        if normalized:
            candidates.append(normalized)

        merged: dict[str, dict] = {}
        for candidate in candidates:
            candidate_results = store.search(query=candidate, top_k=top_k, min_score=score_threshold)
            for item in candidate_results:
                record_id = item["id"]
                if record_id not in merged or item["score"] > merged[record_id]["score"]:
                    merged[record_id] = item

        results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:top_k]
        print(f"\nQ{i}: {query}")
        if not results:
            print("  - No chunk passed threshold")
            no_hit_count += 1
            continue

        for rank, item in enumerate(results, start=1):
            snippet = item["content"].replace("\n", " ")[:120]
            print(f"  {rank}. score={item['score']:.4f} | type={item['metadata'].get('content_type')} | {snippet}")

    print("\n=== Metadata filter demo (content_type=rule) ===")
    filter_query = QUERY_NORMALIZATION.get(GROUP_QUERIES[0], GROUP_QUERIES[0])
    filtered = store.search_with_filter(
        query=filter_query,
        top_k=top_k,
        metadata_filter={"content_type": "rule"},
        min_score=score_threshold,
    )
    if not filtered:
        print("  - No filtered chunk passed threshold")
    else:
        for rank, item in enumerate(filtered, start=1):
            snippet = item["content"].replace("\n", " ")[:120]
            print(f"  {rank}. score={item['score']:.4f} | {snippet}")

    print("\n=== Grounding check via agent ===")
    agent = KnowledgeBaseAgent(
        store=store,
        llm_fn=lambda prompt: "Answer generated from retrieved context only.",
        score_threshold=score_threshold,
    )
    print(agent.answer(GROUP_QUERIES[0], top_k=top_k))

    if "mock" in str(backend).lower() and no_hit_count == len(GROUP_QUERIES):
        print("\n[Info] Mock embeddings are deterministic but not semantic.")
        print("[Info] For official group scoring, rerun with EMBEDDING_PROVIDER=openai and a valid OPENAI_API_KEY.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Member #2 group evaluation (Sentence granular strategy)")
    parser.add_argument("--top-k", type=int, default=3, help="Top-k retrieval results (default: 3)")
    parser.add_argument("--threshold", type=float, default=0.7, help="Score threshold (default: 0.7)")
    parser.add_argument(
        "--export-chunks",
        action="store_true",
        help="Export all generated chunks to JSON for sharing/review",
    )
    parser.add_argument(
        "--export-path",
        type=str,
        default=str(PROJECT_ROOT / "report" / "member2_chunks.json"),
        help="Output path for exported chunk JSON",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.export_chunks:
        target = export_member2_chunks(Path(args.export_path))
        print(f"[Export] Wrote chunk file: {target}")
    run_benchmark(top_k=args.top_k, score_threshold=args.threshold)
