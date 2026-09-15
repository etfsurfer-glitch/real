# -*- coding: utf-8 -*-
"""세제개편안 발표 직후 매물 시장 반응 보고서 — 박재영 기자(매일경제) 단건 발송.
사용:
  python3 scripts/send_tax_reform_mail.py --dry-run   # 미리보기
  python3 scripts/send_tax_reform_mail.py             # 실제 발송

※ 취재 참고자료 전달 메일. 지킨 선:
  - 기사 문장을 대신 써주지 않는다. 관측 사실과 한계만.
  - 하루치 관측임을 본문에서 먼저 밝힌다. '추세'라고 말하지 않는다.
  - 매도 보류인지 매수 위축인지 단정하지 않는다(이 지표로는 못 가른다).
  - 개정 '안'이라는 점을 명시한다.
"""
import argparse
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "design" / "press" / "세제개편안_발표직후_매물시장반응.pdf"
TO_DEFAULT = "jyp8909@mk.co.kr"

SUBJECT = ("[콕집 데이터] 세제개편안 발표 다음 날 — 고가 지역만 매매·전세 동시에 잠김, "
           "취재 참고자료 드립니다")
BODY = """박재영 기자님, 안녕하세요.
부동산 데이터 분석 서비스 콕집(koczip.com)의 황인찬입니다.

8월 3일 저녁 세제개편안 발표 이후 아파트 매물이 어떻게 움직였는지,
저희가 매일 전수 수집하는 데이터로 하루치를 정리해 보고서로 만들었습니다.
취재에 참고가 될까 하여 보내드립니다.

핵심은 반응이 가격대별로 정반대였다는 점입니다.

 · 전국 219개 시군구를 최근 1년 아파트 실거래 평당가로 5등분해 봤더니,
   상위 20%(5분위)에서만 매매와 전세가 동시에 잠겼습니다.
 · 5분위 매매는 실제 거래·회수로 사라진 매물이 전주 같은 요일 대비 32.5% 줄었고,
   신규 유입은 평소의 60% 수준이었습니다.
 · 특히 전세가 더 강하게 멈췄습니다. 5분위 전세 신규 유입은 평소의 52%로
   매매보다 낮았습니다. 장기보유특별공제가 거주 중심으로 바뀌고 종부세 기본공제도
   거주 14억 / 비거주 9억으로 갈리면서, 세 혜택을 받으려면 집주인이 직접 들어가
   살아야 하고 그러면 그 집을 전세로 내놓을 수 없기 때문으로 보입니다.
 · 반대로 2~3분위는 전월세 매물이 오히려 늘었습니다(3분위 월세 평소의 176%).
   종부세 과세선에 걸리지 않아 거주 요건 강화의 영향을 받지 않는 구간입니다.

미리 밝혀 둘 부분이 있습니다.

 · 발표 다음 날 하루를 직전 3주 같은 요일과 비교한 결과입니다.
   추세라고 부르기에는 이르고, 며칠 더 쌓여야 확인됩니다.
 · 매물이 덜 사라진 것이 파는 쪽이 멈춰서인지 사는 쪽이 줄어서인지는
   이 지표만으로 구분되지 않습니다.
 · 실거래로는 아직 확인할 수 없습니다. 계약 후 30일 이내 신고여서
   8월 초 계약분은 9월 초에야 집계가 채워집니다. 일시적 2주택 특례
   경과조치 기준일인 8월 3일 전후의 계약 변화도 그때 확인이 가능합니다.
 · 개정 '안'이라 국회 논의에서 바뀔 수 있습니다.

수치는 네이버 부동산 매물 전수와 국토교통부 실거래가를 바탕으로 했습니다.
광고 기간만료로 자동으로 내려간 매물은 전부 걷어내고, 실제로 거래되거나
거둬들인 건수만 셌습니다(보고서에 산출 방식을 적어 두었습니다).

이후 며칠치가 쌓이면 추세 확인 자료를 다시 정리해 드리겠습니다.
필요하신 지역이나 구간이 있으시면 말씀해 주세요. 따로 뽑아 드리겠습니다.

감사합니다.

런투온라인 대표 황인찬
콕집 koczip.com
010-5942-8014
runtoonline@gmail.com
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", default=TO_DEFAULT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--smtp-user", default=None)
    ap.add_argument("--smtp-pass", default=None)
    a = ap.parse_args()

    user, pw = a.smtp_user, a.smtp_pass
    if not (user and pw):                      # repo 밖 자격증명 자동 로드
        env = Path.home() / ".koczip" / "mail.env"
        if env.exists():
            kv = dict(l.strip().split("=", 1) for l in env.read_text().splitlines()
                      if "=" in l and not l.strip().startswith("#"))
            user = user or kv.get("SMTP_USER")
            pw = pw or kv.get("SMTP_PASS")

    if not PDF.exists():
        print(f"[오류] 보고서가 없습니다: {PDF}")
        return 1

    m = EmailMessage()
    m["From"] = f"콕집 황인찬 <{user}>"
    m["To"] = a.to
    m["Subject"] = SUBJECT
    m.set_content(BODY)
    m.add_attachment(PDF.read_bytes(), maintype="application", subtype="pdf",
                     filename=PDF.name)

    print(f"받는 사람 : {a.to}")
    print(f"제목      : {SUBJECT}")
    print(f"첨부      : {PDF.name} ({PDF.stat().st_size / 1024:.0f} KB)")
    print(f"보내는 계정: {user}")
    print("-" * 60)
    print(BODY)
    if a.dry_run:
        print("[dry-run] 실제로 보내지 않았습니다.")
        return 0
    if not (user and pw):
        print("[오류] SMTP 자격증명이 없습니다(~/.koczip/mail.env).")
        return 1

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.send_message(m)
    print(f"[발송 완료] {a.to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
