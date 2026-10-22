"""중개사 사무소 → 행정동(cortar_no) 매핑 — "우리동네 중개사"용.

vworld 등록 중개사(공식 개설등록) 전체를 사무소 소재 동에 매핑한다. naver 매물 매칭 여부와
무관하게 그 동의 '모든' 등록 중개사를 보여주기 위함(매물 없어도 직원·업력 있는 실제 사무소).

realtor_dong(sys_regno PK, cortar_no, realtor_id, dong_name, sgg_cd)

해석 순서 — 앞 단계에서 풀리면 뒤는 보지 않는다.
  1차  vworld_brokers.dong_name 이 그 시군구 regions(sec) 에 그대로 있는 경우. 공부상 값이라 가장 믿을 만하다.
  2차  1차가 안 되면 vworld 주소 원문에서 그 시군구 동명을 찾는다(최장일치).
       ★ 종전에는 dong_name 이 '비어 있을 때만' 돌았다. 그런데 vworld 는 상가 동호수를
         동명 칸에 넣어 주는 일이 많아('상가동' 3,072곳 · '근린생활시설동' · '제상가동' …)
         값이 있는데도 1차에서 떨어지는 8,666곳이 그대로 버려졌다. 이제 '해석 불가'면 넘긴다.
  3차  그래도 안 되면 매칭된 네이버 계정의 cortar_no 를 쓴다. 도로명만 등록된 신축 상가가
       여기서 살아난다(흑석 새봄 — vworld 주소에 동명이 없고 dong_name 은 '상가동').
       ★ 오귀속 0 원칙상 두 가드 중 하나를 반드시 통과해야 한다.
         ① 네이버 주소 원문에 그 동명이 있다(행정동 번호는 떼고 비교 — '사당2동'→'사당동')
         ② vworld 주소와 네이버 주소의 도로명+건물번호가 같다(같은 건물임이 확인됨)
         cortar_no 에는 옛 등록지가 남아 있는 경우가 있어 단독으로 믿으면 안 된다
         (평택 이민재 — 주소는 고덕동인데 cortar_no 는 장안동).
  4차  주소를 VWorld 에 물어 받아 둔 법정동(coord_addr.broker_dong_fwd). 도로명만 등록되고
       네이버 매칭도 없어 세 단계 모두 단서가 없던 사무소가 여기서 살아난다.
       수집은 scripts/geocode_broker_dong.py 가 따로 한다(가드는 거기서 걸러 'ok' 만 온다).
  5차  승계(office_succession)를 반영한다. 대표가 바뀌면 같은 자리에 새 등록번호가 생기는데
       vworld 에는 폐업 기록이 없어 옛 사무소가 계속 '영업'으로 남는다. 후임이 아직 동을
       못 찾았으면 옛 사무소의 동을 물려주고, 옛 행은 지운다.

광주·전남은 코드 체계가 둘이다. regions(네이버 지역 트리)는 통합 전 29xxx·46xxx 로 남아
있고 vworld 는 통합 코드 12xxx 를 쓴다. 시군구 '이름'으로 이어 준다 — 번호는 통합 때 함께
바뀌어서(광양 12190→46230) 숫자로는 맞출 수 없다. 이 리맵이 없으면 광주·전남 5,435곳이
통째로 빠진다(2026-10-22 확인, 당시 realtor_dong 등재 229곳).
"""
import re
import sqlite3
import sys

sys.path.insert(0, ".")
from collector.config import settings  # noqa: E402
from collector.icn_remap import ICN_DONG_REMAP  # noqa: E402

DB = settings.local_db_path
CA = (DB.parent / "coord_addr.sqlite").as_posix()
DRY = "--dry-run" in sys.argv

