"""콕집매물 동기화 — 수집 DB(읽기만) → data/kok.sqlite(콕집매물 자체 DB), 한 방향.

콕집매물(중개사 연동분)은 더 이상 요청 때마다 수집 DB를 조인하지 않는다. 이 잡이
① 동의한 사무소(kok_realtor_optin.active=1)의 광고 중 매물을 listings_current 에서 읽어 kok_listings 에 upsert 하고
② 이번에 안 보인 매물은 지우지 않고 status='closed' 로 표시하며(거래 이력으로 남김)
③ 동의를 해제한 사무소의 매물도 closed 로 돌리고
④ 상세(방·욕실·입주·공급/전용 보정·융자·위반건축물)는 볼 때가 아니라 여기서 받아 저장한다(한 번 받은 건 7일 유지).
콕집 기준 필드(콕집 등록일 = 동의일과 광고 첫 관측일 중 늦은 쪽, 전용률)도 여기서 계산한다.
광고 쪽 문구(설명·특징·태그·관리비 신고)는 옮기지 않는다 — 사진·설명·키워드는 등록자가 콕집에 직접 쓴다(kok_realtor_extras).

실행: python scripts/kok_sync.py              전체(daily_run step 11f)
      python scripts/kok_sync.py --realtor R  한 사무소만(라운지 동의 직후)
      python scripts/kok_sync.py --migrate    reviews.sqlite 의 kok_* 표를 kok.sqlite 로 옮김(비어 있을 때 한 번)
수집 DB·수집기는 손대지 않는다(mode=ro).
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from collector.config import settings  # noqa: E402

DB_PATH = Path(settings.local_db_path)
KOK_DB = DB_PATH.parent / "kok.sqlite"
REVIEWS_DB = DB_PATH.parent / "reviews.sqlite"
DETAIL_PER_RUN = int(os.environ.get("KOK_DETAIL_PER_RUN", "400"))   # 한 번에 받을 상세 수(사무소가 늘면 올린다)
DETAIL_TTL_DAYS = 7

SCHEMA = """
CREATE TABLE IF NOT EXISTS kok_realtor_optin(
  realtor_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, terms_version TEXT, active INTEGER DEFAULT 1,
  agreed_at TEXT DEFAULT (datetime('now','+9 hours')), updated_at TEXT DEFAULT (datetime('now','+9 hours')));
CREATE TABLE IF NOT EXISTS kok_owner_listings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, phone TEXT, owner_name TEXT,
  complex_no TEXT NOT NULL, complex_name TEXT, dong TEXT, ho TEXT, address TEXT,
  trade TEXT NOT NULL, price INTEGER, rent INTEGER, area_name TEXT, excl_m2 REAL, floor INTEGER, total_floor INTEGER,
  floor_consent INTEGER DEFAULT 1, direction TEXT, move_in TEXT, mgmt_fee INTEGER, feature TEXT, detail TEXT,
  contact_mode TEXT DEFAULT 'kok', photos TEXT, owner_verified INTEGER DEFAULT 0, iros_check_id INTEGER, iros_pin TEXT,
  status TEXT DEFAULT 'active', view_count INTEGER DEFAULT 0, report_count INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now','+9 hours')), updated_at TEXT DEFAULT (datetime('now','+9 hours')),
  expires_at TEXT, keywords TEXT);
CREATE INDEX IF NOT EXISTS kok_owner_cx ON kok_owner_listings(complex_no, status);
CREATE TABLE IF NOT EXISTS kok_inquiries(
  id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL, from_user TEXT, from_phone TEXT, message TEXT,
  created_at TEXT DEFAULT (datetime('now','+9 hours')));
CREATE TABLE IF NOT EXISTS kok_gongsi_cache(complex_no TEXT, year INTEGER, pnu TEXT, units TEXT,
  fetched_at TEXT DEFAULT (datetime('now','+9 hours')), PRIMARY KEY(complex_no, year));
-- 중개사 연동 콕집매물(실체). 광고 문구는 없고 표시 정보 + 콕집 기준 필드만.
CREATE TABLE IF NOT EXISTS kok_listings(
  article_no TEXT PRIMARY KEY, realtor_id TEXT NOT NULL, realtor_name TEXT,
  complex_no TEXT NOT NULL, complex_name TEXT, dong TEXT, lat REAL, lng REAL,
  trade TEXT NOT NULL, price INTEGER, rent INTEGER, area_name TEXT, supply_m2 REAL, excl_m2 REAL, floor INTEGER, direction TEXT,
  rooms TEXT, baths TEXT, move_in TEXT, finance_price INTEGER, violation TEXT,
  first_seen TEXT, kok_since TEXT, status TEXT DEFAULT 'active', closed_at TEXT,
  detail_fetched_at TEXT, synced_at TEXT, floor_label TEXT, total_floor INTEGER, direction_base TEXT, mgmt_fee INTEGER, mgmt_type TEXT, mgmt_items TEXT,
  publish_state TEXT, hold_reasons TEXT, created_at TEXT DEFAULT (datetime('now','+9 hours')), updated_at TEXT DEFAULT (datetime('now','+9 hours')));
CREATE INDEX IF NOT EXISTS kok_listings_cx ON kok_listings(complex_no, status);
CREATE INDEX IF NOT EXISTS kok_listings_rt ON kok_listings(realtor_id, status);
CREATE INDEX IF NOT EXISTS kok_listings_geo ON kok_listings(status, lat, lng);
-- 등록자(중개사)가 콕집에 직접 쓴 것 — 사진(우리 저장소)·설명·키워드
CREATE TABLE IF NOT EXISTS kok_realtor_extras(
  article_no TEXT PRIMARY KEY, realtor_id TEXT NOT NULL, user_id TEXT, photos TEXT, description TEXT, keywords TEXT,
  updated_at TEXT DEFAULT (datetime('now','+9 hours')));
-- 중개사가 콕집에만 올리는 매물(광고와 무관, 모든 유형). 단지형은 complex_no, 비단지는 주소+좌표
CREATE TABLE IF NOT EXISTS kok_direct_listings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, realtor_id TEXT NOT NULL, user_id TEXT,
  ptype TEXT NOT NULL, complex_no TEXT, complex_name TEXT, address TEXT, dong TEXT, ho TEXT, lat REAL, lng REAL, cortar_no TEXT,
  trade TEXT NOT NULL, price INTEGER, rent INTEGER, area_name TEXT, supply_m2 REAL, excl_m2 REAL, land_m2 REAL,
  floor INTEGER, total_floor INTEGER, direction TEXT, move_in TEXT, mgmt_fee INTEGER, rooms TEXT, baths TEXT,
  photos TEXT, description TEXT, keywords TEXT, status TEXT DEFAULT 'active', closed_at TEXT,
  created_at TEXT DEFAULT (datetime('now','+9 hours')), updated_at TEXT DEFAULT (datetime('now','+9 hours')), expires_at TEXT, direction_base TEXT, mgmt_items TEXT, approve_ymd TEXT, parking TEXT, land_use TEXT, publish_state TEXT, hold_reasons TEXT);
