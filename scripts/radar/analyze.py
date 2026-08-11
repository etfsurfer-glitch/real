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
        "reason": {"type": "string"},
        "content_idea": {"type": "string"},
    },
    "required": ["humor", "satire", "gossip", "controversy", "surprise", "empathy",
                 "hook", "realestate_relevance", "categories", "reason"],
}

PROMPT = """너는 SNS 바이럴 콘텐츠 분석가다. 아래 Threads 게시물이 사람들의 관심을 끌
가능성을 분석한다.

게시물:
---
{text}
---

각 항목을 0~10 으로 매긴다.
humor 웃기거나 재미있는 정도
satire 풍자성
gossip 남들이 궁금해할 이야기인 정도
controversy 논쟁을 일으킬 가능성
surprise 의외성·반전
empathy 공감 가능성
hook 첫 문장이 관심을 끄는 정도
realestate_relevance 부동산 콘텐츠로 연결할 수 있는 정도

categories 는 다음 중 해당하는 것만 고른다(복수 가능):
{cats}

reason 은 왜 관심을 끌 수 있는지 한 문장.
content_idea 는 부동산 SNS 콘텐츠로 바꿀 수 있다면 그 아이디어 한 줄.
부동산과 이어붙일 여지가 없으면 content_idea 는 빈 문자열로 둔다.
억지로 부동산에 갖다 붙이지 않는다 — realestate_relevance 를 낮게 주면 된다.

광고·홍보·판매글이면 모든 점수를 낮게 준다.
"""


def log(*a):
    print(datetime.now().strftime("%m-%d %H:%M:%S"), *a, flush=True)


def db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def gemini(text: str, key: str) -> dict | None:
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(
            text=text[:1500], cats=", ".join(CATEGORIES))}]}],
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
        "       age_min, engagement, time_weight, velocity"
        "  FROM posts WHERE analyzed_at IS NULL AND excluded=0"
        "  ORDER BY engagement DESC, first_seen_at DESC LIMIT ?", (a.limit * 4,)).fetchall()

    todo = [r for r in rows if worth_analyzing(r[3], r[4], r[5], r[6], r[7])][:a.limit]
    log(f"미분석 {len(rows)}건 중 1차 통과 {len(todo)}건")
    if not todo:
        return

    done = 0
    for r in todo:
        pid, _pk, text = r[0], r[1], r[2] or ""
        if len(text.strip()) < 20:
            c.execute("UPDATE posts SET analyzed_at=datetime('now','+9 hours'), ai_score=0,"
                      " ai_reason='본문이 너무 짧아 분석하지 않음' WHERE id=?", (pid,))
            c.commit()
            continue
        d = gemini(text, key)
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
            " realestate=?, ai_score=?, categories=?, ai_reason=?, content_idea=?, final_score=?"
            " WHERE id=?",
            (d.get("humor"), d.get("satire"), d.get("gossip"), d.get("controversy"),
             d.get("surprise"), d.get("empathy"), d.get("hook"),
             d.get("realestate_relevance"), round(ai, 1),
             ",".join(d.get("categories") or []), (d.get("reason") or "")[:400],
             (d.get("content_idea") or "")[:400], round(final, 1), pid))
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
