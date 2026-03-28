"""
Generate 1,000 order CSV files with intentional patterns A-F.
Spec: docs/DATA_GENERATION_PROMPT.md

Patterns:
  A — JP sunscreen "비건" uptrend (18% → 58%)
  B — SG sunscreen "워터프루프" steady (72-78%)
  C — JP sunscreen "톤업" downtrend (67% → 43%)
  D — JP sunscreen blue ocean segments (비건+무기자차 = 1 product, high repeat)
  E — "마이크로바이옴" emerging (0→0→0→3→8→25)
  F — Country-specific ingredient preferences in toner/serum
"""
from __future__ import annotations

import csv
import random
from datetime import date
from pathlib import Path

random.seed(42)

# ── Time ────────────────────────────────────────────────────────────────────
MONTHS: list[tuple[int, int]] = [
    (2025, 10), (2025, 11), (2025, 12),
    (2026, 1), (2026, 2), (2026, 3),
]
MONTH_TOTALS: dict[tuple[int, int], int] = {
    (2025, 10): 150, (2025, 11): 160, (2025, 12): 170,
    (2026, 1): 170, (2026, 2): 175, (2026, 3): 175,
}

# ── Geography & Platform ────────────────────────────────────────────────────
COUNTRY_RATIOS: dict[str, float] = {"KR": 0.30, "JP": 0.40, "SG": 0.30}

PLATFORM_WEIGHTS: dict[str, list[tuple[str, float]]] = {
    "KR": [("cafe24", 1.0)],
    "JP": [("cafe24", 0.4), ("qoo10", 0.6)],
    "SG": [("cafe24", 0.2), ("qoo10", 0.3), ("shopee", 0.5)],
}

TYPE_RATIOS: dict[str, dict[str, float]] = {
    "KR": {"sunscreen": 0.20, "toner": 0.25, "serum": 0.25, "cream": 0.20, "lip": 0.10},
    "JP": {"sunscreen": 0.35, "toner": 0.20, "serum": 0.20, "cream": 0.15, "lip": 0.10},
    "SG": {"sunscreen": 0.30, "toner": 0.25, "serum": 0.20, "cream": 0.15, "lip": 0.10},
}

BRANDS = ["Innisfree", "Torriden", "Roundlab", "Skinfood"]

PRICE_RANGE: dict[str, tuple[float, float]] = {
    "sunscreen": (12.0, 28.0),
    "toner": (10.0, 25.0),
    "serum": (15.0, 35.0),
    "cream": (14.0, 32.0),
    "lip": (8.0, 18.0),
}

# ── Pattern Rates ───────────────────────────────────────────────────────────
PAT_A: dict[int, float] = {10: 0.18, 11: 0.25, 12: 0.34, 1: 0.42, 2: 0.51, 3: 0.58}
PAT_B: dict[int, float] = {10: 0.74, 11: 0.76, 12: 0.73, 1: 0.77, 2: 0.75, 3: 0.72}
PAT_C: dict[int, float] = {10: 0.67, 11: 0.62, 12: 0.56, 1: 0.50, 2: 0.46, 3: 0.43}
PAT_E: dict[int, int] = {10: 0, 11: 0, 12: 0, 1: 3, 2: 8, 3: 25}
PAT_F: dict[str, dict[str, float]] = {
    "JP": {"히알루론산": 0.40, "센텔라": 0.30, "나이아신아마이드": 0.25},
    "SG": {"나이아신아마이드": 0.45, "히알루론산": 0.35, "센텔라": 0.15},
    "KR": {"센텔라": 0.35, "히알루론산": 0.30, "나이아신아마이드": 0.25},
}

