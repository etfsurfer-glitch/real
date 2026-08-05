#!/usr/bin/env bash
# 콕집요청 15초 광고 — 조건입력(A) + 받는곳(B) + 제안도착(C) + 아웃트로.
# 컷 지점은 record_request.mjs 콘솔 마크(A0/A1/B0/C0/C1)에서 넘긴다.
#   L="ssA tA ssB tB ssC tC"  (가로)   M="..." (세로)
set -e
SP="${SP:?SP 필요}"; AD=/Users/hcode/auto/naverreal/design/ad; MUS=$AD/Velocity_Peak.mp3
V=$(ls "$SP"/vreq/*.webm | head -1); VM=$(ls "$SP"/vreq_m/*.webm | head -1)

build(){
  local IN=$1 W=$2 H=$3 OUTRO=$4 F=$5 SSA=$6 TA=$7 SSB=$8 TB=$9 SSC=${10} TC=${11}
  # 음악은 30초 트랙의 잔잔한 앞부분만 쓴다(웅장한 후반부 회피) + 볼륨 낮게
  ffmpeg -v error -y \
    -ss "$SSA" -t "$TA" -i "$IN" -ss "$SSB" -t "$TB" -i "$IN" -ss "$SSC" -t "$TC" -i "$IN" \
    -loop 1 -framerate 30 -t 3.6 -i "$SP/$OUTRO" -ss 0.5 -t 15.4 -i "$MUS" \
    -filter_complex "\
[0:v]fps=30,scale=$W:$H,format=yuv420p,fade=t=in:st=0:d=0.35[a];\
[1:v]fps=30,scale=$W:$H,format=yuv420p[b];\
[2:v]fps=30,scale=$W:$H,format=yuv420p[c];\
[3:v]fps=30,scale=$W:$H,format=yuv420p,fade=t=in:st=0:d=0.35,fade=t=out:st=3.0:d=0.55[d];\
[a][b][c][d]concat=n=4:v=1:a=0[out];\
[4:a]volume=0.22,afade=t=in:st=0:d=0.6,afade=t=out:st=13.6:d=1.4[aud]" \
    -map "[out]" -map "[aud]" -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
    -c:a aac -b:a 128k -movflags +faststart -t 15.0 "$F"
}

# 컷이 원본 길이를 넘으면 ffmpeg 이 조용히 짧게 만든다 — 먼저 걸러낸다(실제로 당했다)
check(){
  local IN=$1; shift
  local DUR; DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$IN")
  set -- $@
  while [ $# -ge 2 ]; do
    awk -v e="$(echo "$1 + $2" | bc)" -v d="$DUR" -v s="$1" -v t="$2" \
      'BEGIN{if(e>d+0.05){printf "컷이 원본을 넘습니다: ss=%s t=%s → %.1fs (원본 %.1fs)\n",s,t,e,d; exit 1}}' || exit 1
    shift 2
  done
}
check "$V" $L
check "$VM" $M
build "$V"  1280 720 req_outro.png   "$AD/request_15s_landscape.mp4" $L
build "$VM" 720 1280 req_outro_m.png "$AD/request_15s_portrait.mp4"  $M
echo "built request_15s_{landscape,portrait}.mp4"
