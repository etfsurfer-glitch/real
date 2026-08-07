# 채점 — want 에 적힌 항목만 본다(글에 없는 것은 요구하지 않는다)
import sys, json, collections, time
sys.path.insert(0, "/opt/koczip/scripts"); sys.path.insert(0, "/tmp/qa")
import local_api as A
from corpus import C

def close(k, got, want):
    if got is None or got == "":
        return False
    if isinstance(want, (int, float)):
        try:
            return abs(float(got) - float(want)) <= max(1.0, abs(float(want)) * 0.01)
        except (TypeError, ValueError):
            return False
    return str(want) in str(got)

start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end = int(sys.argv[2]) if len(sys.argv) > 2 else len(C)
tot = collections.Counter(); byk = collections.defaultdict(collections.Counter); fails = []
t0 = time.time()
for idx, (text, want) in enumerate(C[start:end], start):
    try:
        out = A._qa_parse(text)
    except Exception as e:
        tot["파싱실패"] += 1; fails.append((idx, text, "파싱실패", f"{type(e).__name__}")); continue
    rows = out.get("매물") or []
    if want.get("_n"):
        ok = len(rows) == want["_n"]
        tot["맞음" if ok else "틀림"] += 1; byk["_건수"]["맞음" if ok else "틀림"] += 1
        if not ok: fails.append((idx, text, "_건수", f"{len(rows)}건"))
        continue
    m = rows[0] if rows else {}
    A._qa_enrich_listing(m)
    if not want:
        tot["맞음"] += 1; continue
    bad = []
    for k, v in want.items():
        good = close(k, m.get(k), v)
        byk[k]["맞음" if good else "틀림"] += 1
        if not good: bad.append(f"{k}: {m.get(k)!r}≠{v!r}")
    tot["맞음" if not bad else "틀림"] += 1
    if bad: fails.append((idx, text, "항목", " | ".join(bad)))
n = sum(tot.values())
print(f"{n}건 · {(time.time()-t0)/max(n,1):.1f}s/건 — " +
      " · ".join(f"{k} {v}({v/n*100:.0f}%)" for k, v in tot.most_common()))
print("항목별 정확도(틀린 것만):")
for k, cc in sorted(byk.items(), key=lambda x: -x[1]["틀림"]):
    if cc["틀림"]:
        print(f"  {k:16s} {cc['맞음']}/{cc['맞음']+cc['틀림']}")
print("실패:")
for i, t, kind, why in fails[:40]:
    print(f"  [{i:3d}/{kind}] {t[:46]}  → {why[:110]}")
