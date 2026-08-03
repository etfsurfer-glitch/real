#!/usr/bin/env python3
"""온톨로지와 실제 도구가 어긋났는지 검사한다.

도구를 새로 만들고 온톨로지에 안 적으면 AI가 그 도구의 쓰임새·제약을 모른 채 호출한다.
반대로 온톨로지에만 있고 구현이 없으면 존재하지 않는 도구를 부르려 한다.
둘 다 조용히 오답을 만들어서, CI처럼 매번 확인할 수 있게 분리해 둔다.

  python scripts/check_ontology.py     # 어긋나면 exit 1
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    agent = (ROOT / "scripts" / "ai_agent.py").read_text(encoding="utf-8")
    onto = (ROOT / "scripts" / "ai_ontology.py").read_text(encoding="utf-8")

    impl = set(re.findall(
        r"^def (find_[a-z_]+|get_[a-z_]+|rank_[a-z_]+|compare_[a-z_]+|calc_[a-z_]+|region_[a-z_]+)\(",
        agent, re.M))
    blk = onto[onto.index("TOOLS = {"):onto.index("REGION_ALIASES")]
    declared = set(re.findall(r'"([a-z_]{4,40})":\s*\(', blk))

    missing = sorted(impl - declared)      # 구현했는데 온톨로지에 없음
    ghost = sorted(declared - impl)        # 온톨로지에만 있고 구현 없음
    print(f"구현 도구 {len(impl)}개 · 온톨로지 선언 {len(declared)}개")
    if missing:
        print("✗ 온톨로지에 빠진 도구:", ", ".join(missing))
    if ghost:
        print("✗ 구현이 없는 선언:", ", ".join(ghost))
    if not (missing or ghost):
        print("✓ 도구 정합성 이상 없음")

    from importlib import import_module
    sys.path.insert(0, str(ROOT))
    mod = import_module("scripts.ai_ontology")
    n = len(mod.ONTOLOGY_PROMPT)
    print(f"온톨로지 프롬프트 {n:,}자")
    if n > 12000:
        print("△ 프롬프트가 길다 — 매 요청 토큰을 먹는다. 축약 검토")
    return 1 if (missing or ghost) else 0


if __name__ == "__main__":
    raise SystemExit(main())
