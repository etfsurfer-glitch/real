"""콕집 중개사 앱 — 매물 브리핑 푸시(매일 10시·16시).

사무소 연결된 중개사 회원에게: ①내 사무소 매물 증감 ②관심단지 변화(신규·증감)
③관심중개사무소 증감 을 한 줄 요약으로 발송. 랜딩 /biz.
systemd koczip-push-biz.timer(10:00·16:00 KST)로 실행. local_api 의 _send_web_push 재사용.

16시 일반 관심단지 알림(push_daily_favorites)과 중복되지 않도록, 그쪽에서
중개사 회원(realtor_members)을 제외한다(이 브리핑이 상위호환).
"""
import sys
import sqlite3
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.local_api as A  # noqa: E402


def _fav_complex_segs(d, favs) -> list[str]:
    """관심단지별 '이름 +N' 세그먼트(변화 있는 것만)."""
    segs = []
    for cno, cname in favs:
        rows = d.execute(
            "SELECT snapshot_date, SUM(listing_count) FROM complex_daily_agg "
            "WHERE complex_no=? GROUP BY snapshot_date ORDER BY snapshot_date DESC LIMIT 2",
            (cno,)).fetchall()
        if len(rows) >= 2 and rows[0][1] is not None and rows[1][1] is not None:
            diff = rows[0][1] - rows[1][1]
            if diff:
                nm = cname
                if not nm:
                    r = d.execute("SELECT complex_name FROM complexes WHERE complex_no=?", (cno,)).fetchone()
                    nm = r[0] if r else cno
                segs.append(f"{nm} {'+' if diff > 0 else ''}{diff}")
    return segs


def _fav_office_segs(d, fav_ids) -> list[str]:
    segs = []
    for rid in fav_ids:
        rows = d.execute(
            "SELECT total FROM realtor_daily_count WHERE realtor_id=? "
            "ORDER BY snapshot_date DESC LIMIT 2", (rid,)).fetchall()
        if len(rows) >= 2:
            diff = rows[0][0] - rows[1][0]
            if diff:
                office = A._office_brief(rid)
                nm = (office.get("realtor_name") or rid)[:10]
                segs.append(f"{nm} {'+' if diff > 0 else ''}{diff}")
    return segs


def main() -> None:
    hour = datetime.datetime.now().hour
    title = "오전 매물 브리핑 ☀️" if hour < 13 else "오후 매물 브리핑 🌆"

    with A._reviews_db() as c:
        members = c.execute(
            "SELECT rm.user_id, rm.realtor_id FROM realtor_members rm "
            "JOIN push_subscriptions ps ON ps.user_id = rm.user_id "
            "GROUP BY rm.user_id").fetchall()
        favs_by_user = {}
        for uid, cno, cname in c.execute(
                "SELECT user_id, complex_no, complex_name FROM realtor_fav_complexes"):
            favs_by_user.setdefault(uid, []).append((cno, cname))
        offices_by_user = {}
        for uid, rid in c.execute("SELECT user_id, realtor_id FROM realtor_fav_offices"):
            offices_by_user.setdefault(uid, []).append(rid)

    total_sent = 0
    with A._open_db() as d:
        for uid, my_rid in members:
            segs = []
            # ① 내 사무소 매물 증감
            rows = d.execute(
                "SELECT total FROM realtor_daily_count WHERE realtor_id=? "
                "ORDER BY snapshot_date DESC LIMIT 2", (my_rid,)).fetchall()
            if rows:
                cur = rows[0][0]
                diff = (rows[0][0] - rows[1][0]) if len(rows) >= 2 else 0
                segs.append(f"내 매물 {cur}건" + (f" ({'+' if diff > 0 else ''}{diff})" if diff else ""))
            # ② 관심단지 ③ 관심중개사 (변화 있는 것만, 합쳐 최대 3세그)
            segs += _fav_complex_segs(d, favs_by_user.get(uid, []))[:2]
            segs += _fav_office_segs(d, offices_by_user.get(uid, []))[:2]
            if not segs:
                continue
            body = " · ".join(segs[:4])
            res = A._send_web_push([uid], title, body, url="/biz", tag="biz-digest")
            total_sent += res.get("sent", 0)
    print(f"중개사 브리핑({hour}시): 대상 {len(members)}명 · 발송 {total_sent}건")


if __name__ == "__main__":
    main()
