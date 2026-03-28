"""
Generate order CSV data for 3 platforms: Cafe24, Qoo10, Shopee.
Follows the constraints in docs/prompt_generate_orders.md.
"""

import csv
import random
import os
from datetime import date, timedelta

random.seed(42)

# ─── Constants ───────────────────────────────────────────────────────────────

BRANDS = [
    "이니스프리", "토리든", "라운드랩", "스킨푸드", "코스알엑스",
    "닥터지", "아누아", "메디힐", "비플레인", "달바",
]

PRODUCT_TYPES = ["sunscreen", "toner", "serum", "cream", "lip"]

PRICE_RANGES = {
    "sunscreen": (12.00, 28.00),
    "toner":     (12.00, 22.00),
    "serum":     (18.00, 35.00),
    "cream":     (18.00, 32.00),
    "lip":       (7.00,  15.00),
}

# product_type distribution baseline (will be adjusted by season)
TYPE_WEIGHTS_BASE = {
    "sunscreen": 0.30,
    "toner":     0.22,
    "serum":     0.22,
    "cream":     0.16,
    "lip":       0.10,
}

# Platform → country weights
PLATFORM_COUNTRY_WEIGHTS = {
    "cafe24": {"KR": 0.30, "JP": 0.50, "SG": 0.20},
    "qoo10":  {"JP": 0.70, "SG": 0.30},
    "shopee": {"SG": 1.00},
}

# Date range
START_DATE = date(2025, 10, 1)
END_DATE   = date(2026, 3, 25)
TOTAL_DAYS = (END_DATE - START_DATE).days + 1  # inclusive

# ─── Product Name Templates ──────────────────────────────────────────────────

