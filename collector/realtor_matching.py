"""Naver realtor_id ↔ vworld broker(sys_regno) 매칭.

매칭 전략:
  1. Naver realtor의 주 활동 시군구(sgg) 결정 (매물 cortar_no 앞 5자리).
  2. 양쪽 상호명 정규화 (공인중개사/사무소/공백/괄호/구두점 제거).
  3. 같은 sgg에서 정확 매치(1:1) → 'exact'.
  4. 같은 sgg에서 부분 매치 (정규화 후 substring 양방향) → 'fuzzy'.
  5. 매칭 후보가 여러 개면 → 'multi' + candidates_json 보관.
  6. 0개면 'none'.

전화번호 매칭은 detail crawl 완료 후 별도 단계로 추가 가능.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime
from typing import Iterable

# 상호명 잡음 키워드 — 정규화 시 제거 대상.
_NOISE_KEYWORDS = [
    "공인중개사사무소",
    "공인중개사무소",
    "공인중개사",
    "부동산공인중개사",
    "부동산중개법인주식회사",
    "부동산중개법인",
    "부동산중개사무소",
    "부동산중개",
    "중개법인주식회사",
    "중개법인",
    "중개사무소",
    "사무소",
    "법인",
    "주식회사",
    "(주)",
    "(유)",
]

# 매물 상호에 자주 붙는 일반 수식어 — 매칭엔 잡음.
_GENERIC_PREFIXES = [
    "단지내",
    "분양권",
    "분양",
    "아파트전문",
    "아파트",
    "with.",
    "with",
]

# 정규화: noise 키워드 제거, 공백/구두점/한자 부호류 제거, 소문자.
_PUNCT_RE = re.compile(r"[\s\-_\.·…,()\[\]『』「」<>＆&]+")
_PAREN_RE = re.compile(r"\([^)]*\)")
_DIGITS_RE = re.compile(r"\d+")


def normalize_name(name: str | None, *, strip_digits: bool = False) -> str:
    """정규화. strip_digits=True이면 숫자도 제거 (loose 매칭용 fallback)."""
    if not name:
        return ""
    s = name
    # 1. drop bracketed (단지점/지점/전화번호 등)
    s = _PAREN_RE.sub("", s)
    # 2. strict 모드는 숫자 보존 — '고덕365' vs '고덕8000' 구분 유지.
    if strip_digits:
        s = _DIGITS_RE.sub("", s)
    # 3. drop noise keywords
    for kw in _NOISE_KEYWORDS:
        s = s.replace(kw, "")
    # 4. drop generic prefixes
    for kw in _GENERIC_PREFIXES:
        s = s.replace(kw, "")
    # 5. drop whitespace + punctuation
    s = _PUNCT_RE.sub("", s)
    return s.strip().lower()


def fill_vworld_normalized(conn: sqlite3.Connection, batch: int = 5000) -> int:
    """Backfill vworld_brokers.normalized_name (strict) + normalized_loose + dong_name."""
    cur = conn.execute(
        "SELECT sys_regno, business_name, address FROM vworld_brokers "
        "WHERE normalized_name IS NULL OR normalized_loose IS NULL OR dong_name IS NULL"
    )
    n = 0
    buf: list[tuple[str, str, str, str]] = []
    for sys_regno, name, addr in cur.fetchall():
        buf.append((
            normalize_name(name),  # strict (digits kept)
            normalize_name(name, strip_digits=True),  # loose
            extract_dong(addr),
            sys_regno,
        ))
        if len(buf) >= batch:
            conn.executemany(
                "UPDATE vworld_brokers SET normalized_name=?, normalized_loose=?, dong_name=? WHERE sys_regno=?",
                buf,
            )
            n += len(buf)
            buf = []
    if buf:
        conn.executemany(
            "UPDATE vworld_brokers SET normalized_name=?, normalized_loose=?, dong_name=? WHERE sys_regno=?",
            buf,
        )
        n += len(buf)
    conn.commit()
    return n


# vworld 주소 끝: "...(반포동, 단지명)" 또는 "...(반포동)" 또는 "...(반포동, ...)" 패턴.
_DONG_RE = re.compile(r"\(([가-힣]+동)(?:[\),])")
# fallback: 주소 본문에 있는 "XX동" — 동 다음 공백/숫자/괄호/문장끝 OK
# (Naver address: '권선구 곡반정동652 ...' 같이 동 다음에 공백 없이 숫자 오는 경우 포함)
_DONG_INLINE_RE = re.compile(r"([가-힣]{2,6}동)(?=[\s\d\(,]|$)")


def extract_dong(address: str | None) -> str | None:
    if not address:
        return None
    m = _DONG_RE.search(address)
    if m:
        return m.group(1)
    m = _DONG_INLINE_RE.search(address)
    if m:
        return m.group(1)
    return None


def naver_realtors_with_sgg(conn: sqlite3.Connection) -> Iterable[tuple]:
    """For each Naver realtor_id, returns (id, name, primary_sgg, count, total, primary_dong)."""
    # 동 이름은 매물 단지의 cortar_no(앞 8자리)로 찾는다 — regions.cortar_type='sec'.
    rows = conn.execute(
        """
        WITH per_sgg AS (
            SELECT l.realtor_id,
                   MAX(l.realtor_name) AS realtor_name,
                   substr(c.cortar_no, 1, 5) AS sgg,
                   COUNT(*) AS n
            FROM listings_current l
            JOIN complexes c ON c.complex_no = l.complex_no
            WHERE l.realtor_id IS NOT NULL AND c.cortar_no IS NOT NULL
            GROUP BY l.realtor_id, sgg
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY realtor_id ORDER BY n DESC) AS rk,
                   SUM(n) OVER (PARTITION BY realtor_id) AS total
            FROM per_sgg
        ),
        per_dong AS (
            SELECT l.realtor_id, c.cortar_no AS dong_cno, COUNT(*) AS dn
            FROM listings_current l
            JOIN complexes c ON c.complex_no = l.complex_no
            WHERE l.realtor_id IS NOT NULL
            GROUP BY l.realtor_id, c.cortar_no
        ),
        ranked_dong AS (
            SELECT realtor_id, dong_cno,
                   ROW_NUMBER() OVER (PARTITION BY realtor_id ORDER BY dn DESC) AS rk
            FROM per_dong
        ),
        primary_dong AS (
            SELECT rd.realtor_id, r.cortar_name AS dong_name
            FROM ranked_dong rd
            LEFT JOIN regions r ON r.cortar_no = rd.dong_cno AND r.cortar_type='sec'
            WHERE rd.rk = 1
        )
        SELECT k.realtor_id, k.realtor_name, k.sgg, k.n, k.total, d.dong_name
        FROM ranked k
        LEFT JOIN primary_dong d USING (realtor_id)
        WHERE k.rk = 1
        """
    ).fetchall()
    return rows


_PHONE_RE = re.compile(r"(\d{2,3})[-.\s]?(\d{3,4})[-.\s]?(\d{4})")

# 표준 + 선택적 분사무소 일련번호 '-NNN'
# 공인중개사법 제13조의2: 법인 분사무소는 본사 등록번호 + '-일련번호' 형식
_REGNO_STD_RE = re.compile(r"(\d{4,5})-(\d{4})-(\d{4,6})(?:-(\d{1,3}))?")
# 하이픈 없는 연속 숫자 (14자리=본사, 17자리=분사무소)
_REGNO_NOHYPHEN_RE = re.compile(r"^(\d{5})(\d{4})(\d{5})(\d{1,3})?$")


_SIDO_NAMES = (
    "서울특별시", "서울시", "서울",
    "부산광역시", "부산시", "부산",
    "대구광역시", "대구시", "대구",
    "인천광역시", "인천시", "인천",
    "광주광역시", "광주시", "광주",
    "대전광역시", "대전시", "대전",
    "울산광역시", "울산시", "울산",
    "세종특별자치시", "세종시", "세종",
    "경기도", "경기",
    "강원특별자치도", "강원도", "강원",
    "충청북도", "충북",
    "충청남도", "충남",
    "전북특별자치도", "전라북도", "전북",
    "전라남도", "전남",
    "경상북도", "경북",
    "경상남도", "경남",
    "제주특별자치도", "제주도", "제주",
)
# 시도 표기 정규화 — '서울', '서울시', '서울특별시' → '서울'
_SIDO_NORM = {
    "서울": "서울", "서울시": "서울", "서울특별시": "서울",
    "부산": "부산", "부산시": "부산", "부산광역시": "부산",
    "대구": "대구", "대구시": "대구", "대구광역시": "대구",
    "인천": "인천", "인천시": "인천", "인천광역시": "인천",
    "광주": "광주", "광주시": "광주", "광주광역시": "광주",
    "대전": "대전", "대전시": "대전", "대전광역시": "대전",
    "울산": "울산", "울산시": "울산", "울산광역시": "울산",
    "세종": "세종", "세종시": "세종", "세종특별자치시": "세종",
    "경기": "경기", "경기도": "경기",
    "강원": "강원", "강원도": "강원", "강원특별자치도": "강원",
    "충북": "충북", "충청북도": "충북",
    "충남": "충남", "충청남도": "충남",
    "전북": "전북", "전라북도": "전북", "전북특별자치도": "전북",
    "전남": "전남", "전라남도": "전남",
    "경북": "경북", "경상북도": "경북",
    "경남": "경남", "경상남도": "경남",
    "제주": "제주", "제주도": "제주", "제주특별자치도": "제주",
}
_SGG_TOKEN_RE = re.compile(r"([가-힣]+(?:구|시|군))")


def addr_sgg_key(addr: str | None) -> str | None:
    """주소 텍스트에서 '시도-시군구' 키 추출. 예: '서울특별시 강남구 도곡동...' → '서울-강남구'.
    매칭 안 되면 None."""
    if not addr:
        return None
    s = addr.strip()
    tokens = s.split()
    if not tokens:
        return None
    sido = _SIDO_NORM.get(tokens[0])
    if not sido:
        # 첫 토큰이 시도 prefix가 아닌 경우 — '광주광역시'가 한 단어로 안 떨어졌을 수도
        for sn in _SIDO_NAMES:
            if s.startswith(sn):
                sido = _SIDO_NORM.get(sn)
                # rest 잘라내기
                s = s[len(sn):].strip()
                tokens = s.split()
                break
        if not sido:
            return None
    # 시군구: 다음 토큰 중 '구/시/군'으로 끝나는 첫 것
    # tokens가 시도 다음부터 시작인 경우와 시도 포함인 경우 둘 다 처리
    rest = " ".join(tokens[1:]) if (tokens and _SIDO_NORM.get(tokens[0])) else " ".join(tokens)
    m = _SGG_TOKEN_RE.search(rest)
    if not m:
        return None
    return f"{sido}-{m.group(1)}"


def normalize_regno(regno: str | None) -> str | None:
    """Naver 등록번호 변형들 → vworld 표준 포맷으로 정규화.
    - '제42130-2017-00121호' → '42130-2017-00121'
    - '11110202000072' → '11110-2020-00072' (하이픈 없는 14자리)
    - '가3702-536호' → '가3702-536' ('호'만 제거, 한글 prefix는 유지)
    - 매칭 불가능한 짧은 숫자('3223')는 그대로 반환.
    """
    if not regno:
        return None
    s = regno.strip()
    # '제'/'호' 같은 한글 데코 제거 (단, '가XXXX-공XXXX' 의 '가'/'공'은 유지)
    s = s.replace("호", "").strip()
    if s.startswith("제"):
        s = s[1:].strip()
    # 표준 포맷 (분사무소 일련번호 보존)
    m = _REGNO_STD_RE.search(s)
    if m:
        base = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        if m.group(4):
            return f"{base}-{m.group(4).zfill(3)}"
        return base
    # 하이픈 없는 연속 숫자 (14~17자리)
    m = _REGNO_NOHYPHEN_RE.match(s)
    if m:
        base = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        if m.group(4):
            return f"{base}-{m.group(4).zfill(3)}"
        return base
    return s


def normalize_phone(phone: str | None) -> str:
    """Returns digit-only phone, or '' if none."""
    if not phone:
        return ""
    return re.sub(r"\D+", "", phone)


def extract_phone(text: str | None) -> str | None:
    """First phone-looking pattern in text, normalized to digits."""
    if not text:
        return None
    m = _PHONE_RE.search(text)
    if not m:
        return None
    return "".join(m.groups())


def match_one(
    conn: sqlite3.Connection,
    realtor_id: str,
    naver_name: str,
    primary_sgg: str,
    primary_dong: str | None = None,
) -> dict:
    """Match a single Naver realtor against vworld_brokers."""
    # phone-first: Naver 상호에 전화번호가 임베드된 경우, 그 phone으로 직매칭.
    phone_in_name = extract_phone(naver_name)
    if phone_in_name and len(phone_in_name) >= 9:
        rows = conn.execute(
            """
            SELECT sys_regno, business_name, representative, dong_name
            FROM vworld_brokers
            WHERE phone IS NOT NULL
              AND REPLACE(REPLACE(REPLACE(phone, '-', ''), '.', ''), ' ', '') LIKE ?
            LIMIT 5
            """,
            (f"%{phone_in_name}%",),
        ).fetchall()
        if len(rows) == 1:
            return _result("phone_in_name", rows)

    norm_strict = normalize_name(naver_name)
    norm_loose = normalize_name(naver_name, strip_digits=True)
    if not norm_strict:
        return {"match_type": "none", "candidates": []}

    # 1) 같은 sgg 정확 매치 (strict — 숫자 보존)
    rows = conn.execute(
        """
        SELECT sys_regno, business_name, representative, dong_name, registered_ymd
        FROM vworld_brokers
        WHERE sgg_cd=? AND normalized_name=?
        """,
        (primary_sgg, norm_strict),
    ).fetchall()
    if len(rows) == 1:
        return _result("exact_sgg", rows)
    if len(rows) > 1:
        # dong 단위로 narrow
        if primary_dong:
            same_dong = [r for r in rows if r[3] == primary_dong]
            if len(same_dong) == 1:
                return _result("exact_sgg_dong", same_dong)
            if len(same_dong) > 1:
                # 동에 같은 이름이 여러 곳 = 가장 최근 등록(현재 운영)으로 추정.
                pick = max(same_dong, key=lambda r: r[4] or "")
                return _result("exact_sgg_dong_recent", [pick])
        return _result("multi_exact_sgg", rows)

    # 1b) loose 매치 (전화번호 임베드된 Naver 이름 → vworld는 phone 없는 이름과 매칭)
    if norm_loose and norm_loose != norm_strict:
        rows = conn.execute(
            """
            SELECT sys_regno, business_name, representative, dong_name, registered_ymd
            FROM vworld_brokers
            WHERE sgg_cd=? AND normalized_loose=?
            """,
            (primary_sgg, norm_loose),
        ).fetchall()
        if len(rows) == 1:
            return _result("exact_sgg_loose", rows)
        if len(rows) > 1:
            if primary_dong:
                same_dong = [r for r in rows if r[3] == primary_dong]
                if len(same_dong) == 1:
                    return _result("exact_sgg_dong_loose", same_dong)
                if len(same_dong) > 1:
                    pick = max(same_dong, key=lambda r: r[4] or "")
                    return _result("exact_sgg_dong_loose_recent", [pick])
            return _result("multi_exact_sgg_loose", rows)

    # 1c) 전국 strict 매치 — Naver realtor 매물 sgg와 사무소 사무 sgg가 다를 수 있음
    # (예: 아산 매물 다수, 사무소는 천안에 등록). primary_sgg에 정확 일치가 없으면
    # 전국에서 정확 일치 1:1로 잡힐 때만 채택.
    rows = conn.execute(
        """
        SELECT sys_regno, business_name, representative, dong_name, registered_ymd, sgg_cd
        FROM vworld_brokers
        WHERE normalized_name=?
        LIMIT 30
        """,
        (norm_strict,),
    ).fetchall()
    if len(rows) == 1:
        # 한 시군구에 unique한 이름 → 전국에서도 1개라면 정답
        return _result("exact_global_strict", rows)
    if len(rows) > 1:
        # 전국 여러 개: primary_dong과 같은 동의 후보 1개면 채택
        if primary_dong:
            same_dong = [r for r in rows if r[3] == primary_dong]
            if len(same_dong) == 1:
                return _result("exact_global_strict_dong", same_dong)

    # 2) 같은 sgg 양방향 substring (loose 정규화 기준 — 숫자 영향 안 받게)
    nm = norm_loose or norm_strict
    rows = conn.execute(
        """
        SELECT sys_regno, business_name, representative, dong_name, registered_ymd
        FROM vworld_brokers
        WHERE sgg_cd=? AND (
            normalized_loose LIKE ?
            OR ? LIKE '%' || normalized_loose || '%'
        )
        AND normalized_loose IS NOT NULL AND length(normalized_loose) >= 2
        """,
        (primary_sgg, f"%{nm}%", nm),
    ).fetchall()
    if len(rows) == 1:
        return _result("fuzzy_sgg", rows)
    if len(rows) > 1:
        if primary_dong:
            same_dong = [r for r in rows if r[3] == primary_dong]
            if len(same_dong) == 1:
                return _result("fuzzy_sgg_dong", same_dong)
            if len(same_dong) > 1:
                pick = max(same_dong, key=lambda r: r[4] or "")
                return _result("fuzzy_sgg_dong_recent", [pick])
        return _result("multi_fuzzy_sgg", rows)

    # 3) 전국 정확 매치 (strict)
    rows = conn.execute(
        """
        SELECT sys_regno, business_name, representative, dong_name, registered_ymd
        FROM vworld_brokers
        WHERE normalized_name=?
        LIMIT 30
        """,
        (norm_strict,),
    ).fetchall()
    if len(rows) == 1:
        return _result("exact_global", rows)
    if len(rows) > 1:
        if primary_dong:
            same_dong = [r for r in rows if r[3] == primary_dong]
            if len(same_dong) == 1:
                return _result("exact_global_dong", same_dong)
        return _result("multi_exact_global", rows[:10])

    return {"match_type": "none", "candidates": []}


def _result(kind: str, rows: list) -> dict:
    # rows: (sys_regno, name, rep, dong, registered_ymd) — UI엔 sys_regno/name/rep만 필요.
    cands = [
        {"sys_regno": r[0], "name": r[1], "rep": r[2]} for r in rows
    ]
    return {"match_type": kind, "candidates": cands}


def run_matching(conn: sqlite3.Connection, verbose: bool = False) -> dict[str, int]:
    """Run matching for all Naver realtors. Returns counts by match_type."""
    t0 = time.time()
    n_filled = fill_vworld_normalized(conn)
    print(f"  normalized_name filled: {n_filled} rows", flush=True)

    realtors = naver_realtors_with_sgg(conn)
    print(f"  Naver realtors to match: {len(realtors)}", flush=True)
    now = datetime.now().isoformat(timespec="seconds")
    stats: dict[str, int] = {}
    for i, (rid, name, sgg, n_listings, total, dong) in enumerate(realtors, 1):
        r = match_one(conn, rid, name, sgg, primary_dong=dong)
        kind = r["match_type"]
        cands = r["candidates"]
        sys_regno = cands[0]["sys_regno"] if len(cands) == 1 and not kind.startswith("multi") else None
        vname = cands[0]["name"] if len(cands) == 1 and not kind.startswith("multi") else None
        vrep = cands[0]["rep"] if len(cands) == 1 and not kind.startswith("multi") else None
        cands_json = json.dumps(cands, ensure_ascii=False) if cands else None
        conn.execute(
            """
            INSERT INTO realtor_match
                (realtor_id, naver_name, primary_sgg_cd, primary_sgg_count, total_listings,
                 sys_regno, vworld_name, vworld_rep, match_type, candidates_json, matched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(realtor_id) DO UPDATE SET
                naver_name=excluded.naver_name,
                primary_sgg_cd=excluded.primary_sgg_cd,
                primary_sgg_count=excluded.primary_sgg_count,
                total_listings=excluded.total_listings,
                sys_regno=excluded.sys_regno,
                vworld_name=excluded.vworld_name,
                vworld_rep=excluded.vworld_rep,
                match_type=excluded.match_type,
                candidates_json=excluded.candidates_json,
                matched_at=excluded.matched_at
            """,
            (rid, name, sgg, n_listings, total, sys_regno, vname, vrep,
             kind, cands_json, now),
        )
        stats[kind] = stats.get(kind, 0) + 1
        if i % 5000 == 0:
            conn.commit()
            print(f"  [{i}/{len(realtors)}]  {time.time()-t0:.1f}s  {stats}", flush=True)
    conn.commit()
    print(f"  total: {time.time()-t0:.1f}s", flush=True)
    return stats