CREATE INDEX IF NOT EXISTS kok_direct_rt ON kok_direct_listings(realtor_id, status);
CREATE INDEX IF NOT EXISTS kok_direct_geo ON kok_direct_listings(status, lat, lng);
CREATE INDEX IF NOT EXISTS kok_direct_cx ON kok_direct_listings(complex_no, status);
-- 비단지 전환분(1단계: 빌라·단독). 지역 수집 DB(listings_{villa,house}.sqlite, 읽기만)에서 동의 사무소 광고만.
-- 단지형 kok_listings 와 따로 둔다 — 공개 화면 쿼리(단지·지도)에 섞이지 않게. 오픈 전이라 어떤 공개 API 도 이 표를 읽지 않는다.
CREATE TABLE IF NOT EXISTS kok_region_listings(
  article_no TEXT PRIMARY KEY, realtor_id TEXT NOT NULL, realtor_name TEXT, src TEXT NOT NULL, ptype TEXT NOT NULL, type_name TEXT,
  cortar_no TEXT, lat REAL, lng REAL, building_name TEXT, address TEXT, address_mode TEXT, pnu TEXT, bld_use TEXT,
  trade TEXT NOT NULL, price INTEGER, rent INTEGER, supply_m2 REAL, excl_m2 REAL, floor INTEGER, floor_label TEXT, total_floor INTEGER,
  direction TEXT, direction_base TEXT, rooms TEXT, baths TEXT, move_in TEXT, mgmt_fee INTEGER, mgmt_type TEXT,
  approve_ymd TEXT, parking TEXT, violation TEXT, first_seen TEXT, kok_since TEXT, status TEXT DEFAULT 'active', closed_at TEXT,
  detail_fetched_at TEXT, audit_viol TEXT, audit_at TEXT, admin_hold TEXT, publish_state TEXT, hold_reasons TEXT, synced_at TEXT,
  created_at TEXT DEFAULT (datetime('now','+9 hours')), updated_at TEXT DEFAULT (datetime('now','+9 hours')));
CREATE INDEX IF NOT EXISTS kok_region_rt ON kok_region_listings(realtor_id, status);
CREATE TABLE IF NOT EXISTS kok_reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, lid TEXT NOT NULL, reason TEXT NOT NULL, detail TEXT, user_id TEXT, ip_hash TEXT,
  status TEXT DEFAULT 'open', created_at TEXT DEFAULT (datetime('now','+9 hours')));
CREATE INDEX IF NOT EXISTS kok_reports_lid ON kok_reports(lid);
-- 변경 이력: lid = R{article_no} | D{id} | K{id}. 가격·상태(거래완료·재등록·만료) 변경을 남긴다(허위매물 방지·소비자 공개)
CREATE TABLE IF NOT EXISTS kok_change_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, lid TEXT NOT NULL, field TEXT NOT NULL, old TEXT, new TEXT,
  at TEXT DEFAULT (datetime('now','+9 hours')));
CREATE INDEX IF NOT EXISTS kok_change_lid ON kok_change_log(lid, id);
CREATE TABLE IF NOT EXISTS kok_sync_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ran_at TEXT DEFAULT (datetime('now','+9 hours')), scope TEXT,
  realtors INTEGER, upserted INTEGER, closed INTEGER, details INTEGER, seconds REAL, note TEXT);
