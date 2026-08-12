import sys, sqlite3
sys.path.insert(0, "/opt/koczip-radar")
from analyze import is_politics
block = ["국민의힘 지지율 또 떨어졌다","대통령 담화 보셨나요","탄핵 심판 결과",
         "이번 총선 판세가","야당이 발의한 법안","특검 수사 시작",
         "이재명 정권이 다주택자를 규제하면서","8월 13일 본회의를 놓고 여야가 정면으로 붙었습니다",
         "여론조사만 하던 사람 아니야","김건희 여사 명품가방 재판 정치권 공방"]
allow = ["정부가 발표한 부동산 정책 때문에 취득세가 바뀐다",
         "세제개편안 나오고 집주인들 난리났다","재건축 규제 완화되면 우리 아파트도 오를까",
         "전세사기 당했는데 어떻게 하나요","집값 폭등 진짜 미쳤다",
         "LH 임대 신청했는데 붙었다","종부세 고지서 받았는데 작년보다 늘었네",
         "프라하 집 렌트 내놨는데 세입자 후보가 연락을 해 오셨다",
         "태극기 저것도 자유여야 한다고","둘째 밥 먹여야 되서 동생 밥 다 먹으면",
         "상가 손님이랑 오늘 3차 미팅이야 계약까지 딱 가고 싶다",
         "국토부 장관이 발표한 공급 대책","용산 아파트 시세 어떤가요",
         "송파구 재건축 진행 상황"]
bad=0
print("■ 정치(걸러야 함)")
for t in block:
    ok=is_politics(t); bad+= 0 if ok else 1
    print(f"  {'OK ' if ok else '★놓침'} {t[:44]}")
print("\n■ 부동산·일상(통과해야 함)")
for t in allow:
    ok=not is_politics(t); bad+= 0 if ok else 1
    print(f"  {'OK ' if ok else '★오탐'} {t[:44]}")
print(f"\n{'전부 통과' if bad==0 else str(bad)+'건 오류'}")
c=sqlite3.connect("/opt/koczip-radar/radar.sqlite"); c.row_factory=sqlite3.Row
rows=c.execute("SELECT text FROM posts WHERE text IS NOT NULL AND text<>''").fetchall()
hit=sum(1 for r in rows if is_politics(r["text"]))
print(f"실수집 {len(rows)}건 중 {hit}건 제외 ({100*hit/len(rows):.1f}%)")
