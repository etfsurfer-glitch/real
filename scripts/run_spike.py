"""End-to-end spike for 서초동.

1. Ensure Bearer creds (Playwright captures if missing / expired)
2. Walk regions: 0000000000 -> 서울 -> 서초구 -> dongs starting with "서초"
3. For each 서초N동, list complexes
4. For the first complex, fetch articles for A1/B1/B2
5. Print summary; dump raw JSON to data/snapshots/spike_seocho/<dong>/

No DB writes yet — this is just to validate the auth+endpoint loop.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Korean Windows console defaults to cp949; force UTF-8 so prints don't blow up.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.creds import ensure_creds  # noqa: E402
from collector.naver import (  # noqa: E402
    TRADE_TYPES,
    articles_for_complex,
    complexes_in_region,
    find_child,
    list_region_children,
)

SNAP_DIR = settings.snapshot_dir / "spike_seocho"


def dump(name: str, payload) -> Path:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    p = SNAP_DIR / name
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def main() -> int:
    print("[1] ensure_creds() — may launch Playwright if no cache")
    t0 = time.time()
    creds = ensure_creds()
    print(f"    captured/loaded in {time.time() - t0:.1f}s  bearer={creds['bearer'][:24]}...")
    print(f"    cookie keys: {[c.split('=')[0] for c in creds['cookie'].split('; ')]}")

    print("\n[2] walk regions to 서초구")
    sido = list_region_children("0000000000", creds)
    seoul = find_child(sido, "서울")
    print(f"    서울: {seoul}")
    if not seoul:
        return 1

    gu_list = list_region_children(seoul["cortarNo"], creds)
    seocho_gu = find_child(gu_list, "서초구")
    print(f"    서초구: {seocho_gu}")
    if not seocho_gu:
        return 1

    dong_list = list_region_children(seocho_gu["cortarNo"], creds)
    seocho_dongs = [d for d in dong_list if (d.get("cortarName") or "").startswith("서초")]
    print(f"\n[3] 서초N동 후보 {len(seocho_dongs)}개")
    for d in seocho_dongs:
        print(f"    {d['cortarNo']}  {d['cortarName']}")
    dump("01_seocho_dongs.json", seocho_dongs)

    print("\n[4] 단지 목록")
    all_complexes: dict[str, list[dict]] = {}
    for d in seocho_dongs:
        cps = complexes_in_region(d["cortarNo"], creds)
        all_complexes[d["cortarName"]] = cps
        print(f"    {d['cortarName']:<10} 단지 {len(cps):>4}개")
    dump("02_complexes_by_dong.json", all_complexes)

    # Pick the first non-empty dong's first complex
    sample_complex = None
    for nm, cps in all_complexes.items():
        if cps:
            sample_complex = cps[0]
            print(f"\n[5] 샘플 단지: {nm} / {sample_complex.get('complexName')} "
                  f"(no={sample_complex.get('complexNo')})")
            break
    if not sample_complex:
        print("  no complexes found; cannot sample articles")
        return 0

    cno = str(sample_complex.get("complexNo"))
    print(f"\n[6] 매물 페이지네이션 (A1/B1/B2)")
    by_trade: dict[str, list[dict]] = {}
    for tr in TRADE_TYPES:
        items = list(articles_for_complex(cno, tr, creds))
        by_trade[tr] = items
        sample = items[0] if items else None
        print(f"    {tr}: {len(items)}건  sample dealOrWarrantPrc={sample.get('dealOrWarrantPrc') if sample else '-'}")
    dump(f"03_articles_{cno}.json", by_trade)

    print(f"\n[done] artifacts in {SNAP_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
