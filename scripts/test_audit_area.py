# ② 면적(전용㎡) 규칙 회귀 — 2026-10-07 트윈트리빌딩 오탐에서 나온 경우들.
# 반드시 **운영이 쓰는 모듈**(collector.listing_audit)을 본다.
# scripts/listing_audit.py 라는 묵은 사본이 따로 있어 그쪽을 고치고 '고쳤다'고 믿은
# 사고가 있었다(2026-10-08). 그 사본은 지웠고, 테스트도 운영 경로만 본다.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector.listing_audit import audit_listing

TWIN = [9.8, 28.86, 34.13, 38.88, 49.26, 50.73, 62.0, 68.8, 90.78, 104.45, 134.96, 221.42,
        318.14, 390.86, 399.31, 709.82, 748.75, 850.56, 1220.69]

def item(**kw):
    f = {"article_no": "T", "realestate_type_name": "사무실", "real_estate_type": "D01",
         "area_exclusive": 473, "led_expos_areas": TWIN, "price": 1, "floor_info": "3/17"}
    f.update(kw); return f

def rule2(f):
    for r in audit_listing(f).get("findings", []):
        if r.get("no") == 2:
            return r
    return None

res = []
def check(name, f, want_state, want_in=None):
    r = rule2(f)
    why = (r or {}).get("reason", "")
    ok = bool(r) and r["status"] == want_state and (want_in is None or want_in in why)
    print(("  PASS " if ok else "  FAIL ") + "%s: %s — %s" % (name, r["status"] if r else None, why[:72]))
    return ok

# ① 분할 임대(사무실) — 전유보다 작으면 통과여야 한다(실제 오탐 사례)
res.append(check("사무실 473㎡ (전유 850.56 중 일부)", item(), "통과", "분할 임대"))
# ② 상가도 같다
res.append(check("상가 100㎡", item(realestate_type_name="상가", area_exclusive=100), "통과", "분할 임대"))
# ③ 전유 최대값보다 크면 잡아야 한다 — 쪼개서는 나올 수 없다
res.append(check("사무실 2000㎡ (최대 1220.69 초과)", item(area_exclusive=2000), "주의", "큼"))
# ④ 정확히 일치하면 그대로 통과
res.append(check("사무실 850.56㎡ 일치", item(area_exclusive=850.56), "통과", "일치"))
# ⑤ 주거(오피스텔 등)는 분할 임대가 없다 — 불일치면 주의
res.append(check("빌라 473㎡ 불일치", item(realestate_type_name="빌라", real_estate_type="VL"), "주의")
           )
# ⑥ 보여 주는 값이 '가까운 순'이어야 한다(작은 순이면 9.8 이 먼저 나온다)
r = rule2(item(realestate_type_name="빌라", real_estate_type="VL"))
near_ok = bool(r) and "399.31" in r["reason"] and not r["reason"].split("전유(가까운 값 ")[-1].startswith("9.8/")
print(("  PASS " if near_ok else "  FAIL ") + "가까운 값 우선 표시: %s" % (r or {}).get("reason", "")[:72])
res.append(near_ok)
# ⑦ 전용 미표시는 위반 그대로
res.append(check("전용 미표시", item(area_exclusive=None), "위반"))
print("\n%d/%d 통과" % (sum(1 for x in res if x), len(res)))

# ── ⑩ 주차 회귀 (2026-10-08 을지로3가 빌딩 2648738735)
def rule10(f):
    for r in audit_listing(f).get("findings", []):
        if r.get("no") == 10:
            return r
    return None

def pitem(**kw):
    f = {"article_no": "P", "realestate_type_name": "건물", "real_estate_type": "GJCG",
         "price": 1, "parking_count": 0}
    f.update(kw); return f

print()
p = []
def pcheck(name, f, want, want_in=None):
    r = rule10(f); why = (r or {}).get("reason", "")
    ok = bool(r) and r["status"] == want and (want_in is None or want_in in why)
    print(("  PASS " if ok else "  FAIL ") + "%s: %s — %s" % (name, r["status"] if r else None, why[:60]))
    p.append(ok)

pcheck("주차 0대 표시(대장도 0)", pitem(led_parking=0), "통과", "0대로 표시")
pcheck("주차 0대 표시(대장 미확보)", pitem(led_parking=None), "통과", "0대로 표시")
pcheck("주차 정보 전무", pitem(parking_count=None), "위반", "미표시")
pcheck("'가능'만 표시", pitem(parking_count=None, parking_possible="Y"), "위반", "가능")
pcheck("'불가' 표시", pitem(parking_count=None, parking_possible="N"), "통과", "불가")
pcheck("대수 표시(5대)", pitem(parking_count=5), "통과")
print("\n주차 %d/%d 통과" % (sum(1 for x in p if x), len(p)))
