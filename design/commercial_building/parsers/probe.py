# -*- coding: utf-8 -*-
"""임대안내문 PDF 실사 — 텍스트 레이어가 있는가, 쪽수는 몇인가.

추출 경로가 pdfplumber/fitz(텍스트)냐 OCR/비전(이미지)이냐를 가른다.
쪽당 글자수가 0에 가까우면 이미지 PDF다.
"""
import os, statistics, sys
import fitz

def probe(path):
    try:
        d = fitz.open(path)
    except Exception as e:                       # noqa: BLE001
        return {"err": str(e)[:60]}
    n = d.page_count
    # 앞·중간·뒤에서 고르게 12쪽만 본다(전수는 느리고 불필요)
    idx = sorted({int(i * (n - 1) / 11) for i in range(12)}) if n > 1 else [0]
    chars, enc = [], d.is_encrypted
    for i in idx:
        try:
            chars.append(len(d.load_page(i).get_text("text").strip()))
        except Exception:                        # noqa: BLE001
            chars.append(0)
    d.close()
    return {"pages": n, "enc": enc, "med": int(statistics.median(chars)),
            "max": max(chars), "zero": sum(1 for c in chars if c < 20),
            "n_s": len(idx)}

def main(root):
    rows = []
    for dp, _dn, fn in os.walk(root):
        for f in sorted(fn):
            if f.lower().endswith(".pdf"):
                p = os.path.join(dp, f)
                rows.append((os.path.relpath(p, root), probe(p),
                             os.path.getsize(p)))
    print(f"{'파일':<56}{'쪽':>5}{'중앙글자':>8}{'최대':>7}{'빈쪽':>6}{'MB':>6}  판정")
    print("-" * 104)
    tot_pages = 0
    verdict_cnt = {}
    for rel, r, size in rows:
        if "err" in r:
            print(f"{rel[:55]:<56}{'ERR':>5}  {r['err']}")
            verdict_cnt["열기실패"] = verdict_cnt.get("열기실패", 0) + 1
            continue
        tot_pages += r["pages"]
        if r["med"] >= 200:
            v = "텍스트"
        elif r["med"] >= 20:
            v = "텍스트(희박)"
        else:
            v = "이미지→OCR"
        verdict_cnt[v] = verdict_cnt.get(v, 0) + 1
        print(f"{rel[:55]:<56}{r['pages']:>5}{r['med']:>8}{r['max']:>7}"
              f"{r['zero']}/{r['n_s']:<4}{size/1e6:>6.0f}  {v}"
              + ("  [암호]" if r["enc"] else ""))
    print("-" * 104)
    print(f"파일 {len(rows)}개 · 총 {tot_pages:,}쪽")
    for k, v in sorted(verdict_cnt.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}개")

if __name__ == "__main__":
    main(sys.argv[1])
