# -*- coding: utf-8 -*-
"""블로그 원문의 **서술형** 빌딩 정보를 구조화한다.

왜 LLM 인가
  수치(평당 임대료·전용률)는 정규식으로 잡힌다. 그런데 정작 실무에서 돈이 되는 건 서술이다 —
  "아직 원상회복 전이라 인테리어를 그대로 쓸 수 있다", "임대는 층 전체로만 진행된다",
  "9~11층이 서로 연결돼 이전에 한 기업이 다 썼다". 이건 양식이 없어 정규식으로 못 잡고,
  **임대안내문 PDF 에도 없다**(PM 사가 PPT 에 쓰지 않는 종류의 정보다).

저작권
  블로그 문장을 그대로 담지 않는다. 모델에게 **우리 표현의 짧은 구(句)로 바꿔** 달라고 하고,
  출처 URL·작성일만 남긴다. 사실을 옮기는 것이지 글을 복제하는 것이 아니다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import date

from curl_cffi import requests as creq

HOME = os.path.expanduser("~/auto/naverreal_data")
DB = os.path.join(HOME, "blog_building.sqlite")
ENV = os.path.join(HOME, ".env")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 뽑을 서술 항목. 전부 "PDF 에 없는데 거래 판단에 쓰이는 것"으로 골랐다.
FIELDS = {
    "rent_free":       "렌트프리 조건(개월·형태). 없으면 null",
    "fitout":          "핏아웃·인테리어 공사 지원",
    "lease_unit":      "임대 단위 제약(층 전체만 / 분할 가능 / 최소 면적)",
    "restoration":     "원상회복 상태와 기존 인테리어 승계 가능 여부",
    "floor_link":      "층간 연결·전용 동선(계단 연결 등)",
    "core":            "코어(승강기홀) 위치·형태",
    "toilet":          "화장실 구조(층별/남녀분리/외부)",
    "direction":       "건물 방향(출입구 기준)",
    "ceiling":         "층고",
    "hvac":            "냉난방 방식",
    "parking_policy":  "주차 제공 조건(기본 N평당 1대, 추가·유료 조건)",
    "vacancy_context": "공실이 생긴 경위나 추세에 대한 서술",
    "tenants":         "입주사·주요 임차인",
    "amenity":         "건물 내 편의시설(리테일·식당·아케이드 등)",
    "access":          "역 연결 방식(지하 직결/도보 N분)",
    "recent_work":     "리모델링·대수선 이력",
    "condition_note":  "건물 상태에 대한 평가(위 항목에 안 들어가는 것)",
}

SYS = (
    "너는 한국 오피스 빌딩 임대 자료를 읽고 사실만 뽑는 분석가다.\n"
    "입력은 공인중개사가 쓴 블로그 글이다. 아래 규칙을 지켜라.\n"
    "1) 글에 **명시된 것만** 담는다. 추측·일반론·홍보 문구는 버린다.\n"
    "2) 원문 문장을 그대로 베끼지 말고 **20자 내외의 사실 구(句)로 요약**해 적는다.\n"
    "3) 해당 내용이 없으면 그 항목은 null 로 둔다. 모르면 null 이다.\n"
    "4) 건물 자체가 아니라 중개사·회사 홍보인 내용은 전부 버린다.\n"
    "5) 반드시 JSON 객체 하나만 출력한다."
)


def client():
    for line in open(ENV):
        if line.startswith("GEMINI_API_KEY="):
            os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip()
    from google import genai
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def db():
    d = sqlite3.connect(DB, timeout=60)
    d.execute("PRAGMA journal_mode=WAL")
    d.executescript("""
    CREATE TABLE IF NOT EXISTS narrative(
      url TEXT, seed_name TEXT, field TEXT, value TEXT, posted_on TEXT,
      PRIMARY KEY(url, field));
    CREATE INDEX IF NOT EXISTS nar_seed ON narrative(seed_name, field);
    CREATE TABLE IF NOT EXISTS narrative_done(
      url TEXT PRIMARY KEY, n_fields INTEGER, done_on TEXT);
    """)
    return d


def fetch_text(url, delay=2.0):
    time.sleep(delay)
    try:
        r = creq.get(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9",
                                   "Referer": "https://m.blog.naver.com/"},
                     impersonate="chrome120", timeout=30)
    except Exception:                                        # noqa: BLE001
        return ""
    if r.status_code != 200:
        return ""
    b = re.sub(r"<script.*?</script>", " ", r.text, flags=re.S)
    b = re.sub(r"<style.*?</style>", " ", b, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", b).replace("&nbsp;", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def extract(cl, bld, text):
    from google.genai import types
    schema = {"type": "OBJECT", "properties":
              {k: {"type": "STRING", "nullable": True, "description": v}
               for k, v in FIELDS.items()}}
    cfg = types.GenerateContentConfig(
        system_instruction=SYS, temperature=0,
        thinking_config=types.ThinkingConfig(thinking_budget=0),   # 속도(AI 지연 메모 참고)
        response_mime_type="application/json", response_schema=schema)
    prompt = f"[빌딩] {bld}\n\n[블로그 본문]\n{text[:14000]}"
    try:
        r = cl.models.generate_content(model=MODEL, contents=prompt, config=cfg)
    except Exception as e:                                   # noqa: BLE001
        return None, str(e)[:70]
    try:
        return json.loads(r.text), ""
    except Exception:                                        # noqa: BLE001
        return None, "JSON 파싱 실패"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--show", action="store_true", help="뽑은 값을 화면에 출력")
    a = ap.parse_args()

    d = db()
    cl = client()
    rows = d.execute("""
        SELECT p.url, p.seed_name, p.posted_on, p.title FROM post p
        LEFT JOIN narrative_done n ON n.url = p.url
        WHERE n.url IS NULL ORDER BY p.seed_name, p.posted_on DESC""").fetchall()
    if a.limit:
        rows = rows[:a.limit]
    print(f"대상 글 {len(rows)}건 · 모델 {MODEL}", flush=True)

    n_ok = n_field = 0
    for i, (url, bld, posted, title) in enumerate(rows, 1):
        txt = fetch_text(url, a.delay)
        if len(txt) < 400:
            print(f"[{i}/{len(rows)}] {bld}: 본문 못 받음")
            continue
        got, err = extract(cl, bld, txt)
        if got is None:
            print(f"[{i}/{len(rows)}] {bld}: {err}")
            continue
        kept = {k: v for k, v in got.items()
                if v and str(v).strip() and str(v).strip().lower() not in ("null", "none", "-")}
        for k, v in kept.items():
            d.execute("INSERT OR REPLACE INTO narrative VALUES(?,?,?,?,?)",
                      (url, bld, k, str(v).strip()[:200], posted))
        d.execute("INSERT OR REPLACE INTO narrative_done VALUES(?,?,?)",
                  (url, len(kept), date.today().isoformat()))
        d.commit()
        n_ok += 1
        n_field += len(kept)
        print(f"[{i}/{len(rows)}] {bld} ({posted}) → {len(kept)}개", flush=True)
        if a.show and kept:
            for k, v in kept.items():
                print(f"      {k:<16}{v}")
    print(f"\n글 {n_ok}/{len(rows)} · 항목 {n_field}", flush=True)
    d.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
