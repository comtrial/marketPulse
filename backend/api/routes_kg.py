"""KG 직접 조회 API — Neo4j 지식 그래프에 직접 접근.

오케스트레이터를 거치지 않고 인과 체인, 성분 트렌딩 등을 직접 조회할 때 사용.
"""

from fastapi import APIRouter, Depends

from mcp_servers.kg_server import KnowledgeGraphServer

router = APIRouter(prefix="/api/v1/kg", tags=["knowledge-graph"])

_kg_server: KnowledgeGraphServer | None = None


def get_kg_server() -> KnowledgeGraphServer:
    if _kg_server is None:
        raise RuntimeError("KnowledgeGraphServer not initialized.")
    return _kg_server


def init_kg_server(server: KnowledgeGraphServer) -> None:
    global _kg_server
    _kg_server = server


@router.get("/causal-chain/{country}")
def causal_chain(
    country: str,
    server: KnowledgeGraphServer = Depends(get_kg_server),
):
    """인과 체인 조회: 기후→피부고민→기능 수요."""
    return server.query_causal_chain({"country_code": country})


@router.get("/trending/{country}")
def trending_ingredients(
    country: str,
    product_type: str | None = None,
    top_k: int = 5,
    server: KnowledgeGraphServer = Depends(get_kg_server),
):
    """성분 트렌딩: 국가별 성분 등장 빈도."""
    params = {"country_code": country, "top_k": top_k}
    if product_type:
        params["product_type"] = product_type
    return server.find_trending_ingredients(params)


@router.get("/product/{product_id}")
def product_graph(
    product_id: str,
    server: KnowledgeGraphServer = Depends(get_kg_server),
):
    """상품 그래프: 성분, 기능, 국가, 플랫폼 관계."""
    return server.get_product_graph({"product_id": product_id})
