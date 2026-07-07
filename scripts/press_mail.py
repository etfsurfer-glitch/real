# -*- coding: utf-8 -*-
"""보도자료 개인화 발송 — CSV(이메일,소속,이름) → "{이름} 기자님" 본문 + 첨부.

CSV 형식(헤더 자유, 열 순서 무관 — email/이메일, org/소속, name/이름 인식):
    email,org,name
    kim@news.co.kr,한국일보,김민수

Run:
    python3 scripts/press_mail.py reporters.csv --dry-run          # 발송 없이 미리보기
    python3 scripts/press_mail.py reporters.csv --send \
        --smtp-user runtoonline@gmail.com --smtp-pass '<앱 비밀번호>'

Gmail은 2단계 인증 계정의 '앱 비밀번호'(16자리)가 필요합니다:
구글 계정 → 보안 → 2단계 인증 → 앱 비밀번호 생성.
전송 간 4초 간격(스팸 분류 방지), 실패 목록은 press_mail_failed.csv 로 남깁니다.
"""
from __future__ import annotations

import argparse
import csv
import smtplib
import sys
import time
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESS = ROOT / "design" / "press"
sys.path.insert(0, str(PRESS))
from press_text import EMAIL_SUBJECT, EMAIL_BODY  # noqa: E402

ATTACH = [
    PRESS / "콕집_보도자료.docx",
    PRESS / "콕집_보도자료.pdf",
]
SHOTS = sorted((PRESS / "shots").glob("0*.png"))
FROM_NAME = "콕집(koczip) 황인찬"


def read_rows(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.reader(f)
        header = next(rd)
        idx = {}
        for i, h in enumerate(header):
            h = (h or "").strip().lower()
            if h in ("email", "이메일", "메일", "e-mail"):
                idx["email"] = i
            elif h in ("org", "소속", "매체", "언론사"):
                idx["org"] = i
            elif h in ("name", "이름", "기자명", "성명"):
                idx["name"] = i
        if "email" not in idx:   # 헤더가 없으면 (이메일,소속,이름) 순서로 간주
            f.seek(0)
            rd = csv.reader(f)
            for r in rd:
                if len(r) >= 3 and "@" in r[0]:
                    rows.append({"email": r[0].strip(), "org": r[1].strip(), "name": r[2].strip()})
            return rows
        for r in rd:
            try:
                rows.append({"email": r[idx["email"]].strip(),
                             "org": r[idx.get("org", 0)].strip() if "org" in idx else "",
                             "name": r[idx.get("name", 0)].strip() if "name" in idx else ""})
            except IndexError:
                continue
    return [r for r in rows if "@" in r["email"]]


def build_msg(row: dict, smtp_user: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = EMAIL_SUBJECT
    msg["From"] = formataddr((FROM_NAME, smtp_user))
    msg["To"] = row["email"]
    name = row["name"] or (row["org"] + " 담당" if row["org"] else "기자")
    msg.set_content(EMAIL_BODY.format(name=name))
    for p in ATTACH:
        msg.add_attachment(p.read_bytes(), maintype="application", subtype="octet-stream",
                           filename=p.name)
    for p in SHOTS:
        msg.add_attachment(p.read_bytes(), maintype="image", subtype="png", filename=p.name)
    return msg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--send", action="store_true", help="실제 발송(기본은 dry-run)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--smtp-user", default="runtoonline@gmail.com")
    ap.add_argument("--smtp-pass", default="", help="Gmail 앱 비밀번호(16자리)")
    ap.add_argument("--interval", type=float, default=4.0)
    args = ap.parse_args()

    rows = read_rows(args.csv)
    total_attach_mb = sum(p.stat().st_size for p in ATTACH + SHOTS) / 1e6
    print(f"수신자 {len(rows)}명 · 첨부 {len(ATTACH) + len(SHOTS)}개({total_attach_mb:.1f}MB)")
    for r in rows[:5]:
        nm = r["name"] or "(이름없음)"
        print(f"  - {nm} 기자님 <{r['email']}> ({r['org']})")
    if len(rows) > 5:
        print(f"  … 외 {len(rows) - 5}명")

    if not args.send:
        print("\n[dry-run] 실제 발송하려면 --send --smtp-pass '<앱비밀번호>' 를 붙이세요.")
        print("--- 본문 미리보기 (첫 수신자) ---")
        if rows:
            print(EMAIL_BODY.format(name=rows[0]["name"] or "OO"))
        return

    if not args.smtp_pass:
        sys.exit("--smtp-pass (Gmail 앱 비밀번호) 필요")
    failed = []
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(args.smtp_user, args.smtp_pass)
        for i, r in enumerate(rows, 1):
            try:
                s.send_message(build_msg(r, args.smtp_user))
                print(f"[{i}/{len(rows)}] OK {r['email']}")
            except Exception as e:
                print(f"[{i}/{len(rows)}] FAIL {r['email']} — {e}")
                failed.append(r)
            time.sleep(args.interval)
    if failed:
        out = Path("press_mail_failed.csv")
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["email", "org", "name"])
            for r in failed:
                w.writerow([r["email"], r["org"], r["name"]])
        print(f"실패 {len(failed)}건 → {out}")


if __name__ == "__main__":
    main()