# ── Sunscreen Templates ─────────────────────────────────────────────────────
SUN_BASES: dict[str, list[str]] = {
    "Innisfree": [
        "이니스프리 데일리 UV 프로텍션 크림 SPF50+ PA++++ 50ml",
        "이니스프리 인텐시브 안티폴루션 선스크린 SPF50+ PA++++ 50ml",
        "이니스프리 아쿠아 UV 프로텍션 크림 SPF50+ PA++++ 50ml",
    ],
    "Torriden": [
        "토리든 다이브인 워터리 선크림 SPF50+ PA++++ 60ml",
        "토리든 다이브인 마일드 선스크린 SPF50+ PA++++ 60ml",
    ],
    "Roundlab": [
        "라운드랩 자작나무 수분 선크림 SPF50+ PA++++ 50ml",
        "라운드랩 소나무 진정 선크림 SPF50+ PA++++ 40ml",
    ],
    "Skinfood": [
        "스킨푸드 선플라워 노세범 선 SPF50+ PA++++ 50ml",
        "스킨푸드 토마토 선 크림 SPF50+ PA++++ 40ml",
    ],
}

# Pattern D fixed products
BLUE_OCEAN = "이니스프리 아쿠아 UV 프로텍션 크림 SPF50+ PA++++ 50ml 비건 무기자차"
OPPORTUNITY: list[tuple[str, str]] = [
    ("Innisfree", "이니스프리 데일리 UV 프로텍션 크림 SPF50+ PA++++ 50ml 톤업 비건"),
    ("Torriden", "토리든 다이브인 워터리 선크림 SPF50+ PA++++ 60ml 톤업 비건"),
    ("Roundlab", "라운드랩 자작나무 수분 선크림 SPF50+ PA++++ 50ml 톤업 비건"),
]

# ── Toner/Serum Templates ───────────────────────────────────────────────────
# (name, volume, set of ingredient keywords already in name)
_T = list[tuple[str, str, set[str]]]


def _norm(s: str) -> str:
    return "센텔라" if s in ("센텔라", "시카") else s


TONER_BASES: dict[str, _T] = {
    "Innisfree": [
        ("이니스프리 그린티 씨드 히알루론산 토너", "170ml", {"히알루론산"}),
        ("이니스프리 시카 리페어 토너", "200ml", {"센텔라"}),
        ("이니스프리 그린티 밸런싱 토너", "200ml", set()),
    ],
    "Torriden": [
        ("토리든 다이브인 저분자 히알루론산 토너", "300ml", {"히알루론산"}),
        ("토리든 다이브인 클리어패드 토너", "200ml", set()),
    ],
    "Roundlab": [
        ("라운드랩 독도 토너", "300ml", set()),
        ("라운드랩 자작나무 수분 토너", "200ml", set()),
    ],
    "Skinfood": [
        ("스킨푸드 로열허니 프로폴리스 인리치드 토너", "180ml", set()),
        ("스킨푸드 캐롯 카로틴 진정 토너", "300ml", set()),
    ],
}

SERUM_BASES: dict[str, _T] = {
    "Innisfree": [
        ("이니스프리 그린티 씨드 히알루론산 세럼", "80ml", {"히알루론산"}),
        ("이니스프리 비자 시카 세럼", "50ml", {"센텔라"}),
        ("이니스프리 그린티 씨드 세럼", "80ml", set()),
    ],
    "Torriden": [
        ("토리든 다이브인 저분자 히알루론산 세럼", "50ml", {"히알루론산"}),
        ("토리든 셀마이드 세라마이드 세럼", "50ml", set()),
    ],
    "Roundlab": [
        ("라운드랩 독도 세럼", "50ml", set()),
        ("라운드랩 자작나무 수분 세럼", "50ml", set()),
    ],
    "Skinfood": [
        ("스킨푸드 로열허니 프로폴리스 인리치드 에센스", "50ml", set()),
        ("스킨푸드 캐롯 카로틴 진정 세럼", "50ml", set()),
    ],
}

# ── Cream / Lip Templates ──────────────────────────────────────────────────
CREAM_BASES: dict[str, list[str]] = {
    "Innisfree": ["이니스프리 그린티 씨드 크림 50ml", "이니스프리 한란 보습 크림 50ml"],
    "Torriden": ["토리든 다이브인 수분크림 100ml", "토리든 셀마이드 세라마이드 크림 80ml"],
    "Roundlab": ["라운드랩 자작나무 수분 크림 80ml", "라운드랩 소나무 진정 크림 80ml"],
    "Skinfood": ["스킨푸드 로열허니 프로폴리스 인리치드 크림 63ml", "스킨푸드 캐롯 카로틴 진정 크림 50ml"],
}

