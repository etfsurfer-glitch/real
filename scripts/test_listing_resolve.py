# 양식별 회귀 — 들어올 수 있는 매물장 모양마다 몇 건으로 펴지는지 고정한다.
import sys; sys.path.insert(0, __import__("os").path.dirname(__file__) or ".")
import listing_import as li

def run(name, rows, want, check=None):
    out, m, sp = li.resolve_rows([dict(r) for r in rows])
    ok = len(out) == want and (check is None or check(out))
    print(("  PASS " if ok else "  FAIL ") + f"{name}: {len(out)}건(기대 {want}) 합침{m} 가름{sp}")
    if not ok:
        for o in out: print("        ", {k: v for k, v in o.items() if not k.startswith("_")})
    return ok

res = []
# ① 한 줄 = 한 매물
res.append(run("① 평범한 한 줄", [
    {"dong": "101동", "ho": "402호", "trade_type": "매매", "price": 230000000},
], 1))

# ② 한 집 여러 줄 — 매매 + 전세 (둘 다 진짜 매물)
res.append(run("② 매매+전세 두 줄", [
    {"dong": "101동", "ho": "402호", "trade_type": "매매", "price": 230000000},
    {"dong": "101동", "ho": "402호", "trade_type": "전세", "deposit": 185000000},
], 2))

# ③ 메모 전용 줄이 섞임 → 합쳐져야 한다
res.append(run("③ 메모줄 뒤", [
    {"dong": "101동", "ho": "1503호", "trade_type": "매매", "price": 240000000},
    {"dong": "101동", "ho": "1503호", "memo": "근저당 1.68"},
], 1, lambda o: "근저당 1.68" in (o[0].get("memo") or "")))

res.append(run("③ 메모줄 앞", [
    {"dong": "103동", "ho": "2603호", "memo": "매매\n전세우선"},
    {"dong": "103동", "ho": "2603호", "trade_type": "매매", "price": 240000000},
    {"dong": "103동", "ho": "2603호", "trade_type": "전세", "deposit": 180000000},
], 2, lambda o: all("전세우선" in (x.get("memo") or "") for x in o)))

# ④ 가로형 — 매매가·전세가가 각 열, 거래유형 칸 없음
res.append(run("④ 가로형 매매+전세", [
    {"dong": "101동", "ho": "402호", "price": 230000000, "deposit": 185000000},
], 2, lambda o: {x["trade_type"] for x in o} == {"매매", "전세"}
   and all(not (x["trade_type"] == "매매" and x.get("deposit")) for x in o)))

res.append(run("④ 가로형 매매+월세", [
    {"dong": "101동", "ho": "402호", "price": 230000000, "deposit": 20000000, "rent_price": 800000},
], 2, lambda o: {x["trade_type"] for x in o} == {"매매", "월세"}))

# ④ 반례 — 거래유형을 사람이 적었으면 가르지 않는다(월세 보증금)
res.append(run("④ 반례: 월세 보증금은 안 가름", [
    {"dong": "101동", "ho": "402호", "trade_type": "월세", "_trade_col": True,
     "deposit": 20000000, "rent_price": 800000},
], 1))

# ⑤ 조건 미정(연락처만) — 살려야 한다
res.append(run("⑤ 조건 미정 단독", [
    {"dong": "101동", "ho": "1101호", "contact": "010-7172-5321"},
], 1))

# ⑥ 멀리 떨어진 같은 호 — 각각 진짜 매물
res.append(run("⑥ 떨어진 같은 호", [
    {"dong": "101동", "ho": "402호", "trade_type": "매매", "price": 230000000},
    {"dong": "102동", "ho": "101호", "trade_type": "매매", "price": 210000000},
    {"dong": "101동", "ho": "402호", "trade_type": "전세", "deposit": 185000000},
], 3))

# ⑦ 동·호 없는 매물(단지만) — 블록 안 만들고 그대로
res.append(run("⑦ 동·호 없음", [
    {"complex_name": "가나아파트", "trade_type": "매매", "price": 500000000},
    {"complex_name": "가나아파트", "trade_type": "전세", "deposit": 300000000},
], 2))

print("\n%d/%d 통과" % (sum(res), len(res)))
