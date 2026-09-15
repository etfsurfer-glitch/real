# -*- coding: utf-8 -*-
"""서울 빌라 동향 보고서 — 박재영 기자 단건 발송.
사용:
  python3 scripts/send_villa_mail.py --to reporter@example.com --smtp-pass '<Gmail 앱비밀번호>'
  (--dry-run 이면 발송 없이 본문 미리보기)
"""
import argparse
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "design" / "press" / "서울빌라_동향보고서.pdf"

SUBJECT = "[콕집 데이터] 서울 주택 수요의 빌라 이동 — 실거래 25개월·매물 분석 보고서 드립니다"
BODY = """박재영 기자님, 안녕하세요.
부동산 데이터 분석 서비스 콕집(koczip.com)의 황인찬입니다.

말씀 주셨던 기사 방향 — "아파트 가격·전세 부담에 밀린 수요가 빌라로 옮겨간다" — 를
국토부 실거래 25개월과 콕집의 일별 매물 수집 데이터로 검증해 보고서로 정리했습니다.
결론부터 말씀드리면, 데이터가 그 방향을 뚜렷하게 지지합니다.

핵심 수치 (모두 첨부 보고서에 표·출처 포함)
 · 서울 아파트+빌라 매매 계약 중 빌라 비중: 2024년 7월 19.5% → 최근 월 38.4%
   (월 거래 1,100~2,100건 → 2,500~3,500건대)
 · 전세도 같은 방향: 빌라 비중 26% → 2026년 봄 33~35%.
   동인은 서울 아파트 전세 평균 보증금 5.70억 → 6.60억(+15.8%)
 · 서울 25개 자치구 전부에서 빌라 매매 증가 (영등포 +168% ~ 용산 +27%)
 · 증가를 이끄는 건 저가가 아니라 6~10억 중고가 빌라(+206%) —
   그중 88%가 신축 아닌 기존 주택으로, 아파트 대체 수요 성격
 · 참고로 빌라 매물 통계는 광고 거품이 적습니다: 같은 집 중복 광고를 걷어낸
   광고배율이 빌라 x1.21 vs 아파트 x2.65

첨부: 「서울 빌라(연립·다세대) 최근 동향」 보고서 (A4 5매, 표 7개, 산출 기준·한계 명시)

빌라는 아파트와 달리 매물 정보 공개 범위가 제한적이어서(건물명 비공개 등) 이번 자료에
수집상의 한계가 있는 점은 보고서에 함께 명시해 두었습니다. 콕집은 빌라 부문의 일별 상세
집계를 이미 축적하기 시작했고, 앞으로 빌라 데이터를 지속적으로 보강해 나갈 계획입니다.
기사에 필요한 자료가 있으시면 언제든지 연락 주십시오 — 원자료 CSV, 특정 자치구 심층,
기간 조정, 그래프용 데이터 등 어떤 형태든 기사 자료 제공에 최선을 다하겠습니다.

인용 시 출처는 "콕집(koczip.com)"으로 부탁드립니다.

감사합니다.

황인찬 드림
런투온라인 · 콕집(koczip.com)
010-5942-8014 · runtoonline@gmail.com
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True)
    ap.add_argument("--smtp-user", default="runtoonline@gmail.com")
    ap.add_argument("--smtp-pass", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not PDF.exists():
        raise SystemExit(f"첨부 없음: {PDF}")
    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = f"콕집(koczip.com) <{a.smtp_user}>"
    msg["To"] = a.to
    msg.set_content(BODY)
    msg.add_attachment(PDF.read_bytes(), maintype="application", subtype="pdf",
                       filename=PDF.name)

    if a.dry_run:
        print(f"[dry-run] to={a.to} subject={SUBJECT}")
        print(f"[dry-run] 첨부 {PDF.name} ({PDF.stat().st_size:,}B)")
        print(BODY)
        return
    if not a.smtp_pass:
        # ~/.koczip/mail.env 에서 자동 로드 (SMTP_PASS=...)
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