# 도로명 + 건물번호. '한강대로 95' 처럼 '대로'도 뒤의 '로'로 잡힌다.
_ROAD = re.compile(r"([가-힣A-Za-z0-9·]+(?:로|길))\s*(\d+(?:-\d+)?)")
# 주소에 적힌 동 이름. 행정동 번호는 떼어 법정동명과 견준다('노량진제1동'→'노량진동').
_DONG = re.compile(r"([가-힣]{1,10}?)제?\d*동")


def _road_key(addr):
    m = _ROAD.search(addr or "")
    return (m.group(1), m.group(2)) if m else None


def _dong_words(addr):
    return {m.group(1) + "동" for m in _DONG.finditer(addr or "")}


def _sgg_remap(c):
    """광주·전남 통합코드(12xxx) → regions 가 쓰는 29xxx·46xxx. 시군구 이름으로 1:1."""
    by_name = {}
    for no, nm in c.execute("SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='dvsn' "
                            "AND (cortar_no LIKE '29%' OR cortar_no LIKE '46%')"):
        by_name.setdefault(nm, []).append(no[:5])
    out = {}
    for sgg5, nm in c.execute("SELECT DISTINCT sgg5, sgg_nm FROM bjd WHERE code10 LIKE '12%'"):
        hit = by_name.get(nm)
        if hit and len(hit) == 1:        # 이름이 겹치면 가린 게 아니므로 쓰지 않는다
            out[sgg5] = hit[0]
    return out


def _load_sec(c):
    """시군구5 → [(동명, cortar_no)] (긴 이름 먼저), cortar_no → 동명, 허용쌍 {(시군구5, cortar)}.

    인천은 2026-07 개편으로 중·동·서구(28110·28140·28260)가 없어졌는데 vworld 는 아직 그
    번호로 등록해 두고 regions 는 신설구(제물포·영종·서해·검단)만 들고 있다. 그래서 '중구
    운서동'을 중구에서 찾으면 없고, 그 사무소가 통째로 빠진다(2026-10-22, 인천 75곳).
    검증된 옛동→신동 표(collector/icn_remap, 모호 0)로 옛 구 번호에도 같은 동을 달아 둔다.
    표에 실린 동만 달리므로 다른 구가 섞일 여지는 없다. 등재되는 sgg_cd 는 해석된 cortar 의
    앞 5자리라 신설구로 들어간다 — 노출은 현행 구를 따른다는 기준과 같다.
    """
    byset, name = {}, {}
    for no, nm in c.execute("SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='sec'"):
        byset.setdefault(no[:5], []).append((nm, no))
        name[no] = nm
    for old, new in ICN_DONG_REMAP.items():
        nm = name.get(new)
        if nm and (nm, new) not in byset.get(old[:5], []):
            byset.setdefault(old[:5], []).append((nm, new))
    for k in byset:
        byset[k].sort(key=lambda t: -len(t[0]))
    allowed = {(k, no) for k, v in byset.items() for _, no in v}
    return byset, name, allowed


def _load_links(c):
    """사무소 → 매칭 계정 1건. 1:N 이면 매물 많은 쪽(대표 계정)을 쓴다."""
    out = {}
    for sys_regno, rid, naddr, ncortar, tot in c.execute(
            "SELECT m.sys_regno, m.realtor_id, n.address, n.cortar_no, COALESCE(m.total_listings,0) "
            "FROM realtor_match m LEFT JOIN naver_realtors n ON n.realtor_id = m.realtor_id "
            "WHERE m.sys_regno IS NOT NULL AND m.sys_regno <> ''"):
        cur = out.get(sys_regno)
        if cur is None or tot > cur[3]:
            out[sys_regno] = (rid, naddr, ncortar, tot)
    return out


