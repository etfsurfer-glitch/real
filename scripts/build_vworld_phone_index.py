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
    # 사람이 직접 지정한 번호. 이 인덱스는 매일 통째로 지우고 다시 만들기 때문에,
    # naver_realtors 에 손으로 적어 넣으면 네이버 수집이 덮어써서 사라진다. 여기 둬야 남는다.
    con.execute("CREATE TABLE IF NOT EXISTS realtor_phone_manual "
                "(realtor_id TEXT, phone_digits TEXT, note TEXT, added_at TEXT, "
                " PRIMARY KEY(realtor_id, phone_digits))")
    # vworld 등록전화를 쓰지 않을 사무소. vworld 는 한 칸에 번호를 10개 넘게 몰아 적어 두는
    # 곳이 있어(실측: 메이트플러스 15개) 엉뚱한 번호로 남이 들어올 수 있다.
    con.execute("CREATE TABLE IF NOT EXISTS realtor_vworld_optout "
                "(realtor_id TEXT PRIMARY KEY, note TEXT, added_at TEXT)")
    optout = {r[0] for r in con.execute("SELECT realtor_id FROM realtor_vworld_optout")}
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
        if rid in optout:
            continue
        add(phone, rid)
    # ③ 네이버 미매칭 vworld 사무소(영업만) → 합성 ID vw{sys_regno} (2026-07-03)
    #    네이버 ID 숨김·미사용 사무소도 vworld 등록 전화 인증만으로 연결되게.
    #    선택 시 lounge_select가 naver_realtors에 자동 프로비저닝 + 숨김매물 자동귀속.
    n3_before = len(pairs)
    for phone, sregno in con.execute(
            "SELECT vb.phone, vb.sys_regno FROM vworld_brokers vb "
            "WHERE vb.status='영업' AND vb.phone IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM realtor_match rm WHERE rm.sys_regno=vb.sys_regno "
            " AND rm.realtor_id IS NOT NULL)").fetchall():
        if f"vw{sregno}" in optout:
            continue
        add(phone, f"vw{sregno}")
    print(f"  ③ vworld 미매칭(영업) 합성ID 페어: {len(pairs) - n3_before}")
    # ④ 손으로 지정한 번호 — 사무소가 알려 준 실제 연락처. vworld·네이버보다 뒤에 넣지만
    #    set 이라 순서는 상관없고, optout 과 무관하게 **항상** 들어간다.
    n4 = 0
    for rid, dg in con.execute("SELECT realtor_id, phone_digits FROM realtor_phone_manual").fetchall():
        if rid and dg and 10 <= len(dg) <= 11 and dg.startswith("01"):
            pairs.add((dg, rid)); n4 += 1
    print(f"  ④ 수동 지정: {n4}건 · vworld 제외 사무소: {len(optout)}곳")

    con.execute("DELETE FROM realtor_phone_index")
    con.executemany("INSERT OR IGNORE INTO realtor_phone_index VALUES(?,?)", list(pairs))
    con.execute("CREATE INDEX IF NOT EXISTS rpi_phone ON realtor_phone_index(phone_digits)")
    con.commit()
    print(f"realtor_phone_index: {len(pairs)} (phone,office) pairs")


if __name__ == "__main__":
    main()
