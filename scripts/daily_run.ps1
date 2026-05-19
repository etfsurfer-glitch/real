# scripts/daily_run.ps1
#
# Daily nationwide snapshot. Designed to run unattended via Windows Task
# Scheduler at, e.g., 02:00. Stages:
#   1. python -u run_collect.py --all   (collect into local SQLite, resumable)
#   2. python -u upload_to_supabase.py  (push current snapshot to Supabase)
#
# Each invocation writes a timestamped log under logs/. Exit codes from both
# stages are captured at the tail. Errors don't abort the script — both stages
# always attempt to run, so a partial collect still uploads what we have.
#
# Register once with schtasks (no admin needed for user-scope tasks):
#
#   schtasks /create /tn "naverreal_daily" /sc daily /st 02:00 ^
#     /tr "powershell.exe -ExecutionPolicy Bypass -File D:\auto\naverreal\scripts\daily_run.ps1" /f

$ErrorActionPreference = "Continue"
$root = "D:\auto\naverreal"
$py = Join-Path $root ".venv\Scripts\python.exe"
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$log = Join-Path $root "logs\daily_$stamp.log"

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

function Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    $line | Out-File -FilePath $log -Append -Encoding utf8
    Write-Output $line
}

Log "daily run start"

Log "step 1/2: run_collect.py --all"
& $py -u (Join-Path $root "scripts\run_collect.py") --all 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$collect_exit = $LASTEXITCODE
Log "step 1/2: exit=$collect_exit"

Log "step 2/3: upload_to_supabase.py"
& $py -u (Join-Path $root "scripts\upload_to_supabase.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$upload_exit = $LASTEXITCODE
Log "step 2/3: exit=$upload_exit"

Log "step 3/4: archive_listings.py (parquet 백업)"
& $py -u (Join-Path $root "scripts\archive_listings.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$archive_exit = $LASTEXITCODE
Log "step 3/4: exit=$archive_exit"

Log "step 4/4: backfill_realprice.py --all --months 6 (실거래 incremental)"
# 거래 취소 신고가 늦게 처리될 수 있어 최근 6개월 매일 refresh. deal_id 자연키로 dedup.
# 약 1,530 calls (10k 한도의 15%) / ~5분 소요.
& $py -u (Join-Path $root "scripts\backfill_realprice.py") --all --months 6 --apply 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$realprice_exit = $LASTEXITCODE
Log "step 4/4: exit=$realprice_exit"

Log "daily run done  collect=$collect_exit  upload=$upload_exit  archive=$archive_exit  realprice=$realprice_exit"
