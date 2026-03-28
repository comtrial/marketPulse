"""ChromaDB vector store for gold example retrieval.

Few-Shot의 핵심 인프라:
  1. 입력 상품명 → e5-large 임베딩 → ChromaDB 유사도 검색
  2. 단순 유사도가 아닌, 유사도 + 속성 풍부도 가중 점수로 정렬

왜 속성 풍부도를 가중하는가:
  유사도 0.88인데 속성 3개인 사례보다,
  유사도 0.85인데 속성 8개인 사례가 더 좋은 few-shot 예시.
  속성이 풍부한 예시를 보여줘야 LLM이 더 많은 속성을 추출하게 됨.

임베딩 모델:
  intfloat/multilingual-e5-large (1024차원)
  - 한국어/일본어/영어 다국어 지원
  - e5 계열은 "query: " 접두사를 붙여야 검색 성능이 최적화됨

ChromaDB:
  PersistentClient — 로컬 디스크에 인덱스를 영구 저장
  cosine similarity — 정규화된 임베딩이므로 cosine이 적합
"""

import json
from pathlib import Path

import chromadb
import structlog
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger()

E5_MODEL_NAME = "intfloat/multilingual-e5-large"
COLLECTION_NAME = "gold_examples"


class VectorStore:
    """Gold Example 벡터 스토어.

    사용 흐름:
      1. build_index() — gold_examples JSON → 임베딩 → ChromaDB 저장 (초기 1회)
      2. search() — 입력 상품명 → top-K gold example 반환 (추출 시 매번)
      3. add_example() — 새 gold example 개별 추가 (승격 시)
    """

    def __init__(self, persist_dir: str, model_name: str = E5_MODEL_NAME):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = SentenceTransformer(model_name)
        logger.info(
            "vector_store_initialized",
            persist_dir=persist_dir,
            model=model_name,
            count=self.collection.count(),
        )

    def _embed(self, text: str) -> list[float]:
        """텍스트를 e5-large 임베딩 벡터로 변환.

        e5 계열은 "query: " 접두사를 붙여야 검색 성능이 최적화됨.
        normalize_embeddings=True → cosine similarity와 동일한 결과.
        """
        vec = self.embedder.encode(
            f"query: {text}", normalize_embeddings=True
        )
        return vec.tolist()

    def add_example(
        self,
        gold_id: str,
        raw_input: str,
        extracted_output: dict,
        metadata: dict | None = None,
    ) -> None:
        """개별 gold example을 벡터 스토어에 추가.

        documents에 raw_input + extracted_output을 JSON으로 저장해서
        검색 시 원본 텍스트와 정답 추출 결과를 함께 반환할 수 있게 함.
        """
        embedding = self._embed(raw_input)
        doc = json.dumps(
            {"raw_input": raw_input, "extracted_output": extracted_output},
            ensure_ascii=False,
        )
        self.collection.add(
            ids=[gold_id],
            embeddings=[embedding],
            documents=[doc],
            metadatas=[metadata or {}],
        )

    def search(
        self,
        text: str,
        top_k: int = 3,
        min_similarity: float = 0.70,
    ) -> list[dict]:
        """입력 상품명과 유사한 gold example을 검색.

        검색 과정:
          1. top_k * 3개의 후보를 ChromaDB에서 가져옴 (넉넉히)
          2. min_similarity 미만인 후보 필터링
          3. combined_score = similarity×0.7 + richness×0.3 으로 재정렬
          4. 상위 top_k개 반환

        반환값 각 항목:
          - gold_id: gold example ID
          - raw_input: 원본 상품명
          - extracted_output: 정답 추출 결과 (few-shot에 주입됨)
          - similarity: cosine 유사도 (0~1)
          - attr_count: 추출된 속성 개수 (풍부도)
          - combined_score: 가중 점수
        """
        if self.collection.count() == 0:
            return []

        embedding = self._embed(text)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k * 3, self.collection.count()),
        )

        candidates = []
        for i, doc_str in enumerate(results["documents"][0]):
            doc = json.loads(doc_str)
            # ChromaDB는 distance를 반환 → similarity = 1 - distance
            similarity = 1 - results["distances"][0][i]

            if similarity < min_similarity:
                continue

            output = doc["extracted_output"]
            # 속성 풍부도 계산: 채워진 필드가 많을수록 좋은 few-shot 예시
            attr_count = (
                len(output.get("keyIngredients", []))
                + len(output.get("functionalClaims", []))
                + len(output.get("valueClaims", []))
                + (1 if output.get("spf") else 0)
                + (1 if output.get("volume") else 0)
                + (1 if output.get("skinType") else 0)
                + len(output.get("additionalAttrs", {}))
            )

            # 가중 점수: 유사도 70% + 풍부도 30% (풍부도는 10개 기준 정규화)
            combined = similarity * 0.7 + min(attr_count / 10.0, 1.0) * 0.3
            candidates.append(
                {
                    "gold_id": results["ids"][0][i],
                    "raw_input": doc["raw_input"],
                    "extracted_output": output,
                    "similarity": similarity,
                    "attr_count": attr_count,
                    "combined_score": combined,
                }
            )

        # combined_score 내림차순 정렬 후 top_k개 반환
        candidates.sort(key=lambda x: x["combined_score"], reverse=True)
        return candidates[:top_k]

    def build_index(self, gold_examples_path: str | Path) -> int:
        """gold_examples JSON 파일에서 전체 인덱스를 빌드.

        기존 인덱스를 완전히 초기화하고 새로 빌드한다.
        초기 시드 시 1회 실행. 이후 add_example()로 개별 추가.

        Returns:
            인덱싱된 gold example 수
        """
        path = Path(gold_examples_path)
        with open(path) as f:
            examples = json.load(f)

        # 기존 컬렉션 초기화 (멱등성 보장)
        existing_ids = self.collection.get()["ids"]
        if existing_ids:
            self.collection.delete(ids=existing_ids)

        for ex in examples:
            self.add_example(
                gold_id=ex["gold_id"],
                raw_input=ex["raw_input"],
                extracted_output=ex["extracted_output"],
                metadata={
                    "product_type": ex.get("product_type", ""),
                    "brand": ex.get("brand", ""),
                },
            )

        count = self.collection.count()
        logger.info("index_built", count=count, source=str(path))
        return count
