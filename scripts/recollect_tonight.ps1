# Full real-estate re-collection nightly batch.
# Runs after KST midnight (local 23:00) when data.go.kr daily quota resets.
# Per-API daily limit (10k) is separate per service, so apt-trade / offi-trade /
# offi-rent / apt-rent can each run a full 37-month backfill in one night.
# storage.py occurrence-index splits same-amount double-report twins into rows.
# NOTE: ASCII-only on purpose (Windows PowerShell 5.1 reads .ps1 as CP949;
#       non-ASCII breaks parsing).
$ErrorActionPreference = 'Continue'
$root = 'D:\auto\naverreal'
Set-Location $root
$py  = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root ("data\recollect_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmm'))

function Step([string]$desc, [string[]]$cmd) {
    ("===== {0}  {1} =====" -f $desc, (Get-Date -Format 'HH:mm:ss')) | Tee-Object -FilePath $log -Append
    & $py @cmd 2>&1 | Tee-Object -FilePath $log -Append
    ("----- exit={0}  {1} -----" -f $LASTEXITCODE, (Get-Date -Format 'HH:mm:ss')) | Tee-Object -FilePath $log -Append
}

("### recollect start {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) | Tee-Object -FilePath $log -Append

# 1) apt sale (transactions) - 30,898 cancelled, price-pollution core. full 37 months.
Step 'apt-sale 37mo'   @('scripts\backfill_realprice.py','--all','--months','37')
# 2) officetel sale + rent (offi-trade / offi-rent). full 37 months (was only 7).
Step 'offi 37mo'       @('scripts\backfill_offi.py','--all','--months','37')
# 3) apt rent (rentals). full 37 months (was only 7).
Step 'apt-rent 37mo'   @('scripts\backfill_rentals.py','--all','--months','37')
# 4) rebuild pyeong-average rollups (all kinds, cancelled excluded)
Step 'rollups'         @('scripts\build_tx_rollups.py')
# 5) rebuild prebuilt API cache
Step 'api-cache'       @('scripts\build_api_cache.py')
# 6) rollup==live full verification (writes report)
Step 'verify'          @('scripts\verify_tx_rollup.py')

# 7) re-enable the regular nightly task that was disabled for tonight only.
("===== re-enable naverreal_daily  {0} =====" -f (Get-Date -Format 'HH:mm:ss')) | Tee-Object -FilePath $log -Append
schtasks /change /tn "naverreal_daily" /enable 2>&1 | Tee-Object -FilePath $log -Append

("### recollect done {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) | Tee-Object -FilePath $log -Append
