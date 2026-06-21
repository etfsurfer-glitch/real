"""비단지 매물(상가·사무실·빌라/연립·단독다가구) 지역단위 수집 — 격리 파이프라인.

★ 격리 원칙(절대): 기존 naverreal.sqlite / run_collect / daily_run 을 절대 열거나
  수정하지 않는다. 오직 아래 4개 별도 DB 파일에만 기록한다. (DB오염 방지)

검증된 네이버 파라미터(2026-06-21):
  /api/articles?cortarNo={동}&realEstateType=VL:YR:DDDGG:DDDGN:DGN:SMS:SG
    &tradeType=A1:B1:B2&sameAddressGroup=false   ← sameAddressGroup=false 필수(누락방지)
  - APT:OPST 미포함 → 아파트/오피 0건(이중수집 없음)
  - 응답 articleRealEstateTypeName 으로 카테고리 분기
  - realtorId 노출분만 중개사 귀속(attribution=realtor), 나머지 region

사용:
  python scripts/collect_region_listings.py --cortar 1168010100[,1150010300...]
  (cortar 미지정 시 아무것도 안 함 — 안전 기본값)
"""
from __future__ import annotations
import sys, os, sqlite3, json, argparse, datetime

sys.path.insert(0, ".")
from collector.creds import ensure_creds          # noqa: E402
from collector.http import get_json               # noqa: E402

DATA_DIR = os.environ.get("KOCZIP_DATA", "data")
# 유효 필터코드만(DDDGN·DGN은 네이버가 무시하는 노이즈 → 제외). 검증: 5코드 합 = 통합호출 총수.
# 카테고리 분할 호출 → (1) 각 호출 작아짐 (2) 상단탭 = 코드별 (3) 코드별 무결성 대조.
CODES = ["VL", "YR", "DDDGG", "SMS", "SG"]
ARTICLES_URL = "https://new.land.naver.com/api/articles"
PAGE_CAP = 3000   # 안전상한(자연정지가 먼저 멈춰야 정상). 도달하면 truncation = 무결성 위반.

# 카테고리 → (DB파일, 응답 유형명 집합, 권리금 여부)
CATEGORIES = {
    "sangga": ("listings_sangga.sqlite", {"상가점포"}, True),
    "office": ("listings_office.sqlite", {"사무실"}, False),
    "villa":  ("listings_villa.sqlite",  {"빌라/연립", "빌라단지-연립", "원룸", "다세대"}, False),
    "house":  ("listings_house.sqlite",  {"단독/다가구"}, False),
}


def _name_to_cat(name: str) -> str | None:
    """응답 유형명 → 카테고리. 정확 일치 우선, 그다음 포괄 매칭(변형 대비)."""
    name = (name or "").strip()
    for cat, (_db, names, _pr) in CATEGORIES.items():
        if name in names:
            return cat
    if any(k in name for k in ("빌라", "연립", "원룸", "다세대")):
        return "villa"
    if any(k in name for k in ("단독", "다가구")):
        return "house"
    if "상가" in name:
        return "sangga"
    if "사무" in name:
        return "office"
    return None


def _won_man(s) -> int | None:
    """네이버 가격문자열 → 만원 정수. '6,000'→6000, '1억'→10000, '1억 5,000'→15000."""
    if s is None:
        return None
    s = str(s).strip().replace(" ", "")
    if not s:
        return None
    man = 0
    if "억" in s:
        a, _, b = s.partition("억")
        man += int((a.replace(",", "") or "0")) * 10000
        s = b
    if s:
        digits = s.replace(",", "")
        if digits.isdigit():
            man += int(digits)
    return man or None


def _schema(premium: bool) -> str:
    premium_col = "premium_price INTEGER," if premium else ""
    return f"""
    CREATE TABLE IF NOT EXISTS listings(
      article_no            TEXT PRIMARY KEY,
      cortar_no             TEXT NOT NULL,
      real_estate_type      TEXT,
      real_estate_type_name TEXT,
      trade_type            TEXT,
      deal_or_warrant_price INTEGER,
      rent_price            INTEGER,
      {premium_col}
      area1_m2              REAL,
      area2_m2              REAL,
      floor_info            TEXT,
      direction             TEXT,
      building_name         TEXT,
      realtor_id            TEXT,
      realtor_name          TEXT,
      attribution           TEXT NOT NULL,
      latitude              REAL,
      longitude             REAL,
      article_confirm_ymd   TEXT,
      raw                   TEXT,
      first_seen_date       TEXT,
      snapshot_date         TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS listings_cortar_idx  ON listings(cortar_no, real_estate_type_name, trade_type);
    CREATE INDEX IF NOT EXISTS listings_realtor_idx ON listings(realtor_id);
    CREATE TABLE IF NOT EXISTS collection_log(
      cortar_no    TEXT, run_date TEXT, status TEXT, n_articles INTEGER,
      collected_at TEXT, PRIMARY KEY(cortar_no, run_date));
    """


def _open(cat: str) -> sqlite3.Connection:
    db_file, _names, premium = CATEGORIES[cat]
    path = os.path.join(DATA_DIR, db_file)
    assert "naverreal" not in db_file, "안전장치: 메인 DB 접근 금지"
    c = sqlite3.connect(path)
    c.executescript(_schema(premium))
    return c


