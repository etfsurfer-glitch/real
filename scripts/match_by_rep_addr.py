"""대표자명 + 사무소 주소 시·군·구 AND 매칭 — regno로 못 잡은 unmatched 보강.

전제:
  - 같은 사무소 주소엔 여러 중개사무소가 있을 수 있어 주소만으로는 분별 안 됨.
  - 같은 대표자 이름이 여러 시군구에 다른 사무소로 있을 수 있어 이름만으로도 안 됨.
  - 둘을 AND로 묶으면 사실상 유일.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realtor_matching import addr_sgg_key  # noqa: E402


def main() -> int:
    conn = sqlite3.connect(settings.local_db_path, timeout=30.0)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row

    # vworld 인덱스: (rep, sgg_key) → list of (sys_regno, name, address)
    vw_by_rep_sgg: dict[tuple[str, str], list] = {}
    for r in conn.execute("SELECT sys_regno, business_name, representative, address FROM vworld_brokers WHERE representative IS NOT NULL"):
        sgg_key = addr_sgg_key(r["address"])
        if not sgg_key:
            continue
        k = (r["representative"], sgg_key)
        vw_by_rep_sgg.setdefault(k, []).append((r["sys_regno"], r["business_name"], r["representative"], r["address"]))
    print(f"vworld indexed by (rep, sgg): {len(vw_by_rep_sgg):,}", flush=True)

    # 대상: realtor_match에서 multi/none이고 naver_realtors에 rep+address 있음
    targets = conn.execute(
        """
        SELECT m.realtor_id, m.match_type, nr.representative_name, nr.address
        FROM realtor_match m
        JOIN naver_realtors nr ON nr.realtor_id = m.realtor_id
        WHERE (m.match_type='none' OR m.match_type LIKE 'multi%')
          AND nr.representative_name IS NOT NULL
          AND nr.address IS NOT NULL
        """
    ).fetchall()
    print(f"unmatched with rep+addr: {len(targets):,}", flush=True)

    upgraded = no_match = ambiguous = 0
    now = datetime.now().isoformat(timespec="seconds")
    for t in targets:
        sgg_key = addr_sgg_key(t["address"])
        if not sgg_key:
            no_match += 1
            continue
        cands = vw_by_rep_sgg.get((t["representative_name"], sgg_key))
        if not cands:
            no_match += 1
            continue
        if len(cands) > 1:
            ambiguous += 1
            continue
        # 1:1 매칭
        sys_regno, vname, vrep, _ = cands[0]
        conn.execute(
            """
            UPDATE realtor_match
            SET sys_regno=?, vworld_name=?, vworld_rep=?,
                match_type='rep_sgg', candidates_json=NULL, matched_at=?
            WHERE realtor_id=?
            """,
            (sys_regno, vname, vrep, now, t["realtor_id"]),
        )
        upgraded += 1
    conn.commit()
    print(f"\nresult:")
    print(f"  upgraded (rep_sgg 1:1): {upgraded:,}")
    print(f"  ambiguous (rep+sgg 여러 후보): {ambiguous:,}")
    print(f"  no match (rep 다르거나 sgg 불일치): {no_match:,}")

    print()
    print("=== 최종 match_type 분포 ===")
    total_one_to_one = 0
    for kind, n in conn.execute("SELECT match_type, COUNT(*) FROM realtor_match GROUP BY match_type ORDER BY 2 DESC"):
        print(f"  {kind:30s} {n:>6}")
        if not (kind.startswith("multi") or kind == "none"):
            total_one_to_one += n
    print(f"  ── 1:1 합계: {total_one_to_one:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
