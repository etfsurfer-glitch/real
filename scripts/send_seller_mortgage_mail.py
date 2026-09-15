# -*- coding: utf-8 -*-
"""매도인 자금 제공 매물 분석 보고서 — 박재영 기자(매일경제) 단건 발송.
사용:
  python3 scripts/send_seller_mortgage_mail.py --to reporter@mk.co.kr --dry-run   # 미리보기
  python3 scripts/send_seller_mortgage_mail.py --to reporter@mk.co.kr             # 실제 발송

※ 정치적으로 민감한 사안이라 본문에서 지킨 선:
  - 한계를 수치보다 **먼저** 쓴다. 6건을 '전국에 이만큼뿐'으로 읽으면 틀리기 때문.
  - 특정 거래(대통령 건)의 성격은 언급도 평가도 하지 않는다.
  - 어떻게 보도해 달라는 요청은 넣지 않는다. 출처 표기 요청도 뺐다.
"""
import argparse
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "design" / "press" / "매도인자금제공_분석보고서.pdf"

SUBJECT = "[콕집 데이터] ‘매도인 근저당’ 매물 광고 전수 분석 — 취재 참고자료 드립니다"
BODY = """박재영 기자님, 안녕하세요.
부동산 데이터 분석 서비스 콕집(koczip.com)의 황인찬입니다.

매도인이 매수인 앞으로 근저당을 설정하는 거래 방식이 최근 논의되고 있어,
저희가 가진 매물 광고 데이터로 확인되는 부분만 정리해 보고서로 만들었습니다.
취재에 참고가 될까 하여 보내드립니다.

먼저 이 자료의 한계부터 말씀드리는 것이 순서일 것 같습니다.
저희가 센 것은 '중개사가 매물 광고 설명란에 이 조건을 적어 넣은 사례'입니다.
등기부에 실제로 설정된 건수가 아닙니다. 매도인 근저당은 매물을 내놓는 단계가
아니라 매수인과의 계약 협상 과정에서 정해지는 경우가 많고, 그때는 광고 문구에
남지 않습니다. 그래서 이 숫자를 '전국에 이런 거래가 몇 건뿐'이라는 의미로
읽으시면 실제와 달라집니다. 이 점을 보고서에도 여러 번 적어 두었습니다.

그 전제 위에서 집계된 수치는 아래와 같습니다.
 · 전국 매물 광고 175만4,823건 중, 매도인이 매수인에게 직접 자금을 대준다고
   밝힌 광고 6건 (단지 기준 4곳 — 동일 물건의 중복 광고 가능성이 있습니다)
 · 6건 모두 매매 호가 20억원 이상. 전체 매매 광고에서 20억 이상은 6.1%입니다
 · 반대로 '근저당 없음·무융자'처럼 담보가 없다는 점을 내세운 광고는 8,167건
 · 비슷하게 자기자본을 줄이는 다른 조건: 세안고 148,942건, 주인전세 726건

6건의 광고 원문과 소재지·호가는 보고서 부록에 그대로 옮겨 두었습니다.
직접 확인해 보실 수 있도록 중개사가 쓴 문구를 손대지 않고 넣었습니다.

특정 거래가 통상적인지 이례적인지는 저희 데이터로 판단할 수 없어, 보고서에도
그에 대한 평가는 담지 않았습니다. 등기부 기준 실제 설정 빈도나 세무 처리
부분도 저희가 가진 자료로는 답변드리기 어려운 영역입니다.

첨부: 「매도인이 매수인에게 직접 자금을 대주는 매물」 데이터 분석 보고서 (A4 2매)

추가로 필요하신 집계가 있으면 말씀만 주십시오. 지역별·가격대별 재집계, 원자료
CSV, 다른 조건과의 교차 분석 등 어떤 형태든 준비해 드리겠습니다.

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
        print(f"[dry-run] to={a.to}")
        print(f"[dry-run] subject={SUBJECT}")
        print(f"[dry-run] 첨부 {PDF.name} ({PDF.stat().st_size:,}B)")
        print("-" * 70)
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
