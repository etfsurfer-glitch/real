# scripts/weekly_run.ps1
#
# Weekly 작업 — vworld 사무소·직원 / 정지·휴업 lookup / 리포트 갱신.
# daily_run보다 변동이 적은 데이터 갱신 + 정기 보고서.
#
# Register (매주 일요일 03:00):
#   schtasks /create /tn "naverreal_weekly" /sc weekly /d SUN /st 03:00 ^
#     /tr "powershell.exe -ExecutionPolicy Bypass -File D:\auto\naverreal\scripts\weekly_run.ps1" /f

$ErrorActionPreference = "Continue"
$root = "D:\auto\naverreal"
$py = Join-Path $root ".venv\Scripts\python.exe"
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$log = Join-Path $root "logs\weekly_$stamp.log"

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

function Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    $line | Out-File -FilePath $log -Append -Encoding utf8
    Write-Output $line
}

Log "weekly run start"

# Step 1: vworld 사무소 list 갱신 (신규 사무소 / 폐업·이전 반영)
# --skip-done 모드: crawl_log상 완료 안 된 시군구만. 신규 sgg나 verify 후 reset된 곳.
# 전체 강제 재크롤은 분기/년에 별도 실행.
Log "step 1/5: vworld broker list (verify + 누락 보강)"
& $py -u (Join-Path $root "scripts\verify_vworld_coverage.py") --threshold 5 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$vlist_exit = $LASTEXITCODE
Log "step 1/5: exit=$vlist_exit"

# Step 2: 신규 사무소 phone detail (NULL phone만)
Log "step 2/5: vworld broker detail (NULL phone 채우기, parallel=5)"
& $py -u (Join-Path $root "scripts\crawl_vworld_brokers.py") --detail --parallel 5 --sleep 0 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$vdetail_exit = $LASTEXITCODE
Log "step 2/5: exit=$vdetail_exit"

# Step 3: 정지/휴업 사무소 lookup (Naver 광고 중 vworld 영업 안 됨)
Log "step 3/5: find_suspended_brokers (Naver 광고 ↔ vworld 정지·휴업 lookup)"
& $py -u (Join-Path $root "scripts\find_suspended_brokers.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$susp_exit = $LASTEXITCODE
Log "step 3/5: exit=$susp_exit"

# Step 4: vworld 직원 list 갱신 (parallel=5, --skip-done — 이미 받은 sgg는 skip)
# 직원 변동은 비교적 느림. 월간이어도 OK지만 weekly로.
Log "step 4/5: vworld 직원 list (--skip-done)"
& $py -u (Join-Path $root "scripts\crawl_vworld_brokers.py") --employees --skip-done --parallel 5 --sleep 0 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$vemp_exit = $LASTEXITCODE
Log "step 4/5: exit=$vemp_exit"

# Step 5: 리포트 갱신 (HTML DB report + unmatched review)
Log "step 5/5: 리포트 갱신 (db_report.html + unmatched_review.md)"
& $py -u (Join-Path $root "scripts\generate_report.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
& $py -u (Join-Path $root "scripts\export_unmatched_review.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$report_exit = $LASTEXITCODE
Log "step 5/5: exit=$report_exit"

Log "weekly run done  vlist=$vlist_exit  vdetail=$vdetail_exit  susp=$susp_exit  vemp=$vemp_exit  report=$report_exit"
