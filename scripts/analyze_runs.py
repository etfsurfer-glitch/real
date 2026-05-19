"""과거 daily_run.ps1 실행 로그를 파싱해서 시간대별 성능 비교 표 출력.

사용 시점: 여러 시간대에 수동으로 daily_run.ps1을 돌려본 후 패턴 확인.
어느 시간대가 빠른지/에러가 적은지 보고 스케줄러 시간 결정.

  python scripts/analyze_runs.py
  python scripts/analyze_runs.py --days 14   # 최근 14일 로그
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LOG_DIR = Path("D:/auto/naverreal/logs")
DAILY_PATTERN = re.compile(r"daily_(\d{8})_(\d{4})\.log$")
NATIONWIDE_PATTERN = re.compile(r"nationwide_(\d{8})_(\d{4})\.log$")

_DONE_RE = re.compile(r"\[done\] (\d+)s\s+list_err=(\d+)\s+items=(\d+)\s+errs=(\d+)")
_PROGRESS_RE = re.compile(r"\((\d+\.\d+)/s\s+items=\d+\s+errs=(\d+)\)")
_PHASE2_START_RE = re.compile(r"\[2/3\] articles\s+total_tasks=(\d+)")


def parse_log(path: Path) -> dict | None:
    """Handle both UTF-8 (modern logs) and UTF-16 LE BOM (PowerShell Out-File)."""
    try:
        raw = path.read_bytes()
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            text = raw.decode("utf-16", errors="replace")
        else:
            text = raw.decode("utf-8", errors="replace")
    except Exception:
        return None
    m = _DONE_RE.search(text)
    if not m:
        return None
    duration = int(m.group(1))
    list_err = int(m.group(2))
    items = int(m.group(3))
    errs = int(m.group(4))
    # last reported throughput (Phase 2 effective)
    rates = _PROGRESS_RE.findall(text)
    last_rate = float(rates[-1][0]) if rates else 0.0
    # rate variance: max rate, min rate, count of distinct samples
    rate_vals = [float(r[0]) for r in rates if float(r[0]) > 0]
    return {
        "duration_s": duration,
        "duration_h": duration / 3600,
        "items": items,
        "errs": errs,
        "list_err": list_err,
        "rate_last": last_rate,
        "rate_max": max(rate_vals) if rate_vals else 0,
        "rate_min": min(rate_vals) if rate_vals else 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=30)
    args = p.parse_args()

    logs = []
    # Both daily and standalone nationwide logs
    for name_re in (DAILY_PATTERN, NATIONWIDE_PATTERN):
        for log in LOG_DIR.glob("*.log"):
            m = name_re.match(log.name)
            if not m:
                continue
            d_str, t_str = m.group(1), m.group(2)
            try:
                started = datetime.strptime(d_str + t_str, "%Y%m%d%H%M")
            except ValueError:
                continue
            age_days = (datetime.now() - started).days
            if age_days > args.days:
                continue
            stats = parse_log(log)
            if not stats:
                continue
            stats["started"] = started
            stats["name"] = log.name
            stats["hour"] = started.hour
            logs.append(stats)

    if not logs:
        print("[!] no parseable run logs found")
        return 1

    logs.sort(key=lambda x: x["started"])

    print(f"{'start':<17} {'hour':<4} {'duration':<10} {'items':<10} {'errs':<5} {'list_err':<8} {'rate(last)':<10}")
    print("-" * 80)
    for r in logs:
        d_str = r["started"].strftime("%Y-%m-%d %H:%M")
        dur = f"{r['duration_h']:.2f}h" if r["duration_h"] >= 1 else f"{r['duration_s']}s"
        print(f"{d_str:<17} {r['hour']:<4} {dur:<10} "
              f"{r['items']:<10,} {r['errs']:<5} {r['list_err']:<8} {r['rate_last']:<5.1f}")

    # Bucket by hour-of-day
    print("\n=== 시간대별 평균 (UTC+9) ===")
    by_hour: dict[int, list] = {}
    for r in logs:
        by_hour.setdefault(r["hour"], []).append(r)
    print(f"{'시':<4} {'#runs':<8} {'avg_dur':<10} {'avg_errs':<10} {'avg_rate(last)'}")
    print("-" * 60)
    for hr in sorted(by_hour):
        rs = by_hour[hr]
        n = len(rs)
        avg_dur = sum(r["duration_h"] for r in rs) / n
        avg_errs = sum(r["errs"] for r in rs) / n
        avg_rate = sum(r["rate_last"] for r in rs) / n
        print(f"{hr:02d}시  {n:<6}  {avg_dur:.2f}h    "
              f"{avg_errs:.1f}    {avg_rate:.1f}/s")

    print("\n수동으로 여러 시간대 돌려본 뒤 다시 실행하면 패턴 비교 가능.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
