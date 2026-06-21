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
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402
from collector.creds import ensure_creds          # noqa: E402
from collector.http import get_json               # noqa: E402
from collector.config import settings             # noqa: E402

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
    c = sqlite3.connect(path, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA synchronous=NORMAL")
    c.executescript(_schema(premium))
    return c


def _fetch_code(cortar: str, code: str, creds: dict, interface: str | None = None) -> tuple[list[dict], bool, int]:
    """한 동·한 코드의 매물 전수. (items, natural_stop, map_exposed) 반환.
    natural_stop=True → isMoreData=false 도달(=전수 완료). False → 캡/에러로 중단(무결성 위반).
    interface=소스IP 바인딩(멀티IP 병렬)."""
    out, page, natural, map_exposed = [], 1, False, None
    while page <= PAGE_CAP:
        params = {
            "cortarNo": cortar, "realEstateType": code, "tradeType": "A1:B1:B2",
            "sameAddressGroup": "false", "page": str(page),
        }
        st, data = get_json(ARTICLES_URL, creds, params=params, interface=interface)
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


def _fetch_dong(cortar: str, creds: dict, interface: str | None) -> tuple[str, list[dict], bool]:
    """워커: 한 동의 5코드 전수(같은 IP). (cortar, items, natural) 반환. 네트워크만(DB 미접근)."""
    items, natural = [], True
    for code in CODES:
        try:
            its, nat, _mx = _fetch_code(cortar, code, creds, interface)
        except Exception:
            its, nat = [], False
        items.extend(its)
        natural &= nat
    return cortar, items, natural


def _write_dong(conns: dict, cortar: str, items: list[dict], natural: bool, today: str):
    """메인스레드: 한 동 결과를 4 DB에 기록(직렬). 반환 (total, per_cat, status)."""
    per_cat = {c: 0 for c in CATEGORIES}
    seen = set()
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
    status = "success" if natural else "partial"
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for cat in CATEGORIES:
        conns[cat].execute(
            "INSERT INTO collection_log(cortar_no,run_date,status,n_articles,collected_at) "
            "VALUES(?,?,?,?,?) ON CONFLICT(cortar_no,run_date) DO UPDATE SET "
            "status=excluded.status,n_articles=excluded.n_articles,collected_at=excluded.collected_at",
            (cortar, today, status, per_cat[cat], now))
        conns[cat].commit()
    return len(seen), per_cat, status


def _all_dongs() -> list[str]:
    """전국 동 목록 — naverreal.sqlite 를 ★읽기전용(mode=ro)★으로 열어 단지보유 동(동레벨 10자리)."""
    path = os.path.join(DATA_DIR, "naverreal.sqlite")
    ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return [r[0] for r in ro.execute(
            "SELECT DISTINCT cortar_no FROM complexes "
            "WHERE cortar_no IS NOT NULL AND length(cortar_no)=10 ORDER BY cortar_no")]
    finally:
        ro.close()


def _done_today(conns: dict, today: str) -> set:
    """오늘 이미 success 기록된 동(체크포인트 재개)."""
    done = set()
    for c in conns.values():
        for (cortar,) in c.execute(
                "SELECT cortar_no FROM collection_log WHERE run_date=? AND status='success'", (today,)):
            done.add(cortar)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cortar", default="", help="동 cortarNo (쉼표구분, 테스트용)")
    ap.add_argument("--all", action="store_true", help="전국(단지보유 동) 전체 — 멀티IP")
    ap.add_argument("--limit", type=int, default=0, help="동 개수 제한(테스트)")
    ap.add_argument("--resume", action="store_true",
                    help="오늘 이미 success한 동 스킵(크래시 재개용). 기본은 전수 갱신(3회 루틴).")
    args = ap.parse_args()

    if args.all:
        cortars = _all_dongs()
    else:
        cortars = [c.strip() for c in args.cortar.split(",") if c.strip()]
    if args.limit:
        cortars = cortars[:args.limit]
    if not cortars:
        print("대상 없음 — --all 또는 --cortar 지정.")
        return

    today = datetime.date.today().isoformat()
    creds = ensure_creds()
    conns = {cat: _open(cat) for cat in CATEGORIES}
    ips = [s.strip() for s in (settings.naver_source_ips or "").split(",") if s.strip()] or [None]
    nworkers = max(1, settings.naver_concurrency) * len(ips)

    # 기본: 전수 갱신(매물 3회 루틴 — 매번 모든 동 재수집). --resume만 오늘 완료분 스킵(크래시 재개).
    if args.resume:
        done = _done_today(conns, today)
        todo = [c for c in cortars if c not in done]
    else:
        done, todo = set(), cortars
    print(f"전국 비단지 수집: 대상 {len(cortars)}동 · 스킵 {len(done)} · 진행 {len(todo)} "
          f"· IP {len(ips)}×{settings.naver_concurrency}워커={nworkers}", flush=True)

    n_dong = 0
    grand = {c: 0 for c in CATEGORIES}
    n_partial = 0
    try:
        with ThreadPoolExecutor(max_workers=nworkers) as exe:
            futs = {exe.submit(_fetch_dong, cortar, creds, ips[i % len(ips)]): cortar
                    for i, cortar in enumerate(todo)}
            for fut in as_completed(futs):
                cortar = futs[fut]
                try:
                    _c, items, natural = fut.result()
                except Exception:
                    items, natural = [], False
                total, per_cat, status = _write_dong(conns, cortar, items, natural, today)
                n_dong += 1
                if status == "partial":
                    n_partial += 1
                for cat in CATEGORIES:
                    grand[cat] += per_cat[cat]
                if total > 0 or n_dong % 300 == 0:
                    print(f"  [{cortar}] {total} {per_cat} {status}  ({n_dong}/{len(todo)})", flush=True)

        # delisting 정리 — 전국 전수운영 후에만(부분 실행은 다른 동을 잘못 지움). 2일간 안 보인 매물=빠진 매물.
        if args.all and not args.limit:
            purged = 0
            for cat, c in conns.items():
                cur = c.execute("DELETE FROM listings WHERE snapshot_date < date('now','-2 day')")
                purged += cur.rowcount
                c.commit()
            print(f"delisting 정리: {purged}건 제거(2일+ 미노출)", flush=True)
    finally:
        for c in conns.values():
            c.close()
    print(f"완료: {n_dong}동 처리 · 합계 {grand} · partial(재수집필요) {n_partial}동", flush=True)


if __name__ == "__main__":
    main()