def _load_geocoded(c):
    """주소를 물어 받아 둔 법정동. 시군구·동명 가드는 수집 쪽에서 이미 통과한 것만 'ok'."""
    try:
        c.execute("ATTACH ? AS ca", (CA,))   # 읽기만 한다. URI 는 ATTACH 에서 안 먹는 환경이 있어 생경로.
    except sqlite3.OperationalError:
        return {}
    try:
        return {sr: (cn, dn) for sr, cn, dn in c.execute(
            "SELECT sys_regno, cortar_no, dong_name FROM ca.broker_dong_fwd "
            "WHERE status='ok' AND cortar_no IS NOT NULL")}
    except sqlite3.OperationalError:
        return {}                       # 아직 수집 전
    finally:
        # 비단지 집계가 DB 10개를 붙인다 — 자리를 돌려주지 않으면 거기서 터진다.
        c.execute("DETACH ca")


def _load_succession(c):
    try:
        return dict(c.execute("SELECT old_regno, new_regno FROM office_succession"))
    except sqlite3.OperationalError:
        return {}


def build_dong(c):
    remap = _sgg_remap(c)
    sec, secname, allowed = _load_sec(c)
    links = _load_links(c)
    # 광주·전남 법정동 코드도 이름으로 29/46 체계로 옮긴다(네이버 계정 cortar 가 12xxx 인 경우).
    sec_remap = {}
    for code10, sgg5, umd in c.execute("SELECT code10, sgg5, umd_nm FROM bjd WHERE code10 LIKE '12%'"):
        tgt = remap.get(sgg5)
        if tgt:
            hit = next((no for nm, no in sec.get(tgt, []) if nm == umd), None)
            if hit:
                sec_remap[code10] = hit

    geo = _load_geocoded(c)
    rows, stat = {}, {"1차": 0, "2차": 0, "3차": 0, "4차": 0, "가드탈락": 0, "미해결": 0}
    for sys_regno, sgg_cd, dong_name, address in c.execute(
            "SELECT sys_regno, sgg_cd, dong_name, address FROM vworld_brokers"):
        eff = remap.get(sgg_cd, sgg_cd)
        cands = sec.get(eff, [])
        addr = address or ""

        hit = next((no for nm, no in cands if nm == dong_name), None) if dong_name else None
        if hit:
            stat["1차"] += 1
        else:
            hit = next((no for nm, no in cands if len(nm) >= 2 and nm in addr), None)
            if hit:
                stat["2차"] += 1
            else:
                link = links.get(sys_regno)
                nc = link[2] if link else None
                nc = sec_remap.get(nc, nc)
                if nc and (eff, nc) in allowed:
                    nm, naddr = secname[nc], (link[1] or "")
                    rk = _road_key(addr)
                    same_dong = nm in naddr or nm in _dong_words(naddr)
                    same_bldg = bool(rk) and rk == _road_key(naddr)
                    if same_dong or same_bldg:
                        hit = nc
                        stat["3차"] += 1
                    else:
                        stat["가드탈락"] += 1
                if hit is None:
                    g = geo.get(sys_regno)
                    if g and (eff, g[0]) in allowed:
                        rows[sys_regno] = (g[0], secname[g[0]], g[0][:5])
                        stat["4차"] += 1
                        continue
                    stat["미해결"] += 1
                    continue
        rows[sys_regno] = (hit, secname.get(hit), hit[:5])

    # 4차 — 승계. 후임이 못 풀렸으면 옛 사무소 자리를 물려받고, 옛 행은 뺀다.
    succ = _load_succession(c)
    inherited = dropped = 0
    for old, new in succ.items():
        if old in rows:
            if new not in rows:
                rows[new] = rows[old]
                inherited += 1
            del rows[old]
            dropped += 1
    print("  1차 공부상 동명 %6d · 2차 주소 해석 %6d · 3차 계정 동코드 %6d · 4차 주소조회 %6d"
          % (stat["1차"], stat["2차"], stat["3차"], stat["4차"]))
    print("  가드 탈락 %d · 미해결 %d · 승계 물려받음 %d · 옛 사무소 제외 %d"
          % (stat["가드탈락"], stat["미해결"], inherited, dropped))
    return [(sr, cn, (links.get(sr) or (None,))[0], dn, sg) for sr, (cn, dn, sg) in rows.items()]


