#!/bin/bash
# 지도 시험판 배포 — koczip 저장소의 testv2 브랜치로만 push(운영 main 무관).
# CF Pages 프로젝트 koczip-testv2(운영 브랜치=testv2)가 받아 https://testv2.koczip.com 에 올림
set -e
cd "$(dirname "$0")/.."
npx tsc --noEmit -p testv2/tsconfig.json
npx vite build -c vite.testv2.config.ts
D=~/auto/koczip_testv2
git -C "$D" rm -rq --ignore-unmatch assets
cp -r dist-testv2/. "$D"/
git -C "$D" add -A
git -C "$D" commit -qm "testv2 갱신 $(date +%F_%H%M)" || { echo "변경 없음"; exit 0; }
git -C "$D" push -q origin testv2
echo "배포 요청 완료 — 1~2분 뒤 https://testv2.koczip.com"
