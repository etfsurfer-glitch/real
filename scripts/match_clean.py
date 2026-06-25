"""중개사무소 매칭 파이프라인 — 깨끗한 재실행.

규칙:
  1. 등록번호 (regno_exact) — 100% 신뢰. naver.establishRegistrationNo ↔ vworld.ra_regno
  2. 주소(시도+시군구+동) + 이름 — 같은 동이 다른 시에도 있을 수 있어 시단위까지 체크
     (regno 없거나 매칭 실패한 케이스만)
  3. 대표자명 + 전화번호 AND — 최종 보완

매번 realtor_match를 TRUNCATE하고 처음부터 다시 채움.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realtor_matching import (  # noqa: E402
    addr_sgg_key,
    extract_dong,
    fill_vworld_normalized,
    normalize_name,
    normalize_regno,
)


def open_db() -> sqlite3.Connection:
    c = sqlite3.connect(settings.local_db_path, timeout=30.0)
    c.execute("PRAGMA busy_timeout=30000")
    c.row_factory = sqlite3.Row
    return c


def normalize_phone_digits(phone: str | None) -> str:
    if not phone:
        return ""
    return re.sub(r"\D+", "", phone)


def step1_regno(conn) -> int:
    """등록번호로 1:1 매칭. naver.establishRegistrationNo ↔ vworld.ra_regno."""
    # vworld index: normalized ra_regno → (sys_regno, name, rep)
    vw_by_regno = {}
    dup = 0
    for r in conn.execute("SELECT sys_regno, ra_regno, business_name, representative FROM vworld_brokers WHERE ra_regno IS NOT NULL"):
        nrk = normalize_regno(r["ra_regno"])
        if not nrk:
            continue
        if nrk in vw_by_regno:
            dup += 1
            continue
        vw_by_regno[nrk] = (r["sys_regno"], r["business_name"], r["representative"])
    print(f"  vworld indexed by regno: {len(vw_by_regno):,}  (dup skipped: {dup})", flush=True)

    matched = 0
    now = datetime.now().isoformat(timespec="seconds")
    for r in conn.execute(
        "SELECT realtor_id, establish_registration_no FROM naver_realtors WHERE establish_registration_no IS NOT NULL"
    ):
        nk = normalize_regno(r["establish_registration_no"])
        if not nk:
            continue
        hit = vw_by_regno.get(nk)
        if not hit:
            continue
        sys_regno, vname, vrep = hit
        conn.execute(
            """
            INSERT INTO realtor_match
                (realtor_id, sys_regno, vworld_name, vworld_rep, match_type, matched_at)
            VALUES (?, ?, ?, ?, 'regno_exact', ?)
            ON CONFLICT(realtor_id) DO UPDATE SET
                sys_regno=excluded.sys_regno,
                vworld_name=excluded.vworld_name,
                vworld_rep=excluded.vworld_rep,
                match_type=excluded.match_type,
                matched_at=excluded.matched_at
            """,
            (r["realtor_id"], sys_regno, vname, vrep, now),
        )
        matched += 1
    conn.commit()
    return matched


def step2_addr_name(conn) -> int:
    """주소(시도+시군구+동) + 정규화 이름 AND 매칭."""
    # vworld index: (sgg_key, dong, norm_name) → list[(sys_regno, name, rep)]
    vw_idx: dict[tuple[str, str, str], list] = {}
    for r in conn.execute(
        "SELECT sys_regno, business_name, representative, address, normalized_name, dong_name FROM vworld_brokers"
    ):
        sgg_key = addr_sgg_key(r["address"])
        dong = r["dong_name"] or extract_dong(r["address"])
        norm = r["normalized_name"]
        if not (sgg_key and dong and norm):
            continue
        k = (sgg_key, dong, norm)
        vw_idx.setdefault(k, []).append((r["sys_regno"], r["business_name"], r["representative"]))
    print(f"  vworld indexed by (sgg,dong,name): {len(vw_idx):,}", flush=True)

    # 아직 매칭 안 된 Naver realtor (regno로 안 잡힌)
    pending = conn.execute(
        """
        SELECT nr.realtor_id, nr.realtor_name, nr.address, nr.representative_name
        FROM naver_realtors nr
        LEFT JOIN realtor_match m ON m.realtor_id = nr.realtor_id
        WHERE m.sys_regno IS NULL AND nr.address IS NOT NULL AND nr.realtor_name IS NOT NULL
        """
    ).fetchall()
    print(f"  pending naver realtors with addr+name: {len(pending):,}", flush=True)

    matched = 0
    ambiguous = 0
    now = datetime.now().isoformat(timespec="seconds")
    for r in pending:
        sgg_key = addr_sgg_key(r["address"])
        dong = extract_dong(r["address"])
        norm = normalize_name(r["realtor_name"])
        if not (sgg_key and dong and norm):
            continue
        cands = vw_idx.get((sgg_key, dong, norm))
        if not cands:
            continue
        if len(cands) > 1:
            # 대표자명 일치하는 후보 1개면 채택
            naver_rep = r["representative_name"]
            if naver_rep:
                same_rep = [c for c in cands if c[2] == naver_rep]
                if len(same_rep) == 1:
                    cands = same_rep
                else:
                    ambiguous += 1
                    continue
            else:
                ambiguous += 1
                continue
        sys_regno, vname, vrep = cands[0]
        conn.execute(
            """
            INSERT INTO realtor_match
                (realtor_id, sys_regno, vworld_name, vworld_rep, match_type, matched_at)
            VALUES (?, ?, ?, ?, 'addr_name', ?)
            ON CONFLICT(realtor_id) DO UPDATE SET
                sys_regno=excluded.sys_regno,
                vworld_name=excluded.vworld_name,
                vworld_rep=excluded.vworld_rep,
                match_type=excluded.match_type,
                matched_at=excluded.matched_at
            """,
            (r["realtor_id"], sys_regno, vname, vrep, now),
        )
        matched += 1
    conn.commit()
    if ambiguous:
        print(f"  (ambiguous skipped: {ambiguous})", flush=True)
    return matched


def step2b_sgg_name(conn) -> int:
    """step2 보완: dong이 NULL이거나 (sgg+dong+name)으로 못 잡은 경우,
    (sgg+name)으로 매칭 시도. 대표자가 일치하면 ambiguous 해소."""
    # vworld index by (sgg_key, normalized_name)
    vw_idx: dict[tuple[str, str], list] = {}
    for r in conn.execute(
        "SELECT sys_regno, business_name, representative, address, normalized_name FROM vworld_brokers"
    ):
        sgg_key = addr_sgg_key(r["address"])
        norm = r["normalized_name"]
        if not (sgg_key and norm and len(norm) >= 2):
            continue
        vw_idx.setdefault((sgg_key, norm), []).append(
            (r["sys_regno"], r["business_name"], r["representative"])
        )

    pending = conn.execute(
        """
        SELECT nr.realtor_id, nr.realtor_name, nr.address, nr.representative_name
        FROM naver_realtors nr
        LEFT JOIN realtor_match m ON m.realtor_id = nr.realtor_id
        WHERE m.sys_regno IS NULL AND nr.address IS NOT NULL AND nr.realtor_name IS NOT NULL
        """
    ).fetchall()
    print(f"  pending naver realtors with addr+name (sgg only): {len(pending):,}", flush=True)

    matched = 0
    ambiguous = 0
    now = datetime.now().isoformat(timespec="seconds")
    for r in pending:
        sgg_key = addr_sgg_key(r["address"])
        norm = normalize_name(r["realtor_name"])
        if not (sgg_key and norm):
            continue
        cands = vw_idx.get((sgg_key, norm))
        if not cands:
            continue
        if len(cands) > 1:
            naver_rep = r["representative_name"]
            if naver_rep:
                same_rep = [c for c in cands if c[2] == naver_rep]
                if len(same_rep) == 1:
                    cands = same_rep
                else:
                    ambiguous += 1
                    continue
            else:
                ambiguous += 1
                continue
        sys_regno, vname, vrep = cands[0]
        conn.execute(
            """
            INSERT INTO realtor_match
                (realtor_id, sys_regno, vworld_name, vworld_rep, match_type, matched_at)
            VALUES (?, ?, ?, ?, 'sgg_name', ?)
            ON CONFLICT(realtor_id) DO UPDATE SET
                sys_regno=excluded.sys_regno,
                vworld_name=excluded.vworld_name,
                vworld_rep=excluded.vworld_rep,
                match_type=excluded.match_type,
                matched_at=excluded.matched_at
            """,
            (r["realtor_id"], sys_regno, vname, vrep, now),
        )
        matched += 1
    conn.commit()
    if ambiguous:
        print(f"  (ambiguous skipped: {ambiguous})", flush=True)
    return matched


def _addr_key(addr: str | None) -> str:
    """도로명+번지(+호) 정규화 — 괄호(법정동) 제거 후 'OO로NN-NN호' 형태. 같은 건물 식별용."""
    if not addr:
        return ""
    a = re.sub(r"\([^)]*\)", "", addr)
    a = re.sub(r"\s+", "", a).replace(",", "")
    m = re.search(r"(.+?[로길]\d+[-\d]*)(\d+호)?", a)
    return (m.group(1) + (m.group(2) or "")) if m else a


def step4_addr_rep(conn) -> int:
    """도로명+번지(상세주소) + 대표자명 유일일치. regno·이름·전화 다 실패한 잔여를 보완.
    이름 표기차(부동산 접미·오타·법인격)·전화 불일치(대표번호 vs 등록번호)로 누락되던
    명백한 동일사무소(같은 건물·같은 대표)를 잡는다. 유일일치만 채택(모호 스킵)."""
    from collections import defaultdict
    vw_idx: dict[tuple, list] = defaultdict(list)
    for r in conn.execute(
        "SELECT sys_regno, business_name, representative, address, status FROM vworld_brokers "
        "WHERE representative IS NOT NULL AND address IS NOT NULL"
    ):
        sgg = addr_sgg_key(r["address"]); ak = _addr_key(r["address"])
        if sgg and ak:
            vw_idx[(sgg, ak, r["representative"])].append(
                (r["sys_regno"], r["business_name"], r["representative"], r["status"]))
    pending = conn.execute(
        """
        SELECT nr.realtor_id, nr.representative_name, nr.address
        FROM naver_realtors nr LEFT JOIN realtor_match m ON m.realtor_id = nr.realtor_id
        WHERE m.sys_regno IS NULL AND nr.representative_name IS NOT NULL AND nr.address IS NOT NULL
        """
    ).fetchall()
    print(f"  pending with addr+rep: {len(pending):,}", flush=True)
    matched = ambiguous = 0
    now = datetime.now().isoformat(timespec="seconds")
    for r in pending:
        sgg = addr_sgg_key(r["address"]); ak = _addr_key(r["address"])
        cands = vw_idx.get((sgg, ak, r["representative_name"]))
        if not cands:
            continue
        if len(cands) > 1:
            ambiguous += 1
            continue  # 같은 건물에 같은 대표 여러 사무소 → 모호, 스킵
        sysno, bn, rep, stt = cands[0]
        conn.execute(
            """INSERT INTO realtor_match(realtor_id, sys_regno, vworld_name, vworld_rep, match_type, matched_at, vworld_status)
               VALUES (?,?,?,?,'addr_rep',?,?)
               ON CONFLICT(realtor_id) DO UPDATE SET sys_regno=excluded.sys_regno,
                 vworld_name=excluded.vworld_name, vworld_rep=excluded.vworld_rep, match_type=excluded.match_type""",
            (r["realtor_id"], sysno, bn, rep, now, stt))
        matched += 1
    print(f"  step4 addr+rep matched: {matched:,}  (ambiguous skipped: {ambiguous})", flush=True)
    return matched


def step3_rep_phone(conn) -> int:
    """대표자명 + 전화번호 AND 매칭."""
    # vworld index: (representative, phone_digits) — substring matching on phone
    # phone digits stored normalized; if multiple phones in field, store list
    vw_rep_phones: dict[str, list[tuple[str, str, str, str]]] = {}
    for r in conn.execute(
        "SELECT sys_regno, business_name, representative, phone FROM vworld_brokers WHERE representative IS NOT NULL AND phone IS NOT NULL"
    ):
        rep = r["representative"]
        phones_raw = r["phone"]
        # phone field: '032-577-7779 010-5777-7234' 같이 여러 번호 가능
        all_digits = normalize_phone_digits(phones_raw)
        vw_rep_phones.setdefault(rep, []).append((r["sys_regno"], r["business_name"], rep, all_digits))
    print(f"  vworld reps with phone: {len(vw_rep_phones):,}", flush=True)

    pending = conn.execute(
        """
        SELECT nr.realtor_id, nr.representative_name, nr.representative_tel_no, nr.cell_phone_no
        FROM naver_realtors nr
        LEFT JOIN realtor_match m ON m.realtor_id = nr.realtor_id
        WHERE m.sys_regno IS NULL
          AND nr.representative_name IS NOT NULL
          AND (nr.representative_tel_no IS NOT NULL OR nr.cell_phone_no IS NOT NULL)
        """
    ).fetchall()
    print(f"  pending with rep+phone: {len(pending):,}", flush=True)

    matched = 0
    ambiguous = 0
    now = datetime.now().isoformat(timespec="seconds")
    for r in pending:
        rep = r["representative_name"]
        # 두 phone 후보 (대표 전화 + 핸드폰)
        naver_digits = [normalize_phone_digits(r["representative_tel_no"]),
                        normalize_phone_digits(r["cell_phone_no"])]
        naver_digits = [d for d in naver_digits if len(d) >= 9]
        if not naver_digits:
            continue
        candidates = vw_rep_phones.get(rep, [])
        # phone substring 둘 다 비교
        hits = []
        for cnd in candidates:
            cnd_digits = cnd[3]
            # vworld phone은 지역번호 없이 7-8자리로만 저장된 케이스 多 (예: '886-5616').
            # threshold 7로 낮추되 빈 phone은 명백히 제외 (false positive 방지).
            if not cnd_digits or len(cnd_digits) < 7:
                continue
            for nd in naver_digits:
                if nd and (nd in cnd_digits or cnd_digits in nd):
                    hits.append(cnd)
                    break
        if len(hits) == 1:
            sys_regno, vname, vrep, _ = hits[0]
            conn.execute(
                """
                INSERT INTO realtor_match
                    (realtor_id, sys_regno, vworld_name, vworld_rep, match_type, matched_at)
                VALUES (?, ?, ?, ?, 'rep_phone', ?)
                ON CONFLICT(realtor_id) DO UPDATE SET
                    sys_regno=excluded.sys_regno,
                    vworld_name=excluded.vworld_name,
                    vworld_rep=excluded.vworld_rep,
                    match_type=excluded.match_type,
                    matched_at=excluded.matched_at
                """,
                (r["realtor_id"], sys_regno, vname, vrep, now),
            )
            matched += 1
        elif len(hits) > 1:
            ambiguous += 1
    conn.commit()
    if ambiguous:
        print(f"  (ambiguous skipped: {ambiguous})", flush=True)
    return matched


def populate_naver_fields(conn) -> None:
    """realtor_match에 naver_name/primary_sgg 같은 부가 필드 채워두기 (UI 용)."""
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        UPDATE realtor_match SET naver_name=(
            SELECT realtor_name FROM naver_realtors WHERE naver_realtors.realtor_id=realtor_match.realtor_id
        ) WHERE naver_name IS NULL
        """
    )
    # primary_sgg/listings_count는 listings_current에서 계산
    conn.execute(
        """
        UPDATE realtor_match
        SET primary_sgg_cd = sub.sgg, primary_sgg_count = sub.n, total_listings = sub.total
        FROM (
            SELECT realtor_id, sgg, n, total FROM (
                SELECT l.realtor_id, substr(c.cortar_no,1,5) AS sgg, COUNT(*) AS n,
                       SUM(COUNT(*)) OVER (PARTITION BY l.realtor_id) AS total,
                       ROW_NUMBER() OVER (PARTITION BY l.realtor_id ORDER BY COUNT(*) DESC) AS rk
                FROM listings_current l
                JOIN complexes c ON c.complex_no = l.complex_no
                WHERE l.realtor_id IS NOT NULL AND c.cortar_no IS NOT NULL
                GROUP BY l.realtor_id, sgg
            ) WHERE rk = 1
        ) AS sub
        WHERE realtor_match.realtor_id = sub.realtor_id
        """
    )
    conn.commit()