LIP_BASES: dict[str, list[str]] = {
    "Innisfree": ["이니스프리 비비드 코튼 잉크 틴트 4g", "이니스프리 마이 립 밤 3.5g"],
    "Torriden": ["토리든 솔리드인 세라마이드 립 에센스 11ml"],
    "Roundlab": ["라운드랩 독도 립밤 12g"],
    "Skinfood": ["스킨푸드 프레쉬 과일 립앤치크 틴트 8g", "스킨푸드 시어버터 립 케어 밤 9.5g"],
}

LIP_COLORS = [
    "#01 체리레드", "#02 로지브라운", "#03 누드피치", "#04 코랄핑크",
    "#05 플럼", "#06 베리", "#07 브릭레드", "#08 피그핑크",
    "#09 밀키코랄", "#10 로즈우드", "#11 핑크베이지", "#12 오렌지레드",
]
LIP_TEXTURES = ["매트", "글로시", "벨벳", "시어"]

MICROBIOME_TONER = "토리든 다이브인 마이크로바이옴 토너 200ml 유산균 피부장벽"
MICROBIOME_SERUM = "토리든 다이브인 마이크로바이옴 세럼 50ml 유산균 피부장벽"

EXTRA_FUNC = ["수분", "보습", "진정", "노세범", "항산화", "피부장벽"]
EXTRA_VALUE = ["저자극", "무향", "약산성"]


# ── Helpers ─────────────────────────────────────────────────────────────────

def distribute(total: int, ratios: dict[str, float]) -> dict[str, int]:
    """Split total into integers that sum exactly to total, following ratios."""
    keys = list(ratios.keys())
    raw = {k: total * ratios[k] for k in keys}
    floored = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(floored.values())
    by_frac = sorted(keys, key=lambda k: raw[k] - floored[k], reverse=True)
    for k in by_frac[:remainder]:
        floored[k] += 1
    return floored


def rand_date(year: int, month: int) -> date:
    return date(year, month, random.randint(1, 28))


def pick_platform(country: str) -> str:
    r = random.random()
    cum = 0.0
    for platform, w in PLATFORM_WEIGHTS[country]:
        cum += w
        if r < cum:
            return platform
    return PLATFORM_WEIGHTS[country][-1][0]


def qty(*, blue_ocean: bool = False) -> int:
    if blue_ocean:
        return random.choices([2, 3, 4, 5], weights=[25, 35, 25, 15], k=1)[0]
    return random.choices([1, 2, 3, 4, 5], weights=[50, 30, 12, 5, 3], k=1)[0]


def usd(ptype: str) -> float:
    lo, hi = PRICE_RANGE[ptype]
    return round(random.uniform(lo, hi), 2)


# ── Sunscreen Generation (Patterns A, B, C, D) ─────────────────────────────