def _fetch_code(cortar: str, code: str, creds: dict) -> tuple[list[dict], bool, int]:
    """한 동·한 코드의 매물 전수. (items, natural_stop, map_exposed) 반환.
    natural_stop=True → isMoreData=false 도달(=전수 완료). False → 캡/에러로 중단(무결성 위반)."""
    out, page, natural, map_exposed = [], 1, False, None
    while page <= PAGE_CAP:
        params = {
            "cortarNo": cortar, "realEstateType": code, "tradeType": "A1:B1:B2",
            "sameAddressGroup": "false", "page": str(page),
        }
        st, data = get_json(ARTICLES_URL, creds, params=params)
        if st != 200 or not isinstance(data, dict):
            break  # natural=False → 에러로 기록됨
        if map_exposed is None:
            map_exposed = data.get("mapExposedCount")
        out.extend(data.get("articleList") or [])
        if not data.get("isMoreData"):
            natural = True
            break
        page += 1
    return out, natural, map_exposed


def _upsert(conns: dict, cat: str, it: dict, cortar: str, today: str, has_premium: bool):
    rid = it.get("realtorId")
    cols = {
        "article_no": it.get("articleNo"),
        "cortar_no": cortar,  # 쿼리한 동(응답엔 cortarNo 없음 — 우리가 부른 지역이 곧 소속 동)
        "real_estate_type": it.get("articleRealEstateTypeCode"),
        "real_estate_type_name": it.get("articleRealEstateTypeName"),
        "trade_type": it.get("tradeTypeCode") or it.get("tradeTypeName"),
        "deal_or_warrant_price": _won_man(it.get("dealOrWarrantPrc")),
        "rent_price": _won_man(it.get("rentPrc")),
        "area1_m2": it.get("area1"),
        "area2_m2": it.get("area2"),
        "floor_info": it.get("floorInfo"),
        "direction": it.get("direction"),
        "building_name": it.get("buildingName"),
        "realtor_id": rid,
        "realtor_name": it.get("realtorName"),
        "attribution": "realtor" if rid else "region",
        "latitude": it.get("latitude"),
        "longitude": it.get("longitude"),
        "article_confirm_ymd": it.get("articleConfirmYmd"),
        "raw": json.dumps(it, ensure_ascii=False),
        "snapshot_date": today,
    }
    if has_premium:
        cols["premium_price"] = _won_man(it.get("premiumPrc"))
    keys = list(cols)
    placeholders = ",".join("?" * len(keys))
    # first_seen_date: 신규면 today, 기존이면 유지(COALESCE)
    conns[cat].execute(
        f"INSERT INTO listings({','.join(keys)},first_seen_date) VALUES({placeholders},?) "
        f"ON CONFLICT(article_no) DO UPDATE SET "
        + ",".join(f"{k}=excluded.{k}" for k in keys if k != "article_no"),
        [cols[k] for k in keys] + [today],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cortar", default="", help="동 cortarNo (쉼표구분). 미지정시 무동작(안전)")
    args = ap.parse_args()
    cortars = [c.strip() for c in args.cortar.split(",") if c.strip()]
    if not cortars:
        print("cortar 미지정 — 안전상 아무것도 안 함. --cortar 1168010100 처럼 지정.")
        return
    today = datetime.date.today().isoformat()
    creds = ensure_creds()
    conns = {cat: _open(cat) for cat in CATEGORIES}
    try:
        for cortar in cortars:
            per_cat = {c: 0 for c in CATEGORIES}
            attr = {"realtor": 0, "region": 0}
            integrity_ok = True       # 모든 코드가 자연정지(전수) 했는가
            seen = set()              # 코드간 중복 article 방지(혹시 모를 경계 중복)
            for code in CODES:        # ★카테고리 분할 호출 — 각 작아짐 + 코드별 무결성
                items, natural, _mx = _fetch_code(cortar, code, creds)
                if not natural:
                    integrity_ok = False   # 캡/에러로 중단 → 전수 실패
                for it in items:
                    an = it.get("articleNo")
                    if not an or an in seen:
                        continue
                    seen.add(an)
                    cat = _name_to_cat(it.get("articleRealEstateTypeName"))
                    if not cat:
                        continue
                    _upsert(conns, cat, it, cortar, today, CATEGORIES[cat][2])
                    per_cat[cat] += 1
                    attr["realtor" if it.get("realtorId") else "region"] += 1
            status = "success" if integrity_ok else "partial"   # ★무결성 플래그
            for cat, n in per_cat.items():
                conns[cat].execute(
                    "INSERT INTO collection_log(cortar_no,run_date,status,n_articles,collected_at) "
                    "VALUES(?,?,?,?,?) ON CONFLICT(cortar_no,run_date) DO UPDATE SET "
                    "status=excluded.status,n_articles=excluded.n_articles,collected_at=excluded.collected_at",
                    (cortar, today, status, n, datetime.datetime.now().isoformat(timespec="seconds")))
            for c in conns.values():
                c.commit()
            print(f"[{cortar}] 총 {len(seen)} → {per_cat} | 귀속 R{attr['realtor']}/Reg{attr['region']} | 무결성={status}")
    finally:
        for c in conns.values():
            c.close()
    print("완료. 기록 DB:", ", ".join(os.path.join(DATA_DIR, CATEGORIES[c][0]) for c in CATEGORIES))


if __name__ == "__main__":
    main()