def main():
    conn = open_db()
    print("[*] resetting realtor_match...", flush=True)
    conn.execute("DELETE FROM realtor_match")
    conn.commit()

    print("[*] refilling vworld normalized_name/normalized_loose/dong_name...", flush=True)
    n = fill_vworld_normalized(conn)
    print(f"  filled: {n} rows", flush=True)

    print("\n[1/3] regno match...", flush=True)
    r1 = step1_regno(conn)
    print(f"  matched: {r1:,}", flush=True)

    print("\n[2a/3] addr+dong+name match...", flush=True)
    r2 = step2_addr_name(conn)
    print(f"  matched: {r2:,}", flush=True)

    print("\n[2b/3] sgg+name fallback (dong NULL인 케이스)...", flush=True)
    r2b = step2b_sgg_name(conn)
    print(f"  matched: {r2b:,}", flush=True)

    print("\n[3/4] rep+phone match...", flush=True)
    r3 = step3_rep_phone(conn)
    print(f"  matched: {r3:,}", flush=True)

    print("\n[4/4] addr+rep match (주소·대표 유일일치, 이름/전화 변형 보완)...", flush=True)
    r4 = step4_addr_rep(conn)
    print(f"  matched: {r4:,}", flush=True)

    # 매칭 안 된 naver realtor도 row는 만들어두기 (match_type='none')
    print("\n[*] back-filling unmatched as 'none'...", flush=True)
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO realtor_match (realtor_id, match_type, matched_at)
        SELECT DISTINCT l.realtor_id, 'none', ?
        FROM listings_current l
        LEFT JOIN realtor_match m ON m.realtor_id = l.realtor_id
        WHERE l.realtor_id IS NOT NULL AND m.realtor_id IS NULL
        """,
        (now,),
    )
    conn.commit()

    print("\n[*] populating naver_name/primary_sgg fields...", flush=True)
    populate_naver_fields(conn)

    print("\n=== 최종 분포 ===", flush=True)
    total = 0
    matched_total = 0
    for kind, n in conn.execute("SELECT match_type, COUNT(*) FROM realtor_match GROUP BY match_type ORDER BY 2 DESC"):
        total += n
        if kind != "none":
            matched_total += n
        print(f"  {kind:20s} {n:>6}", flush=True)
    print(f"\n  total: {total:,}")
    print(f"  matched (1:1): {matched_total:,}  ({matched_total/total*100:.2f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
