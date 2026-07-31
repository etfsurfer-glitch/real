#!/usr/bin/env python3
"""Threads 반응 마케팅 워커 — nfind 박스 전용.

키워드로 '최신' 글을 찾아 좋아요를 누르고, Gemini가 쓴 댓글을 남긴다.
한 번의 반복에 키워드 1개만 다루고, 2~10분(설정값) 랜덤 간격으로 돈다.
사람처럼 보이도록 스크롤·대기·행동 간격을 모두 무작위로 흔든다.

  --loop     상시 실행(관리자 화면의 켜기/끄기를 따른다)
  --once     한 번만 수행(테스트)
  --dry      좋아요·댓글을 실제로 누르지 않고 무엇을 할지만 출력
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
import urllib.parse
from datetime import datetime

sys.path.insert(0, "/opt/koczip-sns")
import requests                                     # noqa: E402
from sns_worker import (cfg, open_browser, is_logged_in, first_el, shot,   # noqa: E402
                        click_marked, truthy, OUT)

SEARCH = ("https://www.threads.com/search?q={q}&serp_type=default&filter=recent")
ME = "koczip_news"                                  # 내 계정(자기 글은 건너뜀)


def log(*a) -> None:
    print(datetime.now().strftime("%m-%d %H:%M:%S"), *a, flush=True)


def api(path: str, method: str = "GET", **kw):
    c = cfg()
    url = f"{c['api']}{path}"
    if method == "GET":
        r = requests.get(url, params={"key": c["key"], **kw}, timeout=40)
    else:
        r = requests.post(url, json={"key": c["key"], **kw}, timeout=60)
    r.raise_for_status()
    return r.json()


async def human_pause(a: float = 0.8, b: float = 2.4) -> None:
    await asyncio.sleep(random.uniform(a, b))


async def human_scroll(page, times: int = 2) -> None:
    """사람처럼 조금씩 내려보며 읽는 흉내."""
    for _ in range(times):
        try:
            await page.evaluate(
                "() => window.scrollBy(0, 300 + Math.floor(Math.random()*500))")
        except Exception:                           # noqa: BLE001
            pass
        await human_pause(1.0, 2.6)


async def collect_posts(page, limit: int = 8) -> list[dict]:
    """검색 결과에서 글 목록 추출(작성자·본문·글 링크)."""
    js = r"""() => {
      const out = [];
      const cards = document.querySelectorAll('div[data-pressable-container=true]');
      cards.forEach((el, i) => {
        const txt = (el.innerText || '').trim();
        if (!txt || txt.length < 25) return;
        const a = el.querySelector('a[href*="/post/"]');
        const href = a ? a.getAttribute('href') : '';
        const au = el.querySelector('a[href^="/@"]');
        const author = au ? (au.getAttribute('href') || '').replace('/@','').split('?')[0] : '';
        out.push({ idx: i, author: author, href: href, text: txt.slice(0, 900) });
      });
      return JSON.stringify(out.slice(0, 20));
    }"""
    try:
        raw = await page.evaluate(js)
        items = json.loads(raw) if raw else []
    except Exception as e:                          # noqa: BLE001
        log("글 목록 추출 실패:", e)
        return []
    out = []
    for it in items:
        au = (it.get("author") or "").strip()
        href = (it.get("href") or "").strip()
        if not au or au == ME or not href:          # 내 글·작성자불명·링크없음 제외
            continue
        key = href
        it["post_key"] = key
        out.append(it)
        if len(out) >= limit:
            break
    return out


async def like_state(page) -> str:
    """본문 글의 좋아요 상태 — 'Like'(안 눌림) / 'Unlike'(눌림) / ''(없음)."""
    try:
        return str(await page.evaluate(r"""() => {
          const card = document.querySelector('div[data-pressable-container=true]');
          if (!card) return '';
          const e = Array.from(card.querySelectorAll('[aria-label]')).find(x =>
            /^(like|좋아요|unlike|좋아요 취소)$/i.test((x.getAttribute('aria-label')||'').trim()));
          return e ? (e.getAttribute('aria-label')||'').trim() : '';
        }""") or "")
    except Exception:                               # noqa: BLE001
        return ""


async def like_on_detail(page) -> bool:
    """본문 글에 좋아요. 누른 뒤 상태가 'Unlike'로 바뀌었는지 확인해야 진짜 눌린 것이다
    (클릭만 하고 성공으로 기록하면 실제로는 안 눌린 채 지나간다 — 실측)."""
    st = await like_state(page)
    if st.lower().startswith("unlike") or "취소" in st:
        return True                                 # 이미 눌러둔 글
    finder = r"""() => {
      document.querySelectorAll('[data-kc-target]').forEach(e => e.removeAttribute('data-kc-target'));
      const card = document.querySelector('div[data-pressable-container=true]');
      if (!card) return false;
      const svg = Array.from(card.querySelectorAll('[aria-label]')).find(e =>
        /^(like|좋아요)$/i.test((e.getAttribute('aria-label')||'').trim()));
      if (!svg) return false;
      const btn = svg.closest('div[role=button],button') || svg;   // 실제 클릭영역(≈43x36)
      btn.setAttribute('data-kc-target', '1');
      return true;
    }"""
    for attempt in (1, 2):
        try:
            if not truthy(await page.evaluate(finder)):
                return False
            els = await page.get_elements_by_css_selector('[data-kc-target="1"]')
            if not els:
                return False
            await els[0].click()
        except Exception as e:                      # noqa: BLE001
            log("좋아요 클릭 오류:", e)
            return False
        await asyncio.sleep(2.5)
        st = await like_state(page)
        if st.lower().startswith("unlike") or "취소" in st:
            return True
        if attempt == 1:
            log("좋아요 반영 안 됨 — 한 번 더 시도")
            await human_pause(1.5, 3.0)
    log("좋아요 실패(상태 미변경)")
    return False


async def follow_state(page) -> str:
    """프로필의 팔로우 버튼 상태 — 'follow'(아직 안 함) / 'following'(이미 함) / ''(없음)."""
    try:
        v = await page.evaluate(r"""() => {
          const b = Array.from(document.querySelectorAll('div[role=button],button')).find(e => {
            const t = (e.innerText||'').trim();
            return /^(follow|팔로우|following|팔로잉|requested|요청됨)$/i.test(t)
                   && e.getBoundingClientRect().width > 60;
          });
          return b ? (b.innerText||'').trim().toLowerCase() : '';
        }""")
    except Exception:                               # noqa: BLE001
        return ""
    v = str(v or "").strip().lower()
    if v in ("follow", "팔로우"):
        return "follow"
    if v in ("following", "팔로잉", "requested", "요청됨"):
        return "following"
    return ""


async def follow_author(page, author: str) -> bool:
    """작성자 프로필로 가서 팔로우.
    ★ 절대 언팔로우하지 않는다 — 버튼은 Follow↔Following 토글이라, 누르기 직전에
      다시 한 번 'Follow' 상태임을 확인하고, 이미 팔로잉이면 손대지 않는다."""
    try:
        await page.goto(f"https://www.threads.com/@{author}")
    except Exception as e:                          # noqa: BLE001
        log("프로필 이동 실패:", e)
        return False
    await asyncio.sleep(random.uniform(4.0, 6.5))

    st = await follow_state(page)
    if st == "following":
        log(f"@{author}: 이미 팔로우 중 — 건드리지 않음")
        return False
    if st != "follow":
        log(f"@{author}: 팔로우 버튼 없음")
        return False

    for attempt in (1, 2):
        # 클릭 '직전'에 다시 확인 — 그 사이 상태가 바뀌었으면 누르지 않는다(언팔 방지)
        if await follow_state(page) != "follow":
            break
        marked = r"""() => {
          document.querySelectorAll('[data-kc-target]').forEach(e => e.removeAttribute('data-kc-target'));
          const b = Array.from(document.querySelectorAll('div[role=button],button')).find(e => {
            const t = (e.innerText||'').trim();
            return /^(follow|팔로우)$/i.test(t) && e.getBoundingClientRect().width > 60;
          });
          if (!b) return false;                     // 'Following' 은 애초에 잡히지 않음
          b.setAttribute('data-kc-target', '1');
          return true;
        }"""
        try:
            if not truthy(await page.evaluate(marked)):
                break
            els = await page.get_elements_by_css_selector('[data-kc-target="1"]')
            if not els:
                break
            await els[0].click()
        except Exception as e:                      # noqa: BLE001
            log("팔로우 클릭 오류:", e)
            return False
        await asyncio.sleep(3.0)
        if await follow_state(page) == "following":
            log(f"@{author}: 팔로우 완료")
            return True
        if attempt == 1:
            await human_pause(1.5, 3.0)
    log(f"@{author}: 팔로우 반영 안 됨")
    return False


async def reply_on_detail(page, text: str) -> bool:
    """글 상세의 'Reply to …' 입력창에 답글을 쓰고 게시.
    (검색 목록에서 답글 버튼을 누르면 창이 안 열리고 상단 '새 글' 작성창이 잡혀
     자칫 새 글이 올라간다 — 반드시 상세 페이지의 답글창을 쓴다.)"""
    box, _ = await first_el(page, [
        'div[contenteditable="true"][aria-placeholder*="Reply"]',
        'div[contenteditable="true"][aria-placeholder*="답글"]',
        'div[contenteditable="true"]',
    ], timeout=12)
    if not box:
        log("답글 입력창 없음")
        return False
    # 안전장치: 이 입력창이 정말 '답글'용인지 확인(새 글 작성창이면 중단)
    is_reply = truthy(await page.evaluate(r"""() => {
      const e = document.querySelector('div[contenteditable=true]');
      if (!e) return false;
      const ph = (e.getAttribute('aria-placeholder') || e.getAttribute('placeholder') || '');
      return /reply|답글/i.test(ph);
    }"""))
    if not is_reply:
        log("답글창이 아님 — 중단(새 글 작성 방지)")
        return False

    await box.click()
    await human_pause(0.5, 1.2)
    await box.fill(text)
    await human_pause(1.2, 2.4)

    # 답글 게시 버튼은 '텍스트 없는 아이콘'(aria-label="Reply")이다 — 글자로는 못 찾는다(실측).
    # 각 게시물 카드에도 같은 라벨의 답글 아이콘이 있으므로, 반드시 '입력창 주변'으로 범위를 좁힌다.
    post_btn = r"""() => {
      document.querySelectorAll('[data-kc-target]').forEach(e => e.removeAttribute('data-kc-target'));
      let box = document.querySelector('div[contenteditable=true]');
      if (!box) return false;
      let scope = box;
      for (let i = 0; i < 5 && scope.parentElement; i++) scope = scope.parentElement;
      const cand = Array.from(scope.querySelectorAll('[aria-label]')).find(e => {
        const l = (e.getAttribute('aria-label') || '').trim();
        if (!/^(reply|답글|post|게시)$/i.test(l)) return false;
        const r = e.getBoundingClientRect();
        return r.width > 6 && r.height > 6;
      });
      if (!cand) return false;
      const btn = cand.closest('div[role=button],button') || cand.parentElement || cand;
      btn.setAttribute('data-kc-target', '1');
      return true;
    }"""
    if not await click_marked(page, post_btn):
        log("답글 게시 버튼 못 찾음")
        return False
    await asyncio.sleep(random.uniform(4.0, 7.0))
    # 입력창이 비워졌으면 게시된 것으로 본다
    left = await page.evaluate(r"""() => {
      const e = document.querySelector('div[contenteditable=true]');
      return e ? (e.innerText||'').trim().length : 0;
    }""")
    return int(str(left) or 0) < 3


async def comment_visible(page, text: str) -> bool:
    """게시한 댓글이 실제로 글에 붙어 보이는지 — '입력창이 비었다'만으로는 믿지 않는다."""
    head = (text or "").strip()[:14]
    if len(head) < 6:
        return False
    try:
        raw = await page.evaluate(r"""() => JSON.stringify(
          Array.from(document.querySelectorAll('div[data-pressable-container=true]'))
               .map(e => (e.innerText || '').replace(/\n/g, ' ')))""")
        cards = json.loads(str(raw) or "[]")
    except Exception:                               # noqa: BLE001
        return False
    return any(head in c and ME in c for c in cards)   # 내 계정 이름과 함께 보여야 진짜


async def run_cycle(dry: bool = False) -> int:
    conf = api("/sns/engage/config")
    if not conf.get("enabled"):
        return -1                                   # 꺼짐
    if conf.get("remaining", 0) <= 0:
        log("오늘 한도 소진")
        return 0
    kw = conf.get("keyword") or "부동산"
    log(f"검색: {kw} (오늘 {conf['today_count']}/{conf['daily_limit']})")

    b = await open_browser("threads")
    done = 0
    try:
        page = await b.new_page(SEARCH.format(q=urllib.parse.quote(kw)))
        await asyncio.sleep(random.uniform(5, 8))
        if not await is_logged_in(page, "threads"):
            log("로그인 안 됨 — 서버 프로필 재로그인 필요")
            return 0
        await human_scroll(page, random.randint(1, 3))

        posts = await collect_posts(page)
        if not posts:
            log("검색 결과 없음")
            return 0
        seen = set(api("/sns/engage/seen", "POST",
                       post_keys=[p["post_key"] for p in posts]).get("seen", []))
        fresh = [p for p in posts if p["post_key"] not in seen]
        log(f"수집 {len(posts)}건 · 새 글 {len(fresh)}건")
        if not fresh:
            return 0

        # 사람처럼: 한 번에 1건만, 목록에서 무작위로 고른다
        target = random.choice(fresh[:5])
        gen = api("/sns/engage/comment", "POST",
                  text=target["text"], author=target["author"])
        if gen.get("skip"):
            log(f"건너뜀({target['author']}): {gen.get('reason')}")
            api("/sns/engage/report", "POST", post_key=target["post_key"], keyword=kw,
                author=target["author"], post_text=target["text"][:400],
                liked=False, comment="", status="skip", detail=gen.get("reason", ""))
            return 0
        comment = gen["comment"]
        log(f"대상 @{target['author']} · 댓글안: {comment}")
        if dry:
            log("(dry-run — 실제 동작 안 함)")
            return 0

        # 사람처럼 글을 열어 읽고 → 좋아요 → 답글
        await human_pause(1.2, 3.0)
        await page.goto("https://www.threads.com" + target["href"])
        await asyncio.sleep(random.uniform(4.0, 6.5))
        await human_scroll(page, random.randint(1, 2))
        liked = await like_on_detail(page)
        await human_pause(2.0, 4.5)
        posted = False
        if conf.get("do_comment"):
            posted = await reply_on_detail(page, comment)

        verified = False
        if posted:
            await asyncio.sleep(random.uniform(3.0, 5.0))
            verified = await comment_visible(page, comment)
            if not verified:                        # 렌더가 늦을 수 있어 새로고침 후 한 번 더
                try:
                    await page.goto("https://www.threads.com" + target["post_key"])
                    await asyncio.sleep(5.0)
                    verified = await comment_visible(page, comment)
                except Exception:                   # noqa: BLE001
                    pass
            log(f"댓글 화면 확인: {'O' if verified else 'X'}")

        followed = False
        if conf.get("do_follow") and conf.get("follow_remaining", 0) > 0:
            await human_pause(2.0, 4.0)
            followed = await follow_author(page, target["author"])

        api("/sns/engage/report", "POST", post_key=target["post_key"], keyword=kw,
            author=target["author"], post_text=target["text"][:400],
            liked=liked, comment=comment if posted else "", followed=followed,
            verified=verified,
            status="ok" if (liked or posted or followed) else "fail",
            detail=f"like={liked} comment={posted}/{verified} follow={followed}")
        log(f"결과 — 좋아요 {liked} / 댓글 {posted}(확인 {verified}) / 팔로우 {followed}")
        if not (liked or posted):
            await shot(page, str(OUT / f"engage_fail_{int(time.time())}.png"))
        done = 1 if (liked or posted or followed) else 0
    except Exception as e:                          # noqa: BLE001
        log("사이클 오류:", e)
    finally:
        try:
            await b.stop()
        except Exception:                           # noqa: BLE001
            pass
    return done


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.once or a.dry:
        await run_cycle(dry=a.dry)
        return
    log("반응 마케팅 워커 시작")
    while True:
        try:
            r = await run_cycle()
            conf = api("/sns/engage/config")
            if r == -1:                             # 꺼져 있으면 자주 깨지 않는다
                await asyncio.sleep(60)
                continue
            gap = random.randint(int(conf.get("min_gap_sec", 120)),
                                 int(conf.get("max_gap_sec", 600)))
            log(f"다음 반복까지 {gap}초")
            await asyncio.sleep(gap)
        except Exception as e:                      # noqa: BLE001
            log("루프 오류:", e)
            await asyncio.sleep(120)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
