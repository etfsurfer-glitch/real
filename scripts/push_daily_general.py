#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""비회원·관심단지 없는 구독자용 일일 웹푸시 — 오늘의 급매·신고가 요약.

왜 필요한가 (2026-08-14)
  관심단지 알림(push_daily_favorites)은 로그인 + 관심단지가 있어야 대상이 된다.
  하지만 앱 첫 화면에서 '알림 받기'만 누르고 로그인 안 한 비회원(user_id='')이나,
  로그인했어도 아직 단지를 안 찜한 사용자는 정기 알림을 하나도 못 받는다.
  '최대한 알림을 전달' 하려면 이들에게도 매일 무언가 가야 한다 — 전국 오늘의
  급매·신고가 요약을 보낸다(리텐션 + 로그인·찜 유도).

대상
  push_subscriptions 중, 관심단지 알림 대상이 아닌 모든 구독:
    · user_id='' (비회원 익명 구독)
    · 관심단지가 하나도 없는 로그인 사용자
  관심단지 있는 사용자는 push_daily_favorites 가 이미 커버하므로 제외(중복 방지).

systemd koczip-push-general.timer 로 10·16시 실행. local_api 재사용.
"""
import sys

sys.path.insert(0, "/opt/koczip")
import scripts.local_api as A                                   # noqa: E402


def _won(v):
    """원 단위 금액 → '3억 5,000' / '3,700만' 표기(단지형 매매가는 원 단위로 온다)."""
    if not v:
        return None
    v = int(v)
    eok = v // 100_000_000
    man = (v % 100_000_000) // 10_000
    if eok and man:
        return f"{eok}억 {man:,}"
    if eok:
        return f"{eok}억"
    return f"{man:,}만"


def _greeting_by_hour():
    """아침엔 '간밤', 오후엔 '오늘' — 같은 알림이 두 번 와도 어색하지 않게."""
    import datetime
    h = (datetime.datetime.now(datetime.timezone.utc).hour + 9) % 24        # KST
    return "오늘 아침" if h < 13 else "오늘"


def _summary():
    """전국 오늘의 급매 1건 + 신고가 1건을 한 줄로. 데이터 없으면 None."""
    parts = []
    # ① 오늘의 급매(할인율 큰 순 1건)
    try:
        deals = A.today_deals(trade="A1", min_discount=0.1, limit=1, sort="discount")["items"]
        if deals:
            d = deals[0]
            disc = abs(round(d["discount"] * 100))          # discount 는 이미 음수(-0.29)
            parts.append(f"급매 {d['complex_name']} {_won(d['price'])}(실거래보다 {disc}%↓)")
    except Exception:                                          # noqa: BLE001
        pass
    # ② 신고가 경신(상승률 큰 순 1건)
    try:
        highs = A.tx_record_high(days=7, trade="A1", order="premium", limit=1)["items"]
        if highs:
            h = highs[0]
            prem = round(h["premium"] * 100)
            parts.append(f"신고가 {h['complex_name']} {_won(h['record_price'])}(직전보다 {prem}%↑)")
    except Exception:                                          # noqa: BLE001
        pass
    return " · ".join(parts) if parts else None


def main():
    with A._reviews_db() as rc:
        # 관심단지 알림이 커버하는 user 를 뺀 나머지 모든 구독 user_id (익명 '' 포함)
        rows = rc.execute(
            "SELECT DISTINCT user_id FROM push_subscriptions "
            "WHERE user_id NOT IN ("
            "  SELECT DISTINCT user_id FROM realtor_fav_complexes"
            ")").fetchall()
    targets = [r[0] for r in rows]                            # '' (익명) 도 하나의 타깃
    if not targets:
        print("일일 일반알림: 대상 0명"); return

    body = _summary()
    if not body:
        print("일일 일반알림: 오늘 급매·신고가 없음 → 발송 생략"); return

    body = f"{_greeting_by_hour()}의 " + body
    sent = A._send_web_push(targets, "오늘의 급매·신고가 📢", body,
                            url="/quick-deals", tag="daily-general").get("sent", 0)
    print(f"일일 일반알림: 대상 {len(targets)}그룹 · 발송 {sent}건")


if __name__ == "__main__":
    main()
