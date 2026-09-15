# -*- coding: utf-8 -*-
"""실거래 지도 자산별 좌표 커버리지 검증 — 거래건수 기준(최근 6개월).
apt/offi=단지좌표, villa/nrg=지번좌표(+nrg는 대장 복원지번), house=대장 복원지번만.
사용: python3 scripts/tx_map_coverage.py [--tg]  (--tg면 텔레그램 발송)"""
import argparse, sqlite3, subprocess, sys

NV = "/opt/koczip/data/naverreal.sqlite"
CA = "/opt/koczip/data/coord_addr.sqlite"
LR = "/opt/koczip/data/ledger_recover.sqlite"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tg", action="store_true")
    a = ap.parse_args()

    nv = sqlite3.connect(f"file:{NV}?mode=ro", uri=True)
    nv.execute("PRAGMA busy_timeout=120000")
    ca = sqlite3.connect(f"file:{CA}?mode=ro", uri=True)

    fwd = set((s, d, j) for s, d, j in ca.execute(
        "SELECT sgg5,dong,jibun FROM coord_jibun_fwd WHERE status='ok'"))
    rev = set((d, j) for d, j in ca.execute("SELECT dong,jibun FROM coord_jibun"))
    rec = {}
    try:
        lr = sqlite3.connect(f"file:{LR}?mode=ro", uri=True)
        for did, j in lr.execute("SELECT deal_id, jibun FROM recovered WHERE jibun IS NOT NULL"):
            rec[did] = j
    except sqlite3.Error:
        pass

    W = "deal_ymd>=date('now','+9 hours','-6 months') AND is_cancelled=0"
    lines = []

    # 아파트·오피스텔 — 단지 좌표
    for label, t in (("아파트", "transactions"), ("오피스텔", "offi_transactions")):
        tot, m = nv.execute(
            f"SELECT COUNT(*), SUM(matched_complex_no IS NOT NULL AND EXISTS("
            f"SELECT 1 FROM complexes cx WHERE cx.complex_no=matched_complex_no "
            f"AND cx.latitude IS NOT NULL AND cx.latitude<>0)) FROM {t} WHERE {W}").fetchone()
        lines.append((label, tot, m or 0, None))

    # 빌라 — 지번 좌표
    rows = nv.execute(f"SELECT substr(sgg_cd,1,5), umd_nm, jibun FROM rh_transactions WHERE {W}").fetchall()
    m = sum(1 for s, d, j in rows if (s, d, j) in fwd or (d, j) in rev)
    lines.append(("빌라·다세대", len(rows), m, None))

    # 상가 — 지번(+복원지번) 좌표. 마스킹 분해 표기
    rows = nv.execute(f"SELECT deal_id, substr(sgg_cd,1,5), umd_nm, jibun FROM nrg_transactions WHERE {W}").fetchall()
    tot = len(rows); m = mask_unrec = 0
    for did, s, d, j in rows:
        je = rec.get(did, j)
        if "*" in (je or ""):
            mask_unrec += 1
            continue
        if (s, d, je) in fwd or (d, je) in rev:
            m += 1
    lines.append(("상가·사무실", tot, m, f"마스킹 미복원 {mask_unrec:,}건 제외 시 {100*m/max(tot-mask_unrec,1):.1f}%"))

    # 단독 — 복원지번만
    rows = nv.execute(f"SELECT deal_id, substr(sgg_cd,1,5), umd_nm FROM sh_transactions WHERE {W}").fetchall()
    tot = len(rows); m = 0
    for did, s, d in rows:
        je = rec.get(did)
        if je and ((s, d, je) in fwd or (d, je) in rev):
            m += 1
    lines.append(("단독·다가구", tot, m, "원본 지번 무 — 대장 복원분만"))

    out = ["실거래 지도 자산별 좌표 커버리지 (최근 6개월 거래 기준)"]
    for label, tot, m, note in lines:
        pct = 100 * m / tot if tot else 0
        out.append(f"· {label}: {m:,}/{tot:,} ({pct:.1f}%)" + (f" — {note}" if note else ""))
    txt = "\n".join(out)
    print(txt)

    if a.tg:
        try:
            subprocess.run([".venv/bin/python", "scripts/tg_notify.py",
                            "🗺️ 지번복원 데몬 완료 — 최종 커버리지\n" + txt],
                           cwd="/opt/koczip", timeout=30)
        except Exception as e:
            print("tg 발송 실패:", e, file=sys.stderr)

if __name__ == "__main__":
    main()
