#!/usr/bin/env python3
"""계약서·확인설명서 주민번호 5년 파기 배치(개인정보 규제 — 한방 레거시 usp_5year 대응).

기준일 = 계약일(contract_date), 없으면 생성일(created_at). 5년 경과 시 jumin_enc를 NULL로.
body_json에는 애초에 마스킹본만 있으므로 jumin_enc 파기로 원본이 소멸한다.
크론(박스): 50 6 * * * — 결과는 stdout(로그 리다이렉트).
"""
import os
import sqlite3
from datetime import datetime, timedelta

REVIEWS_DB = os.environ.get("KOCZIP_REVIEWS_DB", "/opt/koczip/data/reviews.sqlite")
CUTOFF = (datetime.now() - timedelta(days=365 * 5 + 1)).strftime("%Y-%m-%d")


def main() -> None:
    c = sqlite3.connect(REVIEWS_DB)
    try:
        total = 0
        for table, datecol in (("biz_wcontracts", "contract_date"), ("biz_offerinfo", None)):
            if datecol:
                cond = f"COALESCE(NULLIF({datecol}, ''), substr(created_at, 1, 10)) < ?"
            else:
                # offerinfo는 부모 계약서 기준일을 따른다(1:1)
                cond = ("wcontract_id IN (SELECT id FROM biz_wcontracts WHERE "
                        "COALESCE(NULLIF(contract_date, ''), substr(created_at, 1, 10)) < ?)")
            cur = c.execute(
                f"UPDATE {table} SET jumin_enc=NULL WHERE jumin_enc IS NOT NULL AND {cond}",
                (CUTOFF,))
            if cur.rowcount:
                print(f"{datetime.now():%F %T} {table}: 주민번호 {cur.rowcount}건 파기 (기준 {CUTOFF} 이전)")
            total += cur.rowcount
        c.commit()
        if not total:
            print(f"{datetime.now():%F %T} 파기 대상 없음 (기준 {CUTOFF} 이전)")
    finally:
        c.close()


if __name__ == "__main__":
    main()
