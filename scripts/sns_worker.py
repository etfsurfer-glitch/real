#!/usr/bin/env python3
"""콕집 SNS 자동포스팅 워커 — nfind 박스(/opt/koczip-sns) 전용.

api.koczip.com 의 발행 큐를 폴링해 Threads·Instagram·X 에 뉴스레터 이미지 + 문구를 올린다.
browser-use 의 actor API(CDP 직접, LLM 없음)로 결정적 조작 — 셀렉터가 바뀌면 여기만 고치면 된다.

  --loop              데몬(기본 60초 폴링)
  --once              큐 1건만 처리
  --login PLATFORM    최초 로그인/세션 저장(헤드풀 불가 서버라 자동 입력 + 실패 시 스샷)
  --shot URL OUT      렌더 페이지 캡처만 테스트
  --check             API 연결·세션 상태 점검

세션은 플랫폼별 user_data_dir(/opt/koczip-sns/profiles/<platform>)에 유지된다.
실패하면 /opt/koczip-sns/out/fail_<platform>_<ts>.png 스샷을 남긴다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

BASE = Path("/opt/koczip-sns")
PROFILES = BASE / "profiles"
OUT = BASE / "out"
CONF = BASE / "config.json"
CARD_W, CARD_H = 1240, 1754          # A4 비율 카드 원본 크기
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/149.0.0.0 Safari/537.36")


def cfg() -> dict:
    try:
        return json.loads(CONF.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def truthy(v) -> bool:
    """actor page.evaluate 는 결과를 '문자열'로 준다("true"/"false"/"0"...)."""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1")


def log(*a) -> None:
    print(datetime.now().strftime("%m-%d %H:%M:%S"), *a, flush=True)


# ── 브라우저 ─────────────────────────────────────────────────────────────
async def open_browser(platform: str | None, headless: bool = True):
    """플랫폼별 프로필로 브라우저 시작. platform=None 이면 임시 프로필(캡처용)."""
    from browser_use import Browser
    from browser_use.browser.profile import BrowserProfile

    udd = str(PROFILES / platform) if platform else str(BASE / "profiles" / "_shot")
    Path(udd).mkdir(parents=True, exist_ok=True)
    prof = BrowserProfile(
        user_data_dir=udd,
        headless=headless,
        # 헤드리스 기본 UA("HeadlessChrome")는 Cloudflare가 봇으로 403 처리 → 정상 크롬 UA 고정.
        user_agent=UA,
        enable_default_extensions=False,   # 광고차단 등 기본 확장 불필요 — 탭 간섭 방지
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
              "--lang=ko-KR", "--window-size=1280,1800", f"--user-agent={UA}"],
    )
    b = Browser(browser_profile=prof)
    await b.start()
    return b


async def cdp_upload(page, css: str, path: str) -> None:
    """file input 에 파일 주입 — OS 다이얼로그 없이 CDP 로 직접(숨겨진 input 도 가능).
    ★ 반드시 '그 페이지'의 세션을 써야 한다 — 브라우저 레벨 세션은 다른 타겟을 가리켜
      DOM 조회가 빈 문서에서 돌아 'file input 없음' 이 된다(실측)."""
    sid = await page._ensure_session()              # noqa: SLF001
    cdp = page._client                              # noqa: SLF001
    doc = await cdp.send.DOM.getDocument(session_id=sid)
    root = doc["root"]["nodeId"]
    q = await cdp.send.DOM.querySelector(params={"nodeId": root, "selector": css}, session_id=sid)
    nid = q.get("nodeId")
    if not nid:
        raise RuntimeError(f"file input 없음: {css}")
    desc = await cdp.send.DOM.describeNode(params={"nodeId": nid}, session_id=sid)
    bnid = desc["node"]["backendNodeId"]
    await cdp.send.DOM.setFileInputFiles(
        params={"files": [path], "backendNodeId": bnid}, session_id=sid)


async def first_el(page, selectors: list[str], timeout: float = 12.0):
    """여러 후보 셀렉터 중 먼저 나타나는 요소(플랫폼 UI 변경 대비)."""
    end = time.time() + timeout
    while time.time() < end:
        for css in selectors:
            try:
                els = await page.get_elements_by_css_selector(css)
            except Exception:                       # noqa: BLE001
                els = []
            if els:
                return els[0], css
        await asyncio.sleep(0.4)
    return None, None


async def click_text(page, texts: list[str], tags=("div", "span", "button", "a")) -> bool:
    """보이는 텍스트로 버튼 클릭.
    ① 정확히 일치하는 클릭요소(button/[role=button]/a) ② 정확 일치 아무 태그
    ③ 접두 일치(클릭요소만) 순으로 시도한다. 접두 일치를 먼저 쓰면
    'Log in' 이 'Log in with your Instagram account' 라벨을 물어버린다(실제로 겪음).
    클릭은 요소 자신이 아니라 가장 가까운 클릭 가능한 조상에 건다."""
    js = """(want) => {
      const clickable = el => el.closest('button,[role=button],a,input[type=submit]') || el;
      const vis = el => { const r = el.getBoundingClientRect();
                          return r.width > 4 && r.height > 4; };
      const all = Array.from(document.querySelectorAll('%s'));
      const txt = el => (el.innerText || el.value || '').trim();
      const isBtn = el => el.matches('button,[role=button],a,input[type=submit]');
      for (const w of want) {
        for (const el of all) if (vis(el) && isBtn(el) && txt(el) === w) { clickable(el).click(); return true; }
      }
      for (const w of want) {
        for (const el of all) if (vis(el) && txt(el) === w) { clickable(el).click(); return true; }
      }
      for (const w of want) {
        for (const el of all) if (vis(el) && isBtn(el) && txt(el).startsWith(w)) { clickable(el).click(); return true; }
      }
      return false;
    }""" % ",".join(tags + ("input[type=submit]",))
    try:
        return truthy(await page.evaluate(js, texts))
    except Exception:                               # noqa: BLE001
        return False


async def page_error_text(page) -> str:
    """로그인 실패 사유가 화면에 떠 있으면 그 문구를 뽑아낸다."""
    js = """() => {
      const pats = /incorrect|잘못|일치하지|다시 시도|사용자를 찾을 수|couldn't find|문제가 발생|suspicious|비정상|확인이 필요|verify|challenge|잠긴|disabled/i;
      const out = [];
      document.querySelectorAll('div,span,p').forEach(el => {
        const t = (el.innerText||'').trim();
        if (t && t.length < 160 && pats.test(t) && el.children.length === 0) out.push(t);
      });
      return Array.from(new Set(out)).slice(0,3).join(' | ');
    }"""
    try:
        return str(await page.evaluate(js) or "")
    except Exception:                               # noqa: BLE001
        return ""


async def click_marked(page, finder_js: str) -> bool:
    """JS로 '진짜 눌러야 할 요소'를 찾아 표시한 뒤, 그 요소를 실제 마우스 이벤트로 클릭한다.
    JS의 el.click() 은 React 핸들러를 깨우지 못하는 경우가 있어(실측: Threads 게시 실패)
    반드시 Element.click()(CDP 마우스 이벤트)으로 눌러야 한다."""
    try:
        ok = truthy(await page.evaluate(finder_js))
        if not ok:
            return False
        els = await page.get_elements_by_css_selector('[data-kc-target="1"]')
        if not els:
            return False
        await els[0].click()
        return True
    except Exception as e:                          # noqa: BLE001
        log("click_marked 실패", e)
        return False


async def shot(page, path: str) -> None:
    try:
        data = await page.screenshot()
        if isinstance(data, str):
            import base64
            data = base64.b64decode(data)
        Path(path).write_bytes(data)
    except Exception as e:                          # noqa: BLE001
        log("스샷 실패", e)


# ── 뉴스레터 이미지 캡처 ────────────────────────────────────────────────
async def capture(render_url: str, out_path: str) -> str:
    """렌더 페이지를 카드 실제 높이만큼 정확히 캡처(CDP). 데이터 로드(body[data-nl=ready]) 대기."""
    import base64
    b = await open_browser(None)
    try:
        page = await b.new_page(render_url)
        end = time.time() + 60
        ready = False
        while time.time() < end:
            try:
                if truthy(await page.evaluate("() => document.body.dataset.nl === 'ready'")):
                    ready = True
                    break
            except Exception:                       # noqa: BLE001
                pass
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.8)                    # 폰트·이미지 안정화
        # 카드 실제 크기를 그대로 쓴다 — 뉴스레터(A4 비율)와 홍보 카드뉴스(1080×1350)의
        # 규격이 달라, 가로도 고정하지 않고 요소에서 읽는다(여백 없이 딱 맞게).
        w, h = CARD_W, CARD_H
        try:
            m = await page.evaluate(
                "() => { const e = document.getElementById('nl-card'); if (!e) return '';"
                " const r = e.getBoundingClientRect();"
                " return Math.ceil(r.width) + 'x' + Math.ceil(r.height); }")
            mw, _, mh = str(m or "").partition("x")
            if mw.isdigit() and mh.isdigit() and int(mw) > 300 and int(mh) > 500:
                w, h = int(mw), int(mh)
        except Exception:                           # noqa: BLE001
            pass
        sid = await page._ensure_session()       # noqa: SLF001 — 반드시 '그 페이지'의 세션
        cdp = page._client                        # noqa: SLF001
        await cdp.send.Emulation.setDeviceMetricsOverride(
            params={"width": w, "height": h, "deviceScaleFactor": 2, "mobile": False},
            session_id=sid)
        await asyncio.sleep(0.8)
        res = await cdp.send.Page.captureScreenshot(
            params={"format": "png", "captureBeyondViewport": True,
                    "clip": {"x": 0, "y": 0, "width": w, "height": h, "scale": 1}},
            session_id=sid)
        Path(out_path).write_bytes(base64.b64decode(res["data"]))
        log(f"캡처 {'OK' if ready else '(데이터 미로드)'} {w}x{h} → {out_path}")
        if not ready:
            raise RuntimeError("렌더 데이터 로드 실패(ready 미도달)")
        return out_path
    finally:
        try:
            await b.stop()
        except Exception:                           # noqa: BLE001
            pass


def pad_for_instagram(src: str, dst: str) -> str:
    """인스타는 4:5(0.8)보다 세로로 길면 잘린다 → 흰 배경으로 4:5에 맞춰 넣는다."""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    w, h = im.size
    target_w = max(w, int(h * 0.8) + 1)
    canvas = Image.new("RGB", (target_w, h), "white")
    canvas.paste(im, ((target_w - w) // 2, 0))
    canvas.save(dst, quality=95)
    return dst


# ── 플랫폼별 발행 ───────────────────────────────────────────────────────
async def post_threads(b, page, img: str, caption: str) -> str:
    """반드시 'New thread' 모달로 작성한다 — 홈 상단 인라인 작성창에는 파일 입력이 없어
    이미지 첨부가 불가능하다(실측: 인라인 0개 / 모달 1개)."""
    await page.goto("https://www.threads.com/")
    await asyncio.sleep(4)
    opened = await click_text(page, ["New thread", "새로운 스레드", "스레드 시작"])
    if not opened:
        await page.goto("https://www.threads.com/?compose=true")
        await asyncio.sleep(3)
    el, _ = await first_el(page, ['div[contenteditable="true"]'], timeout=12)
    if not el:
        raise RuntimeError("작성 모달을 열지 못함")
    await el.click()
    await el.fill(caption)
    await asyncio.sleep(0.8)
    try:
        await cdp_upload(page, 'input[type="file"]', img)
        is_video = img.lower().endswith((".mp4", ".mov", ".webm"))
        # 영상은 브라우저가 올리고 처리하는 데 오래 걸린다 — 미리보기가 붙을 때까지 확인하며 대기
        for _ in range(24 if is_video else 6):
            await asyncio.sleep(2)
            ready = truthy(await page.evaluate(
                "() => { const d = document.querySelector('div[role=dialog]') || document;"
                " return !!(d.querySelector('video') || d.querySelector('img[src^=\"blob:\"]')"
                " || d.querySelector('div[style*=\"blob:\"]')); }"))
            if ready:
                break
        await asyncio.sleep(3 if is_video else 1)
    except Exception as e:                          # noqa: BLE001
        log("threads 첨부 실패(텍스트만 진행):", e)
    # 배경 인라인 작성창에도 Post 버튼이 있어, 반드시 '모달(dialog) 안'의 버튼을 눌러야 한다.
    finder = r"""() => {
      document.querySelectorAll('[data-kc-target]').forEach(e => e.removeAttribute('data-kc-target'));
      const dlg = document.querySelector('div[role=dialog]');
      const scope = dlg || document;
      const btns = Array.from(scope.querySelectorAll('div[role=button],button'))
        .filter(e => /^(Post|게시)$/i.test((e.innerText || '').trim())
                     && e.getBoundingClientRect().width > 10);
      const b = btns[btns.length - 1];
      if (b) b.setAttribute('data-kc-target', '1');
      return !!b;
    }"""
    if not await click_marked(page, finder):
        raise RuntimeError("게시 버튼을 찾지 못함")
    await asyncio.sleep(8)
    # 모달이 닫혔는지로 실제 게시 여부를 판정(닫히지 않으면 실패로 본다)
    still = truthy(await page.evaluate(
        "() => !!document.querySelector('div[role=dialog] div[contenteditable=true]')"))
    if still:
        raise RuntimeError("게시 버튼을 눌렀으나 작성창이 닫히지 않음(게시 실패)")
    return "threads posted"


async def post_instagram(b, page, img: str, caption: str) -> str:
    ig_img = pad_for_instagram(img, img.replace(".png", "_ig.jpg"))
    await page.goto("https://www.instagram.com/")
    await asyncio.sleep(3)
    if not await click_text(page, ["만들기", "Create", "새 게시물"]):
        el, _ = await first_el(page, ['svg[aria-label="새 게시물"]', 'svg[aria-label="New post"]',
                                      'a[href="#"][role="link"]'], timeout=6)
        if el:
            await el.click()
    await asyncio.sleep(2.5)
    await cdp_upload(page, 'input[type="file"][accept*="image"], input[type="file"]', ig_img)
    await asyncio.sleep(4)
    for _ in range(2):                              # 자르기 → 필터 → 문구
        if await click_text(page, ["다음", "Next"]):
            await asyncio.sleep(2.5)
    el, _ = await first_el(page, [
        'div[aria-label*="문구"][contenteditable="true"]',
        'textarea[aria-label*="문구"]',
        'div[contenteditable="true"]',
    ], timeout=15)
    if not el:
        raise RuntimeError("문구 입력창 없음")
    await el.click()
    await el.fill(caption)
    await asyncio.sleep(1)
    if not await click_text(page, ["공유하기", "Share"]):
        raise RuntimeError("공유 버튼 클릭 실패")
    await asyncio.sleep(8)
    return "instagram posted"


async def post_x(b, page, img: str, caption: str) -> str:
    await page.goto("https://x.com/compose/post")
    await asyncio.sleep(3.5)
    el, _ = await first_el(page, [
        'div[data-testid="tweetTextarea_0"]',
        'div[contenteditable="true"][role="textbox"]',
    ])
    if not el:
        raise RuntimeError("작성창 없음")
    await el.click()
    await el.fill(caption)
    await asyncio.sleep(0.6)
    try:
        await cdp_upload(page, 'input[data-testid="fileInput"], input[type="file"]', img)
        await asyncio.sleep(5)
    except Exception as e:                          # noqa: BLE001
        log("x 이미지 첨부 실패(텍스트만 진행):", e)
    el2, _ = await first_el(page, [
        'button[data-testid="tweetButton"]',
        'div[data-testid="tweetButton"]',
        'button[data-testid="tweetButtonInline"]',
    ], timeout=8)
    if el2:
        await el2.click()
    elif not await click_text(page, ["게시하기", "게시", "Post"]):
        raise RuntimeError("게시 버튼 클릭 실패")
    await asyncio.sleep(5)
    return "x posted"


POSTERS = {"threads": post_threads, "instagram": post_instagram, "x": post_x}


# ── 로그인 상태 판정 / 로그인 ────────────────────────────────────────────
HOME_URL = {
    "threads": "https://www.threads.com/",
    "instagram": "https://www.instagram.com/",
    "x": "https://x.com/home",
}
LOGGED_OUT_MARK = {          # URL 에 이게 있으면 로그아웃 상태
    "threads": ("/login",),
    "instagram": ("/accounts/login",),
    "x": ("/i/flow/login", "/login", "/?logout"),
}
LOGGED_IN_SEL = {            # 있으면 로그인 상태로 본다
    "threads": ['div[contenteditable="true"]', 'a[href="/settings"]', 'svg[aria-label="홈"]'],
    "instagram": ['svg[aria-label="홈"]', 'svg[aria-label="Home"]', 'a[href="/direct/inbox/"]'],
    "x": ['div[data-testid="tweetTextarea_0"]', 'a[data-testid="AppTabBar_Home_Link"]',
          'div[data-testid="SideNav_AccountSwitcher_Button"]'],
}


LOGIN_CHECK_JS = {
    # 한/영 UI 모두 대응. 작성창은 클릭 전엔 contenteditable 이 아니라 nav·CTA로 판정한다.
    "threads": """() => {
      const t = document.body.innerText || '';
      const cta = /Continue with Instagram|Log in or sign up|Instagram으로 계속|로그인 또는 가입/i.test(t);
      const nav = !!document.querySelector('a[href="/activity"],a[href="/search"],a[href^="/@"]')
                  || /New thread|새로운 스레드|For you|추천 for you/i.test(t);
      return nav && !cta;
    }""",
    "instagram": """() => {
      const form = !!document.querySelector('input[name="username"],input[type="password"]');
      const nav = !!document.querySelector('a[href="/direct/inbox/"],a[href="/explore/"],'
                  + 'svg[aria-label="Home"],svg[aria-label="홈"],a[href^="/accounts/edit"]');
      return nav && !form;
    }""",
    "x": """() => !!document.querySelector('a[data-testid="AppTabBar_Home_Link"],'
      + 'div[data-testid="SideNav_AccountSwitcher_Button"],div[data-testid="tweetTextarea_0"]')""",
}


async def is_logged_in(page, platform: str) -> bool:
    try:
        url = str(await page.get_url() or "")
    except Exception:                               # noqa: BLE001
        url = ""
    if any(m in url for m in LOGGED_OUT_MARK.get(platform, ())):
        return False
    js = LOGIN_CHECK_JS.get(platform)
    if js:
        for _ in range(3):                          # 렌더 지연 대비 재시도
            try:
                if truthy(await page.evaluate(js)):
                    return True
            except Exception:                       # noqa: BLE001
                pass
            await asyncio.sleep(2)
    el, _ = await first_el(page, LOGGED_IN_SEL.get(platform, []), timeout=5)
    return el is not None


async def handle_2fa(page, acc: dict) -> str:
    """2단계 인증 화면이면 TOTP 코드를 계산해 입력."""
    totp = (acc.get("totp") or "").replace(" ", "")
    el, _ = await first_el(page, ['input[name="verificationCode"]',
                                  'input[autocomplete="one-time-code"]',
                                  'input[name="text"]'], timeout=6)
    if not el:
        return ""
    if not totp:
        return " (2단계 인증 화면인데 TOTP 시크릿이 없음)"
    try:
        import pyotp
        await el.click()
        await el.fill(pyotp.TOTP(totp).now())
        await click_text(page, ["확인", "다음", "계속", "Next", "Verify", "Confirm"],
                         tags=("button", "div", "span"))
        await asyncio.sleep(7)
        return " (2FA 입력함)"
    except Exception as e:                          # noqa: BLE001
        return f" (2FA 실패: {e})"


async def fill_login_form(page, user: str, pw: str) -> bool:
    """아이디/비밀번호 폼 채우고 제출. 폼이 없으면 False."""
    el, _ = await first_el(page, ['input[name="username"]', 'input[autocomplete="username"]',
                                  'input[name="email"]', 'input[type="text"]'], timeout=8)
    if not el:
        return False
    await el.click(); await el.fill(user); await asyncio.sleep(0.6)
    el2, _ = await first_el(page, ['input[name="password"]', 'input[type="password"]'], timeout=6)
    if el2:
        await el2.click(); await el2.fill(pw); await asyncio.sleep(0.6)
    # 제출: submit 입력이 있으면 그걸(가장 확실), 없으면 정확 일치 버튼
    clicked = False
    try:   # Threads의 input[type=submit]은 0x0 숨김 — 보이는 경우에만 클릭(실측 확인)
        vis = truthy(await page.evaluate(
            "() => { const e = document.querySelector('input[type=submit]');"
            " if (!e) return false; const r = e.getBoundingClientRect();"
            " return r.width > 4 && r.height > 4; }"))
        if vis:
            els = await page.get_elements_by_css_selector('input[type="submit"]')
            if els:
                await els[0].click(); clicked = True
    except Exception:                               # noqa: BLE001
        pass
    if not clicked:
        await click_text(page, ["로그인", "Log in", "Login", "계속", "Continue"],
                         tags=("button", "div", "span"))
    await asyncio.sleep(9)
    return True


async def login_on_page(b, page, platform: str, acc: dict) -> str:
    """저장된 계정으로 로그인. 플랫폼마다 진입 화면이 다르다."""
    user = acc.get("username") or acc.get("email") or ""
    pw = acc.get("password") or ""
    if not (user and pw):
        return "계정 미설정"

    if platform == "threads":
        # Threads 계정 = 인스타 계정. 로그인 화면이 'Continue with Instagram' 위주라
        # ①'사용자 이름으로 로그인' 경로를 먼저 시도하고 ②없으면 인스타 경로로 넘어간다.
        await page.goto("https://www.threads.com/login")
        await asyncio.sleep(4)
        await click_text(page, ["사용자 이름으로 로그인", "Log in with username instead",
                                "Log in with username"])
        await asyncio.sleep(2)
        if not await fill_login_form(page, user, pw):
            await click_text(page, ["Instagram으로 계속", "Continue with Instagram",
                                    "Instagram으로 로그인"])
            await asyncio.sleep(6)
            if not await fill_login_form(page, user, pw):
                return "Threads 로그인 입력창을 찾지 못함"
        return "로그인 시도함" + await handle_2fa(page, acc)

    if platform == "x":
        await page.goto(LOGIN_URL["x"])
        await asyncio.sleep(4)
        el, _ = await first_el(page, ['input[name="text"]', 'input[autocomplete="username"]'])
        if el:
            await el.click(); await el.fill(user); await asyncio.sleep(0.6)
        await click_text(page, ["다음", "Next"], tags=("button", "div", "span"))
        await asyncio.sleep(3)
        el2, _ = await first_el(page, ['input[name="password"]', 'input[type="password"]'], timeout=8)
        if el2:
            await el2.click(); await el2.fill(pw); await asyncio.sleep(0.6)
        await click_text(page, ["로그인", "Log in"], tags=("button", "div", "span"))
        await asyncio.sleep(8)
        return "로그인 시도함" + await handle_2fa(page, acc)

    await page.goto(LOGIN_URL["instagram"])
    await asyncio.sleep(4)
    if not await fill_login_form(page, user, pw):
        return "Instagram 로그인 입력창을 찾지 못함"
    return "로그인 시도함" + await handle_2fa(page, acc)


COOKIE_DOMAINS = {
    "threads": [".threads.com", ".threads.net", ".instagram.com"],
    "instagram": [".instagram.com"],
    "x": [".x.com", ".twitter.com"],
}


def parse_cookies(raw: str, platform: str) -> list[dict]:
    """브라우저에서 복사한 쿠키를 CDP 형식으로.
    ①확장프로그램 JSON 내보내기(배열) ②'k=v; k=v' 헤더 문자열 둘 다 지원."""
    raw = (raw or "").strip()
    if not raw:
        return []
    out: list[dict] = []
    if raw.startswith("["):
        try:
            for c in json.loads(raw):
                n, v = c.get("name"), c.get("value")
                if not n or v is None:
                    continue
                item = {"name": n, "value": str(v),
                        "domain": c.get("domain") or COOKIE_DOMAINS[platform][0],
                        "path": c.get("path") or "/",
                        "secure": bool(c.get("secure", True)),
                        "httpOnly": bool(c.get("httpOnly", False))}
                exp = c.get("expirationDate") or c.get("expires")
                if isinstance(exp, (int, float)) and exp > 0:
                    item["expires"] = float(exp)
                out.append(item)
        except (ValueError, AttributeError, TypeError):
            return []
        return out
    # "k=v; k=v" 형식 → 플랫폼 도메인 전부에 심는다(해당 사이트만 실제로 사용)
    pairs = []
    for part in raw.replace("\n", ";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        n, v = part.split("=", 1)
        n, v = n.strip(), v.strip()
        if n and v:
            pairs.append((n, v))
    for dom in COOKIE_DOMAINS.get(platform, []):
        for n, v in pairs:
            out.append({"name": n, "value": v, "domain": dom, "path": "/",
                        "secure": True, "httpOnly": False})
    return out


async def apply_cookies(page, platform: str, raw: str) -> int:
    """저장된 쿠키를 브라우저에 주입 — 로그인 절차(본인확인 포함)를 건너뛴다."""
    items = parse_cookies(raw, platform)
    if not items:
        return 0
    sid = await page._ensure_session()             # noqa: SLF001
    cdp = page._client                              # noqa: SLF001
    try:
        await cdp.send.Storage.setCookies(params={"cookies": items}, session_id=sid)
    except Exception:                               # noqa: BLE001
        await cdp.send.Network.setCookies(params={"cookies": items}, session_id=sid)
    return len(items)


async def check_session(platform: str, acc: dict) -> tuple[bool, str]:
    """세션 점검 — 로그아웃 상태면 저장된 계정으로 로그인까지 시도하고 결과를 돌려준다."""
    b = await open_browser(platform)
    try:
        page = await b.new_page(HOME_URL[platform])
        await asyncio.sleep(5)
        if await is_logged_in(page, platform):
            return True, "이미 로그인된 세션 — 정상"
        # ① 쿠키가 저장돼 있으면 먼저 주입(본인확인 화면을 아예 건너뜀)
        n_ck = 0
        if acc.get("cookies"):
            try:
                n_ck = await apply_cookies(page, platform, acc["cookies"])
                await page.goto(HOME_URL[platform])
                await asyncio.sleep(6)
                if await is_logged_in(page, platform):
                    return True, f"쿠키로 로그인됨 — 정상 (쿠키 {n_ck}개)"
            except Exception as e:                  # noqa: BLE001
                log("쿠키 주입 실패", e)
        # ② 쿠키가 없거나 안 먹으면 아이디·비밀번호 로그인
        note = await login_on_page(b, page, platform, acc)
        await page.goto(HOME_URL[platform])
        await asyncio.sleep(6)
        if await is_logged_in(page, platform):
            return True, f"로그인 성공 — 세션 저장됨 ({note})"
        url = str(await page.get_url() or "")
        err = await page_error_text(page)
        p = str(OUT / f"check_{platform}_{int(time.time())}.png")
        await shot(page, p)
        hint = f" | 화면메시지: {err}" if err else ""
        low = url.lower()
        if not acc.get("cookies"):
            hint += " | 해결: 관리자 화면에서 '쿠키 붙여넣기'를 사용하세요"
        if "challenge" in low or "checkpoint" in low or "auth_platform" in low:
            hint += (" — 아이디·비밀번호는 통과했으나 메타가 본인확인을 요구합니다"
                     "(데이터센터 IP 로그인 감지). 쿠키 가져오기 방식이 필요합니다")
        elif "two" in low or "2fa" in low or "verify" in low:
            hint += " — 2단계 인증 필요: TOTP 시크릿을 저장하세요"
        return False, f"로그인 실패 (url={url[:80]}){hint} / 스샷={p}"
    finally:
        try:
            await b.stop()
        except Exception:                           # noqa: BLE001
            pass


# ── 로그인(최초 1회 세션 만들기) ─────────────────────────────────────────
LOGIN_URL = {
    "threads": "https://www.threads.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "x": "https://x.com/i/flow/login",
}


async def do_login(platform: str, acc: dict) -> str:
    ok, msg = await check_session(platform, acc)
    return ("OK " if ok else "실패 ") + msg


# ── 큐 처리 ─────────────────────────────────────────────────────────────
async def handle_job(job: dict) -> tuple[bool, str]:
    plat = job["platform"]
    if job.get("kind") == "check":                  # 관리자 '연결 확인'
        try:
            return await check_session(plat, job.get("account") or {})
        except Exception as e:                      # noqa: BLE001
            return False, f"점검 오류: {type(e).__name__}: {e}"
    media = str(job.get("media_path") or "").strip()
    if media:                                       # 광고 영상처럼 미리 놓아둔 파일
        if not os.path.exists(media):
            return False, f"미디어 파일이 없음: {media}"
        img = media
    else:
        img = str(OUT / f"nl_{job['id']}.png")
        try:
            await capture(job["render_url"], img)
            if not os.path.exists(img) or os.path.getsize(img) < 10000:
                return False, "이미지 캡처 실패"
        except Exception as e:                      # noqa: BLE001
            return False, f"캡처 오류: {e}"

    b = await open_browser(plat)
    try:
        page = await b.new_page(HOME_URL[plat])
        await asyncio.sleep(4)
        if not await is_logged_in(page, plat):      # 세션 끊겼으면 쿠키→로그인 순으로 복구
            _acc = job.get("account") or {}
            if _acc.get("cookies"):
                try:
                    await apply_cookies(page, plat, _acc["cookies"])
                    await page.goto(HOME_URL[plat])
                    await asyncio.sleep(5)
                except Exception:                   # noqa: BLE001
                    pass
            if not await is_logged_in(page, plat):
                await login_on_page(b, page, plat, _acc)
            await page.goto(HOME_URL[plat])
            await asyncio.sleep(5)
            if not await is_logged_in(page, plat):
                return False, "로그인 안 됨 — 관리자 화면에서 '연결 확인'을 먼저 실행하세요"
        res = await POSTERS[plat](b, page, img, job["caption"])
        return True, res
    except Exception as e:                          # noqa: BLE001
        try:
            page = await b.must_get_current_page()
            await shot(page, str(OUT / f"fail_{plat}_{int(time.time())}.png"))
        except Exception:                           # noqa: BLE001
            pass
        return False, f"{type(e).__name__}: {e}"
    finally:
        try:
            await b.stop()
        except Exception:                           # noqa: BLE001
            pass


def api_next(c: dict) -> dict | None:
    r = requests.get(f"{c['api']}/sns/worker/next", params={"key": c["key"]}, timeout=30)
    r.raise_for_status()
    return r.json().get("job")


def api_report(c: dict, qid: int, ok: bool, msg: str) -> None:
    requests.post(f"{c['api']}/sns/worker/report",
                  json={"key": c["key"], "id": qid, "ok": ok, "result": msg}, timeout=30)


async def run_once(c: dict) -> bool:
    job = api_next(c)
    if not job:
        return False
    log(f"작업 #{job['id']} {job['platform']} ({job.get('routine')})")
    ok, msg = await handle_job(job)
    api_report(c, job["id"], ok, msg)
    log(("성공 " if ok else "실패 ") + msg)
    return True


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--login")
    ap.add_argument("--shot", nargs=2, metavar=("URL", "OUT"))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    PROFILES.mkdir(parents=True, exist_ok=True)
    c = cfg()

    if a.shot:
        await capture(a.shot[0], a.shot[1])
        return
    if a.check:
        try:
            j = api_next(c)
            log("API 연결 OK, 대기작업:", "있음" if j else "없음")
            if j:
                api_report(c, j["id"], False, "check 모드 — 반환")
        except Exception as e:                      # noqa: BLE001
            log("API 연결 실패:", e)
        for p in ("threads", "instagram", "x"):
            d = PROFILES / p
            log(f"세션 {p}:", "있음" if d.exists() and any(d.iterdir()) else "없음")
        return
    if a.login:
        r = requests.get(f"{c['api']}/sns/worker/next", params={"key": c["key"]}, timeout=20)
        acc = {}
        try:                                        # 계정은 큐 응답에만 실려오므로 별도 조회 불가 →
            acc = (r.json().get("job") or {}).get("account") or {}
        except Exception:                           # noqa: BLE001
            pass
        if not acc:
            acc = (cfg().get("accounts") or {}).get(a.login, {})
        log(await do_login(a.login, acc))
        return
    if a.once:
        if not await run_once(c):
            log("대기 작업 없음")
        return
    if a.loop:
        log("워커 시작 — 폴링", a.interval, "초")
        while True:
            try:
                while await run_once(c):
                    await asyncio.sleep(3)
            except Exception as e:                  # noqa: BLE001
                log("루프 오류:", e)
            await asyncio.sleep(a.interval)
    ap.print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