def make_sunscreen_group(
    country: str, month: int, n: int,
) -> list[tuple[str, str, int, float]]:
    """Deterministically allocate n sunscreen orders to pattern segments."""
    results: list[tuple[str, str, int, float]] = []

    if country == "JP":
        n_vegan = round(n * PAT_A[month])
        n_toneup = round(n * PAT_C[month])

        # Joint: assume independence, but respect constraints
        n_both = round(n * PAT_A[month] * PAT_C[month])
        n_both = max(0, min(n_both, n_vegan, n_toneup))
        n_vegan_only = n_vegan - n_both
        n_toneup_only = n_toneup - n_both
        n_neither = n - n_both - n_vegan_only - n_toneup_only

        # Fix rounding overflow
        if n_neither < 0:
            excess = -n_neither
            n_toneup_only = max(0, n_toneup_only - excess)
            n_neither = n - n_both - n_vegan_only - n_toneup_only

        # Split vegan-only into blue-ocean vs regular
        n_blue = max(1, round(n_vegan_only * 0.4)) if n_vegan_only > 0 else 0
        n_vegan_reg = n_vegan_only - n_blue

        # ── Opportunity (비건+톤업) — 2-3 products
        for _ in range(n_both):
            brand, pname = random.choice(OPPORTUNITY)
            results.append((brand, pname, qty(), usd("sunscreen")))

        # ── Blue ocean (비건+무기자차) — 1 Innisfree product, high repeat
        for _ in range(n_blue):
            results.append(("Innisfree", BLUE_OCEAN, qty(blue_ocean=True), usd("sunscreen")))

        # ── Regular vegan (비건 only, no 톤업/무기자차)
        for _ in range(n_vegan_reg):
            brand = random.choice(BRANDS)
            base = random.choice(SUN_BASES[brand])
            suf = ["비건"]
            if random.random() < 0.3:
                suf.append(random.choice(["저자극", "수분", "진정"]))
            results.append((brand, f"{base} {' '.join(suf)}", qty(), usd("sunscreen")))

        # ── Red ocean (톤업 only, no 비건)
        for _ in range(n_toneup_only):
            brand = random.choice(BRANDS)
            base = random.choice(SUN_BASES[brand])
            suf = ["톤업"]
            if random.random() < 0.3:
                suf.append(random.choice(["노세범", "자외선차단", "수분"]))
            results.append((brand, f"{base} {' '.join(suf)}", qty(), usd("sunscreen")))

        # ── Neither
        for _ in range(n_neither):
            brand = random.choice(BRANDS)
            base = random.choice(SUN_BASES[brand])
            if random.random() < 0.3:
                results.append((brand, f"{base} {random.choice(['저자극', '수분', '진정', '노세범'])}", qty(), usd("sunscreen")))
            else:
                results.append((brand, base, qty(), usd("sunscreen")))

    elif country == "SG":
        n_wp = round(n * PAT_B[month])
        indices = list(range(n))
        random.shuffle(indices)
        wp_set = set(indices[:n_wp])

        for i in range(n):
            brand = random.choice(BRANDS)
            base = random.choice(SUN_BASES[brand])
            if i in wp_set:
                suf = ["워터프루프"]
                if random.random() < 0.2:
                    suf.append(random.choice(["노세범", "저자극", "수분"]))
                results.append((brand, f"{base} {' '.join(suf)}", qty(), usd("sunscreen")))
            else:
                if random.random() < 0.3:
                    results.append((brand, f"{base} {random.choice(['노세범', '수분', '저자극'])}", qty(), usd("sunscreen")))
                else:
                    results.append((brand, base, qty(), usd("sunscreen")))

    else:  # KR — no specific sunscreen pattern
        for _ in range(n):
            brand = random.choice(BRANDS)
            base = random.choice(SUN_BASES[brand])
            if random.random() < 0.3:
                results.append((brand, f"{base} {random.choice(['저자극', '수분', '진정', '노세범', '톤업'])}", qty(), usd("sunscreen")))
            else:
                results.append((brand, base, qty(), usd("sunscreen")))

    random.shuffle(results)
    return results


# ── Toner/Serum Generation (Patterns E, F) ──────────────────────────────────

