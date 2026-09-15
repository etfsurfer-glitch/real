# -*- coding: utf-8 -*-
"""입주예정물량 적재 — 한국부동산원 주택공급정보(data.go.kr 15111714).

개업입지(학원 제휴)의 '미래 수요' 축: 향후 24개월 단지별 입주예정(주소·세대수·입주월).
다운로드는 무인증 — 메타데이터 POST로 최신 atchFileId를 동적 해석 후 fileDownload.do.
주소(지번) → bjd 법정동표로 동(cortar10)·시군구(sgg5) 매핑. 반기 갱신 데이터라 월 1회면 충분.

사용: .venv/bin/python scripts/load_molip_supply.py          # 다운로드+적재
      .venv/bin/python scripts/load_molip_supply.py --file X # 로컬 CSV 적재만
"""
from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "naverreal.sqlite"
PK = "15111714"
DETAIL_PK = "uddi:0b257760-ac19-4841-adb4-b38b4d153397"
UA = {"User-Agent": "Mozilla/5.0", "Referer": f"https://www.data.go.kr/data/{PK}/fileData.do"}


def _fetch_csv() -> str:
    """메타데이터에서 최신 atchFileId 해석 → CSV 본문. (파일 교체돼도 자동 추적)"""
    body = urllib.parse.urlencode({"publicDataPk": PK, "publicDataDetailPk": DETAIL_PK}).encode()
    req = urllib.request.Request(
        "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do", data=body, headers=UA)
    meta = json.loads(urllib.request.urlopen(req, timeout=30).read())
    vo = meta.get("fileDataRegistVO") or {}
    fid, sn = vo.get("atchFileId"), vo.get("fileDetailSn") or 1
    if not fid:
        raise RuntimeError("atchFileId 해석 실패 — data.go.kr 응답 구조 변경?")
    url = f"https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={fid}&fileDetailSn={sn}"
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    txt = raw.decode("utf-8-sig", errors="replace")
    if "입주예정월" not in txt.split("\n", 1)[0]:
        raise RuntimeError("CSV 헤더 불일치 — 포맷 변경 의심")
    print(f"다운로드: {vo.get('orginlFileNm')} ({len(raw):,}B, atchFileId={fid})")
    return txt


# 주소의 옛 표기 → bjd 현행 명칭 별칭(포함 판정용).
# 인천 2026-07 개편: 공급데이터 주소가 옛 구(중·동·서구)로 온다 → 신구의 '옛구 이름'을 인정.
_SGG_ALIAS = {"제물포구": ("중구", "동구"), "영종구": ("중구",),
              "서해구": ("서구",), "검단구": ("서구",)}
# 시도: 주소 표기 ↔ bjd sido_nm(통합특별시 등) 느슨 대조용 앞머리.
_SIDO_HEADS = {"전남광주통합특별시": ("전라남도", "광주광역시", "전남", "광주")}


def _sido_ok(addr: str, sido: str) -> bool:
    heads = _SIDO_HEADS.get(sido, (sido,))
    return any(addr.startswith(h[:2]) for h in heads)


def _sgg_ok(addr: str, sgg: str) -> bool:
    toks = (sgg or "").split()
    if all(t in addr for t in toks):
        return True
    return any(a in addr for t in toks for a in _SGG_ALIAS.get(t, ()))


def _map_region(c: sqlite3.Connection, addr: str) -> tuple[str | None, str | None, str | None]:
    """주소 → (sgg5, umd_nm, cortar10). 주소 토큰을 bjd 법정동명과 직접 대조(정규식 의존 제거)
    — '보문동1가' 같은 …가 표기, 통합시도·인천 옛구 표기까지 커버."""
    addr = (addr or "").strip()
    toks = [t for t in addr.replace(" 산 ", " ").split() if t and not t[0].isdigit()]
    # 뒤쪽 토큰부터: 법정동명은 주소 후반부에 온다
    for tok in reversed(toks):
        rows = c.execute("SELECT code10, sido_nm, sgg_nm FROM bjd WHERE umd_nm=?", (tok,)).fetchall()
        if not rows:
            continue
        for c10, sido, sgg in rows:
            if _sido_ok(addr, sido or "") and _sgg_ok(addr, sgg or ""):
                return c10[:5], tok, c10
        if len(rows) == 1:                       # 전국 유일 동이면 수용
            return rows[0][0][:5], tok, rows[0][0]
        return None, tok, None                   # 동은 찾았는데 시군구 검증 실패
    return None, None, None


def main() -> int:
    if "--file" in sys.argv:
        txt = Path(sys.argv[sys.argv.index("--file") + 1]).read_text("utf-8-sig")
    else:
        txt = _fetch_csv()
    rows = list(csv.DictReader(io.StringIO(txt)))
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS molip_supply(
        ym TEXT, sido TEXT, biz_type TEXT, addr TEXT, apt_nm TEXT, hh INTEGER,
        sgg5 TEXT, umd_nm TEXT, cortar10 TEXT, loaded_at TEXT DEFAULT (datetime('now','+9 hours')),
        PRIMARY KEY(ym, addr, apt_nm))""")
    c.execute("CREATE INDEX IF NOT EXISTS molip_sgg ON molip_supply(sgg5, ym)")
    c.execute("CREATE INDEX IF NOT EXISTS molip_cortar ON molip_supply(cortar10, ym)")
    c.execute("DELETE FROM molip_supply")        # 스냅샷 교체(반기 전량 갱신)
    ok = miss = 0
    for r in rows:
        sgg5, umd, c10 = _map_region(c, r.get("주소", ""))
        if c10:
            ok += 1
        else:
            miss += 1
        c.execute("INSERT OR REPLACE INTO molip_supply(ym,sido,biz_type,addr,apt_nm,hh,sgg5,umd_nm,cortar10) "
                  "VALUES(?,?,?,?,?,?,?,?,?)",
                  (r.get("입주예정월"), r.get("지역"), r.get("사업유형"), r.get("주소"),
                   r.get("아파트명"), int(r.get("세대수") or 0), sgg5, umd, c10))
    c.commit()
    tot = c.execute("SELECT COUNT(*), SUM(hh) FROM molip_supply").fetchone()
    print(f"적재 {tot[0]}행 · {tot[1]:,}세대 | 동매핑 {ok} / 미매핑 {miss}")
    for row in c.execute("SELECT sgg5, SUM(hh) h, COUNT(*) n FROM molip_supply WHERE cortar10 IS NOT NULL "
                         "GROUP BY sgg5 ORDER BY h DESC LIMIT 5"):
        print("  top:", row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
