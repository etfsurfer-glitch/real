"""실거래 매칭 감시 — 거래 법정동과 단지 동이 다른데 지번만으로 붙은 행 세기(2026-11-12 사고 재발 방지).

daily_run step 10(재매칭) 뒤. 0 이 아니면 텔레그램. 경계 단지(지번·이름 둘 다 같음)는
'jibun+name' 으로 따로 붙으므로 여기 세는 'jibun' 에는 없어야 정상이다.

    python scripts/check_tx_crossdong.py           # 세고, 0 아니면 알림
    python scripts/check_tx_crossdong.py --quiet   # 알림 없이 숫자만
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realprice import matching as rp_match  # noqa: E402

TABLES = ("transactions", "rentals", "offi_transactions", "offi_rentals")


def count(conn: sqlite3.Connection) -> dict[str, int]:
    dong = {r[0]: r[1] or "" for r in conn.execute(
        "SELECT c.complex_no, r.cortar_name FROM complexes c LEFT JOIN regions r ON r.cortar_no=c.cortar_no")}
    out = {}
    for t in TABLES:
        n = 0
        for umd, cno in conn.execute(f"SELECT umd_nm, matched_complex_no FROM {t} "
                                     f"WHERE matched_method='jibun' AND manual_override=0"):
            if not rp_match.dong_compatible(umd or "", dong.get(cno, "")):
                n += 1
        out[t] = n
    unm = conn.execute("SELECT COUNT(*) FROM transactions WHERE matched_complex_no IS NULL").fetchone()[0]
    out["transactions_unmatched"] = unm
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    conn = sqlite3.connect(f"file:{settings.local_db_path}?mode=ro", uri=True, timeout=30)
    res = count(conn)
    print("[crossdong]", res)
    bad = sum(v for k, v in res.items() if k in TABLES)
    if bad and not a.quiet:
        try:
            from scripts.tg_notify import tg_send
        except Exception:  # noqa: BLE001
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from tg_notify import tg_send
        tg_send("⚠️ 실거래 매칭: 동이 다른데 지번만으로 붙은 거래 "
                + ", ".join(f"{k} {v:,}" for k, v in res.items() if k in TABLES and v)
                + " — collector/realprice/matching.py 동 검증 확인")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