def make_toner_serum_group(
    country: str, month: int, ptype: str, n: int, *, n_micro: int = 0,
) -> list[tuple[str, str, int, float]]:
    """Deterministically allocate ingredient keywords per Pattern F."""
    results: list[tuple[str, str, int, float]] = []

    # ── Pattern E: microbiome orders (Torriden only)
    for _ in range(n_micro):
        pname = MICROBIOME_TONER if ptype == "toner" else MICROBIOME_SERUM
        results.append(("Torriden", pname, qty(), usd(ptype)))

    n_regular = n - n_micro
    if n_regular <= 0:
        random.shuffle(results)
        return results

    # ── Pattern F: deterministic ingredient allocation
    prefs = PAT_F[country]
    ing_names = sorted(prefs.keys())

    # Build assignment matrix (rows=orders, cols=ingredients)
    matrix: list[list[bool]] = [[False] * len(ing_names) for _ in range(n_regular)]
    for j, ing in enumerate(ing_names):
        count = round(n_regular * prefs[ing])
        indices = list(range(n_regular))
        random.shuffle(indices)
        for idx in indices[:count]:
            matrix[idx][j] = True

    templates = TONER_BASES if ptype == "toner" else SERUM_BASES

    for i in range(n_regular):
        target_ings = {ing_names[j] for j in range(len(ing_names)) if matrix[i][j]}
        target_norm = {_norm(x) for x in target_ings}

        brand = random.choice(BRANDS)
        brand_tmpls = templates[brand]

        # Pick template compatible with target (existing ⊆ target)
        compat = [t for t in brand_tmpls if {_norm(x) for x in t[2]}.issubset(target_norm)]
        if not compat:
            compat = [t for t in brand_tmpls if not t[2]]
            if not compat:
                compat = brand_tmpls

        base, vol, existing = random.choice(compat)
        existing_norm = {_norm(x) for x in existing}

        parts = [f"{base} {vol}"]
        for ing in sorted(target_ings):
            if _norm(ing) not in existing_norm:
                parts.append(ing)

        # Extra functional attributes for variety
        if random.random() < 0.4:
            parts.append(random.choice(EXTRA_FUNC))

        results.append((brand, " ".join(parts), qty(), usd(ptype)))

    random.shuffle(results)
    return results


# ── Cream / Lip Generation ──────────────────────────────────────────────────

def make_cream() -> tuple[str, str, int, float]:
    brand = random.choice(BRANDS)
    base = random.choice(CREAM_BASES[brand])
    if random.random() < 0.4:
        return brand, f"{base} {random.choice(['수분', '보습', '진정', '저자극'])}", qty(), usd("cream")
    return brand, base, qty(), usd("cream")


def make_lip() -> tuple[str, str, int, float]:
    brand = random.choice(BRANDS)
    base = random.choice(LIP_BASES[brand])
    if "틴트" in base or "잉크" in base:
        color = random.choice(LIP_COLORS)
        texture = random.choice(LIP_TEXTURES)
        return brand, f"{base} {color} {texture}", qty(), usd("lip")
    return brand, base, qty(), usd("lip")


# ── Microbiome Allocation ───────────────────────────────────────────────────

def allocate_microbiome(
    month: int,
    type_allocs: dict[str, dict[str, int]],
) -> dict[tuple[str, str], int]:
    """Distribute Pattern E microbiome count across (country, ptype) groups."""
    total = PAT_E[month]
    if total == 0:
        return {}

    eligible: list[tuple[str, str, int]] = []
    for country in ("KR", "JP", "SG"):
        for ptype in ("toner", "serum"):
            n = type_allocs[country].get(ptype, 0)
            if n > 0:
                eligible.append((country, ptype, n))

    total_pool = sum(x[2] for x in eligible)
    result: dict[tuple[str, str], int] = {}
    remaining = total

    for i, (country, ptype, n) in enumerate(eligible):
        if i == len(eligible) - 1:
            alloc = remaining
        else:
            alloc = round(total * n / total_pool)
            alloc = min(alloc, remaining, n)
        if alloc > 0:
            result[(country, ptype)] = alloc
        remaining -= alloc

    return result


# ── Main Generation ─────────────────────────────────────────────────────────

