#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNS 소재 레이더 — Threads 키워드 검색 수집기.

Meta 공식 Threads API 의 keyword search 는 '내 계정 글'만 검색된다(공개 전수 검색은
비즈니스 심사 대상). 그래서 nfind 박스에 이미 로그인해 둔 브라우저 세션을 그대로 쓴다
— /opt/koczip-sns 의 sns_worker.open_browser 를 재사용하므로 계정이 하나만 뜬다.

검색은 키워드마다 두 번 돈다.
  recent : 아직 안 터졌지만 반응이 붙기 시작한 글을 일찍 잡는다(이 도구의 핵심)
  top    : 지금 잘 나가는 글

Run: python3 collect.py [--limit 12] [--max-keywords 8]
"""
import argparse
import asyncio
import json
import re
import sqlite3
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path("/opt/koczip-radar")
DB = BASE / "radar.sqlite"
sys.path.insert(0, "/opt/koczip-sns")

SEARCH = "https://www.threads.com/search?q={q}&serp_type=default&filter={f}"
ME = "koczip_news"                       # 내 글은 소재가 아니다
FEED_KW = "(피드)"                        # 키워드 없이 홈 피드에서 주운 글의 표시
# 발행 워커(koczip-sns-engage)가 상시로 도는 탓에 같은 크롬 프로필을 쓰면 충돌한다.
# 로그인 세션만 복사한 별도 프로필을 써서 둘이 동시에 떠도 되게 한다.
PROFILE = "threads_radar"


def log(*a):
    print(datetime.now().strftime("%m-%d %H:%M:%S"), *a, flush=True)


def db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA journal_size_limit=268435456")
    return c


# ── 카드에서 글과 반응 수를 뜯는다 ────────────────────────────────────────
# Threads 검색 결과 카드에는 좋아요·댓글·리포스트·인용이 aria-label 로 붙는다.
# 숫자는 "1.2만", "3,456", "1.2K" 등으로 축약돼 오므로 파이썬에서 되돌린다.
COLLECT_JS = r"""() => {
  const out = [];
  const cards = document.querySelectorAll('div[data-pressable-container=true]');
  cards.forEach((el, i) => {
    const txt = (el.innerText || '').trim();
    // 밈은 사진이 본체라 글이 거의 없다 — 글자수로만 자르면 통째로 버려진다.
    // 미디어가 있으면 짧아도 남긴다.
    const media = [];
    el.querySelectorAll('img').forEach(m => {
      const r = m.getBoundingClientRect();
      // 프로필 사진은 화면에서 36x36 로 그려진다. 본문 이미지는 200px 이상.
      if (r.width < 80 || m.naturalWidth <= 150) return;
      const src = m.getAttribute('src') || '';
      if (src) media.push(src);
    });
    const hasVideo = !!el.querySelector('video');
    if ((!txt || txt.length < 20) && !media.length && !hasVideo) return;
    const a  = el.querySelector('a[href*="/post/"]');
    const au = el.querySelector('a[href^="/@"]');
    // 반응 숫자는 아이콘 옆 텍스트에 있다. aria-label 로 종류를 가른다.
    const stat = (re) => {
      const e = Array.from(el.querySelectorAll('[aria-label]')).find(x =>
        re.test((x.getAttribute('aria-label') || '').trim()));
      if (!e) return '';
      const host = e.closest('div[role=button],button,a') || e.parentElement;
      const t = host ? (host.innerText || '').trim() : '';
      return t.replace(/[^\d.,만천KkMm]/g, '');
    };
    // 시간 표기는 <time> 또는 카드 상단의 "3시간" 류 문자열
    const tm = el.querySelector('time');
    out.push({
      idx: i,
      href: a ? a.getAttribute('href') : '',
      author: au ? (au.getAttribute('href') || '').replace('/@', '').split('?')[0] : '',
      text: txt.slice(0, 1200),
      like:   stat(/^(like|좋아요|unlike|좋아요 취소)$/i),
      reply:  stat(/^(reply|답글|comment|댓글)$/i),
      repost: stat(/^(repost|리포스트|재게시)$/i),
      quote:  stat(/^(quote|인용)$/i),
      time_attr: tm ? (tm.getAttribute('datetime') || '') : '',
      time_txt:  tm ? (tm.innerText || '').trim() : '',
      image: media[0] || '',
      n_media: media.length,
      video: hasVideo,
    });
  });
  return JSON.stringify(out.slice(0, 25));
}"""


def clean_text(txt: str, author: str, time_txt: str = "") -> str:
    """카드 innerText 앞머리의 '작성자 표시명 20h' 와 꼬리의 반응 숫자를 걷어낸다.

    시간 문자열은 추측하지 않고 <time> 요소에서 읽은 값(time_txt)만 정확히 지운다.
    앞머리를 정규식으로 짐작해 자르면 본문이 "3분 만에 팔렸다" 로 시작할 때
    '3분' 을 시간으로 오해해 먹어버린다(실측).
    """
    t = (txt or "").strip()
    if author and t.startswith(author):
        t = t[len(author):].lstrip()
    tt = (time_txt or "").strip()
    if tt:
        # 핸들 뒤 표시명이 한 번 더 붙는 경우가 있어, 시간 표기까지를 통째로 버린다
        i = t.find(tt)
        if 0 <= i <= 30:
            t = t[i + len(tt):].lstrip(" ·•\n")
    # 꼬리에 남는 반응 숫자만 있는 줄 제거
    t = re.sub(r"(?:\n\s*[\d.,]+\s*[만천KkMm]?\s*)+$", "", t)
    return t.strip()


def to_num(s) -> int:
    """'1.2만' '3,456' '1.2K' → 정수. 못 읽으면 0."""
    t = str(s or "").strip().replace(",", "")
    if not t:
        return 0
    m = re.match(r"^([\d.]+)\s*([만천KkMm]?)$", t)
    if not m:
        d = re.sub(r"[^\d]", "", t)
        return int(d) if d else 0
    v, u = float(m.group(1)), m.group(2)
    mul = {"만": 10000, "천": 1000, "K": 1000, "k": 1000, "M": 1000000, "m": 1000000}.get(u, 1)
    return int(v * mul)


def age_minutes(time_attr: str, time_txt: str) -> int | None:
    """게시 후 경과(분). datetime 속성이 있으면 그걸 쓰고, 없으면 '3시간' 류를 환산."""
    if time_attr:
        try:
            t = datetime.fromisoformat(time_attr.replace("Z", "+00:00"))
            now = datetime.now(t.tzinfo)
            return max(0, int((now - t).total_seconds() // 60))
        except Exception:                                   # noqa: BLE001
            pass
    t = (time_txt or "").strip()
    m = re.match(r"^(\d+)\s*(분|시간|일|주|초|m|h|d|w)", t)
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2)
    return n * {"초": 0, "분": 1, "m": 1, "시간": 60, "h": 60,
                "일": 1440, "d": 1440, "주": 10080, "w": 10080}.get(u, 1)


def scores(like, reply, repost, quote, age_min):
    """반응 점수·속도·시간가중치.

    Like 총량보다 '얼마나 빨리 붙었나'가 중요하다 — 2일 된 200 좋아요보다
    30분 만의 100 좋아요가 소재로서 값어치가 크다.
    """
    eng = like + reply * 4 + repost * 7 + quote * 6
    hours = max((age_min or 0) / 60.0, 0.25)            # 15분 미만은 15분으로 본다
    velocity = eng / hours
    time_weight = 1 / ((hours + 2) ** 0.5)
    return eng, velocity, eng * time_weight + velocity * 0.5


# 정치 판정은 analyze.py 한 곳에만 둔다(규칙이 두 벌이면 반드시 어긋난다).
try:
    from analyze import is_politics
except Exception:                                           # noqa: BLE001
    def is_politics(_t):                                    # 분석기를 못 읽으면 거르지 않는다
        return False


def to_post(it: dict, kw: str) -> dict | None:
    """카드 하나 → 저장 형태. 못 쓰는 카드면 None."""
    href = (it.get("href") or "").strip()
    au = (it.get("author") or "").strip()
    if not href or not au or au == ME:
        return None
    txt = clean_text(it.get("text"), au, it.get("time_txt", ""))
    if is_politics(txt):            # 정치 글은 담지도 않는다 — 저장·AI 토큰 모두 아낀다
        return None
    am = age_minutes(it.get("time_attr", ""), it.get("time_txt", ""))
    like, reply = to_num(it.get("like")), to_num(it.get("reply"))
    repost, quote = to_num(it.get("repost")), to_num(it.get("quote"))
    eng, vel, _ = scores(like, reply, repost, quote, am)
    return {
        "post_key": href.split("?")[0],
        "author": au,
        "text": txt,
        "url": "https://www.threads.com" + href.split("?")[0],
        "like": like, "reply": reply, "repost": repost, "quote": quote,
        "age_min": am, "engagement": eng, "velocity": vel,
        "keyword": kw,
        "image": (it.get("image") or "")[:600],
        "n_media": int(it.get("n_media") or 0),
        "video": 1 if it.get("video") else 0,
    }


async def feed(page, rounds: int = 12) -> list[dict]:
    """홈 'For you' 피드 — 키워드에 묶이지 않은 소재를 줍는다.

    검색만 돌면 우리가 미리 정한 낱말 밖의 글은 영영 안 보인다. 알고리즘이
    밀어주는 글에는 주제와 무관하게 지금 터지는 것이 섞여 있다.
    (다만 로그인 계정 취향이 반영되므로 완전히 중립은 아니다 — 그래서 검색과 병행한다)
    """
    await page.goto("https://www.threads.com/")
    await asyncio.sleep(5)
    seen: dict[str, dict] = {}
    for i in range(rounds):
        try:
            items = json.loads(await page.evaluate(COLLECT_JS) or "[]")
        except Exception as e:                                  # noqa: BLE001
            log(f"  ! 피드 추출 실패: {e}")
            break
        for it in items:
            p = to_post(it, FEED_KW)
            if p:
                seen.setdefault(p["post_key"], p)
        await page.evaluate("() => window.scrollBy(0, 2000)")
        await asyncio.sleep(1.6)
    return list(seen.values())


async def search(page, kw: str, mode: str, limit: int) -> list[dict]:
    url = SEARCH.format(q=urllib.parse.quote(kw), f=mode)
    await page.goto(url)
    await asyncio.sleep(3.5)
    # 검색 결과는 지연 로딩이라 조금 내려야 더 나온다
    for _ in range(3):
        await page.evaluate("() => window.scrollBy(0, 1400)")
        await asyncio.sleep(1.2)
    try:
        raw = await page.evaluate(COLLECT_JS)
        items = json.loads(raw) if raw else []
    except Exception as e:                                  # noqa: BLE001
        log(f"  ! {kw}/{mode} 추출 실패: {e}")
        return []
    out = []
    for it in items:
        p = to_post(it, kw)
        if p:
            out.append(p)
        if len(out) >= limit:
            break
    return out


def save(c, posts: list[dict]) -> int:
    """새 글은 넣고, 이미 본 글은 반응만 갱신한다(추이를 남긴다)."""
    fresh = 0
    for p in posts:
        eng, vel, base = scores(p["like"], p["reply"], p["repost"], p["quote"], p["age_min"])
        tw = base / eng if eng else 1
        row = c.execute("SELECT id, keywords_all FROM posts WHERE post_key=?",
                        (p["post_key"],)).fetchone()
        if row:
            kws = set(filter(None, (row[1] or "").split(",")))
            kws.add(p["keyword"])
            c.execute(
                "UPDATE posts SET like_count=?, reply_count=?, repost_count=?, quote_count=?,"
                " age_min=?, engagement=?, velocity=?, time_weight=?, collected_at=datetime('now','+9 hours'),"
                " keywords_all=?, image_url=COALESCE(NULLIF(?,''), image_url),"
                " n_media=?, has_video=? WHERE post_key=?",
                (p["like"], p["reply"], p["repost"], p["quote"], p["age_min"],
                 eng, vel, tw, ",".join(sorted(kws)), p["image"], p["n_media"],
                 p["video"], p["post_key"]))
        else:
            c.execute(
                "INSERT INTO posts(post_key,author,text,url,like_count,reply_count,"
                " repost_count,quote_count,age_min,keyword,keywords_all,engagement,velocity,"
                " time_weight,image_url,n_media,has_video)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["post_key"], p["author"], p["text"], p["url"], p["like"], p["reply"],
                 p["repost"], p["quote"], p["age_min"], p["keyword"], p["keyword"],
                 eng, vel, tw, p["image"], p["n_media"], p["video"]))
            fresh += 1
        c.execute("INSERT OR IGNORE INTO post_snapshots(post_key,like_count,reply_count,"
                  "repost_count,quote_count) VALUES(?,?,?,?,?)",
                  (p["post_key"], p["like"], p["reply"], p["repost"], p["quote"]))
    c.commit()
    return fresh


def due_keywords(c, limit: int) -> list[tuple]:
    """돌 차례가 된 키워드 — 우선순위가 높고 오래 안 본 것부터."""
    rows = c.execute(
        "SELECT id, keyword FROM keywords WHERE enabled=1"
        "  AND (last_run_at IS NULL"
        "       OR datetime(last_run_at, '+' || every_min || ' minutes') <= datetime('now','+9 hours'))"
        " ORDER BY priority DESC, COALESCE(last_run_at,'') ASC LIMIT ?", (limit,)).fetchall()
    return rows


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=12, help="검색·모드당 최대 글 수")
    ap.add_argument("--max-keywords", type=int, default=8, help="한 번에 볼 키워드 수")
    ap.add_argument("--feed", action="store_true", help="홈 피드도 같이 훑는다(키워드 무관)")
    ap.add_argument("--feed-rounds", type=int, default=12, help="피드 스크롤 횟수")
    a = ap.parse_args()

    from sns_worker import open_browser, is_logged_in       # noqa: E402

    c = db()
    run = c.execute("INSERT INTO runs DEFAULT VALUES").lastrowid
    c.commit()
    kws = due_keywords(c, a.max_keywords)
    if not kws and not a.feed:
        log("돌 차례인 키워드가 없다")
        c.execute("UPDATE runs SET ended_at=datetime('now','+9 hours') WHERE id=?", (run,))
        c.commit()
        return
    if kws:
        log(f"키워드 {len(kws)}개: {', '.join(k for _, k in kws)}")
    if a.feed:
        log("홈 피드도 함께 훑는다")

    found = fresh = 0
    b = await open_browser(PROFILE)
    try:
        # 빈 탭에서 시작하면 로그인 판정이 안 된다 — 첫 검색 URL 로 바로 연다
        first = (SEARCH.format(q=urllib.parse.quote(kws[0][1]), f="recent")
                 if kws else "https://www.threads.com/")
        page = await b.new_page(first)
        await asyncio.sleep(6)
        if not await is_logged_in(page, "threads"):
            raise RuntimeError("Threads 로그인 세션이 없다 — sns_login_gui.sh 로 로그인할 것")
        for kid, kw in kws:
            got = []
            for mode in ("recent", "top"):
                try:
                    r = await search(page, kw, mode, a.limit)
                except Exception as e:                      # noqa: BLE001
                    log(f"  ! {kw}/{mode}: {e}")
                    r = []
                got += r
                log(f"  {kw}/{mode}: {len(r)}건")
                await asyncio.sleep(2)
            # 같은 글이 recent·top 양쪽에 있을 수 있다
            uniq = {p["post_key"]: p for p in got}
            found += len(uniq)
            fresh += save(c, list(uniq.values()))
            c.execute("UPDATE keywords SET last_run_at=datetime('now','+9 hours') WHERE id=?", (kid,))
            c.commit()

        if a.feed:
            fp = await feed(page, a.feed_rounds)
            found += len(fp)
            fresh += save(c, fp)
            log(f"  피드: {len(fp)}건")
    except Exception as e:                                  # noqa: BLE001
        c.execute("UPDATE runs SET ended_at=datetime('now','+9 hours'), error=? WHERE id=?",
                  (str(e)[:300], run))
        c.commit()
        log("실패:", e)
        raise
    finally:
        try:
            await b.stop()
        except Exception:                                   # noqa: BLE001
            pass

    c.execute("UPDATE runs SET ended_at=datetime('now','+9 hours'), keywords=?, found=?, fresh=?"
              " WHERE id=?", (len(kws), found, fresh, run))
    c.commit()
    log(f"완료 — 본 글 {found}건, 새 글 {fresh}건")


if __name__ == "__main__":
    asyncio.run(main())
