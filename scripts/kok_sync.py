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
CREATE TABLE IF NOT EXISTS kok_sync_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ran_at TEXT DEFAULT (datetime('now','+9 hours')), scope TEXT,
  realtors INTEGER, upserted INTEGER, closed INTEGER, details INTEGER, seconds REAL, note TEXT);
"""


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
                          ("kok_direct_listings", "publish_state", "TEXT"), ("kok_direct_listings", "hold_reasons", "TEXT")):
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
FLOORED = {"APT", "OPST", "ABYG", "OBYG", "JGC", "VL", "OR", "SG", "SMS", "GM", "GJCG"}
# 분양권(아파트·오피스텔): 준공 전이라 관리비·사용승인일은 아직 없다(해당 없음). 층·방향·방·욕실·입주 예정은 표시 대상.
# 2026-11-12 이전엔 OBYG 가 위 집합에 없어 검사 없이 공개됐고, ABYG 는 관리비 없음으로 전부 보류됐다.
PRESALE = {"ABYG", "OBYG"}
HOLD_LABEL = {"price": "가격", "rent": "월세", "area": "면적", "floor": "층", "total_floor": "총 층수", "direction": "방향", "rooms": "방 수", "baths": "욕실 수",
              "move_in": "입주 가능일", "mgmt": "관리비", "approve": "사용승인일", "parking": "주차대수", "land_use": "지목", "address": "소재지",
              "dong": "동(건물 번호)"}


def publish_check(r: dict, ptype: str, *, kapt_ok: bool = False, source: str = "converted", n_buildings: int | None = None,
                  cx_facts: dict | None = None) -> list[str]:
    """빠진 필수 항목 코드 목록. 비면 게시 가능. 전환분 아파트는 K-apt 실제 관리비가 있으면 관리비 표시로 본다."""
    miss: list[str] = []
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
    if ptype in FLOORED and ptype not in ("GM", "GJCG") and not r.get("floor") and str(r.get("floor_label") or "") not in ("고", "중", "저"):
        miss.append("floor")
    if ptype in FLOORED and not r.get("total_floor"):
        miss.append("total_floor")
    if ptype in HOUSING and not r.get("direction"):
        miss.append("direction")
    if ptype in HOUSING and not r.get("rooms"):
        miss.append("rooms")
    if ptype in HOUSING and not r.get("baths"):
        miss.append("baths")
    if not r.get("move_in"):
        miss.append("move_in")
    if (ptype in FLOORED and ptype not in ("GM", "GJCG") and ptype not in PRESALE
            and not r.get("mgmt_fee") and not (ptype == "APT" and kapt_ok)):
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
    if source == "direct" and ptype not in COMPLEX_PTYPES:
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
            for r in rows:
                seen.add(r["article_no"])
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
                    "status='active', closed_at=NULL, synced_at=excluded.synced_at, updated_at=excluded.synced_at, floor_label=excluded.floor_label, total_floor=COALESCE(excluded.total_floor, kok_listings.total_floor)",
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
            det_n = _fetch_details(k, realtor_id)
        live, hold = recompute_publish(k, d, realtor_id)
        k.execute("INSERT INTO kok_sync_log(scope, realtors, upserted, closed, details, seconds, note) VALUES(?,?,?,?,?,?,?)",
                  (realtor_id or "all", len(active), up, closed, det_n, round(time.time() - t0, 1), f"live {live} hold {hold}"))
        k.commit()
    return {"realtors": len(active), "upserted": up, "closed": closed, "details": det_n, "live": live, "hold": hold, "seconds": round(time.time() - t0, 1)}


def _fetch_details(k: sqlite3.Connection, realtor_id: str | None) -> int:
    try:
        from collector.article_detail import fetch_article_detail
        from collector.creds import ensure_creds
        creds = ensure_creds()
    except Exception as e:  # noqa: BLE001
        print("detail: creds 실패 —", str(e)[:120]); return 0
    q = ("SELECT article_no, complex_no FROM kok_listings WHERE status='active' AND (detail_fetched_at IS NULL OR detail_fetched_at<datetime('now','+9 hours',?))"
         + (" AND realtor_id=?" if realtor_id else "") + " ORDER BY detail_fetched_at IS NOT NULL, kok_since DESC LIMIT ?")
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--realtor", help="한 사무소만")
    ap.add_argument("--migrate", action="store_true")
    ap.add_argument("--no-details", action="store_true")
    a = ap.parse_args()
    if a.migrate:
        migrate()
    res = sync(a.realtor, fetch_details=not a.no_details)
    print("kok_sync", json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