def generate_all() -> list[dict]:
    all_orders: list[dict] = []

    for year, month in MONTHS:
        m = month
        total = MONTH_TOTALS[(year, month)]
        country_alloc = distribute(total, COUNTRY_RATIOS)

        type_allocs: dict[str, dict[str, int]] = {}
        for country, c_total in country_alloc.items():
            type_allocs[country] = distribute(c_total, TYPE_RATIOS[country])

        micro_alloc = allocate_microbiome(m, type_allocs)

        for country in ("KR", "JP", "SG"):
            for ptype, n in type_allocs[country].items():
                if ptype == "sunscreen":
                    group = make_sunscreen_group(country, m, n)
                elif ptype in ("toner", "serum"):
                    n_micro = micro_alloc.get((country, ptype), 0)
                    group = make_toner_serum_group(country, m, ptype, n, n_micro=n_micro)
                elif ptype == "cream":
                    group = [make_cream() for _ in range(n)]
                else:
                    group = [make_lip() for _ in range(n)]

                for brand, pname, quantity, unit_price in group:
                    all_orders.append({
                        "year": year,
                        "month": m,
                        "country": country,
                        "product_type": ptype,
                        "order_date": rand_date(year, m),
                        "platform": pick_platform(country),
                        "brand": brand,
                        "product_name": pname,
                        "quantity": quantity,
                        "unit_price_usd": f"{unit_price:.2f}",
                    })

    return all_orders


# ── CSV Output ──────────────────────────────────────────────────────────────

FIELDNAMES = [
    "order_id", "order_date", "destination_country", "brand",
    "product_name", "product_type", "quantity", "unit_price_usd",
]

PREFIXES = {"cafe24": "CF24", "qoo10": "QO10", "shopee": "SHPE"}


def write_csvs(orders: list[dict]) -> None:
    base_dir = Path(__file__).parent
    for platform in ("cafe24", "qoo10", "shopee"):
        rows = sorted(
            [o for o in orders if o["platform"] == platform],
            key=lambda r: r["order_date"],
        )
        prefix = PREFIXES[platform]
        for i, r in enumerate(rows, 1):
            r["order_id"] = f"{prefix}-{i:06d}"
            r["destination_country"] = r["country"]

        filepath = base_dir / f"orders_{platform}.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"  {filepath.name}: {len(rows)} rows")


# ── Verification ────────────────────────────────────────────────────────────

