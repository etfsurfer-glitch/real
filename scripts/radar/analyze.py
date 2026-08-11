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
            raw = d["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw)
        except Exception as e:                              # noqa: BLE001
            if attempt == 3:
                log("  ! Gemini 실패:", str(e)[:120])
                return None
            time.sleep(2 * attempt)
    return None


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

    c = db()
    rows = c.execute(
        "SELECT id, post_key, text, like_count, reply_count, repost_count, quote_count,"
        "       age_min, engagement, time_weight, velocity, image_url, has_video"
        "  FROM posts WHERE analyzed_at IS NULL AND excluded=0"
        "  ORDER BY engagement DESC, first_seen_at DESC LIMIT ?", (a.limit * 4,)).fetchall()

    todo = [r for r in rows if worth_analyzing(r[3], r[4], r[5], r[6], r[7])][:a.limit]
    log(f"미분석 {len(rows)}건 중 1차 통과 {len(todo)}건")
    if not todo:
        return

    done = 0
    for r in todo:
        pid, _pk, text = r[0], r[1], r[2] or ""
        img_url, has_video = r[11], r[12]
        # 글이 짧아도 사진이 있으면 밈일 수 있다 — 사진을 보고 판단한다
        img = None
        if img_url and len(text.strip()) < IMG_TEXT_LIMIT:
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
