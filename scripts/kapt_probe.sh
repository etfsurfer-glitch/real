#!/bin/bash
# K-apt 제공기관 가용성 탐침 — 5분마다 장충금 서비스 한 번 호출해 결과 코드를 기록(OK / 04 등). 정비 시간대 파악용.
cd /opt/koczip
for i in $(seq 1 150); do
  r=$(/opt/koczip/.venv/bin/python - <<'PY'
import scripts.local_api as api, urllib.parse as up, urllib.request as ur, json
key=api._dgk_keys()[2]
qs=up.urlencode({'kaptCode':'A10027898','searchDate':'202605','_type':'json'})+'&serviceKey='+up.quote(key,safe='')
try:
    j=json.loads(ur.urlopen(f"{api._KAPT_BASE}{api._KAPT_SVC['ltf']}/getHsmpMonthFeeInfoV3?{qs}",timeout=12).read())
    print(j['OpenAPI_ServiceResponse']['cmmMsgHeader']['returnReasonCode'] if 'OpenAPI_ServiceResponse' in j else 'OK')
except Exception as e: print(str(e)[:30])
PY
)
  echo "$(date +%m-%d\ %H:%M) $r" >> /tmp/kapt_probe.log
  sleep 300
done
