#!/usr/bin/env bash
# 매물점검 12초 광고 — 인트로(점검 시작·검사중, 빠르게) + 위반 도장 시퀀스(실시간, 강조) + 콕집 아웃트로.
# 컷 지점(ssA/tA=인트로, ssB/tB=도장시퀀스)은 녹화 마크(A0/A1끝, B0/B1)에서 넘긴다.
set -e
SP="${SP:-$(pwd)}"; AD=/Users/hcode/auto/naverreal/design/ad; MUS=$AD/Velocity_Peak.mp3
V=$(ls "$SP"/vida/*.webm); VM=$(ls "$SP"/vida_m/*.webm)
build(){
  local IN=$1 W=$2 H=$3 OUTRO=$4 F=$5 SSA=$6 TA=$7 SSB=$8 TB=$9
  ffmpeg -v error -y \
    -ss $SSA -t $TA -i "$IN" -ss $SSB -t $TB -i "$IN" \
    -loop 1 -framerate 30 -t 3.2 -i "$SP/$OUTRO" -ss 0 -t 12.4 -i "$MUS" \
    -filter_complex "\
[0:v]setpts=PTS*0.72,fps=30,scale=$W:$H,format=yuv420p,fade=t=in:st=0:d=0.15[a];\
[1:v]fps=30,scale=$W:$H,format=yuv420p[b];\
[2:v]fps=30,scale=$W:$H,format=yuv420p,fade=t=in:st=0:d=0.25[c];\
[a][b][c]concat=n=3:v=1:a=0[out];\
[3:a]volume=0.3,afade=t=in:st=0:d=0.4,afade=t=out:st=11.0:d=1.0[aud]" \
    -map "[out]" -map "[aud]" -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart -t 12.0 "$F"
}
# 인자: ssA tA(인트로 A0~검사중) / ssB tB(도장 B0~B1). 아래 값은 record 콘솔 마크로 채움.
build "$V"  1280 720 audit_outro.png   "$AD/audit_12s_landscape.mp4" $LA
build "$VM" 720 1280 audit_outro_m.png "$AD/audit_12s_portrait.mp4"  $LM
echo "built audit_12s_{landscape,portrait}.mp4"
