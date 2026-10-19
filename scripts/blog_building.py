# -*- coding: utf-8 -*-
"""네이버 플레이스 블로그리뷰에서 상업용 빌딩의 운영·임대 정보를 수집한다.

왜 이게 핵심인가
  건축물대장은 언제든 받을 수 있는 공부(公簿)다. 반면 블로그는 **사라진다** —
  공실은 달마다 바뀌고 글은 지워진다. 그리고 대장에 없는 칸(평당 보증금·임대료·관리비,
  층별 공실, 렌트프리, 냉난방, 주차 운영조건)이 여기에만 있다.

경로 (2026-10-19 실증)
  건물명 + 도로명주소
    → pcmap.place.naver.com/place/list?query={건물명}      place_id 찾기
       category 가 빌딩/임대업 계열 + **도로명 일치**인 것만 채택(오귀속 방지)
    → /place/{id}/review/ugc                               블로그 10건
    → m.blog.naver.com/{id}/{post}  원문                    ★ 여기서만 임대료가 나온다

  주의: 플레이스 응답의 FsasReview.contents 는 1,200자에서 잘린다. 그것만 보면
  "블로그에 임대료 없음"으로 오판한다(실측 10건 중 0건). 원문을 받아야 한다.

본문을 저장한다 (2026-10-19 방침 변경)
  이 글들은 **표**로 임대조건을 적는다. 표를 읽으면 층별 공실 재고가 나온다
  (원자 127 → 537, 3.8배). 파서는 계속 고쳐질 것이므로 표 HTML + 평문을 zlib 으로
  남긴다 — 글당 5.7KB, 1,264글에 7.2MB. 그러면 재수집 없이 재파싱만 하면 된다
  (scripts/blog_reparse.py). 저장은 우리 내부 검증용 캐시이고 재배포하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import zlib
from datetime import date

from curl_cffi import requests as creq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blog_tables as T                                      # noqa: E402

HOME = os.path.expanduser("~/auto/naverreal_data")
DB = os.path.join(HOME, "blog_building.sqlite")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9",
     "Referer": "https://map.naver.com/"}
# 빌딩 자체인 플레이스만. 입점 식당·카페는 같은 주소라도 건물이 아니다.
BLD_CAT = ("빌딩", "임대업", "부동산", "오피스", "사무실")


def db_init():
    os.makedirs(HOME, exist_ok=True)
    d = sqlite3.connect(DB, timeout=60)
    d.execute("PRAGMA journal_mode=WAL")
    d.execute("PRAGMA journal_size_limit=1073741824")        # WAL 팽창 방지
    d.executescript("""
    CREATE TABLE IF NOT EXISTS place(
      seed_name TEXT PRIMARY KEY, seed_addr TEXT,
      place_id TEXT, place_name TEXT, category TEXT, road_addr TEXT,
      status TEXT, checked_on TEXT);
    CREATE TABLE IF NOT EXISTS post(
      url TEXT PRIMARY KEY, place_id TEXT, seed_name TEXT,
      title TEXT, blogger TEXT, posted_on TEXT, n_chars INTEGER, fetched_on TEXT);
    CREATE TABLE IF NOT EXISTS fact(
      url TEXT, seed_name TEXT, field TEXT, value TEXT, posted_on TEXT,
      PRIMARY KEY(url, field));
    CREATE INDEX IF NOT EXISTS fact_seed ON fact(seed_name, field);

    -- 본문 캐시(zlib). 파서를 고칠 때 재수집하지 않기 위한 것.
    CREATE TABLE IF NOT EXISTS body(
      url TEXT PRIMARY KEY, tables BLOB, text BLOB, n_tab INTEGER, n_txt INTEGER);

    -- 표에서 나온 건물 제원(블로거 표기 그대로. 대조는 건축물대장이 본다)
    CREATE TABLE IF NOT EXISTS spec(
      url TEXT, seed_name TEXT, field TEXT, value TEXT, posted_on TEXT,
      PRIMARY KEY(url, field));
    CREATE INDEX IF NOT EXISTS spec_seed ON spec(seed_name, field);

    -- 평당 단가. 층마다 다르면 범위로 적히므로 lo/hi 둘 다 남긴다.
    CREATE TABLE IF NOT EXISTS unit_price(
      url TEXT, seed_name TEXT, field TEXT, lo REAL, hi REAL,
      derived INTEGER, posted_on TEXT, PRIMARY KEY(url, field));
    CREATE INDEX IF NOT EXISTS up_seed ON unit_price(seed_name, field);

    -- ★ 층별 공실 재고. 지금까지 스키마에 없던 차원이다.
    CREATE TABLE IF NOT EXISTS floor_area(
      url TEXT, seed_name TEXT, idx INTEGER, floor TEXT, span INTEGER,
      rent_py REAL, rent_m2 REAL, excl_py REAL, excl_m2 REAL,
      movein TEXT, posted_on TEXT, PRIMARY KEY(url, idx));
    CREATE INDEX IF NOT EXISTS fa_seed ON floor_area(seed_name, posted_on);
    CREATE TABLE IF NOT EXISTS floor_price(
      url TEXT, seed_name TEXT, idx INTEGER, floor TEXT, span INTEGER,
      deposit REAL, rent REAL, cam REAL, posted_on TEXT, PRIMARY KEY(url, idx));
    CREATE INDEX IF NOT EXISTS fp_seed ON floor_price(seed_name, posted_on);
    """)
    for col, typ in (("posted_raw", "TEXT"), ("kind", "TEXT")):
        try:
            d.execute(f"ALTER TABLE post ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    d.commit()
    return d


def apollo(url, delay=2.0):
    time.sleep(delay)
    try:
        r = creq.get(url, headers=H, impersonate="chrome120", timeout=30)
    except Exception:                                        # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    i = r.text.find("window.__APOLLO_STATE__")
    if i < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(r.text[r.text.find("{", i):])[0]
    except Exception:                                        # noqa: BLE001
        return None


def norm_addr(s):
    """'서울시중구세종대로73' → ('서울시중구세종대로','73') / '세종대로 73' → ('세종대로','73').

    PDF 의 한글 주소는 공백이 없어 시·구까지 도로명에 붙어 버린다. 그래서 도로명은
    **접미 비교**로 맞춘다(아래 same_addr). 숫자는 그대로 쓴다.
    """
    if not s:
        return None
    s = s.replace(" ", "")
    m = re.search(r"([가-힣A-Za-z0-9]+(?:대로|로|길))(\d+(?:-\d+)?)", s)
    return (m.group(1), m.group(2)) if m else None


def same_addr(a, b):
    """번지가 같고 도로명이 서로의 접미사면 같은 주소로 본다."""
    if not a or not b or a[1] != b[1]:
        return False
    x, y = a[0], b[0]
    return x.endswith(y) or y.endswith(x)


def find_place(name, addr, delay):
    st = apollo("https://pcmap.place.naver.com/place/list?query="
                + urllib.parse.quote(name), delay)
    if not st:
        return None, "검색실패"
    want = norm_addr(addr)
    cands = [v for v in st.values()
             if isinstance(v, dict) and v.get("__typename") == "PlaceListBusinessesItem"
             and v.get("name")]
    best = None
    for v in cands:
        cat = v.get("category") or ""
        if not any(c in cat for c in BLD_CAT):
            continue
        got = norm_addr(v.get("roadAddress") or v.get("address") or "")
        if same_addr(want, got):                     # 도로명·번지 일치 = 확정
            return v, "ok"
        if best is None and name.replace(" ", "") in (v.get("name") or "").replace(" ", ""):
            best = v
    if best is not None:
        return best, "이름만일치"                     # 주소 확인 안 됨 — 보류 표시
    return None, "빌딩후보없음"


# 표에 안 들어가고 본문에만 적히는 것들만 남긴다. 표로 얻는 값(평당 단가·연면적·
# 전용률·준공·총주차대수)은 **여기서 뺐다** — 특히 '주차 대수'는 호실 배정분
# ("10대 이용 가능")을 건물 총대수로 오인해 362대짜리를 10대로 만든 전력이 있다.
PAT = {
    "렌트프리":  r"(렌트\s*프리[^.\n]{0,40})",
    "냉난방":    r"(중앙\s*냉난방|개별\s*냉난방|시스템\s*에어컨|EHP|FCU)",
    "무주설계":  r"(무주\s*설계|기둥\s*없[는이]|중간\s*기둥\s*없)",
    "층고":      r"(층고[\s:]*[\d.]+\s*(?:m|미터|mm))",
    "역도보":    r"([가-힣]+역[^.\n]{0,12}도보\s*\d+\s*분)",
    "리모델링":  r"((?:19|20)\d{2}\s*년?\s*(?:부분\s*)?(?:리모델링|리노베이션))",
    "보증금배수": r"(보증금[^.\n]{0,10}임대료\s*\d+\s*배|임대료\s*\d+\s*배)",
}


def fetch_post(url, delay):
    """원문 HTML → (표만 모은 HTML, 평문). 둘 다 저장해 재파싱 가능하게 한다."""
    time.sleep(delay)
    try:
        r = creq.get(url, headers={**H, "Referer": "https://m.blog.naver.com/"},
                     impersonate="chrome120", timeout=30)
    except Exception:                                        # noqa: BLE001
        return None, None
    if r.status_code != 200:
        return None, None
    tabs = "\n".join(re.findall(r"<table.*?</table>", r.text, flags=re.S))
    b = re.sub(r"<script.*?</script>", " ", r.text, flags=re.S)
    b = re.sub(r"<style.*?</style>", " ", b, flags=re.S)
    b = re.sub(r"<(br|/p|/div|/td|/tr|/h\d)[^>]*>", "\n", b)
    b = re.sub(r"<[^>]+>", " ", b)
    b = b.replace("&nbsp;", " ").replace("\xa0", " ")
    b = re.sub(r"[ \t]+", " ", b)
    return tabs, re.sub(r"\n{3,}", "\n\n", b).strip()


def store(d, url, seed, pid, rev, tabs, txt, today):
    """한 글에서 나온 모든 것을 쓴다. 호출 한 번에 커밋은 하지 않는다."""
    posted_raw = (rev.get("date") or "").strip()
    posted = T.norm_posted(posted_raw, today)
    src = (tabs or "") + "\n" + (txt or "")
    p = T.parse(tabs or "")
    kind = T.kind(src, p)

    d.execute("INSERT OR REPLACE INTO post(url,place_id,seed_name,title,blogger,"
              "posted_on,n_chars,fetched_on,posted_raw,kind) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (url, pid, seed, rev.get("title"), rev.get("name"), posted,
               len(txt or ""), today, posted_raw, kind))
    d.execute("INSERT OR REPLACE INTO body VALUES(?,?,?,?,?)",
              (url, zlib.compress((tabs or "").encode(), 9),
               zlib.compress((txt or "").encode(), 9), len(tabs or ""), len(txt or "")))

    n = 0
    for f, v in p["spec"].items():
        d.execute("INSERT OR REPLACE INTO spec VALUES(?,?,?,?,?)", (url, seed, f, v, posted))
        n += 1
    for f, (lo, hi) in p["unit"].items():
        d.execute("INSERT OR REPLACE INTO unit_price VALUES(?,?,?,?,?,?,?)",
                  (url, seed, f, lo, hi, int("unit_derived" in p["extra"]), posted))
        n += 1
    for r in p["floor_area"]:
        d.execute("INSERT OR REPLACE INTO floor_area VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (url, seed, r["idx"], r["floor"], r["span"], r["rent_py"], r["rent_m2"],
                   r["excl_py"], r["excl_m2"], r["movein"], posted))
        n += 1
    for r in p["floor_price"]:
        d.execute("INSERT OR REPLACE INTO floor_price VALUES(?,?,?,?,?,?,?,?,?)",
                  (url, seed, r["idx"], r["floor"], r["span"], r["deposit"], r["rent"],
                   r["cam"], posted))
        n += 1
    for f, v in p["extra"].items():
        d.execute("INSERT OR REPLACE INTO fact VALUES(?,?,?,?,?)", (url, seed, f, v, posted))
        n += 1
    for f, pat in PAT.items():
        m = re.search(pat, txt or "")
        if m:
            d.execute("INSERT OR REPLACE INTO fact VALUES(?,?,?,?,?)",
                      (url, seed, f, m.group(1).strip()[:60], posted))
            n += 1
    return kind, n, len(p["floor_area"]) + len(p["floor_price"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", required=True, help="빌딩 시드 JSON [{name, addr}]")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--max-posts", type=int, default=4, help="빌딩당 원문 받을 글 수")
    ap.add_argument("--redo", action="store_true",
                    help="이미 ok 인 빌딩도 다시 — 파서를 고쳤을 때 쓴다")
    a = ap.parse_args()

    d = db_init()
    today = date.today().isoformat()
    seeds = json.load(open(a.seeds))
    done = set() if a.redo else {
        r[0] for r in d.execute("SELECT seed_name FROM place WHERE status='ok'")}
    todo = [s for s in seeds if s["name"] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"시드 {len(seeds)} · 할 일 {len(todo)} · 지연 {a.delay}s "
          f"· 예상 {len(todo)*(1+a.max_posts)*a.delay/60:.0f}분", flush=True)

    t0 = time.time()
    n_ok = n_post = n_atom = n_floor = 0
    kinds: dict[str, int] = {}
    for i, s in enumerate(todo, 1):
        nm, addr = s["name"], s.get("addr", "")
        pv, why = find_place(nm, addr, a.delay)
        pid = (pv or {}).get("id")
        d.execute("INSERT OR REPLACE INTO place VALUES(?,?,?,?,?,?,?,?)",
                  (nm, addr, pid, (pv or {}).get("name"), (pv or {}).get("category"),
                   (pv or {}).get("roadAddress"), why, today))
        d.commit()
        if why != "ok":
            print(f"[{i}/{len(todo)}] {nm}: {why}", flush=True)
            continue
        n_ok += 1
        st = apollo(f"https://pcmap.place.naver.com/place/{pid}/review/ugc", a.delay)
        revs = [v for v in (st or {}).values()
                if isinstance(v, dict) and v.get("__typename") == "FsasReview"
                and (v.get("url") or "").startswith("https://m.blog.naver.com/")]
        got = fl = 0
        for v in revs[:a.max_posts]:
            tabs, txt = fetch_post(v["url"], a.delay)
            if txt is None:
                continue
            kind, n, nf = store(d, v["url"], nm, pid, v, tabs, txt, today)
            kinds[kind] = kinds.get(kind, 0) + 1
            n_atom += n
            n_floor += nf
            got += 1
            fl += nf
            n_post += 1
        d.commit()
        print(f"[{i}/{len(todo)}] {nm} → {pid} ({pv.get('category')}) · "
              f"글 {got}건 · 층별 {fl}행", flush=True)

    print(f"\n빌딩 매칭 {n_ok}/{len(todo)} · 글 {n_post} · 원자 {n_atom} · "
          f"층별 {n_floor}행 · {kinds} · {(time.time()-t0)/60:.1f}분", flush=True)
    d.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
