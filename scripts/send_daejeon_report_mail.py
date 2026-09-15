# -*- coding: utf-8 -*-
"""대전 선도지구 발표 후 동향 보고서 — 박재영 기자(매일경제) 단건 발송.
사용:
  python3 scripts/send_daejeon_report_mail.py --dry-run   # 미리보기
  python3 scripts/send_daejeon_report_mail.py             # 실제 발송

※ 취재 참고자료(보고서) 전달 메일. 지킨 선:
  - 기사 문장을 대신 써주지 않는다. 관측 사실과 한계만.
  - '선정되면 오른다'는 예측 금지 — 매물이 잠겼다는 사실까지만.
  - 실거래 미완성(신고 30일 지연)을 본문에서 먼저 밝힌다.
"""
import argparse
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "design" / "press" / "대전선도지구_발표후동향.pdf"
TO_DEFAULT = "jyp8909@mk.co.kr"

SUBJECT = "[콕집 데이터] 대전 선도지구 발표 후 열흘 — 6개 단지 매물 40% 잠김, 취재 참고자료 드립니다"
BODY = """박재영 기자님, 안녕하세요.
부동산 데이터 분석 서비스 콕집(koczip.com)의 황인찬입니다.

7월 15일 대전 노후계획도시 선도지구 선정 발표 이후, 선정된 6개 단지의 매물이
어떻게 움직였는지 저희가 매일 수집하는 데이터로 정리해 보고서로 만들었습니다.
취재에 참고가 될까 하여 보내드립니다.

핵심은 매물이 빠르게 잠겼다는 점입니다.

 · 선도지구 6개 단지(크로바·목련·한가람·공작한양·보람·삼익소월, 7,797세대)의
   매매 광고매물이 발표 전날 227건에서 7월 24일 135건으로 40.5% 줄었습니다.
 · 특정일에 몰린 게 아니라 발표 직후부터 열흘간 거의 매일 줄었습니다.
 · 같은 동네(둔산·탄방·법동)의 선정되지 않은 아파트는 -5~-9%,
   대전 전체 아파트는 -2.3%에 그쳤습니다. 선도지구에서만 급격히 잠긴 셈입니다.
 · 새 매물이 안 나온 게 아니라(신규 등록은 43→45건으로 그대로),
   있던 매물을 거둬들인 것이 감소를 이끌었습니다.

다만 미리 밝혀 둘 부분이 있습니다.
호가는 아직 뚜렷하게 움직이지 않았고(6개 단지 평균 7.68억 → 7.61억),
발표 이후 실거래는 신고 기한 30일 때문에 아직 대부분 신고되지 않았습니다.
따라서 이번 발표가 실제 거래가격에 어떤 영향을 줬는지는 8월 이후에야 확인됩니다.
관측 기간도 발표 후 열흘로 짧아, 이 매물 잠김이 일시적 관망인지 지속될 흐름인지는
더 지켜봐야 합니다. 이 자료로 앞으로의 가격을 예측하기는 어렵다는 점을 함께
말씀드립니다.

첨부: 「대전 선도지구 발표 후 동향」 데이터 분석 보고서 (A4 2매, 단지별 원자료 표 포함)

단지별 발표 전후 매물·호가는 보고서 부록 표에 그대로 옮겨 두었습니다.
추가로 필요하신 집계가 있으면 말씀만 주십시오 — 특정 단지 심층, 일자별 원자료,
인근 다른 지역 비교 등 어떤 형태든 준비해 드리겠습니다.

감사합니다.

황인찬 드림
런투온라인 · 콕집(koczip.com)
010-5942-8014 · runtoonline@gmail.com
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", default=TO_DEFAULT)
    ap.add_argument("--smtp-user", default="runtoonline@gmail.com")
    ap.add_argument("--smtp-pass", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not PDF.exists():
        raise SystemExit(f"첨부 없음: {PDF} — 먼저 make_daejeon_seondo_report.py 실행")
    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = f"콕집(koczip.com) <{a.smtp_user}>"
    msg["To"] = a.to
    msg.set_content(BODY)
    msg.add_attachment(PDF.read_bytes(), maintype="application", subtype="pdf",
                       filename=PDF.name)

    if a.dry_run:
        print(f"[dry-run] to={a.to}")
        print(f"[dry-run] subject={SUBJECT}")
        print(f"[dry-run] 첨부 {PDF.name} ({PDF.stat().st_size:,}B)")
        print("-" * 72)
        print(BODY)
        return
    if not a.smtp_pass:
        env = Path.home() / ".koczip" / "mail.env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("SMTP_PASS="):
                    a.smtp_pass = line.split("=", 1)[1].strip()
                elif line.startswith("SMTP_USER=") and a.smtp_user == "runtoonline@gmail.com":
                    a.smtp_user = line.split("=", 1)[1].strip()
    if not a.smtp_pass:
        raise SystemExit("--smtp-pass 또는 ~/.koczip/mail.env 필요")
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(a.smtp_user, a.smtp_pass)
        s.send_message(msg)
    print(f"발송 완료 → {a.to} (첨부 {PDF.name})")


if __name__ == "__main__":
    main()