PRODUCT_NAMES = {
    "sunscreen": [
        "{brand} 데일리 UV 디펜스 선크림 SPF50+ PA++++ 50ml",
        "{brand} 워터리 선 에센스 SPF50+ PA++++ 50ml",
        "{brand} 에어리 UV 에센스 SPF50+ PA++++ 60ml",
        "{brand} 무기자차 마일드 선크림 SPF50+ PA++++ 50ml",
        "{brand} 톤업 UV 쉴드 선크림 SPF50+ 35ml",
        "{brand} 비건 선 세럼 SPF50+ PA++++ 40ml",
        "{brand} 시카 수딩 선 로션 SPF50+ PA++++ 50ml",
        "{brand} 글루타치온 톤업 선크림 SPF50+ 50ml",
        "[리뉴얼] {brand} 퍼펙트 UV 프로텍션 크림 SPF50+ 50ml",
        "[1+1] {brand} 선크림 SPF50+ PA++++ 50ml 더블기획",
        "{brand} 노세범 선 젤크림 SPF50+ PA++++ 50ml",
        "{brand} 히알루론 워터핏 선크림 SPF50+ PA++++ 50ml",
        "{brand} 미니 선크림 SPF50+ PA++++ 25ml",
        "{brand} 프레쉬 칼라민 선스틱 SPF50+ 22g",
        "[대용량] {brand} 워터리 선크림 SPF50+ PA++++ 100ml",
        "{brand} 알로에 수딩 선크림 SPF50+ PA++++ 50ml",
        "{brand} 그린티 UV 프로텍션 선크림 SPF50+ 50ml",
        "{brand} 센텔라 마일드 선크림 SPF50+ PA++++ 60ml",
    ],
    "toner": [
        "{brand} 쌀겨 브라이트닝 토너 150ml",
        "{brand} 히알루론산 수분 토너 200ml",
        "{brand} 독도 토너 200ml",
        "{brand} 자작나무 수액 토너 300ml",
        "{brand} 어성초 진정 토너 200ml",
        "[대용량] {brand} 약산성 클렌징 토너 500ml",
        "{brand} 녹차 밸런싱 토너 200ml",
        "{brand} BHA 블랙헤드 파워 리퀴드 100ml",
        "{brand} AHA/BHA 클래리파잉 트리트먼트 토너 150ml",
        "{brand} 프로폴리스 시너지 토너 150ml",
        "{brand} 비타민C 브라이트닝 토너 200ml",
        "{brand} 쌀 브라이트닝 클리어 토너 150ml",
        "{brand} 약산성 녹차 토너 150ml",
        "[리뉴얼] {brand} 자작나무 수분 토너 200ml",
        "{brand} 어성초 77 수딩 토너 250ml",
    ],
    "serum": [
        "{brand} 비타민C 세럼 30ml",
        "{brand} 레티놀 인텐시브 앰플 30ml",
        "{brand} 히알루론산 수분 앰플 50ml",
        "{brand} 프로폴리스 라이트 앰플 30ml",
        "{brand} 나이아신아마이드 10 세럼 30ml",
        "[1+1] {brand} 비타민C 세럼 더블기획 30ml x2",
        "{brand} 센텔라 앰플 50ml",
        "{brand} 머시룸 바이탈 세럼 40ml",
        "{brand} 쌀겨 브라이트닝 에센스 30ml",
        "{brand} 펩타이드 탄력 세럼 30ml",
        "{brand} 스네일 뮤신 96 에센스 100ml",
        "{brand} 콜라겐 부스팅 세럼 40ml",
        "{brand} 달바 화이트 트러플 퍼스트 스프레이 세럼 100ml",
        "[리뉴얼] {brand} 갈락토미세스 에센스 100ml",
        "{brand} AHA BHA PHA 30 데이즈 미라클 세럼 50ml",
    ],
    "cream": [
        "{brand} 시카 밤 크림 50ml",
        "{brand} 히알루론산 수분 크림 50ml",
        "{brand} 리치 모이스처 크림 60ml",
        "{brand} 어드밴스드 스네일 92 올인원 크림 100ml",
        "{brand} 달팽이 리페어 크림 50ml",
        "[기획세트] {brand} 수분 크림 + 토너 세트",
        "{brand} 콜라겐 탄력 크림 50ml",
        "{brand} 자작나무 수분 크림 50ml",
        "{brand} 녹차 수분 진정 크림 50ml",
        "{brand} 병풀 리커버리 크림 50ml",
        "{brand} 비건 그린티 카밍 크림 50ml",
        "[대용량] {brand} 수딩 젤 크림 100ml",
        "{brand} 세라마이드 배리어 크림 50ml",
        "{brand} 프로바이오틱스 수분 크림 50ml",
    ],
    "lip": [
        "{brand} 컬러 립밤 3.2g",
        "{brand} 글로시 립 오일 4ml",
        "{brand} 립 슬리핑 마스크 20g",
        "{brand} 매트 립스틱 3.5g",
        "{brand} 립 세럼 10ml",
        "[1+1] {brand} 립밤 기획세트 3.2g x2",
        "{brand} 틴티드 립밤 3.5g",
        "{brand} 벨벳 틴트 4.5g",
        "{brand} 허니 립 마스크 15g",
        "{brand} 비건 립 버터 10g",
    ],
}


def get_seasonal_type_weights(month: int) -> dict[str, float]:
    """Return adjusted product type weights based on month."""
    w = dict(TYPE_WEIGHTS_BASE)

    if month in (10, 11):
        # Oct-Nov: cream/serum heavy (winter prep)
        w["cream"]     += 0.06
        w["serum"]     += 0.04
        w["sunscreen"] -= 0.08
        w["lip"]       -= 0.02

    elif month in (12, 1):
        # Dec-Jan: sunscreen low, moisturizing up, lip/gift up in Dec
        w["sunscreen"] -= 0.12
        w["cream"]     += 0.05
        w["toner"]     += 0.03
        if month == 12:
            w["lip"]   += 0.04

    elif month in (2, 3):
        # Feb-Mar: sunscreen surge
        w["sunscreen"] += 0.12
        w["cream"]     -= 0.06
        w["serum"]     -= 0.04
        w["lip"]       -= 0.02

    # Normalize
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def get_seasonal_country_bias_jp(month: int) -> float:
    """Extra multiplier for JP sunscreen in Feb-Mar."""
    if month in (2, 3):
        return 1.3  # JP sunscreen is especially heavy in spring
    return 1.0