def main():
    if DRY:                      # 해석 결과만 보고 아무것도 쓰지 않는다
        ro = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=300)
        build_dong(ro)
        ro.close()
        return 0
    c = sqlite3.connect(DB)
    c.execute("DROP TABLE IF EXISTS realtor_dong")
    c.execute("""
        CREATE TABLE realtor_dong(
          sys_regno  TEXT PRIMARY KEY,
          cortar_no  TEXT,
          realtor_id TEXT,
          dong_name  TEXT,
          sgg_cd     TEXT
        )""")
    rows = build_dong(c)
    c.executemany("INSERT OR IGNORE INTO realtor_dong(sys_regno, cortar_no, realtor_id, dong_name, sgg_cd) "
                  "VALUES(?,?,?,?,?)", rows)
    c.execute("CREATE INDEX realtor_dong_cortar_idx ON realtor_dong(cortar_no)")
    c.execute("CREATE INDEX realtor_dong_rid_idx ON realtor_dong(realtor_id)")
    c.commit()
    total = c.execute("SELECT COUNT(*) FROM realtor_dong").fetchone()[0]
    dongs = c.execute("SELECT COUNT(DISTINCT cortar_no) FROM realtor_dong").fetchone()[0]
    matched = c.execute("SELECT COUNT(*) FROM realtor_dong WHERE realtor_id IS NOT NULL").fetchone()[0]
    print(f"realtor_dong(office): {total}곳 / {dongs}개 동 / naver매칭 {matched}곳")

    # 비단지(빌라·단독·상가·사무실·토지·공장·빌딩) realtor_id별 매물수 집계 — 랭킹 매물 범위(scope)용.
    # 소스 비단지 DB는 읽기 전용(ATTACH), 파생 집계 테이블만 재생성.
    base = DB.parent
    REGION = [("villa", "listings_villa.sqlite"), ("house", "listings_house.sqlite"),
              ("oneroom", "listings_oneroom.sqlite"),
              ("sangga", "listings_sangga.sqlite"), ("office", "listings_office.sqlite"),
              ("land", "listings_land.sqlite"), ("factory", "listings_factory.sqlite"),
              ("building", "listings_building.sqlite"),
              ("knowledge", "listings_knowledge.sqlite"), ("redev", "listings_redev.sqlite")]
    present = []
    for alias, fn in REGION:
        p = base / fn
        if p.exists():
            c.execute(f"ATTACH '{p.as_posix()}' AS {alias}")
            present.append(alias)
    TYPES = ["villa", "house", "sangga", "office", "land", "factory", "building", "knowledge", "redev", "oneroom"]
    cols = [t + "_n" for t in TYPES]
    coldefs = ", ".join(f"{c0} INT DEFAULT 0" for c0 in cols)

    def _branch(alias: str, per_sido: bool) -> str:
        counts = ", ".join((f"COUNT(*) {c}" if t == alias else f"0 {c}") for t, c in zip(TYPES, cols))
        sido_sel = "substr(cortar_no,1,2) sido, " if per_sido else ""
        whe = " AND cortar_no!=''" if per_sido else ""
        grp = ", substr(cortar_no,1,2)" if per_sido else ""
        return (f"SELECT realtor_id, {sido_sel}{counts} FROM {alias}.listings "
                f"WHERE realtor_id!=''{whe} AND snapshot_date=(SELECT MAX(snapshot_date) FROM {alias}.listings) "
                f"GROUP BY realtor_id{grp}")

    sums = ", ".join(f"SUM({c0})" for c0 in cols)
    c.execute("DROP TABLE IF EXISTS realtor_region_counts")
    c.execute(f"CREATE TABLE realtor_region_counts(realtor_id TEXT PRIMARY KEY, {coldefs})")
    if present:
        union = " UNION ALL ".join(_branch(a, False) for a in present)
        c.execute(f"INSERT INTO realtor_region_counts(realtor_id,{','.join(cols)}) "
                  f"SELECT realtor_id,{sums} FROM ({union}) GROUP BY realtor_id")
    c.execute("DROP TABLE IF EXISTS realtor_region_sido")
    c.execute(f"CREATE TABLE realtor_region_sido(realtor_id TEXT, sido TEXT, {coldefs}, PRIMARY KEY(realtor_id,sido))")
    if present:
        union_s = " UNION ALL ".join(_branch(a, True) for a in present)
        c.execute(f"INSERT INTO realtor_region_sido(realtor_id,sido,{','.join(cols)}) "
                  f"SELECT realtor_id,sido,{sums} FROM ({union_s}) GROUP BY realtor_id,sido")
    c.execute("CREATE INDEX IF NOT EXISTS rrs_sido_idx ON realtor_region_sido(sido)")
    # 단지형(listings_current) 시도×중개사 카운트 미리 집계 — by-sido 랭킹 라이브 풀스캔(2s) 제거.
    c.execute("DROP TABLE IF EXISTS realtor_complex_sido")
    c.execute("""
        CREATE TABLE realtor_complex_sido AS
        SELECT substr(c.cortar_no,1,2) sido, l.realtor_id, COUNT(*) n
        FROM listings_current l JOIN complexes c ON c.complex_no=l.complex_no
        WHERE l.realtor_id IS NOT NULL AND l.realtor_id!='' AND c.cortar_no IS NOT NULL
        GROUP BY substr(c.cortar_no,1,2), l.realtor_id
    """)
    c.execute("CREATE INDEX IF NOT EXISTS rcs_sido_idx ON realtor_complex_sido(sido)")
    # 전체 매물수(단지형+비단지) 합산 — 중개사 세부 '전체 순위'용.
    c.execute("DROP TABLE IF EXISTS realtor_total")
    c.execute("""
        CREATE TABLE realtor_total AS
        SELECT realtor_id, SUM(n) total_n FROM (
          SELECT realtor_id, COALESCE(total_listings,0) n FROM realtor_match WHERE total_listings>0
          UNION ALL
          SELECT realtor_id, (villa_n+house_n+sangga_n+office_n+land_n+factory_n+building_n+knowledge_n+redev_n+COALESCE(oneroom_n,0)) n FROM realtor_region_counts
        ) WHERE realtor_id IS NOT NULL AND realtor_id!='' GROUP BY realtor_id
    """)
    c.execute("CREATE INDEX IF NOT EXISTS rt_total_idx ON realtor_total(total_n)")
    # 통합 중개사명(naver_realtors + 비단지 매물명) — 랭킹 이름 표시용.
    c.execute("DROP TABLE IF EXISTS realtor_names")
    c.execute("CREATE TABLE realtor_names(realtor_id TEXT PRIMARY KEY, realtor_name TEXT)")
    c.execute("INSERT OR REPLACE INTO realtor_names SELECT realtor_id, realtor_name FROM naver_realtors "
              "WHERE realtor_id IS NOT NULL AND realtor_name IS NOT NULL")
    for alias in present:
        c.execute(f"INSERT OR IGNORE INTO realtor_names SELECT realtor_id, MAX(realtor_name) "
                  f"FROM {alias}.listings WHERE realtor_id!='' AND realtor_name!='' GROUP BY realtor_id")
    c.commit()
    rc = c.execute("SELECT COUNT(*) FROM realtor_region_counts").fetchone()[0]
    tot = c.execute("SELECT SUM(villa_n+house_n+sangga_n+office_n+land_n+factory_n+building_n) FROM realtor_region_counts").fetchone()[0]
    print(f"realtor_region_counts(비단지 집계): {rc}곳 · 매물 {tot:,}")
    c.close()


if __name__ == "__main__":
    main()
