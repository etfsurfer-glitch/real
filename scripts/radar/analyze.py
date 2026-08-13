#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNS 소재 레이더 — 1차 숫자 필터 + AI 분석.

모든 글을 LLM 에 보내면 돈이 샌다. 먼저 숫자로 거른 뒤 남은 것만 분석한다.
1차 필터는 '반응이 적다'가 아니라 '경과 시간에 견줘 반응이 적다'로 본다 —
올라온 지 20분 된 글에 좋아요 3개면 오히려 빠른 편이다.

작문 모델은 OpenAI 대신 Gemini 를 쓴다(콕집이 이미 이 키로 AI·카피를 돌린다).
Run: python3 analyze.py [--limit 40]
"""
import argparse
import base64
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path("/opt/koczip-radar")
DB = BASE / "radar.sqlite"
MODEL = "gemini-flash-latest"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
MAX_IMG_BYTES = 3_000_000        # 이보다 크면 그림 없이 분석한다
IMG_TEXT_LIMIT = 120             # 글이 이보다 짧으면 사진이 본체로 보고 함께 보낸다
MAX_AGE_MIN = 1440               # 하루 넘은 글은 분석하지 않는다(통과율 0.1%)
# ③ 사진은 유머·밈 계열에서만 본다. 부동산 글의 사진은 대개 시세표·매물 사진이라
#    글만으로 충분한데 입력 토큰이 3.6배(358→1307) 든다.
#    홈 피드는 주제가 섞여 있지만 사진이 본체인 밈이 가장 많이 들어오는 통로라 포함한다
#    (실측: 사진 동반 39건 중 피드 20 · 짤 12 · 밈 2).
IMG_KEYWORDS = ("밈", "짤", "웃긴", "유머", "웃픈", "현타", "어이없", "황당", "레전드",
                "주접", "(피드)")
API = os.environ.get("KOCZIP_API", "https://api.koczip.com")
WORKER_KEY = ""                  # .env 의 SNS_WORKER_KEY — 비용 보고에 쓴다

CATEGORIES = ["풍자", "주접", "가십", "팩폭", "논쟁", "황당", "밈", "반전", "공감",
              "정보", "사건", "경험담"]

# AI 점수 가중치 — hook 과 부동산 연관성을 가장 높게 본다.
# 이 도구의 목적이 '읽히는 글'을 찾아 '부동산으로 옮기는' 것이기 때문이다.
W = {"humor": 1.0, "satire": 1.2, "gossip": 0.7, "controversy": 1.1,
     "surprise": 1.1, "empathy": 1.2, "hook": 1.5, "realestate": 1.5}

SCHEMA = {
    "type": "object",
    "properties": {
        **{k: {"type": "integer"} for k in
           ("humor", "satire", "gossip", "controversy", "surprise", "empathy", "hook",
            "realestate_relevance")},
        "categories": {"type": "array", "items": {"type": "string", "enum": CATEGORIES}},
    },
    # 설명 문장(왜 읽히나 / 콘텐츠 아이디어)은 받지 않는다 — 점수와 분류만으로
    # 목록을 세우는 데 충분하고, 문장 생성이 출력 토큰의 대부분을 먹었다.
    "required": ["humor", "satire", "gossip", "controversy", "surprise", "empathy",
                 "hook", "realestate_relevance", "categories"],
}

PROMPT = """SNS 게시물의 관심 유발 가능성을 점수로만 매긴다. 설명은 쓰지 않는다.
사진이 함께 오면 사진이 본체다(밈·짤). 사진을 보고 판단한다.

게시물:
---
{text}
---

0~10 점: humor 재미 / satire 풍자 / gossip 남들이 궁금해할 이야기 /
controversy 논쟁 가능성 / surprise 의외성·반전 / empathy 공감 /
hook 첫 문장이 끄는 힘 / realestate_relevance 부동산으로 연결 가능한 정도.

categories 는 해당하는 것만 고른다(복수 가능): {cats}

광고·홍보·판매글은 모든 점수를 낮게.
정당·정치인·선거·탄핵 등 정치 이야기면 모든 점수를 0 으로 준다
(부동산 정책 자체를 다루는 글은 정치가 아니다).
"""


def log(*a):
    print(datetime.now().strftime("%m-%d %H:%M:%S"), *a, flush=True)


def db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def fetch_image(url: str) -> tuple[str, str] | None:
    """이미지를 받아 (base64, mime). 실패하면 None — 그림 없이 글만으로 분석한다."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
            raw = r.read(MAX_IMG_BYTES + 1)
        if not raw or len(raw) > MAX_IMG_BYTES or not mime.startswith("image/"):
            return None
        return base64.b64encode(raw).decode(), mime
    except Exception:                                       # noqa: BLE001
        return None


