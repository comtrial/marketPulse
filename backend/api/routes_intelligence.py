"""인텔리전스 API — 히트맵, 트렌드 데이터 직접 조회.

LLM 오케스트레이터를 거치지 않고 데이터를 직접 가져올 때 사용.
프론트엔드 히트맵/차트 초기 로딩 등.
"""

from fastapi import APIRouter, Depends

from mcp_servers.order_server import OrderDataServer

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

_order_server: OrderDataServer | None = None


def get_order_server() -> OrderDataServer:
    if _order_server is None:
        raise RuntimeError("OrderDataServer not initialized.")
    return _order_server


def init_order_server(server: OrderDataServer) -> None:
    global _order_server
    _order_server = server


@router.get("/heatmap")
def get_heatmap(
    type: str,
    start: str,
    end: str,
    server: OrderDataServer = Depends(get_order_server),
):
    """국가별 속성 히트맵.

    params:
      type: sunscreen, toner, serum, cream, lip
      start: YYYY-MM (예: 2025-10)
      end: YYYY-MM (예: 2026-03)
    """
    return server.get_country_attribute_heatmap({
        "product_type": type,
        "period_start": start,
        "period_end": end,
    })


@router.get("/trend")
def get_trend(
    attribute: str,
    type: str,
    countries: str,
    months: int = 6,
    server: OrderDataServer = Depends(get_order_server),
):
    """속성 시계열 트렌드.

    params:
      attribute: 비건, 톤업, 워터프루프, 히알루론산 등
      type: functional, value, ingredient
      countries: 콤마 구분 (예: JP,SG)
      months: 기간 (기본 6)
    """
    country_list = [c.strip() for c in countries.split(",")]
    return server.get_attribute_trend({
        "attribute_name": attribute,
        "attribute_type": type,
        "countries": country_list,
        "months": months,
    })
