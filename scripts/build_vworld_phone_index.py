"""중개사 전화 → realtor_id 통합 사전 인덱스(realtor_phone_index).
naver_realtors 연락처 + vworld 등록전화(한 필드 여러 번호) 둘 다 인덱싱 →
라운지 전화매칭을 풀스캔(143ms) 대신 인덱스 조회(<1ms)로. naver수집·vworld·매칭 갱신 후 재빌드(daily)."""
import re
import sqlite3
import sys
from pathlib import Path

DB = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "naverreal.sqlite"


def digits(s):
    return re.sub(r"\D", "", s or "")


def main():
    con = sqlite3.connect(str(DB))
    con.execute("CREATE TABLE IF NOT EXISTS realtor_phone_index "
                "(phone_digits TEXT, realtor_id TEXT, PRIMARY KEY(phone_digits, realtor_id))")
    pairs = set()

    def add(phone, rid):
        if not phone or not rid:
            return
        for tok in str(phone).replace("~", " ").replace(",", " ").split():
            dg = digits(tok)
            if 10 <= len(dg) <= 11 and dg.startswith("01"):  # 인증=휴대폰(010…)만
                pairs.add((dg, rid))

    # ① naver_realtors 연락처(휴대폰/대표전화)
    for rid, cell, rep in con.execute(
            "SELECT realtor_id, cell_phone_no, representative_tel_no FROM naver_realtors").fetchall():
        add(cell, rid); add(rep, rid)
    # ② vworld 등록전화(한 필드 여러 번호) → realtor_match → naver realtor_id
    for phone, rid in con.execute(
            "SELECT vb.phone, rm.realtor_id FROM vworld_brokers vb "
            "JOIN realtor_match rm ON rm.sys_regno=vb.sys_regno "
            "WHERE rm.realtor_id IS NOT NULL AND vb.phone IS NOT NULL").fetchall():
        add(phone, rid)

    con.execute("DELETE FROM realtor_phone_index")
    con.executemany("INSERT OR IGNORE INTO realtor_phone_index VALUES(?,?)", list(pairs))
    con.execute("CREATE INDEX IF NOT EXISTS rpi_phone ON realtor_phone_index(phone_digits)")
    con.commit()
    print(f"realtor_phone_index: {len(pairs)} (phone,office) pairs")


if __name__ == "__main__":
    main()
