"""naver_realtors.establish_registration_no ↔ vworld_brokers.ra_regno로 매칭 강화.

기존 realtor_match를 덮어쓰지 않고 추가 매칭만 보강:
  - 기존 match_type이 'regno_exact'면 skip
  - 등록번호 1:1 매치되면 match_type='regno_exact'로 upsert
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realtor_matching import normalize_regno  # noqa: E402


def main() -> int:
    conn = sqlite3.connect(settings.local_db_path, timeout=30.0)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row

    # Build normalized regno → list[vworld_broker] map
    # vworld ra_regno는 표준 포맷이지만 안전하게 normalize_regno로 통일
    vw_by_regno: dict[str, tuple] = {}
    n_dups = 0
    for r in conn.execute(
        "SELECT sys_regno, ra_regno, business_name, representative FROM vworld_brokers WHERE ra_regno IS NOT NULL"
    ):
        nr = normalize_regno(r["ra_regno"])
        if not nr:
            continue
        if nr in vw_by_regno:
            n_dups += 1
            continue  # 첫 번째 (가장 옛것) 유지 — 나중에 status로 분별 가능
        vw_by_regno[nr] = (r["sys_regno"], r["business_name"], r["representative"])
    print(f"vworld brokers indexed: {len(vw_by_regno)} (dup regno skipped: {n_dups})", flush=True)

    # Walk naver_realtors, JOIN by normalized regno
    rows = conn.execute(
        """
        SELECT nr.realtor_id, nr.realtor_name, nr.representative_name,
               nr.establish_registration_no, nr.address, nr.cortar_no
        FROM naver_realtors nr
        WHERE nr.establish_registration_no IS NOT NULL
        """
    ).fetchall()
    print(f"naver_realtors with regno: {len(rows)}", flush=True)

    upgraded = 0
    inserted = 0
    no_match = 0
    now = datetime.now().isoformat(timespec="seconds")

    for r in rows:
        rid = r["realtor_id"]
        nr_regno = normalize_regno(r["establish_registration_no"])
        if not nr_regno:
            continue
        hit = vw_by_regno.get(nr_regno)
        if not hit:
            no_match += 1
            continue
        sys_regno, vname, vrep = hit

        # 기존 row 있나 확인
        existing = conn.execute(
            "SELECT match_type FROM realtor_match WHERE realtor_id=?", (rid,)
        ).fetchone()
        if existing and existing["match_type"] == "regno_exact":
            continue

        conn.execute(
            """
            INSERT INTO realtor_match
                (realtor_id, naver_name, primary_sgg_cd, primary_sgg_count, total_listings,
                 sys_regno, vworld_name, vworld_rep, match_type, candidates_json, matched_at)
            VALUES (?, ?, NULL, NULL, NULL, ?, ?, ?, 'regno_exact', ?, ?)
            ON CONFLICT(realtor_id) DO UPDATE SET
                sys_regno=excluded.sys_regno,
                vworld_name=excluded.vworld_name,
                vworld_rep=excluded.vworld_rep,
                match_type=excluded.match_type,
                candidates_json=excluded.candidates_json,
                matched_at=excluded.matched_at,
                naver_name=COALESCE(realtor_match.naver_name, excluded.naver_name)
            """,
            (
                rid, r["realtor_name"], sys_regno, vname, vrep,
                None, now,
            ),
        )
        if existing:
            upgraded += 1
        else:
            inserted += 1

    conn.commit()
    print(f"\nresult:")
    print(f"  upgraded (existing → regno_exact): {upgraded}")
    print(f"  inserted (new):                    {inserted}")
    print(f"  no vworld match:                   {no_match}")

    # final stats
    print("\n=== match_type 분포 (전체) ===")
    total = 0
    for kind, n in conn.execute("SELECT match_type, COUNT(*) FROM realtor_match GROUP BY match_type ORDER BY 2 DESC"):
        print(f"  {kind:30s} {n:>6}")
        total += n
    print(f"  {'total':30s} {total:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
