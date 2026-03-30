"""
Generate 2,000 order CSV files with intentional patterns A-J.
Spec: docs/DATA_GENERATION_PROMPT.md + docs/scenario/DOC-08C-TEST-SCENARIOS.md

Patterns (existing):
  A — JP sunscreen "비건" uptrend (18% → 58%)
  B — SG sunscreen "워터프루프" steady (72-78%)
  C — JP sunscreen "톤업" downtrend (67% → 43%)
  E — "마이크로바이옴" emerging (0→0→0→3→8→25)
  F — Country-specific ingredient preferences in toner/serum

Patterns (new — DOC-08C):
  G — JP sunscreen 비건+무기자차 synergy (lift ≈ 1.54)
  H — JP sunscreen 비건↑ 톤업↓ temporal correlation ≈ -0.99 (auto from A+C)
  I — KR sunscreen 수분 60% vs SG sunscreen 수분 35% (cross-market gap)
  J — JP serum 비건 uptrend (8% → 30%)

Old Pattern D (blue ocean = 1 Innisfree product) is subsumed by Pattern G:
  비건+무기자차 now appears across all brands (not restricted to Innisfree).
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
    (2025, 10): 300, (2025, 11): 320, (2025, 12): 340,
    (2026, 1): 340, (2026, 2): 350, (2026, 3): 350,
}  # Total: 2000

# ── Geography & Platform ────────────────────────────────────────────────────
COUNTRY_RATIOS: dict[str, float] = {"KR": 0.30, "JP": 0.40, "SG": 0.30}

PLATFORM_WEIGHTS: dict[str, list[tuple[str, float]]] = {
    "KR": [("cafe24", 1.0)],
    "JP": [("cafe24", 0.4), ("qoo10", 0.6)],
    "SG": [("cafe24", 0.2), ("qoo10", 0.3), ("shopee", 0.5)],
}

# Type ratios: lip ≥ 12% for KR/JP (min 10/month), SG lip intentionally sparse
TYPE_RATIOS: dict[str, dict[str, float]] = {
    "KR": {"sunscreen": 0.20, "toner": 0.24, "serum": 0.24, "cream": 0.20, "lip": 0.12},
    "JP": {"sunscreen": 0.33, "toner": 0.20, "serum": 0.20, "cream": 0.16, "lip": 0.11},
    "SG": {"sunscreen": 0.28, "toner": 0.23, "serum": 0.20, "cream": 0.28, "lip": 0.01},
    # SG lip: intentional gap — ~8 orders total (조건 1)
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
# A: JP sunscreen 비건 monthly rate
PAT_A: dict[int, float] = {10: 0.18, 11: 0.25, 12: 0.34, 1: 0.42, 2: 0.51, 3: 0.58}
# B: SG sunscreen 워터프루프 monthly rate
PAT_B: dict[int, float] = {10: 0.74, 11: 0.76, 12: 0.73, 1: 0.77, 2: 0.75, 3: 0.72}
# C: JP sunscreen 톤업 monthly rate
PAT_C: dict[int, float] = {10: 0.67, 11: 0.62, 12: 0.56, 1: 0.50, 2: 0.46, 3: 0.43}
# E: 마이크로바이옴 absolute counts per month (not scaled)
PAT_E: dict[int, int] = {10: 0, 11: 0, 12: 0, 1: 3, 2: 8, 3: 25}
# F: Country ingredient preferences for toner/serum
PAT_F: dict[str, dict[str, float]] = {
    "JP": {"히알루론산": 0.40, "센텔라": 0.30, "나이아신아마이드": 0.25},
    "SG": {"나이아신아마이드": 0.45, "히알루론산": 0.35, "센텔라": 0.15},
    "KR": {"센텔라": 0.35, "히알루론산": 0.30, "나이아신아마이드": 0.25},
}
# G: JP sunscreen 무기자차 overall = 47%, lift with 비건 = 1.54
PAT_G_MINERAL = 0.47
PAT_G_P_MINERAL_GIVEN_VEGAN = 0.47 * 1.54  # ≈ 0.7238
# I: KR/SG sunscreen 수분 rate (adjusted for ~12.5% base template "수분" incidence)
#    effective = 0.875 × suffix_rate + 0.125
#    KR target 60%: suffix_rate = (0.60 - 0.125) / 0.875 = 0.543
#    SG target 35%: suffix_rate = (0.35 - 0.125) / 0.875 = 0.257
PAT_I: dict[str, float] = {"KR": 0.543, "SG": 0.257}
PAT_I_TARGET: dict[str, float] = {"KR": 0.60, "SG": 0.35}  # real targets for verification
# J: JP serum 비건 monthly rate
PAT_J: dict[int, float] = {10: 0.08, 11: 0.10, 12: 0.13, 1: 0.18, 2: 0.24, 3: 0.30}

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

# ── Toner/Serum Templates ───────────────────────────────────────────────────
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
    "Roundlab": ["라운드랩 독도 모이스처 립밤 12g"],
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

EXTRA_FUNC = ["보습", "진정", "노세범", "항산화", "피부장벽"]


# ── Helpers ─────────────────────────────────────────────────────────────────

def distribute(total: int, ratios: dict[str, float]) -> dict[str, int]:
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


def qty(*, high: bool = False) -> int:
    if high:
        return random.choices([2, 3, 4, 5], weights=[25, 35, 25, 15], k=1)[0]
    return random.choices([1, 2, 3, 4, 5], weights=[50, 30, 12, 5, 3], k=1)[0]


def usd(ptype: str) -> float:
    lo, hi = PRICE_RANGE[ptype]
    return round(random.uniform(lo, hi), 2)


def _sun_name(brand: str, suffixes: list[str]) -> str:
    base = random.choice(SUN_BASES[brand])
    if suffixes:
        return f"{base} {' '.join(suffixes)}"
    return base


# ── Sunscreen: JP (Patterns A, C, G) ────────────────────────────────────────

def make_sunscreen_jp(month: int, n: int) -> list[tuple[str, str, int, float]]:
    """JP sunscreen with 비건(A), 톤업(C), 무기자차(G) attributes."""
    n_vegan = round(n * PAT_A[month])
    n_toneup = round(n * PAT_C[month])

    # Pattern G: 무기자차 conditional on 비건
    n_min_in_vegan = round(n_vegan * PAT_G_P_MINERAL_GIVEN_VEGAN)
    n_min_in_vegan = min(n_min_in_vegan, n_vegan)
    n_mineral_total = round(n * PAT_G_MINERAL)
    n_min_in_not_vegan = max(0, min(n_mineral_total - n_min_in_vegan, n - n_vegan))

    # Assign attributes per slot
    slots = list(range(n))
    random.shuffle(slots)
    vegan_set = set(slots[:n_vegan])

    random.shuffle(slots)
    toneup_set = set(slots[:n_toneup])

    vegan_list = [i for i in range(n) if i in vegan_set]
    not_vegan_list = [i for i in range(n) if i not in vegan_set]
    random.shuffle(vegan_list)
    random.shuffle(not_vegan_list)
    mineral_set = set(vegan_list[:n_min_in_vegan]) | set(not_vegan_list[:n_min_in_not_vegan])

    results: list[tuple[str, str, int, float]] = []
    for i in range(n):
        brand = random.choice(BRANDS)
        suf: list[str] = []
        if i in toneup_set:
            suf.append("톤업")
        if i in vegan_set:
            suf.append("비건")
        if i in mineral_set:
            suf.append("무기자차")
        # Extra flavor for plain orders
        if not suf and random.random() < 0.3:
            suf.append(random.choice(["저자극", "수분", "진정", "노세범"]))

        is_high = (i in vegan_set and i in mineral_set)
        results.append((brand, _sun_name(brand, suf), qty(high=is_high), usd("sunscreen")))

    random.shuffle(results)
    return results


# ── Sunscreen: SG (Patterns B, I) ───────────────────────────────────────────

def make_sunscreen_sg(month: int, n: int) -> list[tuple[str, str, int, float]]:
    """SG sunscreen with 워터프루프(B) and 수분(I)."""
    n_wp = round(n * PAT_B[month])
    n_moisture = round(n * PAT_I["SG"])

    slots = list(range(n))
    random.shuffle(slots)
    wp_set = set(slots[:n_wp])
    random.shuffle(slots)
    moisture_set = set(slots[:n_moisture])

    results: list[tuple[str, str, int, float]] = []
    for i in range(n):
        brand = random.choice(BRANDS)
        suf: list[str] = []
        if i in wp_set:
            suf.append("워터프루프")
        if i in moisture_set:
            suf.append("수분")
        if not suf and random.random() < 0.2:
            suf.append(random.choice(["노세범", "저자극"]))
        results.append((brand, _sun_name(brand, suf), qty(), usd("sunscreen")))

    random.shuffle(results)
    return results


# ── Sunscreen: KR (Pattern I) ───────────────────────────────────────────────

def make_sunscreen_kr(month: int, n: int) -> list[tuple[str, str, int, float]]:
    """KR sunscreen with 수분(I) = 60%."""
    n_moisture = round(n * PAT_I["KR"])
    slots = list(range(n))
    random.shuffle(slots)
    moisture_set = set(slots[:n_moisture])

    results: list[tuple[str, str, int, float]] = []
    for i in range(n):
        brand = random.choice(BRANDS)
        suf: list[str] = []
        if i in moisture_set:
            suf.append("수분")
        if random.random() < 0.25:
            suf.append(random.choice(["저자극", "진정", "노세범", "톤업"]))
        results.append((brand, _sun_name(brand, suf), qty(), usd("sunscreen")))

    random.shuffle(results)
    return results


# ── Toner/Serum (Patterns E, F, J) ──────────────────────────────────────────

def make_toner_serum_group(
    country: str, month: int, ptype: str, n: int,
    *, n_micro: int = 0, vegan_rate: float = 0.0,
) -> list[tuple[str, str, int, float]]:
    results: list[tuple[str, str, int, float]] = []

    # Pattern E: microbiome
    for _ in range(n_micro):
        pname = MICROBIOME_TONER if ptype == "toner" else MICROBIOME_SERUM
        results.append(("Torriden", pname, qty(), usd(ptype)))

    n_regular = n - n_micro
    if n_regular <= 0:
        random.shuffle(results)
        return results

    # Pattern J: JP serum 비건 (deterministic count)
    n_vegan = round(n_regular * vegan_rate) if vegan_rate > 0 else 0
    vegan_slots = set()
    if n_vegan > 0:
        idxs = list(range(n_regular))
        random.shuffle(idxs)
        vegan_slots = set(idxs[:n_vegan])

    # Pattern F: ingredient allocation
    prefs = PAT_F[country]
    ing_names = sorted(prefs.keys())
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

        # Pattern J: add 비건 suffix
        if i in vegan_slots:
            parts.append("비건")

        if random.random() < 0.35:
            parts.append(random.choice(EXTRA_FUNC))

        results.append((brand, " ".join(parts), qty(), usd(ptype)))

    random.shuffle(results)
    return results


# ── Cream / Lip ──────────────────────────────────────────────────────────────

def make_cream() -> tuple[str, str, int, float]:
    brand = random.choice(BRANDS)
    base = random.choice(CREAM_BASES[brand])
    if random.random() < 0.4:
        return brand, f"{base} {random.choice(['수분', '보습', '진정', '저자극'])}", qty(), usd("cream")
    return brand, base, qty(), usd("cream")


def make_lip(*, bare: bool = False) -> tuple[str, str, int, float]:
    """bare=True: 속성 없는 상품명만 생성 (조건 2: KR lip 속성 단조)."""
    brand = random.choice(BRANDS)
    base = random.choice(LIP_BASES[brand])
    if bare:
        # No color, no texture — just the base product name
        return brand, base, qty(), usd("lip")
    if "틴트" in base or "잉크" in base:
        color = random.choice(LIP_COLORS)
        texture = random.choice(LIP_TEXTURES)
        return brand, f"{base} {color} {texture}", qty(), usd("lip")
    return brand, base, qty(), usd("lip")


# ── Microbiome Allocation ───────────────────────────────────────────────────

def allocate_microbiome(
    month: int, type_allocs: dict[str, dict[str, int]],
) -> dict[tuple[str, str], int]:
    total = PAT_E[month]
    if total == 0:
        return {}
    eligible = []
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
                    if country == "JP":
                        group = make_sunscreen_jp(m, n)
                    elif country == "SG":
                        group = make_sunscreen_sg(m, n)
                    else:
                        group = make_sunscreen_kr(m, n)
                elif ptype in ("toner", "serum"):
                    n_micro = micro_alloc.get((country, ptype), 0)
                    # Pattern J: JP serum 비건 rate
                    vr = PAT_J[m] if (country == "JP" and ptype == "serum") else 0.0
                    group = make_toner_serum_group(
                        country, m, ptype, n, n_micro=n_micro, vegan_rate=vr,
                    )
                elif ptype == "cream":
                    group = [make_cream() for _ in range(n)]
                else:  # lip
                    # 조건 2: KR lip은 bare(속성 없음) — 속성 단조 공백
                    is_bare = (country == "KR")
                    group = [make_lip(bare=is_bare) for _ in range(n)]

                for brand, pname, quantity, unit_price in group:
                    all_orders.append({
                        "year": year, "month": m, "country": country,
                        "product_type": ptype,
                        "order_date": rand_date(year, m),
                        "platform": pick_platform(country),
                        "brand": brand, "product_name": pname,
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
    total = len(orders)
    expected_total = sum(MONTH_TOTALS.values())
    print(f"\n{'='*70}")
    print(f"VERIFICATION REPORT — Total: {total} (expected {expected_total})")
    print(f"{'='*70}")

    # Monthly
    print("\n── Monthly Counts ──")
    for (y, m), exp in MONTH_TOTALS.items():
        act = sum(1 for o in orders if o["year"] == y and o["month"] == m)
        print(f"  {y}-{m:02d}: {act}/{exp} {'✓' if act == exp else '✗'}")

    # Min 10 per combo (제약 5) — SG lip is intentional gap (조건 1)
    print("\n── 제약 5: Min 10 per country×type×month (SG lip 제외) ──")
    violations = 0
    sg_lip_total = 0
    for y, m in MONTHS:
        for c in ("KR", "JP", "SG"):
            for t in ("sunscreen", "toner", "serum", "cream", "lip"):
                cnt = sum(1 for o in orders if o["year"] == y and o["month"] == m and o["country"] == c and o["product_type"] == t)
                if c == "SG" and t == "lip":
                    sg_lip_total += cnt
                    continue  # intentional gap
                if cnt < 10:
                    print(f"  ✗ {y}-{m:02d} {c} {t}: {cnt} < 10")
                    violations += 1
    print(f"  {'✓ All ≥ 10 (SG lip 제외)' if violations == 0 else f'✗ {violations} violations'}")
    print(f"  SG lip total: {sg_lip_total} (intentional gap, target ≤ 8)")

    # Pattern A
    print("\n── Pattern A: JP sunscreen '비건' rate ──")
    for y, m in MONTHS:
        pool = [o for o in orders if o["country"] == "JP" and o["product_type"] == "sunscreen" and o["year"] == y and o["month"] == m]
        hit = sum(1 for o in pool if "비건" in o["product_name"])
        rate = hit / len(pool) * 100 if pool else 0
        exp = PAT_A[m] * 100
        print(f"  {y}-{m:02d}: {hit}/{len(pool)} = {rate:5.1f}% (target ~{exp:.0f}%) {'✓' if abs(rate - exp) <= 5 else '✗'}")

    # Pattern B
    print("\n── Pattern B: SG sunscreen '워터프루프' rate ──")
    for y, m in MONTHS:
        pool = [o for o in orders if o["country"] == "SG" and o["product_type"] == "sunscreen" and o["year"] == y and o["month"] == m]
        hit = sum(1 for o in pool if "워터프루프" in o["product_name"])
        rate = hit / len(pool) * 100 if pool else 0
        exp = PAT_B[m] * 100
        print(f"  {y}-{m:02d}: {hit}/{len(pool)} = {rate:5.1f}% (target ~{exp:.0f}%) {'✓' if abs(rate - exp) <= 5 else '✗'}")

    # Pattern C
    print("\n── Pattern C: JP sunscreen '톤업' rate ──")
    for y, m in MONTHS:
        pool = [o for o in orders if o["country"] == "JP" and o["product_type"] == "sunscreen" and o["year"] == y and o["month"] == m]
        hit = sum(1 for o in pool if "톤업" in o["product_name"])
        rate = hit / len(pool) * 100 if pool else 0
        exp = PAT_C[m] * 100
        print(f"  {y}-{m:02d}: {hit}/{len(pool)} = {rate:5.1f}% (target ~{exp:.0f}%) {'✓' if abs(rate - exp) <= 5 else '✗'}")

    # Pattern E
    print("\n── Pattern E: '마이크로바이옴' counts ──")
    for y, m in MONTHS:
        hit = [o for o in orders if o["year"] == y and o["month"] == m and "마이크로바이옴" in o["product_name"]]
        exp = PAT_E[m]
        print(f"  {y}-{m:02d}: {len(hit)} (expected {exp}) {'✓' if len(hit) == exp else '✗'}  brands={set(o['brand'] for o in hit) or '-'}")

    # Pattern F
    print("\n── Pattern F: Country ingredient preferences (toner+serum) ──")
    for country in ("JP", "SG", "KR"):
        pool = [o for o in orders if o["country"] == country and o["product_type"] in ("toner", "serum") and "마이크로바이옴" not in o["product_name"]]
        np_ = len(pool)
        if np_ == 0:
            continue
        hyal = sum(1 for o in pool if "히알루론" in o["product_name"])
        cent = sum(1 for o in pool if "센텔라" in o["product_name"] or "시카" in o["product_name"])
        niac = sum(1 for o in pool if "나이아신아마이드" in o["product_name"])
        prefs = PAT_F[country]
        print(f"  {country} (n={np_}):")
        print(f"    히알루론산:       {hyal:3d}/{np_} = {hyal/np_*100:5.1f}% (target ~{prefs.get('히알루론산',0)*100:.0f}%)")
        print(f"    센텔라/시카:      {cent:3d}/{np_} = {cent/np_*100:5.1f}% (target ~{prefs.get('센텔라',0)*100:.0f}%)")
        print(f"    나이아신아마이드: {niac:3d}/{np_} = {niac/np_*100:5.1f}% (target ~{prefs.get('나이아신아마이드',0)*100:.0f}%)")

    # Pattern G: lift
    print("\n── Pattern G: JP sunscreen 비건+무기자차 synergy ──")
    jp_sun = [o for o in orders if o["country"] == "JP" and o["product_type"] == "sunscreen"]
    n_jp = len(jp_sun)
    n_v = sum(1 for o in jp_sun if "비건" in o["product_name"])
    n_m = sum(1 for o in jp_sun if "무기자차" in o["product_name"])
    n_vm = sum(1 for o in jp_sun if "비건" in o["product_name"] and "무기자차" in o["product_name"])
    p_v, p_m, p_vm = n_v / n_jp, n_m / n_jp, n_vm / n_jp
    lift = p_vm / (p_v * p_m) if (p_v * p_m) > 0 else 0
    print(f"  JP sunscreen total: {n_jp}")
    print(f"  비건: {n_v}/{n_jp} = {p_v*100:.1f}% (avg)")
    print(f"  무기자차: {n_m}/{n_jp} = {p_m*100:.1f}% (target ~47%)")
    print(f"  비건∩무기자차: {n_vm}/{n_jp} = {p_vm*100:.1f}%")
    print(f"  lift = {lift:.2f} (target ~1.54) {'✓' if abs(lift - 1.54) < 0.15 else '✗'}")

    # Pattern H: temporal correlation
    print("\n── Pattern H: 비건↑ 톤업↓ temporal correlation ──")
    vegan_rates, toneup_rates = [], []
    for y, m in MONTHS:
        pool = [o for o in orders if o["country"] == "JP" and o["product_type"] == "sunscreen" and o["year"] == y and o["month"] == m]
        if not pool:
            continue
        vegan_rates.append(sum(1 for o in pool if "비건" in o["product_name"]) / len(pool))
        toneup_rates.append(sum(1 for o in pool if "톤업" in o["product_name"]) / len(pool))
    if len(vegan_rates) >= 2:
        n_ = len(vegan_rates)
        mv = sum(vegan_rates) / n_
        mt = sum(toneup_rates) / n_
        cov = sum((v - mv) * (t - mt) for v, t in zip(vegan_rates, toneup_rates)) / n_
        sv = (sum((v - mv) ** 2 for v in vegan_rates) / n_) ** 0.5
        st = (sum((t - mt) ** 2 for t in toneup_rates) / n_) ** 0.5
        corr = cov / (sv * st) if sv * st > 0 else 0
        print(f"  Pearson r = {corr:.3f} (target ≈ -0.99) {'✓' if corr < -0.95 else '✗'}")

    # Pattern I: KR vs SG 수분
    print("\n── Pattern I: KR vs SG sunscreen '수분' gap ──")
    for c in ("KR", "SG"):
        pool = [o for o in orders if o["country"] == c and o["product_type"] == "sunscreen"]
        hit = sum(1 for o in pool if "수분" in o["product_name"])
        rate = hit / len(pool) * 100 if pool else 0
        exp = PAT_I_TARGET.get(c, 0) * 100
        print(f"  {c}: {hit}/{len(pool)} = {rate:.1f}% (target ~{exp:.0f}%) {'✓' if abs(rate - exp) <= 7 else '✗'}")

    # Pattern J: JP serum 비건
    print("\n── Pattern J: JP serum '비건' uptrend ──")
    for y, m in MONTHS:
        pool = [o for o in orders if o["country"] == "JP" and o["product_type"] == "serum" and o["year"] == y and o["month"] == m]
        hit = sum(1 for o in pool if "비건" in o["product_name"])
        rate = hit / len(pool) * 100 if pool else 0
        exp = PAT_J[m] * 100
        print(f"  {y}-{m:02d}: {hit}/{len(pool)} = {rate:5.1f}% (target ~{exp:.0f}%) {'✓' if abs(rate - exp) <= 7 else '✗'}")

    # Coverage gaps (조건 1, 2)
    print("\n── Coverage Gaps (intentional) ──")
    # 조건 1: SG lip ≤ 8
    sg_lip = [o for o in orders if o["country"] == "SG" and o["product_type"] == "lip"]
    print(f"  조건1 SG lip: {len(sg_lip)} orders (target ≤ 8) {'✓' if len(sg_lip) <= 8 else '✗'}")

    # 조건 2: KR lip — functionalClaims/valueClaims 키워드 없어야 함
    kr_lip = [o for o in orders if o["country"] == "KR" and o["product_type"] == "lip"]
    attr_keywords = ["수분", "보습", "진정", "톤업", "노세범", "항산화", "피부장벽",
                     "비건", "저자극", "무향", "약산성", "워터프루프", "대용량"]
    kr_lip_with_attrs = sum(1 for o in kr_lip if any(kw in o["product_name"] for kw in attr_keywords))
    print(f"  조건2 KR lip 속성 포함: {kr_lip_with_attrs}/{len(kr_lip)} (target 0) {'✓' if kr_lip_with_attrs == 0 else '✗'}")

    # Platform & brand consistency
    print("\n── Consistency ──")
    brands = set(o["brand"] for o in orders)
    print(f"  Brands: {sorted(brands)} {'✓' if brands == set(BRANDS) else '✗'}")
    for pf in ("cafe24", "qoo10", "shopee"):
        cnt = sum(1 for o in orders if o["platform"] == pf)
        print(f"  {pf}: {cnt}")

    print(f"\n{'='*70}")


# ── Entry Point ─────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Generating {sum(MONTH_TOTALS.values())} orders with patterns A-J...\n")
    orders = generate_all()
    write_csvs(orders)
    verify(orders)


if __name__ == "__main__":
    main()