def verify(orders: list[dict]) -> None:
    print(f"\n{'='*60}")
    print("VERIFICATION REPORT")
    print(f"{'='*60}")

    print(f"\nTotal: {len(orders)} (expected 1000)")

    # Monthly
    print("\n── Monthly Counts ──")
    for (y, m), expected in MONTH_TOTALS.items():
        actual = sum(1 for o in orders if o["year"] == y and o["month"] == m)
        ok = "✓" if actual == expected else "✗"
        print(f"  {y}-{m:02d}: {actual}/{expected} {ok}")

    # Pattern A
    print("\n── Pattern A: JP sunscreen '비건' rate ──")
    for y, m in MONTHS:
        pool = [o for o in orders if o["country"] == "JP" and o["product_type"] == "sunscreen" and o["year"] == y and o["month"] == m]
        hit = [o for o in pool if "비건" in o["product_name"]]
        rate = len(hit) / len(pool) * 100 if pool else 0
        exp = PAT_A[m] * 100
        ok = "✓" if abs(rate - exp) <= 5 else "✗"
        print(f"  {y}-{m:02d}: {len(hit)}/{len(pool)} = {rate:5.1f}% (target ~{exp:.0f}%) {ok}")

    # Pattern B
    print("\n── Pattern B: SG sunscreen '워터프루프' rate ──")
    for y, m in MONTHS:
        pool = [o for o in orders if o["country"] == "SG" and o["product_type"] == "sunscreen" and o["year"] == y and o["month"] == m]
        hit = [o for o in pool if "워터프루프" in o["product_name"]]
        rate = len(hit) / len(pool) * 100 if pool else 0
        exp = PAT_B[m] * 100
        ok = "✓" if abs(rate - exp) <= 5 else "✗"
        print(f"  {y}-{m:02d}: {len(hit)}/{len(pool)} = {rate:5.1f}% (target ~{exp:.0f}%) {ok}")

    # Pattern C
    print("\n── Pattern C: JP sunscreen '톤업' rate ──")
    for y, m in MONTHS:
        pool = [o for o in orders if o["country"] == "JP" and o["product_type"] == "sunscreen" and o["year"] == y and o["month"] == m]
        hit = [o for o in pool if "톤업" in o["product_name"]]
        rate = len(hit) / len(pool) * 100 if pool else 0
        exp = PAT_C[m] * 100
        ok = "✓" if abs(rate - exp) <= 5 else "✗"
        print(f"  {y}-{m:02d}: {len(hit)}/{len(pool)} = {rate:5.1f}% (target ~{exp:.0f}%) {ok}")

    # Pattern D
    print("\n── Pattern D: JP sunscreen segments ──")
    jp_sun = [o for o in orders if o["country"] == "JP" and o["product_type"] == "sunscreen"]
    red = [o for o in jp_sun if "톤업" in o["product_name"] and "비건" not in o["product_name"]]
    blue = [o for o in jp_sun if "비건" in o["product_name"] and "무기자차" in o["product_name"]]
    opp = [o for o in jp_sun if "비건" in o["product_name"] and "톤업" in o["product_name"]]
    print(f"  Red ocean  (톤업 only):    {len(red):3d} orders, {len(set(o['product_name'] for o in red)):2d} products")
    print(f"  Blue ocean (비건+무기자차): {len(blue):3d} orders, {len(set(o['product_name'] for o in blue)):2d} product(s)")
    print(f"  Opportunity(비건+톤업):     {len(opp):3d} orders, {len(set(o['product_name'] for o in opp)):2d} products")
    if blue:
        avg_qty = sum(o["quantity"] for o in blue) / len(blue)
        print(f"  Blue ocean avg qty: {avg_qty:.1f} (expect >2)")

    # Pattern E
    print("\n── Pattern E: '마이크로바이옴' counts ──")
    for y, m in MONTHS:
        hit = [o for o in orders if o["year"] == y and o["month"] == m and "마이크로바이옴" in o["product_name"]]
        exp = PAT_E[m]
        ok = "✓" if len(hit) == exp else "✗"
        brands = set(o["brand"] for o in hit)
        print(f"  {y}-{m:02d}: {len(hit)} (expected {exp}) {ok}  brands={brands or '-'}")

    # Pattern F
    print("\n── Pattern F: Country ingredient preferences (toner+serum) ──")
    for country in ("JP", "SG", "KR"):
        pool = [o for o in orders if o["country"] == country and o["product_type"] in ("toner", "serum") and "마이크로바이옴" not in o["product_name"]]
        n_pool = len(pool)
        hyal = sum(1 for o in pool if "히알루론산" in o["product_name"] or "히알루론" in o["product_name"])
        cent = sum(1 for o in pool if "센텔라" in o["product_name"] or "시카" in o["product_name"])
        niac = sum(1 for o in pool if "나이아신아마이드" in o["product_name"])
        prefs = PAT_F[country]
        print(f"  {country} (n={n_pool}):")
        print(f"    히알루론산:       {hyal:3d}/{n_pool} = {hyal/n_pool*100:5.1f}% (target ~{prefs.get('히알루론산', 0)*100:.0f}%)")
        print(f"    센텔라/시카:      {cent:3d}/{n_pool} = {cent/n_pool*100:5.1f}% (target ~{prefs.get('센텔라', 0)*100:.0f}%)")
        print(f"    나이아신아마이드: {niac:3d}/{n_pool} = {niac/n_pool*100:5.1f}% (target ~{prefs.get('나이아신아마이드', 0)*100:.0f}%)")

    # Platform counts
    print("\n── Platform Distribution ──")
    for pf in ("cafe24", "qoo10", "shopee"):
        cnt = sum(1 for o in orders if o["platform"] == pf)
        print(f"  {pf}: {cnt}")

    print(f"\n{'='*60}")


# ── Entry Point ─────────────────────────────────────────────────────────────

def main() -> None:
    print("Generating 1,000 orders with patterns A-F...\n")
    orders = generate_all()
    write_csvs(orders)
    verify(orders)


if __name__ == "__main__":
    main()
