#!/usr/bin/env python
"""data.go.kr 실거래 API 헬스체크. UP=exit 0, DOWN=exit 1.

공공데이터(apis.data.go.kr) 서버는 502/timeout 장애가 잦다. 실거래 수집(backfill)
전에 이걸로 살아있는지 확인해서, 죽었으면 아예 손대지 않는다(헛돌기·부분수집 방지).
"""
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/koczip")
from collector.config import settings  # noqa: E402

EP = ("https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/"
      "getRTMSDataSvcAptTradeDev")


def is_up(timeout: int = 25) -> bool:
    key = settings.data_go_kr_service_key
    if not key:
        return False
    qs = urllib.parse.urlencode({
        "serviceKey": key, "LAWD_CD": "11680", "DEAL_YMD": "202604",
        "pageNo": 1, "numOfRows": 5,
    })
    try:
        req = urllib.request.Request(EP + "?" + qs, headers={"Accept": "application/xml"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
        return ("<resultCode>00" in body) or ("<item>" in body)
    except Exception:
        return False


if __name__ == "__main__":
    t = time.time()
    up = is_up()
    print(f"data.go.kr: {'UP' if up else 'DOWN'} ({time.time()-t:.1f}s)")
    sys.exit(0 if up else 1)