"""


def price_key(trade, price, rent) -> str:
    """변경 이력에 남길 가격 문자열(원 단위 그대로) — 'A1:950000000' / 'B2:10000000/500000'."""
    return f"{trade or ''}:{int(price or 0)}" + (f"/{int(rent or 0)}" if trade == "B2" else "")


def log_change(k, lid: str, field: str, old, new) -> None:
    k.execute("INSERT INTO kok_change_log(lid, field, old, new) VALUES(?,?,?,?)", (lid, field, None if old is None else str(old), None if new is None else str(new)))


def kok_db() -> sqlite3.Connection:
    c = sqlite3.connect(KOK_DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(SCHEMA)
    for tbl, col, typ in (("kok_owner_listings", "keywords", "TEXT"), ("kok_listings", "floor_label", "TEXT"), ("kok_listings", "total_floor", "INTEGER"),
                          ("kok_listings", "direction_base", "TEXT"), ("kok_listings", "mgmt_fee", "INTEGER"), ("kok_listings", "mgmt_type", "TEXT"), ("kok_listings", "mgmt_items", "TEXT"),
                          ("kok_direct_listings", "direction_base", "TEXT"), ("kok_direct_listings", "mgmt_items", "TEXT"), ("kok_direct_listings", "approve_ymd", "TEXT"),
                          ("kok_direct_listings", "parking", "TEXT"), ("kok_direct_listings", "land_use", "TEXT"),
                          ("kok_listings", "publish_state", "TEXT"), ("kok_listings", "hold_reasons", "TEXT"),
                          ("kok_direct_listings", "publish_state", "TEXT"), ("kok_direct_listings", "hold_reasons", "TEXT"),
                          ("kok_direct_listings", "mgmt_type", "TEXT"),
                          ("kok_listings", "admin_hold", "TEXT"), ("kok_direct_listings", "admin_hold", "TEXT"),
                          ("kok_direct_listings", "violation", "TEXT"),
                          ("kok_listings", "audit_viol", "TEXT"), ("kok_listings", "audit_at", "TEXT"),
                          ("kok_region_listings", "land_m2", "REAL"), ("kok_region_listings", "land_use", "TEXT"), ("kok_region_listings", "land_use_ledger", "TEXT"), ("kok_region_listings", "land_m2_ledger", "REAL"),
                          ("kok_region_listings", "land_price", "INTEGER")):
        if col not in {r[1] for r in c.execute(f"PRAGMA table_info({tbl})")}:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
    c.commit()
    return c


def main_db() -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=60)
    c.row_factory = sqlite3.Row
    return c


def migrate() -> None:
    """reviews.sqlite 에 남아 있는 kok_* 표를 kok.sqlite 로 옮긴다(목적지 표가 비어 있을 때만)."""
    if not REVIEWS_DB.exists():
        print("reviews.sqlite 없음"); return
    src = sqlite3.connect(f"file:{REVIEWS_DB}?mode=ro", uri=True)
    with kok_db() as k:
        for t in ("kok_realtor_optin", "kok_owner_listings", "kok_inquiries", "kok_gongsi_cache"):
            if not src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone():
                print(t, "원본 없음"); continue
            if k.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]:
                print(t, "목적지에 이미 있음 — 건너뜀"); continue
            cols = [r[1] for r in src.execute(f"PRAGMA table_info({t})")]
            rows = src.execute(f"SELECT {','.join(cols)} FROM {t}").fetchall()
            k.executemany(f"INSERT INTO {t}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", rows)
            print(t, len(rows), "행 옮김")
        k.commit()


def _int_or_none(v) -> int | None:
    try:
        return int(float(v)) if str(v).strip() not in ("", "None") else None
    except (TypeError, ValueError):
        return None


# ── 게시 게이트: 표시·광고 필수 항목이 비면 공개 화면에 내보내지 않는다(게시 전) ─────────
COMPLEX_PTYPES = {"APT", "OPST", "ABYG", "OBYG", "JGC"}
HOUSING = {"APT", "OPST", "ABYG", "OBYG", "JGC", "VL", "DDDGG", "OR"}
FLOORED = {"APT", "OPST", "ABYG", "OBYG", "JGC", "VL", "OR", "SG", "SMS", "GM", "GJCG", "APTHGJ"}
# 그 밖의 건축물(상가·사무실·건물·공장·지식산업센터): 방향은 주출입구 기준으로 필수, 관리비는 표시하지 않아도 된다,
# 층은 정확한 층(고·중·저는 주택에서 의뢰인이 요청할 때만). 법 기준 정리: design/kok_listings/비단지_전환_계획.md 1절.
NONRES = {"SG", "SMS", "GM", "GJCG", "APTHGJ"}
# 분양권(아파트·오피스텔): 준공 전이라 관리비·사용승인일은 아직 없다(해당 없음). 층·방향·방·욕실·입주 예정은 표시 대상.
# 2026-11-12 이전엔 OBYG 가 위 집합에 없어 검사 없이 공개됐고, ABYG 는 관리비 없음으로 전부 보류됐다.
PRESALE = {"ABYG", "OBYG"}
MGMT_REQUIRED = HOUSING - PRESALE          # 관리비 표시 의무: 주택·준주택(분양권 제외). '관리비 없음'(mgmt_type none)도 표시로 본다
HOLD_LABEL = {"price": "가격", "rent": "월세", "area": "면적", "floor": "층", "total_floor": "총 층수", "direction": "방향", "rooms": "방 수", "baths": "욕실 수",
              "move_in": "입주 가능일", "mgmt": "관리비", "approve": "사용승인일", "parking": "주차대수", "land_use": "지목", "address": "소재지",
              "dong": "동(건물 번호)", "report": "신고 확인 중(콕집 운영자 보류)",
              "audit_pending": "광고 점검 전(다음 동기화에서 점검)",
              "land_unverified": "지목(필지를 확인하지 못함 — 여러 필지를 묶었거나 위치가 필지 대표점이 아님)",
              "jibun": "지번(공동주택은 지번까지 표시해야 해요 — 원 광고에서 지번을 숨김)"}
AUDIT_PREFIX = "audit:"   # hold_reasons 에 'audit:항목 — 사유' 로 들어간다. 라벨은 hold_label() 이 붙인다


def hold_label(code: str) -> str:
    if code.startswith(AUDIT_PREFIX):
        return "광고 점검 위반(원 광고를 고쳐야 전환) — " + code[len(AUDIT_PREFIX):]
    return HOLD_LABEL.get(code, code)


# ── 전환 차단: 원 광고가 우리 매물 점검(collector/listing_audit.py) 기준으로 '위반'이면 전환하지 않는다 ──
# 주의(권장·조건부)는 막지 않는다 — 명백한 위반만. 판정은 원 광고 값으로만 하고, 등록자가 콕집에서 고친 값으로는 풀리지 않는다
# (원 광고를 고치면 다음 동기화에서 다시 점검해 풀린다. 위반 매물은 상세를 매일 다시 받는다).
def audit_source_ad(raw: dict, lrow: dict | None, complex_name: str | None) -> list[str]:
    from collector.article_detail import extract_checklist_fields
    from collector.listing_audit import audit_listing, is_saengsuk
    det = extract_checklist_fields(raw)
    r = lrow or {}
    f = {
        "article_no": r.get("article_no"), "real_estate_type": r.get("real_estate_type"),
        "realestate_type_name": det.get("realestate_type") or r.get("real_estate_type_name"),
        "trade_type": det.get("trade_type") or r.get("trade_type"), "floor_info": det.get("floor_info") or r.get("floor_info"),
        "area_exclusive": r.get("area2_m2"), "price": r.get("deal_or_warrant_price"), "rent_price": r.get("rent_price"),
        "building_name": det.get("building_name") or r.get("building_name"), "dong_name": r.get("dong_name"), "detail_address": r.get("detail_address"),
        "is_saengsuk": is_saengsuk(complex_name), "total_floor": det.get("total_floor"),
        "movein_type": det.get("movein_type"), "movein_negotiable": det.get("movein_negotiable"), "movein_ymd": det.get("movein_ymd"),
        "finance_price": det.get("finance_price"), "room_count": det.get("room_count"), "bathroom_count": det.get("bathroom_count"),
        "use_approve_ymd": det.get("use_approve_ymd"), "parking_count": det.get("parking_count"), "parking_possible": det.get("parking_possible"),
        "monthly_management_cost": det.get("monthly_management_cost"), "admin_cost_info": det.get("admin_cost_info"),
        "violation_building": det.get("violation_building"), "unregistered_building": det.get("unregistered_building"),
        "direction": det.get("direction") or r.get("direction"), "direction_base": det.get("direction_base"),
        "corresponding_floor": det.get("corresponding_floor"),
    }
    return violations(audit_listing(f, cp_autofilled=True))   # 단지형 — 면적·총층·사용승인·주차는 단지 정보 자동입력


def violations(res: dict) -> list[str]:
    """점검 결과에서 '위반'만 → ['항목: 짧은 사유', ...]. '주의'는 전환을 막지 않는다."""
    out = []
    for x in res.get("findings") or []:
        if x.get("status") != "위반":
            continue
        why = str(x.get("reason") or "").split(" — ")[0].split(". ")[0].strip()
        out.append(f"{x['item']}" + (f": {why[:60]}" if why else ""))
    return out


def publish_check(r: dict, ptype: str, *, kapt_ok: bool = False, source: str = "converted", n_buildings: int | None = None,
                  cx_facts: dict | None = None) -> list[str]:
    """빠진 필수 항목 코드 목록. 비면 게시 가능. 전환분 아파트는 K-apt 실제 관리비가 있으면 관리비 표시로 본다."""
    miss: list[str] = []
    try:
        miss += [AUDIT_PREFIX + v for v in json.loads(r.get("audit_viol") or "[]")]
    except (TypeError, ValueError):
        pass
    if r.get("admin_hold"):   # 허위매물 신고를 운영자가 보류한 매물 — 다시 계산해도 풀리지 않는다(관리자가 '보류 풀기'로만)
        miss.append("report")
    if not r.get("price"):
        miss.append("price")
    if r.get("trade") == "B2" and not r.get("rent"):
        miss.append("rent")
    if ptype == "TJ":
        if not r.get("land_m2"):
            miss.append("area")
        if not r.get("land_use"):
            miss.append("land_use")
        return miss
    if not r.get("excl_m2"):
        miss.append("area")
    if (ptype in FLOORED and ptype not in ("GM", "GJCG") and not r.get("floor")
            and not (ptype in HOUSING and str(r.get("floor_label") or "") in ("고", "중", "저"))):
        miss.append("floor")
    if ptype in FLOORED and not r.get("total_floor"):
        miss.append("total_floor")
    if (ptype in HOUSING or ptype in NONRES) and not r.get("direction"):
        miss.append("direction")
    if ptype in HOUSING and not r.get("rooms"):
        miss.append("rooms")
    if ptype in HOUSING and not r.get("baths"):
        miss.append("baths")
    if not r.get("move_in"):
        miss.append("move_in")
    mgmt_declared = str(r.get("mgmt_type") or "") == "none" or (source == "region" and bool(r.get("mgmt_type")))
    if (ptype in MGMT_REQUIRED and not r.get("mgmt_fee") and not mgmt_declared
            and not (ptype == "APT" and kapt_ok)):
        miss.append("mgmt")
    # 공동주택·준주택 소재지 = 지번 + 동 + 층. 동이 둘 이상인 단지에서 동 번호가 비면 소재지를 특정할 수 없다.
    if ptype in COMPLEX_PTYPES and (n_buildings or 0) > 1 and not str(r.get("dong") or "").strip():
        miss.append("dong")
    # 단지형 전환분의 사용승인일(분양권은 입주 예정)·주차대수는 우리 단지 자료로 표시한다 — 단지 자료에 없으면 보류
    if cx_facts is not None and ptype in COMPLEX_PTYPES:
        if not cx_facts.get("approve"):
            miss.append("approve")
        if not (cx_facts.get("parking_total") or cx_facts.get("parking_per")):
            miss.append("parking")
    # 공동주택(빌라)은 지번까지 표시해야 한다. 단독은 의뢰인이 원하면 동까지(원 광고가 지번을 숨겼으면 그 뜻으로 본다)
    if source == "region" and ptype in ("VL", "OR") and r.get("address_mode") != "jibun":
        miss.append("jibun")
    if source in ("direct", "region") and ptype not in COMPLEX_PTYPES:
        if not r.get("address"):
            miss.append("address")
        if not r.get("approve_ymd"):
            miss.append("approve")
        if not r.get("parking"):
            miss.append("parking")
    return miss


def kapt_linked() -> set[str]:
    p = DB_PATH.parent / "kapt.sqlite"
    if not p.exists():
        return set()
    try:
        with sqlite3.connect(f"file:{p}?mode=ro", uri=True) as c:
            return {r[0] for r in c.execute("SELECT complex_no FROM kapt_map WHERE kapt_code IS NOT NULL")}
    except sqlite3.Error:
        return set()


def recompute_publish(k: sqlite3.Connection, d: sqlite3.Connection, realtor_id: str | None = None) -> tuple[int, int]:
    """active 전환분의 게시 상태(live/hold)와 사유를 다시 계산 → (live, hold)."""
    kapt = kapt_linked()
    q = "SELECT * FROM kok_listings WHERE status='active'" + (" AND realtor_id=?" if realtor_id else "")
    rows = k.execute(q, (realtor_id,) if realtor_id else ()).fetchall()
    cxs = {r["complex_no"] for r in rows}
    types: dict = {}
    nb: dict = {}
    facts: dict = {}
    if cxs:
        ph = ",".join("?" * len(cxs))
        types, nb = {}, {}
        for x in d.execute(f"SELECT complex_no, real_estate_type, total_building_count, use_approve_ymd, parking_possible_count, "
                           f"parking_per_household FROM complexes WHERE complex_no IN ({ph})", list(cxs)):
            types[x[0]], nb[x[0]] = x[1], x[2]
            facts[x[0]] = {"approve": x[3], "parking_total": x[4], "parking_per": x[5]}
    live = hold = 0
    for r in rows:
        miss = publish_check(dict(r), types.get(r["complex_no"]) or "APT", kapt_ok=r["complex_no"] in kapt,
                             n_buildings=nb.get(r["complex_no"]), cx_facts=facts.get(r["complex_no"], {}))
        st = "hold" if miss else "live"
        live += st == "live"; hold += st == "hold"
        k.execute("UPDATE kok_listings SET publish_state=?, hold_reasons=? WHERE article_no=?", (st, json.dumps(miss) if miss else None, r["article_no"]))
    k.commit()
    return live, hold


def recompute_direct(k: sqlite3.Connection, d: sqlite3.Connection, realtor_id: str | None = None) -> tuple[int, int]:
    """콕집 전용 등록(active)의 게시 상태를 지금 기준으로 다시 계산 → (live, hold). 규칙이 바뀌었을 때 한 번 돌린다."""
    q = "SELECT * FROM kok_direct_listings WHERE status='active'" + (" AND realtor_id=?" if realtor_id else "")
    rows = k.execute(q, (realtor_id,) if realtor_id else ()).fetchall()
    cxs = {r["complex_no"] for r in rows if r["complex_no"]}
    nb: dict = {}
    facts: dict = {}
    if cxs:
        ph = ",".join("?" * len(cxs))
        for x in d.execute(f"SELECT complex_no, total_building_count, use_approve_ymd, parking_possible_count, parking_per_household "
                           f"FROM complexes WHERE complex_no IN ({ph})", list(cxs)):
            nb[x[0]] = x[1]
            facts[x[0]] = {"approve": x[2], "parking_total": x[3], "parking_per": x[4]}
    live = hold = 0
    for r in rows:
        pt = r["ptype"]
        if pt in COMPLEX_PTYPES:
            miss = publish_check(dict(r), pt, source="direct", n_buildings=nb.get(r["complex_no"]), cx_facts=facts.get(r["complex_no"], {}))
        else:
            miss = publish_check(dict(r), pt, source="direct")
        st = "hold" if miss else "live"
        live += st == "live"; hold += st == "hold"
        k.execute("UPDATE kok_direct_listings SET publish_state=?, hold_reasons=? WHERE id=?", (st, json.dumps(miss) if miss else None, r["id"]))
    k.commit()
    return live, hold


def _kok_since(agreed_at: str | None, first_seen: str | None) -> str:
    return max(str(agreed_at or "")[:10], str(first_seen or "")[:10])


def sync(realtor_id: str | None = None, fetch_details: bool = True) -> dict:
    t0 = time.time()
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 9 * 3600))
    up = closed = det_n = 0
    with kok_db() as k, main_db() as d:
        q = "SELECT realtor_id, agreed_at, active FROM kok_realtor_optin"
        if realtor_id:
            q += " WHERE realtor_id=?"
        opt = k.execute(q, (realtor_id,) if realtor_id else ()).fetchall()
        active = {r["realtor_id"]: r["agreed_at"] for r in opt if r["active"]}
        inactive = [r["realtor_id"] for r in opt if not r["active"]]
        # ③ 해제 사무소 → closed
        for rid in inactive:
            closed += k.execute("UPDATE kok_listings SET status='closed', closed_at=?, updated_at=? WHERE realtor_id=? AND status='active'", (now, now, rid)).rowcount
        # ①② 동의 사무소의 광고 중 매물 upsert, 안 보인 건 closed
        for rid, agreed in active.items():
            rows = d.execute(
                "SELECT l.article_no, l.complex_no, cx.complex_name, cx.latitude, cx.longitude, l.trade_type, l.deal_or_warrant_price, l.rent_price, "
                "l.area_name, l.area1_m2, l.area2_m2, l.floor_info, l.direction, l.building_name, l.realtor_name, a.first_seen_date "
                "FROM listings_current l JOIN complexes cx ON cx.complex_no=l.complex_no LEFT JOIN articles a ON a.article_no=l.article_no "
                "WHERE l.realtor_id=?", (rid,)).fetchall()
            seen = set()
            prev = {x["article_no"]: x for x in k.execute("SELECT article_no, trade, price, rent, status FROM kok_listings WHERE realtor_id=?", (rid,))}
            for r in rows:
                seen.add(r["article_no"])
                pv = prev.get(r["article_no"])
                if pv is not None and pv["status"] == "active" and price_key(pv["trade"], pv["price"], pv["rent"]) != price_key(r["trade_type"], r["deal_or_warrant_price"], r["rent_price"]):
                    log_change(k, "R" + r["article_no"], "price", price_key(pv["trade"], pv["price"], pv["rent"]),
                               price_key(r["trade_type"], r["deal_or_warrant_price"], r["rent_price"]))
                fl = None
                try:
                    fl = int(str(r["floor_info"] or "").split("/")[0]) if str(r["floor_info"] or "").split("/")[0].isdigit() else None
                except ValueError:
                    fl = None
                k.execute(
                    "INSERT INTO kok_listings(article_no, realtor_id, realtor_name, complex_no, complex_name, dong, lat, lng, trade, price, rent, area_name, "
                    "supply_m2, excl_m2, floor, direction, first_seen, kok_since, status, synced_at, floor_label, total_floor) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?,?,?) "
                    "ON CONFLICT(article_no) DO UPDATE SET realtor_name=excluded.realtor_name, complex_name=excluded.complex_name, "
                    "dong=COALESCE(NULLIF(kok_listings.dong,''), excluded.dong), lat=excluded.lat, lng=excluded.lng, trade=excluded.trade, price=excluded.price, rent=excluded.rent, "
                    "area_name=excluded.area_name, supply_m2=COALESCE(kok_listings.supply_m2, excluded.supply_m2), excl_m2=COALESCE(kok_listings.excl_m2, excluded.excl_m2), "
                    "floor=COALESCE(kok_listings.floor, excluded.floor), direction=COALESCE(NULLIF(kok_listings.direction,''), excluded.direction), "
                    "first_seen=COALESCE(kok_listings.first_seen, excluded.first_seen), kok_since=excluded.kok_since, "
                    "status=CASE WHEN kok_listings.status='sold' THEN 'sold' ELSE 'active' END, "
                    "closed_at=CASE WHEN kok_listings.status='sold' THEN kok_listings.closed_at ELSE NULL END, synced_at=excluded.synced_at, updated_at=excluded.synced_at, floor_label=excluded.floor_label, total_floor=COALESCE(excluded.total_floor, kok_listings.total_floor)",
                    (r["article_no"], rid, r["realtor_name"], r["complex_no"], r["complex_name"], (r["building_name"] or "").replace("동", ""),
                     r["latitude"], r["longitude"], r["trade_type"], r["deal_or_warrant_price"], r["rent_price"], r["area_name"],
                     r["area1_m2"], r["area2_m2"], fl, r["direction"] or "", r["first_seen_date"], _kok_since(agreed, r["first_seen_date"]), now,
                     (str(r["floor_info"] or "").split("/")[0] or None), _int_or_none(str(r["floor_info"] or "").split("/")[-1])))
                up += 1
            stale = [x[0] for x in k.execute("SELECT article_no FROM kok_listings WHERE realtor_id=? AND status='active'", (rid,)) if x[0] not in seen]
            for a in stale:
                k.execute("UPDATE kok_listings SET status='closed', closed_at=?, updated_at=? WHERE article_no=?", (now, now, a))
            closed += len(stale)
        k.commit()
        # ④ 상세 — 아직 안 받았거나 오래된 것부터, 한 번에 DETAIL_PER_RUN 건
        if fetch_details and active:
            det_n = _fetch_details(k, d, realtor_id)
        live, hold = recompute_publish(k, d, realtor_id)
        # 비단지(빌라·단독) — 동의 사무소만. 오픈 전: 공개 API 는 이 표를 읽지 않는다
        g_up, g_closed = sync_region(k, active, inactive, now)
        g_det = _fetch_region_details(k, realtor_id) if (fetch_details and active) else 0
        g_live, g_hold = recompute_region(k, realtor_id)
        k.execute("INSERT INTO kok_sync_log(scope, realtors, upserted, closed, details, seconds, note) VALUES(?,?,?,?,?,?,?)",
                  (realtor_id or "all", len(active), up, closed, det_n, round(time.time() - t0, 1),
                   f"live {live} hold {hold} | region up {g_up} closed {g_closed} det {g_det} live {g_live} hold {g_hold}"))
        k.commit()
    return {"realtors": len(active), "upserted": up, "closed": closed, "details": det_n, "live": live, "hold": hold,
            "region": {"upserted": g_up, "closed": g_closed, "details": g_det, "live": g_live, "hold": g_hold}, "seconds": round(time.time() - t0, 1)}


def _fetch_details(k: sqlite3.Connection, d: sqlite3.Connection, realtor_id: str | None) -> int:
    try:
        from collector.article_detail import fetch_article_detail
        from collector.creds import ensure_creds
        creds = ensure_creds()
    except Exception as e:  # noqa: BLE001
        print("detail: creds 실패 —", str(e)[:120]); return 0
    # 아직 점검 안 한 것(audit_at NULL)·위반으로 막힌 것(하루 지나면 다시 — 원 광고를 고쳤을 수 있다)도 다시 받는다
    q = ("SELECT article_no, complex_no, complex_name FROM kok_listings WHERE status='active' AND (detail_fetched_at IS NULL OR detail_fetched_at<datetime('now','+9 hours',?) "
         "OR audit_at IS NULL OR (audit_viol IS NOT NULL AND detail_fetched_at<datetime('now','+9 hours','-20 hours')))"
         + (" AND realtor_id=?" if realtor_id else "") + " ORDER BY detail_fetched_at IS NOT NULL, audit_at IS NOT NULL, kok_since DESC LIMIT ?")
    args: list = [f"-{DETAIL_TTL_DAYS} days"] + ([realtor_id] if realtor_id else []) + [DETAIL_PER_RUN]
    todo = k.execute(q, args).fetchall()
    n = fails = 0
    for r in todo:
        try:
            st, det = fetch_article_detail(r["article_no"], r["complex_no"], creds)
        except Exception as e:  # noqa: BLE001
            st, det = 0, None
            print("detail err", r["article_no"], str(e)[:80])
        if st != 200 or not det:
            fails += 1
            if fails >= 5 and n == 0:
                print("detail: 연속 실패 — 이번엔 멈춤"); break
            time.sleep(1.0); continue
        ad = det.get("articleDetail") or {}
        if not ad.get("articleNo"):      # 광고가 내려감 — 빈 값으로 점검하면 전 항목 위반 오탐. 동기화가 closed 로 돌린다
            continue
        try:
            lrow = d.execute("SELECT l.article_no, l.real_estate_type, l.trade_type, l.floor_info, l.area2_m2, l.deal_or_warrant_price, l.rent_price, "
                             "l.building_name, l.direction, cx.dong_name, cx.detail_address FROM listings_current l "
                             "JOIN complexes cx ON cx.complex_no=l.complex_no WHERE l.article_no=?", (r["article_no"],)).fetchone()
            viol = audit_source_ad(det, dict(lrow) if lrow else None, r["complex_name"])
            k.execute("UPDATE kok_listings SET audit_viol=?, audit_at=datetime('now','+9 hours') WHERE article_no=?",
                      (json.dumps(viol, ensure_ascii=False) if viol else None, r["article_no"]))
        except Exception as e:  # noqa: BLE001 — 점검 실패는 판정 보류(audit_at 그대로라 다음에 다시)
            print("audit err", r["article_no"], str(e)[:100])
        fac = det.get("articleFacility") or {}
        sp = det.get("articleSpace") or {}
        pr = det.get("articlePrice") or {}
        move_in = " ".join(x for x in [ad.get("moveInTypeName") or "", "협의 가능" if ad.get("moveInDiscussionPossibleYN") == "Y" else ""] if x).strip()
        cost = det.get("administrationCostInfo") or {}
        mgmt_fee = _int_or_none(ad.get("monthlyManagementCost"))
        if not mgmt_fee:
            mgmt_fee = _int_or_none((cost.get("etcFeeDetails") or {}).get("etcFeeAmount"))
        # 비목은 이름과 금액만(표시 의무 항목). 금액 확인 불가(amountCodeType 02)는 None 으로 남긴다
        items = [{"name": x.get("detailCodeTypeName") or x.get("detailCodeType"), "amount": None if x.get("amountCodeType") == "02" else _int_or_none(x.get("amount"))}
                 for x in (cost.get("fixedFeeDetails") or []) if x.get("detailCodeTypeName") or x.get("detailCodeType")]
        total_floor = _int_or_none(ad.get("totalFloorCount") or (str(ad.get("floorInfo") or "").split("/")[-1] if "/" in str(ad.get("floorInfo") or "") else None))
        k.execute(
            "UPDATE kok_listings SET rooms=?, baths=?, move_in=?, direction=COALESCE(NULLIF(?,''), direction), direction_base=?, supply_m2=COALESCE(?, supply_m2), excl_m2=COALESCE(?, excl_m2), "
            "finance_price=?, violation=?, dong=COALESCE(NULLIF(?,''), dong), mgmt_fee=?, mgmt_type=?, mgmt_items=?, total_floor=COALESCE(?, total_floor), "
            "detail_fetched_at=datetime('now','+9 hours'), updated_at=datetime('now','+9 hours') WHERE article_no=?",
            (str(ad.get("roomCount") or "") or None, str(ad.get("bathroomCount") or "") or None, move_in, fac.get("directionTypeName") or "", fac.get("directionBaseTypeName") or None,
             sp.get("supplySpace"), sp.get("exclusiveSpace"), (int(pr["financePrice"]) * 10000) if str(pr.get("financePrice") or "").isdigit() else None,
             ad.get("violationBuildingYN") or "", (ad.get("buildingName") or "").replace("동", ""),
             mgmt_fee, str(cost.get("chargeCodeType") or "") or None, json.dumps(items, ensure_ascii=False) if items else None, total_floor, r["article_no"]))
        n += 1
        if n % 50 == 0:
            k.commit()
        time.sleep(0.4)
    k.commit()
    return n

# ── 비단지 전환(1단계: 빌라·단독 / 2단계: 상가·사무실·지산·건물·공장) ─────────────────────────────────────────────────────────────
# 지역 수집 DB(3일 롤링)를 읽기만 한다. 대상 = 동의 사무소(kok_realtor_optin.active)의 attribution='realtor' 광고.
# 등록번호로 귀속한 광고(attribution='region')는 오귀속 0 보장이 없어 넣지 않는다.
# 점검은 라운지 '매물 점검'과 같은 실행부(collector/audit_runner.py — 상세 + 건축물대장 대조)로 하고, '위반'이면 전환하지 않는다.
REGION_SOURCES = {
    "villa": {"빌라/연립": "VL", "빌라단지-연립": "VL"},
    "house": {"단독/다가구": "DDDGG", "전원주택": "DDDGG"},
    # 2단계(11-13): 그 밖의 건축물 — 방향은 주출입구 기준, 관리비 선택, 정확한 층, 소재지는 동까지 가능
    "sangga": {"상가점포": "SG"},
    "office": {"사무실": "SMS"},
    "knowledge": {"지식산업센터": "APTHGJ"},
    "building": {"빌딩/건물": "GM", "상가건물": "GM", "상가주택": "GM"},   # 기타·숙박/콘도는 뺌
    "factory": {"공장/창고": "GJCG"},
    # 3단계(11-13): 토지 — 원 광고에 지목이 없어 좌표의 필지(VWorld)를 찾고, 대장 면적이 광고 면적과 맞을 때만 지목·공시지가를 쓴다
    "land": {"토지/임야": "TJ"},
}
REGION_STALE_DAYS = 2      # 지역 DB 최신 수집분이 이보다 오래되면 '안 보인 매물 닫기'를 하지 않는다(수집이 멈춘 것)


def region_db(cat: str) -> sqlite3.Connection | None:
    p = DB_PATH.parent / f"listings_{cat}.sqlite"
    if not p.exists():
        return None
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=60)
    c.row_factory = sqlite3.Row
    return c


def _floor_parse(floor_info) -> tuple[int | None, str | None, int | None]:
    """'3/5' → (3,'3',5), 'B1/2' → (-1,'B1',2), '중/15' → (None,'중',15)."""
    a, _, b = str(floor_info or "").partition("/")
    a = a.strip()
    fl = int(a) if a.isdigit() else (-int(a[1:]) if a[:1] == "B" and a[1:].isdigit() else None)
    return fl, (a or None), _int_or_none(b)


def _tg(msg: str) -> None:
    try:
        from scripts.tg_notify import tg_send
        tg_send(msg)
    except Exception:  # noqa: BLE001
        pass


def sync_region(k: sqlite3.Connection, active: dict, inactive: list, now: str) -> tuple[int, int]:
    up = closed = 0
    for rid in inactive:
        closed += k.execute("UPDATE kok_region_listings SET status='closed', closed_at=?, updated_at=? WHERE realtor_id=? AND status='active'",
                            (now, now, rid)).rowcount
    if not active:
        return up, closed
    ph = ",".join("?" * len(active))
    for cat, tmap in REGION_SOURCES.items():
        rd = region_db(cat)
        if rd is None:
            print(f"region {cat}: DB 없음"); continue
        with rd:
            snap = rd.execute("SELECT MAX(snapshot_date) FROM listings").fetchone()[0]
            fresh = bool(snap) and snap >= time.strftime("%Y-%m-%d", time.gmtime(time.time() + 9 * 3600 - REGION_STALE_DAYS * 86400))
            if not fresh:
                print(f"region {cat}: 최신 수집분 {snap} — 오래돼 닫기 생략")
                _tg(f"[콕집매물] 비단지 전환 원천 {cat} 최신 수집분이 {snap} — 수집이 멈췄는지 확인")
            rows = rd.execute(
                "SELECT article_no, realtor_id, realtor_name, real_estate_type_name, trade_type, deal_or_warrant_price, rent_price, area1_m2, area2_m2, "
                f"floor_info, direction, building_name, latitude, longitude, cortar_no, first_seen_date FROM listings WHERE realtor_id IN ({ph}) "
                "AND attribution='realtor' AND snapshot_date=?", [*active, snap]).fetchall()
        seen: dict[str, set] = {}
        for r in rows:
            pt = tmap.get(r["real_estate_type_name"] or "")
            if not pt:
                continue
            rid = r["realtor_id"]
            seen.setdefault(rid, set()).add(r["article_no"])
            pv = k.execute("SELECT trade, price, rent, status FROM kok_region_listings WHERE article_no=?", (r["article_no"],)).fetchone()
            if pv is not None and pv["status"] == "active" and price_key(pv["trade"], pv["price"], pv["rent"]) != price_key(r["trade_type"], r["deal_or_warrant_price"], r["rent_price"]):
                log_change(k, "G" + r["article_no"], "price", price_key(pv["trade"], pv["price"], pv["rent"]),
                           price_key(r["trade_type"], r["deal_or_warrant_price"], r["rent_price"]))
            fl, flabel, tf = _floor_parse(r["floor_info"])
            k.execute(
                "INSERT INTO kok_region_listings(article_no, realtor_id, realtor_name, src, ptype, type_name, cortar_no, lat, lng, building_name, trade, price, rent, "
                "supply_m2, excl_m2, floor, floor_label, total_floor, direction, first_seen, kok_since, status, synced_at, land_m2) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?,?) "
                "ON CONFLICT(article_no) DO UPDATE SET realtor_name=excluded.realtor_name, type_name=excluded.type_name, lat=excluded.lat, lng=excluded.lng, "
                "building_name=excluded.building_name, trade=excluded.trade, price=excluded.price, rent=excluded.rent, supply_m2=excluded.supply_m2, excl_m2=excluded.excl_m2, "
                "floor=excluded.floor, floor_label=excluded.floor_label, total_floor=COALESCE(kok_region_listings.total_floor, excluded.total_floor), "
                "direction=COALESCE(NULLIF(kok_region_listings.direction,''), excluded.direction), first_seen=COALESCE(kok_region_listings.first_seen, excluded.first_seen), "
                "kok_since=excluded.kok_since, land_m2=excluded.land_m2, status=CASE WHEN kok_region_listings.status='sold' THEN 'sold' ELSE 'active' END, "
                "closed_at=CASE WHEN kok_region_listings.status='sold' THEN kok_region_listings.closed_at ELSE NULL END, synced_at=excluded.synced_at, updated_at=excluded.synced_at",
                (r["article_no"], rid, r["realtor_name"], cat, pt, r["real_estate_type_name"], r["cortar_no"], r["latitude"], r["longitude"], r["building_name"],
                 r["trade_type"], r["deal_or_warrant_price"], r["rent_price"], r["area1_m2"], r["area2_m2"], fl, flabel, tf, r["direction"] or "",
                 r["first_seen_date"], _kok_since(active[rid], r["first_seen_date"]), now, r["area1_m2"] if pt == "TJ" else None))
            up += 1
        if fresh:
            for rid in active:
                cur = seen.get(rid, set())
                for (a,) in k.execute("SELECT article_no FROM kok_region_listings WHERE realtor_id=? AND src=? AND status='active'", (rid, cat)).fetchall():
                    if a not in cur:
                        k.execute("UPDATE kok_region_listings SET status='closed', closed_at=?, updated_at=? WHERE article_no=?", (now, now, a))
                        closed += 1
    k.commit()
    return up, closed


def _move_in_text(f: dict) -> str | None:
    """원 광고에 찍히는 입주 가능일 문구(점검 엔진 ⑦과 같은 해석): 8자리 날짜면 그 날짜, NOW 면 즉시 입주, 그 밖엔 'YYYY년 M월 초·중·하순'."""
    ymd = str(f.get("movein_ymd") or "").strip()
    t = str(f.get("movein_type") or "").strip()
    nego = str(f.get("movein_negotiable") or "").strip() in ("Y", "협의가능")
    if len(ymd) == 8 and ymd.isdigit():
        return f"{ymd[:4]}.{ymd[4:6]}.{ymd[6:]}"
    if "즉시" in t or ymd == "NOW":
        return "즉시 입주" + (" (협의 가능)" if nego else "")
    if t:
        return t + (", 협의 가능" if nego and any(x in t for x in ("초순", "중순", "하순")) else "")
    return None


def _to_f(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _land_facts(lat, lng, land_m2, vw: str, pnu: str | None = None) -> dict | None:
    """필지 → 토지특성(대장 지목·면적·공시지가). 지목 자체는 광고 값을 쓰고, 이건 공시지가·대조용.
    광고가 준 필지 번호(pnu)가 있으면 그 필지를 그대로 쓴다. 없으면 좌표가 놓인 필지를 찾되,
    대장 면적이 광고 면적과 1%(최소 1㎡) 안에서 맞을 때만 — 엉뚱한 필지를 붙이지 않게."""
    import urllib.parse
    import urllib.request
    if not vw or not (pnu or (lat and lng and land_m2)):
        return None
    given = bool(pnu)

    def get(u: str) -> dict:
        req = urllib.request.Request(u, headers={"User-Agent": "koczip/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    try:
        if not pnu:
            q = urllib.parse.urlencode({"service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN", "key": vw, "domain": "koczip.com",
                                        "geomFilter": f"POINT({lng} {lat})", "size": "1", "format": "json"})
            feats = get("https://api.vworld.kr/req/data?" + q)["response"].get("result", {}).get("featureCollection", {}).get("features", [])
            if not feats:
                return None
            pnu = feats[0]["properties"]["pnu"]
        q = urllib.parse.urlencode({"key": vw, "domain": "koczip.com", "pnu": pnu, "format": "json", "numOfRows": "20", "pageNo": "1"})
        root = next(iter(get("https://api.vworld.kr/ned/data/getLandCharacteristics?" + q).values()), {})
        fl = root.get("field", []) if isinstance(root, dict) else []
        fl = fl if isinstance(fl, list) else [fl]
        if not fl:
            return None
        last = sorted(fl, key=lambda x: (str(x.get("stdrYear") or ""), str(x.get("lastUpdtDt") or "")))[-1]   # 같은 해 여러 줄(분할 등) → 마지막 갱신
        area = float(last.get("lndpclAr") or 0)
    except Exception as e:  # noqa: BLE001
        print("land facts err", str(e)[:80]); return None
    if not given and (not area or abs(area - float(land_m2)) > max(1.0, float(land_m2) * 0.01)):
        return {"pnu": pnu, "matched": False}
    return {"pnu": pnu, "matched": True, "land_use": last.get("lndcgrCodeNm"), "land_price": _int_or_none(last.get("pblntfPclnd")),
            "area": area or None}


def _fetch_region_details(k: sqlite3.Connection, realtor_id: str | None) -> int:
    try:
        from collector.audit_runner import _audit_keys, _audit_nonresi_one
        from collector.creds import ensure_creds
        creds = ensure_creds()
        vw, dks = _audit_keys()
    except Exception as e:  # noqa: BLE001
        print("region detail: 준비 실패 —", str(e)[:120]); return 0
    q = ("SELECT * FROM kok_region_listings WHERE status='active' AND (detail_fetched_at IS NULL OR detail_fetched_at<datetime('now','+9 hours',?) "
         "OR audit_at IS NULL OR (audit_viol IS NOT NULL AND detail_fetched_at<datetime('now','+9 hours','-20 hours')))"
         + (" AND realtor_id=?" if realtor_id else "") + " ORDER BY audit_at IS NOT NULL, kok_since DESC LIMIT ?")
    todo = k.execute(q, [f"-{DETAIL_TTL_DAYS} days"] + ([realtor_id] if realtor_id else []) + [DETAIL_PER_RUN]).fetchall()
    n = fails = 0
    for x in todo:
        r = {"article_no": x["article_no"], "real_estate_type_name": x["type_name"], "trade_type": x["trade"], "floor_info": None,
             "area2_m2": x["excl_m2"], "deal_or_warrant_price": x["price"], "rent_price": x["rent"], "building_name": x["building_name"],
             "direction": x["direction"], "latitude": x["lat"], "longitude": x["lng"], "cortar_no": x["cortar_no"]}
        if x["floor_label"]:
            r["floor_info"] = f"{x['floor_label']}/{x['total_floor'] or ''}".rstrip("/")
        try:
            res = _audit_nonresi_one(r, x["src"], creds, vw, dks)
        except Exception as e:  # noqa: BLE001
            print("region audit err", x["article_no"], str(e)[:100]); fails += 1
            if fails >= 5 and n == 0:
                print("region detail: 연속 실패 — 이번엔 멈춤"); break
            continue
        f = res.get("_audit_input")
        if not f:          # 광고가 내려갔거나 상세 일시 실패 — 판정 보류(내려간 건 다음 동기화가 닫는다)
            continue
        aci = f.get("admin_cost_info") or {}
        pk = f.get("parking_count")
        parking = "불가" if f.get("parking_possible") == "N" else (str(pk) if pk is not None else None)
        addr = (f.get("exposure_address") or "").strip()
        mode = "jibun" if addr and any(ch.isdigit() for ch in addr.split()[-1]) else ("dong" if addr else None)
        viol = violations(res)
        k.execute(
            "UPDATE kok_region_listings SET rooms=?, baths=?, move_in=?, direction=COALESCE(NULLIF(?,''), direction), direction_base=?, total_floor=COALESCE(?, total_floor), "
            "approve_ymd=?, parking=?, violation=?, mgmt_fee=?, mgmt_type=?, address=?, address_mode=?, pnu=?, bld_use=?, audit_viol=?, "
            "audit_at=datetime('now','+9 hours'), detail_fetched_at=datetime('now','+9 hours'), updated_at=datetime('now','+9 hours') WHERE article_no=?",
            (None if f.get("room_count") is None else str(f["room_count"]), None if f.get("bathroom_count") is None else str(f["bathroom_count"]),
             _move_in_text(f), f.get("direction") or "", "주출입구" if x["ptype"] in NONRES else f.get("direction_base"), _int_or_none(f.get("total_floor")),
             str(f.get("use_approve_ymd") or "") or None, parking, f.get("violation_building") or "",
             _int_or_none(f.get("monthly_management_cost")), str(aci.get("chargeCodeType") or "") or None,
             addr or None, mode, f.get("led_pnu"), f.get("led_main_purps"),
             json.dumps(viol, ensure_ascii=False) if viol else None, x["article_no"]))
        if x["ptype"] == "TJ":
            # 지목 = 원 광고 값(광고에 표시된 그대로). 필지 대장 지목은 대조용으로 따로 둔다.
            ad_pnu = str(f.get("ad_pnu") or "").strip()
            lf = _land_facts(x["lat"], x["lng"], x["land_m2"], vw, pnu=ad_pnu if len(ad_pnu) == 19 else None) or {}
            k.execute("UPDATE kok_region_listings SET land_use=?, land_use_ledger=?, land_m2_ledger=?, land_price=?, pnu=COALESCE(?, pnu) WHERE article_no=?",
                      ((f.get("land_category") or "").strip() or None, lf.get("land_use"), lf.get("area"), lf.get("land_price"),
                       lf.get("pnu") if lf.get("matched") else None, x["article_no"]))
            ad_lu = (f.get("land_category") or "").strip()
            la, ll = _to_f(x["land_m2"]), _to_f(lf.get("area"))
            single = bool(la and ll and la <= ll + 1.0)   # 광고 면적이 대표 필지를 넘지 않음 = 한 필지 광고로 볼 수 있음
            # 지목이 토지대장과 다르면 위반(사용자 결정 11-14) — 한 필지 광고일 때만. 여러 필지 합계 광고면 다른 필지의 지목일 수 있다.
            if single and ad_lu and lf.get("land_use") and ad_lu != lf["land_use"]:
                viol.append(f"지목: 광고({ad_lu}) ≠ 토지대장 기준 {lf['land_use']}")
            # 토지 면적이 대장과 다르면 위반(사용자 결정 11-14). 1㎡ 이하는 반올림 차이. 광고가 대표 필지보다 '넓은' 건
            # 여러 필지를 묶은 합계일 수 있어(광고엔 대표 필지 번호만 온다) 단정 못 함 → 막지 않는다(land_m2_ledger 로 남김).
            if la and ll and la < ll - 1.0:
                viol.append(f"토지면적: 광고({la:g}㎡) ≠ 토지대장 기준 {ll:g}㎡")
            if viol and any(v.startswith(("지목:", "토지면적:")) for v in viol):
                k.execute("UPDATE kok_region_listings SET audit_viol=? WHERE article_no=?", (json.dumps(viol, ensure_ascii=False), x["article_no"]))
        n += 1
        if n % 20 == 0:
            k.commit()
        time.sleep(0.4)
    k.commit()
    return n


def recompute_region(k: sqlite3.Connection, realtor_id: str | None = None) -> tuple[int, int]:
    q = "SELECT * FROM kok_region_listings WHERE status='active'" + (" AND realtor_id=?" if realtor_id else "")
    live = hold = 0
    for r in k.execute(q, (realtor_id,) if realtor_id else ()).fetchall():
        miss = publish_check(dict(r), r["ptype"], source="region") if r["audit_at"] else ["audit_pending"]
        st = "hold" if miss else "live"
        live += st == "live"; hold += st == "hold"
        k.execute("UPDATE kok_region_listings SET publish_state=?, hold_reasons=? WHERE article_no=?", (st, json.dumps(miss) if miss else None, r["article_no"]))
    k.commit()
    return live, hold


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--realtor", help="한 사무소만")
    ap.add_argument("--migrate", action="store_true")
    ap.add_argument("--no-details", action="store_true")
    ap.add_argument("--recompute", action="store_true", help="동기화 없이 게시 상태만 다시 계산(규칙을 바꾼 뒤)")
    a = ap.parse_args()
    if a.migrate:
        migrate()
    if a.recompute:
        k, d = kok_db(), main_db()
        before = {t: dict(k.execute(f"SELECT COALESCE(publish_state,'live'), COUNT(*) FROM {t} WHERE status='active' GROUP BY 1").fetchall())
                  for t in ("kok_listings", "kok_direct_listings")}
        conv, direct, region = recompute_publish(k, d), recompute_direct(k, d), recompute_region(k)
        print("recompute", json.dumps({"before": before, "converted(live,hold)": conv, "direct(live,hold)": direct, "region(live,hold)": region}, ensure_ascii=False))
        return 0
    res = sync(a.realtor, fetch_details=not a.no_details)
    print("kok_sync", json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
