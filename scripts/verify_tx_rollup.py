"""tx_avg_rollup 정확성 전수 검증 — 레거시(라이브 매칭) vs rollup 경로 동시 비교.

같은 시점에 두 코드 경로로 quick_deals 를 실행해 항목 단위로 diff 한다.
대상: (전국 + 시도17 + 시군구255) × 매매/전세 × 90/180일 = 1,092 조합.

판정 규칙:
- (complex_no, area_name) 키 집합이 다르면 FAIL — 단, 두 쪽 다 limit 에 걸렸고
  경계 할인율이 동률이면 'tie@limit'(허용)으로 분류 후 상세 기록.
- 모든 수치 필드는 완전 일치 요구. 예외: avg_excl 만 REAL 합산 순서 차이로
  상대오차 1e-9 허용 (금액·건수·할인율은 정수합 기반이라 비트 동일해야 함).
- 결과는 data/rollup_verify_report.txt 에 기록. 불일치 0 이어야 합격.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.local_api as api  # noqa: E402

REPORT = Path("data/rollup_verify_report.txt")

TOL_FIELDS = {"avg_excl"}        # REAL 합산순서 → 1e-9 상대오차 허용
REL_TOL = 1e-9


def get_regions() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = [("전국", {})]
    with api._open_db() as c:
        sidos = [r[0] for r in c.execute(
            "SELECT DISTINCT substr(cortar_no,1,2)||'00000000' FROM complexes ORDER BY 1")]
        sggs = [r[0] for r in c.execute(
            "SELECT DISTINCT substr(cortar_no,1,5)||'00000' FROM complexes ORDER BY 1")]
    out += [(f"시도{s[:2]}", {"sido": s}) for s in sidos]
    out += [(f"시군구{g[:5]}", {"sigungu": g}) for g in sggs]
    return out


def call(legacy: bool, **kw) -> dict:
    api.USE_TX_ROLLUP = not legacy
    return api.quick_deals(days=kw.pop("days"), min_samples=3, trade_type=kw.pop("tt"),
                           min_discount=0.03, min_listings=1, limit=500, **kw)


def diff_items(old: list[dict], new: list[dict], limit: int = 500):
    """(키차이 목록, 필드차이 목록, tie@limit 여부)"""
    ko = {(x["complex_no"], x["area_name"]): x for x in old}
    kn = {(x["complex_no"], x["area_name"]): x for x in new}
    only_o = set(ko) - set(kn)
    only_n = set(kn) - set(ko)
    tie_at_limit = False
    if (only_o or only_n) and len(old) == limit and len(new) == limit:
        # limit 컷 경계의 동률 할인율이면 허용 (정렬 동률의 임의성)
        b_old = old[-1]["discount_min"]
        b_new = new[-1]["discount_min"]
        if b_old == b_new and all(ko[k]["discount_min"] == b_old for k in only_o) \
           and all(kn[k]["discount_min"] == b_new for k in only_n):
            tie_at_limit = True
    fdiffs = []
    for k in set(ko) & set(kn):
        a, b = ko[k], kn[k]
        for f in a:
            va, vb = a[f], b[f]
            if f in TOL_FIELDS:
                fa, fb = (va or 0.0), (vb or 0.0)
                if fa != fb and abs(fa - fb) > REL_TOL * max(abs(fa), abs(fb), 1.0):
                    fdiffs.append((k, f, va, vb))
            elif va != vb:
                fdiffs.append((k, f, va, vb))
    return only_o, only_n, fdiffs, tie_at_limit


def main() -> None:
    regions = get_regions()
    cases = [(rn, rkw, tt, d) for rn, rkw in regions for tt in ("A1", "B1") for d in (90, 180)]
    print(f"검증 대상: {len(cases)} 조합", flush=True)

    t0 = time.perf_counter()
    n_ok = n_tie = n_fail = 0
    fails: list[str] = []
    ties: list[str] = []
    for i, (rname, rkw, tt, d) in enumerate(cases, 1):
        new = call(False, days=d, tt=tt, **rkw)
        old = call(True, days=d, tt=tt, **rkw)
        oo, on, fd, tie = diff_items(old["items"], new["items"])
        label = f"{rname} {tt} {d}d"
        if fd or ((oo or on) and not tie):
            n_fail += 1
            detail = [f"FAIL {label}  count old={old['count']} new={new['count']}"]
            for k in list(oo)[:5]:
                detail.append(f"  레거시에만: {k}")
            for k in list(on)[:5]:
                detail.append(f"  rollup에만: {k}")
            for k, f, va, vb in fd[:10]:
                detail.append(f"  필드차 {k} .{f}: {va!r} != {vb!r}")
            fails.append("\n".join(detail))
            print(detail[0], flush=True)
        elif tie:
            n_tie += 1
            ties.append(f"tie@limit {label} (경계동률 old-only={len(oo)} new-only={len(on)})")
        else:
            n_ok += 1
        if i % 100 == 0:
            el = time.perf_counter() - t0
            print(f"  {i}/{len(cases)}  ok={n_ok} tie={n_tie} fail={n_fail}  "
                  f"{el:.0f}s (ETA {el / i * (len(cases) - i):.0f}s)", flush=True)

    el = time.perf_counter() - t0
    verdict = "PASS" if n_fail == 0 else "FAIL"
    lines = [
        f"tx_avg_rollup 전수 검증 결과 — {verdict}",
        f"조합 {len(cases)}개: 완전일치 {n_ok} / tie@limit(허용) {n_tie} / 불일치 {n_fail}",
        f"소요 {el:.0f}s",
        "",
        *ties,
        "",
        *fails,
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:3]), flush=True)
    print(f"리포트: {REPORT}", flush=True)
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
