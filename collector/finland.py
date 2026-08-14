# -*- coding: utf-8 -*-
"""네이버 신규 부동산(fin.land) 건물·단지 정보 조회 + 캐시.

왜 필요한가 (2026-08-14)
  매물점검 ⑨사용승인일이 멀쩡한 매물을 위반으로 찍는 오탐이 있었다. 원인은 우리가 보던
  new.land `/api/articles/{no}` 응답에 사용승인일이 없는 매물이 있는데, 정작 네이버 광고
  화면에는 **건축물 정보** 블록으로 버젓이 노출된다는 것이었다(빌라 2643364583·2643352573).
  그 값은 fin.land 의 별도 API 가 단지·건물 단위로 준다.

왜 브리지를 거치나
  fin.land 는 TLS/HTTP2 지문으로 클라이언트를 가린다. 헤더를 완전히 맞춘 curl 도 429,
  헤드리스 크롬은 404 다. Xvfb 위 헤드풀 크로미움 안에서 fetch 해야만 통과한다.
  그래서 nfind 박스에 브리지(koczip-finland.service)를 두고 SSH 터널로 부른다.

캐시
  건물 사실관계(사용승인일·층수·세대수·주차·용적률)는 거의 안 변하는 정적 데이터다.
  ondemand_ledger 와 같은 원칙으로 오래 보관한다(기본 180일).
"""
from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# 본서버에서 SSH 터널로 nfind:4320 을 이 포트에 붙여 쓴다(carosell·radar 와 동일 구조).
BRIDGE = "http://127.0.0.1:4320"
TIMEOUT_S = 150            # 매물 1건당 페이지 로드가 있어 넉넉히 준다
TTL_S = 180 * 86400        # 정적 데이터 — 180일
NEG_TTL_S = 7 * 86400      # 못 찾은 건은 1주일만 기억(나중에 매칭될 수 있다)

_DB_PATH: Path | None = None

FIELDS = ("complex_number", "building_number", "use_approve_ymd", "total_floor",
          "underground_floor", "household_count", "elevator_count", "building_use",
          "main_structure", "parking_total", "parking_per_household",
          "floor_area_ratio", "building_coverage_ratio", "construction_company",
          "complex_name", "jibun", "road_name")


def _db(path: str | Path | None = None) -> sqlite3.Connection:
    global _DB_PATH
    if path:
        _DB_PATH = Path(path)
    if _DB_PATH is None:
        _DB_PATH = Path(__file__).resolve().parent.parent / "data" / "finland_cache.sqlite"
    c = sqlite3.connect(_DB_PATH, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA journal_size_limit=134217728")
    c.execute("""CREATE TABLE IF NOT EXISTS building_cache(
        article_no TEXT PRIMARY KEY,
        ok INTEGER NOT NULL,
        reason TEXT,
        payload TEXT,
        fetched_at REAL NOT NULL)""")
    return c


def _get_cached(article_no: str) -> dict[str, Any] | None:
    with _db() as c:
        row = c.execute("SELECT ok, reason, payload, fetched_at FROM building_cache"
                        " WHERE article_no=?", (str(article_no),)).fetchone()
    if not row:
        return None
    ok, reason, payload, at = row
    if time.time() - at > (TTL_S if ok else NEG_TTL_S):
        return None
    if not ok:
        return {"ok": False, "reason": reason, "_cached": True}
    d = json.loads(payload)
    # payload 에는 FIELDS 만 담기므로 ok 를 여기서 되살린다.
    # 이게 빠져 있어 캐시 히트일 때 호출부의 `if r.get("ok")` 가 전부 거짓이 됐다(2026-08-14).
    d["ok"] = True
    d["_cached"] = True
    return d


def _put_cache(article_no: str, data: dict) -> None:
    with _db() as c:
        c.execute("INSERT OR REPLACE INTO building_cache(article_no, ok, reason, payload, fetched_at)"
                  " VALUES(?,?,?,?,?)",
                  (str(article_no), 1 if data.get("ok") else 0, data.get("reason"),
                   json.dumps({k: data.get(k) for k in FIELDS}, ensure_ascii=False)
                   if data.get("ok") else None, time.time()))
        c.commit()


def building_for_article(article_no: str, *, use_cache: bool = True) -> dict[str, Any] | None:
    """매물번호 → 네이버가 광고에 싣는 건물 사실관계. 실패 시 {'ok': False, 'reason': ...}.

    반환 dict 는 점검 엔진이 바로 쓰도록 평평하다(use_approve_ymd 등 FIELDS 참조).
    """
    if use_cache:
        hit = _get_cached(article_no)
        if hit is not None:
            return hit
    url = f"{BRIDGE}/article?articleNumber={article_no}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:                     # 브리지가 502 로 사유를 준다
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:                                   # noqa: BLE001
            return {"ok": False, "reason": f"http_{e.code}"}
    except Exception as e:                                  # noqa: BLE001
        # 브리지가 죽었거나 터널이 끊긴 경우 — 캐시에 남기지 않는다(일시 장애).
        return {"ok": False, "reason": f"bridge_down:{type(e).__name__}", "_transient": True}
    if not data.get("_transient"):
        _put_cache(article_no, data)
    return data


def health() -> dict[str, Any]:
    """브리지가 살아 있고 세션이 데워져 있는지."""
    try:
        with urllib.request.urlopen(f"{BRIDGE}/health", timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                                  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}
