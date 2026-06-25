# scripts/monthly_run.ps1
#
# Monthly 작업 — vworld 직원 전체 강제 재크롤. weekly의 --skip-done은 이미 받은 sgg
# 를 skip하므로 직원 변동(퇴사·신규·정지)이 누락됨. 월 1회는 전체 다시.
#
# Register (매월 1일 04:00):
#   schtasks /create /tn "naverreal_monthly" /sc monthly /mo 1 /d 1 /st 04:00 ^
#     /tr "powershell.exe -ExecutionPolicy Bypass -File D:\auto\naverreal\scripts\monthly_run.ps1" /f

$ErrorActionPreference = "Continue"
$root = "D:\auto\naverreal"
$py = Join-Path $root ".venv\Scripts\python.exe"
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$log = Join-Path $root "logs\monthly_$stamp.log"

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

function Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    $line | Out-File -FilePath $log -Append -Encoding utf8
    Write-Output $line
}

Log "monthly run start"

# Step 1: vworld 직원 list 전체 강제 재크롤 (--skip-done 안 함)
# 약 ~30만 직원 × ~1시간
Log "step 1/2: vworld 직원 list 전체 재크롤 (parallel=5)"
& $py -u (Join-Path $root "scripts\crawl_vworld_brokers.py") --employees --parallel 5 --sleep 0 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$vemp_exit = $LASTEXITCODE
Log "step 1/2: exit=$vemp_exit"

# Step 2: 매칭 갱신 (직원 변동 반영)
Log "step 2/2: match_clean.py (매칭 재실행)"
& $py -u (Join-Path $root "scripts\match_clean.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$match_exit = $LASTEXITCODE
Log "step 2/2: exit=$match_exit"

Log "monthly run done  vemp=$vemp_exit  match=$match_exit"
