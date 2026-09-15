#!/bin/bash
# nfind 서버에서 '사람이 직접 로그인'하기 위한 임시 원격 화면.
#   ./sns_login_gui.sh threads|instagram|x
#   로그인을 마치면 Ctrl+C → 크롬·VNC·가상화면을 정리하고 워커를 다시 켠다.
#
# 접속은 SSH 터널로만 (외부 포트 개방 없음):
#   맥에서:  ssh -N -L 5900:127.0.0.1:5900 root@115.68.177.72
#   그다음:  Finder ⌘K → vnc://127.0.0.1:5900
#
# 주의: 프로세스 종료는 반드시 '우리가 띄운 PID'로만 한다.
#       pkill -f 는 패턴이 다른 명령줄(심지어 SSH 세션)에 걸려 엉뚱한 것을 죽인다(실제로 겪음).
set -u
PLAT="${1:-threads}"
BASE=/opt/koczip-sns
PROFILE="$BASE/profiles/$PLAT"
DISP=":99"
VNCPW="$BASE/.vncpass"
PWTXT="$BASE/.vncpass.txt"

case "$PLAT" in
  threads)   URL="https://www.threads.com/login" ;;
  instagram) URL="https://www.instagram.com/accounts/login/" ;;
  x)         URL="https://x.com/i/flow/login" ;;
  *) echo "사용법: $0 threads|instagram|x"; exit 1 ;;
esac

XVFB_PID=""; VNC_PID=""; CHROME_PID=""
cleanup() {
  echo ""
  echo "정리 중..."
  [ -n "$CHROME_PID" ] && kill "$CHROME_PID" 2>/dev/null
  sleep 2
  [ -n "$VNC_PID" ]  && kill "$VNC_PID" 2>/dev/null
  [ -n "$XVFB_PID" ] && kill "$XVFB_PID" 2>/dev/null
  sleep 1
  systemctl start koczip-sns-worker 2>/dev/null
  echo "완료 — 워커 재가동. 로그인 세션은 $PROFILE 에 남습니다."
}
trap cleanup EXIT INT TERM

# 크롬 프로필은 동시 사용 불가 → 워커를 잠시 멈춘다
systemctl stop koczip-sns-worker 2>/dev/null
sleep 2

# VNC 비밀번호(최초 1회) — x11vnc 는 6자 이상을 요구한다
if [ ! -f "$VNCPW" ]; then
  PW=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 10)
  x11vnc -storepasswd "$PW" "$VNCPW" >/dev/null 2>&1 || { echo "VNC 비밀번호 생성 실패"; exit 1; }
  printf '%s\n' "$PW" > "$PWTXT"; chmod 600 "$PWTXT"
fi

Xvfb "$DISP" -screen 0 1280x900x24 >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!
sleep 3
kill -0 "$XVFB_PID" 2>/dev/null || { echo "Xvfb 실행 실패: $(tail -2 /tmp/xvfb.log)"; exit 1; }

# 127.0.0.1 에만 바인딩 — 외부 직접 접속 불가(SSH 터널 필요)
x11vnc -display "$DISP" -rfbauth "$VNCPW" -localhost -rfbport 5900 \
       -forever -shared -noxdamage >/tmp/x11vnc.log 2>&1 &
VNC_PID=$!
sleep 3
kill -0 "$VNC_PID" 2>/dev/null || { echo "x11vnc 실행 실패: $(tail -3 /tmp/x11vnc.log)"; exit 1; }

mkdir -p "$PROFILE"
CHROME=$(find "$BASE/browsers" -maxdepth 3 -type f -name chrome -path "*chromium-*" 2>/dev/null | head -1)
[ -x "$CHROME" ] || { echo "크롬 실행파일을 찾지 못했습니다"; exit 1; }

DISPLAY="$DISP" "$CHROME" \
  --user-data-dir="$PROFILE" --no-sandbox --disable-dev-shm-usage \
  --no-first-run --no-default-browser-check --window-size=1280,880 \
  --lang=ko-KR "$URL" >/tmp/chrome_gui.log 2>&1 &
CHROME_PID=$!
sleep 3

echo "════════════════════════════════════════════════════════"
echo " $PLAT 로그인 화면 준비 완료"
echo "   Xvfb=$XVFB_PID  x11vnc=$VNC_PID  chrome=$CHROME_PID"
echo "   5900 리스닝: $(ss -tln 2>/dev/null | grep -c 5900) 개"
echo ""
echo " 1) 맥 터미널에서 (그대로 두세요):"
echo "    ssh -N -L 5900:127.0.0.1:5900 root@115.68.177.72"
echo ""
echo " 2) 맥 Finder → ⌘K → vnc://127.0.0.1:5900"
echo "    비밀번호: $(cat "$PWTXT" 2>/dev/null)"
echo ""
echo " 3) 열린 크롬에서 $PLAT 로그인 (본인확인이 뜨면 그 화면에서 처리)"
echo " 4) 끝나면 여기서 Ctrl+C → 정리 + 워커 재가동"
echo "════════════════════════════════════════════════════════"
while true; do sleep 5; done
