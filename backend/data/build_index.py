"""ChromaDB 벡터 인덱스 빌드 스크립트.

gold_examples JSON → e5-large 임베딩 → ChromaDB PersistentClient 저장.
시드 후 1회 실행. 이후 gold example 추가 시 재실행.

Usage:
    cd backend && python -m data.build_index
    cd backend && python -m data.build_index --verify
"""

import argparse
from pathlib import Path

from core.config import settings
from extraction.vector_store import VectorStore

DATA_DIR = Path(__file__).parent
GOLD_EXAMPLES_PATH = DATA_DIR / "seed_gold_examples.json"


def build() -> None:
    store = VectorStore(persist_dir=settings.chroma_persist_dir)
    count = store.build_index(GOLD_EXAMPLES_PATH)
    print(f"Indexed {count} gold examples")


def verify() -> None:
    store = VectorStore(persist_dir=settings.chroma_persist_dir)

    test_queries = [
        "토리든 다이브인 무기자차 선크림 SPF50+ PA++++ 60ml 비건",
        "라운드랩 독도 토너 200ml 약산성",
        "이니스프리 비비드 코튼 잉크 틴트 4g #09 코랄",
    ]

    for query in test_queries:
        results = store.search(query, top_k=3)
        print(f"\n입력: {query[:40]}...")
        for r in results:
            print(
                f"  [{r['gold_id']}] sim={r['similarity']:.3f} "
                f"combined={r['combined_score']:.3f} "
                f"attrs={r['attr_count']}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        verify()
    else:
        build()
        verify()