def report_cost(u: dict, model: str = "") -> None:
    """토큰 사용량을 본서버로 보낸다(관리자 AI 비용 화면 집계용). 실패해도 무시한다."""
    if not (API and WORKER_KEY and u):
        return
    try:
        body = json.dumps({
            "key": WORKER_KEY, "feature": "sns-radar", "model": model or MODEL,
            "in_tokens": u.get("promptTokenCount", 0),
            "out_tokens": u.get("candidatesTokenCount", 0),
            "think_tokens": u.get("thoughtsTokenCount", 0),
        }).encode()
        req = urllib.request.Request(f"{API}/ai-cost/report", data=body,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=8).read()
    except Exception:                                       # noqa: BLE001
        pass


def gemini(text: str, key: str, image: tuple[str, str] | None = None) -> dict | None:
    parts: list[dict] = [{"text": PROMPT.format(
        text=text[:800] or "(글 없음 — 사진이 본체다)", cats=", ".join(CATEGORIES))}]
    if image:
        # 밈은 사진이 본체라 글만 보면 점수를 매길 수 없다.
        # 다만 그림 한 장이 토큰을 먹으므로 글이 짧을 때만 붙인다(호출부에서 판단).
        parts.append({"inlineData": {"mimeType": image[1], "data": image[0]}})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "temperature": 0.4,
            # 생각 토큰도 출력으로 과금된다. 이 작업엔 깊은 추론이 필요 없다.
            # (gemini-flash-latest 는 thinkingBudget 를 400 으로 거절한다 — thinkingLevel 을 쓴다)
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}"
           f":generateContent?key={key}")
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    for attempt in (1, 2, 3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                d = json.loads(r.read())
            # 별칭(gemini-flash-latest)이 아니라 실제 해석된 모델을 적어야 단가가 맞는다
            report_cost(d.get("usageMetadata") or {}, d.get("modelVersion") or "")
            raw = d["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw)
        except Exception as e:                              # noqa: BLE001
            if attempt == 3:
                log("  ! Gemini 실패:", str(e)[:120])
                return None
            time.sleep(2 * attempt)
    return None


# ── 정치 글 제외 ─────────────────────────────────────────────────────────
# 정당·정치인·선거 이야기는 콕집 소재가 아니고, 잘못 인용하면 브랜드가 다친다.
# 다만 '부동산 정책'은 우리 본업이라 살려야 한다 — 정책 낱말만으로는 자르지 않고,
# 정치 낱말이 있을 때 그 글을 버린다.
# 낱말만으로 자르면 어미·지명에 걸린다(실측). 두 벌로 나눈다.
#   HARD  — 이 낱말이 있으면 정치로 본다
#   REGEX — 어미에 얹히는 낱말은 앞뒤 경계를 봐야 한다
POLITICS = (
    # 정당·진영
    "국민의힘", "더불어민주당", "민주당", "조국혁신당", "정의당", "개혁신당", "진보당",
    "여당", "야당", "좌파", "우파", "보수정권", "진보정권", "친문", "친윤", "친명",
    # 정치 행위·기관
    "대통령", "대선", "총선", "지방선거", "국회의원", "탄핵", "특검",
    "내란", "청문회", "국정감사", "국정조사", "개헌", "정계", "정치권", "표심",
    "지지율", "여론조사", "공천", "청와대", "영부인", "구청장", "시장 후보",
    # ⚠ 부동산 문맥에서 흔해 뺀 낱말(실측 오탐):
    #   후보 "세입자 후보"   용산·송파 등 자치구명   장관 "국토부 장관"
    #   정당 "정당한 사유"   국회 "국회의사당역"     계엄 — 일상 비유로도 쓰임
)
# '여야'는 "자유여야 한다", "먹여야 되서" 처럼 어미에 얹힌다 — 낱말 경계를 본다.
# '정권'은 "이재명 정권"처럼 앞에 사람·정당이 붙을 때만 정치다.
import re as _re
POLITICS_RE = (
    _re.compile(r"(?:^|[\s\W])여야(?:가|는|의|와|도|에|를|$|[\s\W])"),
    _re.compile(r"(?:정권\s*(?:교체|퇴진|심판)|[가-힣]{2,3}\s*정권)"),
)


def is_politics(text: str) -> bool:
    """정치 글이면 True. 부동산 정책 이야기는 통과시킨다."""
    t = (text or "")
    if any(w in t for w in POLITICS):
        return True
    return any(r.search(t) for r in POLITICS_RE)


def worth_analyzing(like, reply, repost, quote, age_min) -> bool:
    """1차 필터 — 경과 시간을 감안해 '반응이 붙고 있는가'로 본다."""
    eng = like + reply * 4 + repost * 7 + quote * 6
    if age_min is None:                       # 시간을 모르면 절대량으로만 본다
        return eng >= 30
    if age_min <= 60:                         # 1시간 안쪽이면 작은 반응도 신호다
        return eng >= 5
    if age_min <= 360:
        return eng >= 20
    if age_min <= 1440:
        return eng >= 60
    return eng >= 150                         # 하루 넘은 글은 확실히 큰 것만


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40, help="한 번에 분석할 글 수")
    a = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        env = BASE / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("GEMINI_API_KEY 가 없다")
    global WORKER_KEY
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("SNS_WORKER_KEY="):
                WORKER_KEY = line.split("=", 1)[1].strip()

    c = db()
    # ① 순서는 velocity(시간당 반응). engagement 내림차순으로 뽑으면 '오래됐지만 총량이
    #    큰 글'이 앞자리를 차지해, 정작 이 도구의 목적인 '아직 안 터진 글'이 뒤로 밀린다
    #    (실측: 다음 회차 40건 중 1시간 이내 글이 1건뿐이었다).
    # ② 하루 넘은 글은 아예 빼둔다 — 통과율이 0.1% 인데 매번 정렬 대상에 들어간다.
    rows = c.execute(
        "SELECT id, post_key, text, like_count, reply_count, repost_count, quote_count,"
        "       age_min, engagement, time_weight, velocity, image_url, has_video, keywords_all"
        "  FROM posts WHERE analyzed_at IS NULL AND excluded=0"
        "    AND (age_min IS NULL OR age_min <= ?)"
        "  ORDER BY velocity DESC, first_seen_at DESC LIMIT ?",
        (MAX_AGE_MIN, a.limit * 4)).fetchall()

    # 하루 넘도록 분석 대기에 남은 글은 다시 볼 이유가 없다 — 대기열에서 내린다.
    # (지우지 않고 analyzed_at 만 찍어 목록엔 반응 점수로 남는다)
    stale = c.execute(
        "UPDATE posts SET analyzed_at=datetime('now','+9 hours'), ai_score=0"
        " WHERE analyzed_at IS NULL AND excluded=0 AND age_min > ?", (MAX_AGE_MIN,)).rowcount
    if stale:
        c.commit()
        log(f"하루 지난 미분석 {stale}건 대기열에서 내림")

    # 정치 글은 분석하지 않는다. 지우지 않고 excluded 로 표시해 다음 회차에도 안 걸리게 한다
    # (AI 에 보내기 전에 걸러야 토큰도 아낀다).
    pol = [r for r in rows if is_politics(r[2])]
    if pol:
        c.executemany("UPDATE posts SET excluded=1, analyzed_at=datetime('now','+9 hours'),"
                      " ai_score=0, categories='정치제외' WHERE id=?", [(r[0],) for r in pol])
        c.commit()
        log(f"정치 글 {len(pol)}건 제외")
    rows = [r for r in rows if not is_politics(r[2])]

    todo = [r for r in rows if worth_analyzing(r[3], r[4], r[5], r[6], r[7])][:a.limit]
    log(f"미분석 {len(rows)}건 중 1차 통과 {len(todo)}건")
    if not todo:
        return

    done = 0
    for r in todo:
        pid, _pk, text = r[0], r[1], r[2] or ""
        img_url, has_video, kws = r[11], r[12], (r[13] or "")
        # 글이 짧고 사진이 있으면 밈일 수 있다 — 그때만 사진을 함께 본다.
        # 단 유머·밈 계열 키워드에서 온 글로 한정한다(부동산 글의 사진은 시세표·매물
        # 사진이라 글만으로 충분한데 입력 토큰이 3.6배 든다).
        img = None
        if (img_url and len(text.strip()) < IMG_TEXT_LIMIT
                and any(k in kws for k in IMG_KEYWORDS)):
            img = fetch_image(img_url)
        if len(text.strip()) < 20 and not img:
            c.execute("UPDATE posts SET analyzed_at=datetime('now','+9 hours'), ai_score=0"
                      " WHERE id=?", (pid,))
            c.commit()
            continue
        d = gemini(text, key, img)
        if not d:
            continue
        ai = sum(int(d.get(k if k != "realestate" else "realestate_relevance", 0)) * w
                 for k, w in W.items())
        eng, tw, vel = r[8], r[9], r[10]
        # 최종 = 반응(시간가중 적용) 0.6 + AI 0.4.
        # 두 축의 단위가 달라 그대로 더하면 반응이 압도하므로 AI 쪽을 10배로 맞춘다.
        final = (eng * tw + vel * 0.5) * 0.6 + ai * 10 * 0.4
        c.execute(
            "UPDATE posts SET analyzed_at=datetime('now','+9 hours'),"
            " humor=?, satire=?, gossip=?, controversy=?, surprise=?, empathy=?, hook=?,"
            " realestate=?, ai_score=?, categories=?, final_score=? WHERE id=?",
            (d.get("humor"), d.get("satire"), d.get("gossip"), d.get("controversy"),
             d.get("surprise"), d.get("empathy"), d.get("hook"),
             d.get("realestate_relevance"), round(ai, 1),
             ",".join(d.get("categories") or []), round(final, 1), pid))
        c.commit()
        done += 1
        if done % 10 == 0:
            log(f"  {done}/{len(todo)}")
    log(f"분석 완료 {done}건")

    # 분석 안 된 글도 목록에서 순서를 갖도록 반응 점수만으로 최종점수를 채운다
    c.execute("UPDATE posts SET final_score = engagement * time_weight + velocity * 0.5"
              " WHERE analyzed_at IS NULL")
    c.commit()


if __name__ == "__main__":
    main()
