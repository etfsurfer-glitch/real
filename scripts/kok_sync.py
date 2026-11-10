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
  detail_fetched_at TEXT, synced_at TEXT, floor_label TEXT, created_at TEXT DEFAULT (datetime('now','+9 hours')), updated_at TEXT DEFAULT (datetime('now','+9 hours')));
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
  created_at TEXT DEFAULT (datetime('now','+9 hours')), updated_at TEXT DEFAULT (datetime('now','+9 hours')), expires_at TEXT);
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
    for tbl, col in (("kok_owner_listings", "keywords"), ("kok_listings", "floor_label")):
        if col not in {r[1] for r in c.execute(f"PRAGMA table_info({tbl})")}:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} TEXT")
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
                    "supply_m2, excl_m2, floor, direction, first_seen, kok_since, status, synced_at, floor_label) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?,?) "
                    "ON CONFLICT(article_no) DO UPDATE SET realtor_name=excluded.realtor_name, complex_name=excluded.complex_name, "
                    "dong=COALESCE(NULLIF(kok_listings.dong,''), excluded.dong), lat=excluded.lat, lng=excluded.lng, trade=excluded.trade, price=excluded.price, rent=excluded.rent, "
                    "area_name=excluded.area_name, supply_m2=COALESCE(kok_listings.supply_m2, excluded.supply_m2), excl_m2=COALESCE(kok_listings.excl_m2, excluded.excl_m2), "
                    "floor=COALESCE(kok_listings.floor, excluded.floor), direction=COALESCE(NULLIF(kok_listings.direction,''), excluded.direction), "
                    "first_seen=COALESCE(kok_listings.first_seen, excluded.first_seen), kok_since=excluded.kok_since, "
                    "status='active', closed_at=NULL, synced_at=excluded.synced_at, updated_at=excluded.synced_at, floor_label=excluded.floor_label",
                    (r["article_no"], rid, r["realtor_name"], r["complex_no"], r["complex_name"], (r["building_name"] or "").replace("동", ""),
                     r["latitude"], r["longitude"], r["trade_type"], r["deal_or_warrant_price"], r["rent_price"], r["area_name"],
                     r["area1_m2"], r["area2_m2"], fl, r["direction"] or "", r["first_seen_date"], _kok_since(agreed, r["first_seen_date"]), now,
                     (str(r["floor_info"] or "").split("/")[0] or None)))
                up += 1
            stale = [x[0] for x in k.execute("SELECT article_no FROM kok_listings WHERE realtor_id=? AND status='active'", (rid,)) if x[0] not in seen]
            for a in stale:
                k.execute("UPDATE kok_listings SET status='closed', closed_at=?, updated_at=? WHERE article_no=?", (now, now, a))
            closed += len(stale)
        k.commit()
        # ④ 상세 — 아직 안 받았거나 오래된 것부터, 한 번에 DETAIL_PER_RUN 건
        if fetch_details and active:
            det_n = _fetch_details(k, realtor_id)
        k.execute("INSERT INTO kok_sync_log(scope, realtors, upserted, closed, details, seconds) VALUES(?,?,?,?,?,?)",
                  (realtor_id or "all", len(active), up, closed, det_n, round(time.time() - t0, 1)))
        k.commit()
    return {"realtors": len(active), "upserted": up, "closed": closed, "details": det_n, "seconds": round(time.time() - t0, 1)}


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
        k.execute(
            "UPDATE kok_listings SET rooms=?, baths=?, move_in=?, direction=COALESCE(NULLIF(?,''), direction), supply_m2=COALESCE(?, supply_m2), excl_m2=COALESCE(?, excl_m2), "
            "finance_price=?, violation=?, dong=COALESCE(NULLIF(?,''), dong), detail_fetched_at=datetime('now','+9 hours'), updated_at=datetime('now','+9 hours') WHERE article_no=?",
            (str(ad.get("roomCount") or "") or None, str(ad.get("bathroomCount") or "") or None, move_in, fac.get("directionTypeName") or "",
             sp.get("supplySpace"), sp.get("exclusiveSpace"), (int(pr["financePrice"]) * 10000) if str(pr.get("financePrice") or "").isdigit() else None,
             ad.get("violationBuildingYN") or "", (ad.get("buildingName") or "").replace("동", ""), r["article_no"]))
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
