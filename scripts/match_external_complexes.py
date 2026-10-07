# -*- coding: utf-8 -*-
"""미매칭 단지 → 콕집 complex_no 매칭.

정규화·변형 규칙은 collector/realprice/matching.py 를 그대로 재사용한다(동일 동작 보장).
입력 데이터 특성상 실거래 매칭과 다른 점 두 가지를 반영했다.

 1) 재건축 함정 — 신축 단지가 철거된 옛 단지와 **같은 지번**을 쓴다.
    (예: 의왕역SKVIEW(신축) 지번이 우리 마스터의 '영동'(옛 단지)과 일치)
    → 지번이 맞아도 단지명이 전혀 다르면 자동 채택하지 않고 재건축 의심으로 보류.
 2) 법정동코드10 이 100% 들어있다 — 동명 문자열 비교 대신 코드 완전일치를 쓴다.

세대수·사용승인일은 보조 검증으로만 쓴다(가점/감점, 단독 근거 아님).
"""
import csv, sys, re, collections
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, "/Users/hcode/auto/naverreal")
from collector.realprice.matching import (           # noqa: E402
    name_variants, normalize_jibun as _nj, bonbun_of, normalize_road, base_normalize)

# 운영 normalize_jibun 은 지번이 문자열 끝에 있다고 가정한다. 그런데 마스터의
# 신축 단지는 '17-6번지 일대' / '856-6번지 일원' / '236번지' 처럼 뒤에 말이 붙어
# 있어 정규화가 통째로 실패한다(마스터 798단지, 1.24%). 꼬리말을 떼고 넘긴다.
_TAIL = re.compile(r"\s*(번지|일대|일원|일곽|외\s*\d+\s*필지?|외)+\s*$")


def normalize_jibun(s):
    if not s:
        return ""
    prev = None
    cur = s.strip()
    while cur != prev:                 # '236번지 일원' 처럼 두 겹인 경우
        prev = cur
        cur = _TAIL.sub("", cur).strip()
    return _nj(cur)

SRC = "/Users/hcode/auto/review/data/미매칭_단지_콕집채움용.csv"
MASTER = "/Users/hcode/auto/naverreal/data/complexes_master.csv"
OUT = Path(__file__).resolve().parent / "matched.csv"

# ── 마스터 적재 ───────────────────────────────────────────────
M = []
for r in csv.DictReader(open(MASTER, encoding="utf-8")):
    M.append({
        "complex_no": r["complex_no"],
        "name": r["complex_name"],
        "variants": name_variants(r["complex_name"]),
        "cortar10": r["cortar_no"],
        "sgg5": r["cortar_no"][:5],
        "jibun": normalize_jibun(r["detail_address"]),
        "road": normalize_road(r["road_address"]),
        "hh": int(r["total_household_count"] or 0),
        "appr": (r["use_approve_ymd"] or "").strip(),
        "type": r["real_estate_type"],
    })
print("마스터 %s단지 적재" % format(len(M), ","))

idx_j10, idx_j5, idx_bb5, idx_road5, idx_name5 = ({} for _ in range(5))
for c in M:
    if c["jibun"]:
        idx_j10.setdefault((c["cortar10"], c["jibun"]), []).append(c)
        idx_j5.setdefault((c["sgg5"], c["jibun"]), []).append(c)
        bb = bonbun_of(c["jibun"])
        if bb:
            idx_bb5.setdefault((c["sgg5"], bb), []).append(c)
    if c["road"]:
        idx_road5.setdefault((c["sgg5"], c["road"]), []).append(c)
    for v in c["variants"]:
        idx_name5.setdefault((c["sgg5"], v), []).append(c)


_DIGITS = re.compile(r"\d+")


def digit_key(s):
    """이름 안의 숫자 나열. '서초네이처힐5단지' → ('5',)  '경남2단지' → ('2',)"""
    return tuple(_DIGITS.findall(base_normalize(s or "")))


def digit_clash(src_name, c):
    """단지 번호·차수가 다르면 True. 유사도로는 절대 못 거르는 오매칭을 막는다.
    예: 천안아이파크시티3단지 vs 2단지(0.993), 서초네이처힐5단지 vs 4단지(0.977)."""
    a = digit_key(src_name)
    b = digit_key(c["name"])
    if not a and not b:
        return False
    return a != b


