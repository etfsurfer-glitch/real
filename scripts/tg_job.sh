#!/usr/bin/env bash
# systemd 수집 잡 → 텔레그램 (시작/완료/오류). $1=start|end, $2=서비스명, end 시 $SERVICE_RESULT 사용
NAME_KO="$2"
case "$2" in
  koczip-daily)    NAME_KO="일일 데이터수집(실거래·대장)";;
  koczip-listings) NAME_KO="매물 수집";;
  koczip-catchup)  NAME_KO="수집 보충(catchup)";;
esac
if [ "$1" = "start" ]; then
  MSG="▶️ ${NAME_KO} 시작"
elif [ "$1" = "end-quiet" ]; then
  # 고빈도 잡(catchup 30분 주기)용 — 성공은 침묵, 실패만 알림
  [ "${SERVICE_RESULT:-success}" = "success" ] && exit 0
  MSG="🚨 ${NAME_KO} 오류 — ${SERVICE_RESULT} (exit ${EXIT_STATUS:-?})"
else
  if [ "${SERVICE_RESULT:-success}" = "success" ]; then
    MSG="✅ ${NAME_KO} 완료"
  else
    MSG="🚨 ${NAME_KO} 오류 — ${SERVICE_RESULT} (exit ${EXIT_STATUS:-?})"
  fi
fi
exec /opt/koczip/.venv/bin/python /opt/koczip/scripts/tg_notify.py "$MSG"
