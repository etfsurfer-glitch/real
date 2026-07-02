"""관심단지 일일 알림 (매일 16:00 KST). 관심단지(realtor_fav_complexes)가 있고
   웹푸시를 구독한 사용자에게, 관심단지의 매물 변동·최근 실거래를 요약해 푸시한다.
   systemd koczip-push-fav.timer 로 실행. local_api 의 _send_web_push 재사용."""
import sys
sys.path.insert(0, "scripts")
import local_api as A  # noqa: E402


def _won(v):
    if not v:
        return ""
    if v >= 1e8:
        e = int(v // 1e8); m = int((v % 1e8) // 1e4)
        return f"{e}억{(' ' + format(m, ',')) if m else ''}"
    return f"{int(v // 1e4):,}만"


def _complex_seg(d, cno, cname):
    """관심단지 1곳 요약 세그먼트. 현재 매물수 + 어제 대비 증감 + 최근 실거래가."""
    cur = d.execute("SELECT COUNT(*) FROM listings_current WHERE complex_no=?", (cno,)).fetchone()[0]
    # 어제(직전 스냅샷) 매물수 — complex_daily_agg 합
    snaps = [r[0] for r in d.execute(
        "SELECT DISTINCT snapshot_date FROM complex_daily_agg WHERE complex_no=? "
        "ORDER BY snapshot_date DESC LIMIT 2", (cno,)).fetchall()]
    delta = None
    if len(snaps) == 2:
        yest = d.execute("SELECT COALESCE(SUM(listing_count),0) FROM complex_daily_agg "
                         "WHERE complex_no=? AND snapshot_date=?", (cno, snaps[1])).fetchone()[0]
        delta = cur - yest
    tx = d.execute("SELECT deal_amount, deal_ymd FROM transactions WHERE matched_complex_no=? "
                   "AND is_cancelled=0 ORDER BY deal_ymd DESC LIMIT 1", (cno,)).fetchone()
    name = (cname or "")[:11]
    seg = f"{name} 매물 {cur}"
    if delta:
        seg += f"({'+' if delta > 0 else ''}{delta})"
    if tx and tx[0]:
        seg += f"·실거래 {_won(tx[0])}"
    return seg


def main():
    with A._reviews_db() as rc:
        users = [r[0] for r in rc.execute(
            "SELECT DISTINCT f.user_id FROM realtor_fav_complexes f "
            "JOIN push_subscriptions p ON p.user_id = f.user_id").fetchall()]
    total_sent = 0
    for uid in users:
        with A._reviews_db() as rc:
            favs = rc.execute(
                "SELECT complex_no, complex_name FROM realtor_fav_complexes "
                "WHERE user_id=? ORDER BY created_at LIMIT 12", (uid,)).fetchall()
        if not favs:
            continue
        segs = []
        with A._open_db() as d:
            for cno, cname in favs:
                try:
                    segs.append(_complex_seg(d, cno, cname))
                except Exception:
                    continue
        if not segs:
            continue
        body = " · ".join(segs[:3])
        if len(segs) > 3:
            body += f" 외 {len(segs) - 3}곳"
        # 일반사용자 알림 — 랜딩은 홈(/lounge는 중개사 전용이라 부적합, 2026-07-02 정정)
        res = A._send_web_push([uid], "관심단지 오늘의 소식 🏠", body, url="/", tag="fav-daily")
        total_sent += res.get("sent", 0)
    print(f"관심단지 일일알림: 대상 {len(users)}명 · 발송 {total_sent}건")


if __name__ == "__main__":
    main()