def name_agree(tv, c):
    """단지명 일치도. 2=완전일치 1=부분일치(3자↑) 0=불일치"""
    for cn in c["variants"]:
        if cn in tv:
            return 2
    best = 0
    for cn in c["variants"]:
        if len(cn) < 3:
            continue
        for tn in tv:
            if len(tn) < 3:
                continue
            if cn in tn or tn in cn:
                best = 1
    return best


def sim(tv, c):
    return max((SequenceMatcher(None, tn, cn).ratio()
                for tn in tv for cn in c["variants"] if tn and cn), default=0.0)


def hh_ok(src_hh, c):
    """세대수 교차검증: 둘 다 있고 30% 넘게 차이나면 False"""
    if not src_hh or not c["hh"]:
        return None
    return abs(src_hh - c["hh"]) / max(src_hh, c["hh"]) <= 0.30


def appr_ok(src_a, c):
    """사용승인 연도 2년 초과 차이면 False"""
    if not src_a or not c["appr"] or len(src_a) < 4 or len(c["appr"]) < 4:
        return None
    return abs(int(src_a[:4]) - int(c["appr"][:4])) <= 2


rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
out_rows = []
stat = collections.Counter()

for r in rows:
    tv = name_variants(r["단지명"])
    c10 = (r["법정동코드10"] or "").strip()
    s5 = (r["시군구코드5"] or "").strip()
    jb = normalize_jibun(r["지번"] or "")
    rd = normalize_road(r["도로명주소"] or "")
    try:
        src_hh = int(r["세대수"] or 0)
    except ValueError:
        src_hh = 0
    src_a = (r["사용승인일"] or "").strip()

    src_name = r["단지명"]
    src_offi = ("(오)" in src_name) or (r.get("유형") or "").startswith("오피")

    cands = []

    def add(c, method, score, reason):
        cands.append((c, method, score, reason))

    def strong():
        """0.80 이상 후보가 있을 때만 뒷단계를 건너뛴다.
        재건축 의심(0.45) 같은 저신뢰 후보가 이름 완전일치를 막던 문제를 없앤다."""
        return any(x[2] >= 0.80 for x in cands)

    # 1) 지번 (법정동코드10 완전일치) — 이름 일치도로 등급 분리
    for c in idx_j10.get((c10, jb), []):
        na = name_agree(tv, c)
        if na == 2:
            add(c, "jibun10+name", 1.00, "법정동코드+지번+단지명 완전일치")
        elif na == 1:
            add(c, "jibun10+partname", 0.93, "법정동코드+지번 일치, 단지명 부분일치")
        else:
            add(c, "jibun10+namemismatch", 0.45, "지번은 같으나 단지명 불일치 — 재건축 의심")

    # 2) 지번 (시군구 범위) — 법정동이 다른 경우
    if not strong():
        for c in idx_j5.get((s5, jb), []):
            na = name_agree(tv, c)
            if na == 2:
                add(c, "jibun5+name", 0.95, "시군구+지번+단지명 일치(법정동 불일치)")
            elif na == 1:
                add(c, "jibun5+partname", 0.88, "시군구+지번 일치, 단지명 부분일치")
            else:
                add(c, "jibun5+namemismatch", 0.40, "지번만 일치 — 재건축 의심")

    # 3) 도로명 + 단지명
    if not strong() and rd:
        for c in idx_road5.get((s5, rd), []):
            na = name_agree(tv, c)
            if na == 2:
                add(c, "road+name", 0.92, "도로명+단지명 일치")
            elif na == 1:
                add(c, "road+partname", 0.85, "도로명 일치, 단지명 부분일치")

    # 4) 단지명 완전일치 (시군구 범위)
    if not strong():
        seen = set()
        for v in tv:
            for c in idx_name5.get((s5, v), []):
                if c["complex_no"] in seen:
                    continue
                seen.add(c["complex_no"])
                same_dong = (c["cortar10"] == c10)
                add(c, "exact+dong" if same_dong else "exact",
                    0.90 if same_dong else 0.80,
                    "단지명 완전일치" + ("(동일 법정동)" if same_dong else "(동 다름)"))

    # 5) 본번 fallback — 유일 + 이름 검증
    if not strong() and jb:
        bb = bonbun_of(jb)
        if bb and bb != jb:
            hits = idx_bb5.get((s5, bb), [])
            if len(hits) == 1 and name_agree(tv, hits[0]) >= 1:
                add(hits[0], "bonbun+name", 0.85, "본번 유일 + 단지명 일치")

    # 6) 유사도 (동일 법정동 한정)
    if not strong():
        best, bs = None, 0.0
        for c in M:
            if c["cortar10"] != c10:
                continue
            s = sim(tv, c)
            if s > bs:
                bs, best = s, c
        if best is not None and bs >= 0.85:
            add(best, "fuzzy+dong", round(bs, 3), "법정동 내 이름 유사도 %.3f" % bs)

    # ── 보조검증 반영 ────────────────────────────────────────
    scored = []
    for c, method, score, reason in cands:
        ho, ao = hh_ok(src_hh, c), appr_ok(src_a, c)
        adj, notes = score, []
        # 단지 번호 불일치 — 이름 기반 매칭에서는 치명적이라 아예 탈락시킨다.
        if digit_clash(src_name, c):
            if method.startswith(("fuzzy", "exact", "substr", "road")):
                notes.append("단지번호 불일치(%s vs %s) — 탈락"
                             % ("".join(digit_key(src_name)) or "-",
                                "".join(digit_key(c["name"])) or "-"))
                scored.append((c, method + "+numclash", 0.30, reason, "; ".join(notes)))
                continue
            adj -= 0.20
            notes.append("단지번호 불일치")
        # 유형 선호(오피스텔 ↔ OPST/OBYG). tie-break 성격이라 폭을 작게 둔다.
        is_offi = c["type"] in ("OPST", "OBYG")
        if src_offi != is_offi:
            adj -= 0.08
            notes.append("유형 불일치(입력 %s / 마스터 %s)"
                         % ("오피스텔" if src_offi else "아파트", c["type"]))
        elif src_offi and is_offi:
            adj += 0.03
            notes.append("유형 일치(오피스텔)")
        if ho is False:
            adj -= 0.25; notes.append("세대수 불일치(%s vs %s)" % (src_hh, c["hh"]))
        elif ho is True:
            adj += 0.03; notes.append("세대수 일치")
        if ao is False:
            adj -= 0.25; notes.append("사용승인 %s vs %s" % (src_a[:4], c["appr"][:4]))
        elif ao is True:
            adj += 0.03; notes.append("사용승인 일치")
        scored.append((c, method, round(min(adj, 1.0), 3), reason, "; ".join(notes)))

    scored.sort(key=lambda x: -x[2])
    top = scored[0] if scored else None

    if top and top[2] >= 0.90:
        verdict, fill = "자동채택", top[0]["complex_no"]
    elif top and top[2] >= 0.70:
        verdict, fill = "검수필요", ""
    elif top:
        verdict, fill = "보류(저신뢰)", ""
    else:
        verdict, fill = "후보없음", ""
    stat[verdict] += 1
    if top:
        stat["method:" + top[1]] += 1

    o = dict(r)
    o["complex_no(채워주세요)"] = fill
    o["판정"] = verdict
    o["매칭방법"] = top[1] if top else ""
    o["점수"] = top[2] if top else ""
    o["매칭단지명"] = top[0]["name"] if top else ""
    o["매칭단지no"] = top[0]["complex_no"] if top else ""
    o["근거"] = (top[3] + (" | " + top[4] if top[4] else "")) if top else ""
    o["후보수"] = len(scored)
    o["차순위"] = (" / ".join("%s(%s,%s,%s)" % (x[0]["name"], x[0]["complex_no"], x[1], x[2])
                            for x in scored[1:4]))
    out_rows.append(o)

cols = list(rows[0].keys()) + ["판정", "매칭방법", "점수", "매칭단지명", "매칭단지no",
                               "근거", "후보수", "차순위"]
cols = list(dict.fromkeys(cols))
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(out_rows)

print("\n=== 판정 ===")
for k in ("자동채택", "검수필요", "보류(저신뢰)", "후보없음"):
    print("  %-12s %5s  %.1f%%" % (k, format(stat[k], ","), stat[k] / len(rows) * 100))
print("\n=== 방법별 ===")
for k, v in sorted(((k, v) for k, v in stat.items() if k.startswith("method:")),
                   key=lambda x: -x[1]):
    print("  %-26s %s" % (k[7:], format(v, ",")))
print("\n출력:", OUT)