def weighted_choice(options: dict[str, float]) -> str:
    """Pick a key from a dict of {option: weight}."""
    keys = list(options.keys())
    weights = [options[k] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


def generate_quantity() -> int:
    """Quantity 1-5, heavily skewed toward 1-2."""
    return random.choices([1, 2, 3, 4, 5], weights=[50, 30, 12, 5, 3], k=1)[0]


def generate_price(product_type: str) -> float:
    lo, hi = PRICE_RANGES[product_type]
    return round(random.uniform(lo, hi), 2)


def pick_product_name(brand: str, product_type: str) -> str:
    templates = PRODUCT_NAMES[product_type]
    template = random.choice(templates)
    return template.format(brand=brand)


def generate_date_for_month(year: int, month: int) -> date:
    """Generate a random date within the given year/month, clamped to our range."""
    if month == 2:
        last_day = 28
    elif month in (4, 6, 9, 11):
        last_day = 30
    else:
        last_day = 31
    day = random.randint(1, last_day)
    d = date(year, month, day)
    # Clamp to our range
    if d < START_DATE:
        d = START_DATE
    if d > END_DATE:
        d = END_DATE
    return d


def distribute_orders_by_month(total: int) -> list[tuple[int, int]]:
    """
    Distribute `total` orders across the 6 months (Oct 2025 - Mar 2026).
    Returns list of (year, month) tuples, one per order.
    Slight monthly variation for realism.
    """
    months = [
        (2025, 10), (2025, 11), (2025, 12),
        (2026, 1),  (2026, 2),  (2026, 3),
    ]
    # Rough monthly weights (Feb-Mar slightly higher due to spring rush)
    month_weights = [0.15, 0.15, 0.16, 0.15, 0.19, 0.20]

    assignments = []
    remaining = total
    for i, (y, m) in enumerate(months):
        if i == len(months) - 1:
            count = remaining
        else:
            count = int(total * month_weights[i])
            # add small noise
            count = max(1, count + random.randint(-3, 3))
        remaining -= count
        for _ in range(count):
            assignments.append((y, m))

    random.shuffle(assignments)
    return assignments[:total]


def generate_orders_for_platform(
    platform: str,
    prefix: str,
    total: int,
    country_weights: dict[str, float],
) -> list[dict]:
    """Generate all orders for a single platform."""
    rows = []
    month_assignments = distribute_orders_by_month(total)

    for idx, (year, month) in enumerate(month_assignments, start=1):
        order_id = f"{prefix}-{idx:04d}"
        order_date = generate_date_for_month(year, month)

        # Pick country
        country = weighted_choice(country_weights)

        # Pick product type with seasonal adjustment
        type_weights = get_seasonal_type_weights(month)

        # JP sunscreen bias in Feb-Mar
        if country == "JP" and month in (2, 3):
            type_weights["sunscreen"] *= get_seasonal_country_bias_jp(month)
            total_w = sum(type_weights.values())
            type_weights = {k: v / total_w for k, v in type_weights.items()}

        product_type = weighted_choice(type_weights)
        brand = random.choice(BRANDS)
        product_name = pick_product_name(brand, product_type)
        quantity = generate_quantity()
        unit_price = generate_price(product_type)

        rows.append({
            "order_id": order_id,
            "order_date": order_date.isoformat(),
            "destination_country": country,
            "brand": brand,
            "product_name": product_name,
            "product_type": product_type,
            "quantity": quantity,
            "unit_price_usd": f"{unit_price:.2f}",
        })

    # Sort by order_date for readability, then reassign order_ids sequentially
    rows.sort(key=lambda r: r["order_date"])
    for i, row in enumerate(rows, start=1):
        row["order_id"] = f"{prefix}-{i:04d}"

    return rows


def write_csv(filepath: str, rows: list[dict]) -> None:
    fieldnames = [
        "order_id", "order_date", "destination_country", "brand",
        "product_name", "product_type", "quantity", "unit_price_usd",
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} rows → {filepath}")


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))

    platforms = [
        ("cafe24", "C24",  400, PLATFORM_COUNTRY_WEIGHTS["cafe24"]),
        ("qoo10",  "Q10",  350, PLATFORM_COUNTRY_WEIGHTS["qoo10"]),
        ("shopee", "SHP",  250, PLATFORM_COUNTRY_WEIGHTS["shopee"]),
    ]

    for name, prefix, total, cw in platforms:
        print(f"Generating {name} ({total} rows)...")
        rows = generate_orders_for_platform(name, prefix, total, cw)
        filepath = os.path.join(base_dir, f"orders_{name}.csv")
        write_csv(filepath, rows)

    print("Done. Total: 1,000 rows across 3 files.")


if __name__ == "__main__":
    main()
