# -*- coding: utf-8 -*-
"""매도인 자금제공 매물 현재 목록(14건) — 박재영 기자 후속 발송.
사용:
  python3 scripts/send_loan_list_mail.py --dry-run     # 미리보기
  python3 scripts/send_loan_list_mail.py               # 실제 발송

※ 오늘자 목록만 전달한다. 해석·정정 서술을 붙이지 않는다(사용자 지시).
   숫자는 매일 바뀌므로 '오늘 기준'임을 제목·본문에 명시하는 선까지만.
"""
import argparse
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

TO_DEFAULT = "jyp8909@mk.co.kr"

# (단지, 소재지, 호가억, 면적, 광고원문, 확인일) — 2026-07-23 09시 기준, 호가 내림차순
ROWS = [
    ("포제스한강", "서울 광진구 광장동", 54.0, "168",
     "매도인근저당가능 방음벽너머 한강뷰 개방감최고", "07-13"),
    ("반포자이", "서울 서초구 반포동", 45.0, "116B",
     "35 입주가능급매 매도인대출찬스 갑니다", "07-22"),
    ("디에이치아너힐즈", "서울 강남구 개포동", 35.0, "103A",
     "집주인 대출 가능 귀한매물 뷰좋고 해볕잘드는 입주가능한 집", "07-22"),
    ("광교중흥에스클래스(주상복합)", "경기 수원 영통구 원천동", 27.5, "173",
     "강추 올수리 환상적인 호수뷰 매도인대출가능 신분당선 역세권", "07-21"),
    ("판교원4단지휴먼시아푸르지오", "경기 성남 분당구 판교동", 23.0, "186",
     "단독주택 같은 분위기, 앞에 마당, 집주인대출 7억 가능, 서판교역 호재", "07-10"),
    ("센트라스", "서울 성동구 하왕십리동", 20.4, "88E",
     "26 인기구조, 매도인 근저당2억으로 갭11억 가능 토허제제외, 에어컨3", "07-23"),
    ("센트라스", "서울 성동구 하왕십리동", 20.4, "88E",
     "12억대갭투 강추. 매도인 근저당2억 가능. 공동0", "07-22"),
    ("강남자곡아이파크", "서울 강남구 자곡동", 20.0, "81A",
     "집주인대출6억. 수서역세권 개발호재. 추천매물. 자곡초. 풍문고 학세권.", "06-29"),
    ("래미안슈르", "경기 과천시 원문동", 19.4, "86",
     "매도인 대출 슈르 최고 로얄동 하시 입주가능", "07-22"),
    ("해운대아이파크(주상복합)", "부산 해운대구 우동", 18.0, "164F",
     "확트인 수영강 조망, 환기잘되는 양면창 구조, 집주인대출가능", "06-29"),
    ("동작삼성래미안", "서울 동작구 사당동", 16.5, "154",
     "컨디션양호 조망우수 매도인대출가능 숲세권", "07-22"),
    ("산성역자이푸르지오3단지", "경기 성남 수정구 신흥동", 16.0, "109B",
     "세끼고, 84B로얄동로얄층, 주인근저당가능매물, 고층뻥뷰, 희망대공원", "07-22"),
    ("에스탑(20-10)", "서울 송파구 송파동", 14.0, "99",
     "8호9호더블석촌역 도보5분거리소재 강추 매도인대출가능", "06-29"),
    ("해링턴플레이스다산파크", "경기 남양주시 다산동", 13.8, "114C",
     "꿈의 집, 옥상공간을 혼자 독차지,갭투, 집주인대출가능,썬룸", "07-06"),
]

SUBJECT = "[콕집 데이터] 7월 23일 기준 ‘매도인 대출’ 매물 14건 목록"


def build_table() -> str:
    w = [max(len(r[0]) for r in ROWS), max(len(r[1]) for r in ROWS)]
    out = []
    for i, (nm, loc, price, area, desc, ymd) in enumerate(ROWS, 1):
        out.append(f"{i:2d}. {nm}  ({loc})")
        out.append(f"    {price}억 · 전용 {area} · 확인 {ymd}")
        out.append(f"    “{desc}”")
        out.append("")
    return "\n".join(out).rstrip()


BODY = f"""박재영 기자님, 안녕하세요.
콕집(koczip.com) 황인찬입니다.

오늘(7월 23일) 기준 ‘매도인 대출’ 매물 목록을 보내드립니다. 14건입니다.

── 호가 내림차순 ─────────────────────────

{build_table()}

──────────────────────────────────────

광고 문구를 집계한 것이며 등기부상 실제 설정 건수는 아닙니다.
원문은 중개사가 쓴 그대로 옮겼고, 실제 조건은 해당 중개사무소 확인이 필요합니다.
센트라스 2건은 같은 면적·같은 호가로 동일 물건일 수 있어 단지로는 13곳입니다.

날마다 달라지는 수치라 필요하신 시점에 다시 뽑아드리겠습니다.

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

    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = f"콕집(koczip.com) <{a.smtp_user}>"
    msg["To"] = a.to
    msg.set_content(BODY)

    if a.dry_run:
        print(f"[dry-run] to={a.to}")
        print(f"[dry-run] subject={SUBJECT}")
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
    print(f"발송 완료 → {a.to}")


if __name__ == "__main__":
    main()
