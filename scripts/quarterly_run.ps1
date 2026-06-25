# scripts/quarterly_run.ps1
#
# Quarterly 작업 — 변동이 느린 master 데이터를 전체 강제 재실행.
# daily/weekly의 --only-missing/--skip-done 모드로 누락되는 갱신을 잡음.
#
# 작업:
#   - complexes detail 전체 (관리실 전화/건설사/용적률 등 변경 반영)
#   - naver_realtors 전체 (rep/주소/매물수 등 갱신)
#   - vworld 사무소 list 전체 (이름·주소·대표자 변경 반영)
#   - vworld 사무소 detail 전체 (phone 변경 반영)
#   - regions 트리 (행정개편 신규 동/구)
#
# 약 8-12시간 소요. 야간 또는 주말에 수동 실행 권장.
#
# Register (매분기 1일 02:00 — 1/4/7/10월):
#   schtasks /create /tn "naverreal_quarterly" /sc monthly /mo 3 /d 1 /st 02:00 ^
#     /tr "powershell.exe -ExecutionPolicy Bypass -File D:\auto\naverreal\scripts\quarterly_run.ps1" /f

$ErrorActionPreference = "Continue"
$root = "D:\auto\naverreal"
$py = Join-Path $root ".venv\Scripts\python.exe"
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$log = Join-Path $root "logs\quarterly_$stamp.log"

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

function Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    $line | Out-File -FilePath $log -Append -Encoding utf8
    Write-Output $line
}

Log "quarterly run start"

# Step 1: regions 행정구역 트리 (신규 동/구 행정개편 반영) — 시도 17개 × 재귀
# build_region_tree.py가 있다면. 없으면 skip.
Log "step 1/6: regions 트리 갱신 (있을 때만)"
$rgScript = Join-Path $root "scripts\build_region_tree.py"
if (Test-Path $rgScript) {
    & $py -u $rgScript 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
    $rg_exit = $LASTEXITCODE
} else {
    $rg_exit = 0
    Log "  build_region_tree.py 없음 — skip"
}
Log "step 1/6: exit=$rg_exit"

# Step 2: complexes detail 전체 강제 (--only-missing 빼기)
# 64k 단지 × parallel 8 → ~1.5시간
Log "step 2/6: complexes detail 전체 재크롤 (모든 단지)"
& $py -u (Join-Path $root "scripts\fetch_complex_detail.py") --parallel 8 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$cdetail_exit = $LASTEXITCODE
Log "step 2/6: exit=$cdetail_exit"

# Step 3: naver_realtors 전체 재크롤 (rep/주소/매물수 갱신)
# 52k realtor × parallel 8 → ~1시간
Log "step 3/6: naver_realtors 전체 재크롤"
& $py -u (Join-Path $root "scripts\fetch_naver_realtors_direct.py") --parallel 8 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$nrealtor_exit = $LASTEXITCODE
Log "step 3/6: exit=$nrealtor_exit"

# Step 4: vworld 사무소 list 전체 (사무소 이름·주소·대표자 변경 반영)
# 255 시군구 × parallel 3 → ~30분
Log "step 4/6: vworld 사무소 list 전체 재크롤"
& $py -u (Join-Path $root "scripts\crawl_vworld_brokers.py") --list --parallel 3 --page-size 50 --sleep 0.4 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$vlist_exit = $LASTEXITCODE
Log "step 4/6: exit=$vlist_exit"

# Step 5: vworld 사무소 detail 전체 (phone 갱신, NULL 아닌 것도 다시)
# 약 100k 사무소 × parallel 5 → ~6시간
# 주의: 매우 오래 걸림. 부담되면 skip 또는 별도 실행.
Log "step 5/6: vworld 사무소 detail 전체 (phone 등 갱신)"
# detail은 NULL phone만 채우는 게 default. 전체 강제 갱신은 별도 작업 — 일단 skip.
# 필요 시 직접 실행: scripts/crawl_vworld_brokers.py --detail (모든 sys_regno 대상으로)
Log "  (전체 detail 강제 갱신은 별도 수동 실행 권장)"
$vdetail_exit = 0
Log "step 5/6: exit=$vdetail_exit"

# Step 6: supply_area + 매칭 갱신
Log "step 6/6: refresh_supply_area + match_clean"
& $py -u (Join-Path $root "scripts\refresh_supply_area.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
& $py -u (Join-Path $root "scripts\match_clean.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$final_exit = $LASTEXITCODE
Log "step 6/6: exit=$final_exit"

Log "quarterly run done  rg=$rg_exit  cdetail=$cdetail_exit  nrealtor=$nrealtor_exit  vlist=$vlist_exit  vdetail=$vdetail_exit  final=$final_exit"
