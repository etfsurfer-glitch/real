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

# 실행 내내 시스템 절전 차단 (ES_CONTINUOUS|ES_SYSTEM_REQUIRED). 야간 무인 실행
# 중 노트북이 절전에 들어가면 프로세스가 종료돼 캐시 빌드가 중단되던 문제 방지.
# ps1 프로세스가 끝나면 플래그는 자동 해제된다.
try {
    $sig = '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
    $Pwr = Add-Type -MemberDefinition $sig -Name Pwr -Namespace W32 -PassThru
    [void]$Pwr::SetThreadExecutionState(2147483649)  # 0x80000001
} catch { }

function Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    $line | Out-File -FilePath $log -Append -Encoding utf8
    Write-Output $line
}

Log "daily run start"

Log "step 1/6: run_collect.py --all"
& $py -u (Join-Path $root "scripts\run_collect.py") --all 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$collect_exit = $LASTEXITCODE
Log "step 1/6: exit=$collect_exit"

# Single-instance guard: run_collect returns 3 when another collection already
# holds the lock. In that case a concurrent daily_run is already doing today's
# work, so skip the entire rest of the pipeline to avoid double-processing.
if ($collect_exit -eq 3) {
    Log "another collection already running (collect exit=3) - skipping rest of daily_run"
    exit 0
}

# Completeness gate: publish (upload/archive) only on a COMPLETE collect.
# run_collect returns exit 2 when the day's snapshot is partial; in that case
# skip upload+archive so a partial snapshot is never published as a full day.
if ($collect_exit -eq 0) {
    Log "step 2/6: upload_to_supabase.py"
    & $py -u (Join-Path $root "scripts\upload_to_supabase.py") 2>&1 |
        Out-File -FilePath $log -Append -Encoding utf8
    $upload_exit = $LASTEXITCODE
    Log "step 2/6: exit=$upload_exit"

    Log "step 3/6: archive_listings.py (parquet backup)"
    & $py -u (Join-Path $root "scripts\archive_listings.py") 2>&1 |
        Out-File -FilePath $log -Append -Encoding utf8
    $archive_exit = $LASTEXITCODE
    Log "step 3/6: exit=$archive_exit"
} else {
    $upload_exit = -1
    $archive_exit = -1
    Log "step 2-3/6: SKIPPED (collect exit=$collect_exit, incomplete snapshot - not publishing partial day)"
}

Log "step 4/6: backfill_realprice.py --all --months 6 (매매 incremental)"
# 거래 취소 신고가 늦게 처리될 수 있어 최근 6개월 매일 refresh. deal_id 자연키로 dedup.
# 약 1,530 calls (10k 한도의 15%) / ~5분 소요.
& $py -u (Join-Path $root "scripts\backfill_realprice.py") --all --months 6 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$realprice_exit = $LASTEXITCODE
Log "step 4/6: exit=$realprice_exit"

Log "step 5/6: backfill_rentals.py --all --months 6 (아파트 전월세 incremental)"
# 전월세 신고도 30일 이내. rental_id에 deposit/monthly_rent 포함이라 갱신·재계약도 별개 행.
& $py -u (Join-Path $root "scripts\backfill_rentals.py") --all --months 6 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$rentals_exit = $LASTEXITCODE
Log "step 5/6: exit=$rentals_exit"

Log "step 6/6: backfill_offi.py --all --months 6 (오피스텔 매매+전월세 incremental)"
# 오피스텔 두 endpoint(OffiTrade + OffiRent). 시군구×월×2 호출 ≈ 3,060 calls / ~10분.
& $py -u (Join-Path $root "scripts\backfill_offi.py") --all --months 6 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$offi_exit = $LASTEXITCODE
Log "step 6/6: exit=$offi_exit"

Log "step 7/10: refresh_supply_area.py (Naver 매물 area mapping → 실거래 공급면적)"
& $py -u (Join-Path $root "scripts\refresh_supply_area.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$supply_exit = $LASTEXITCODE
Log "step 7/10: exit=$supply_exit"

Log "step 8/10: fetch_complex_detail.py --only-missing (신규 단지 평형 정보)"
& $py -u (Join-Path $root "scripts\fetch_complex_detail.py") --only-missing --parallel 8 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$cdetail_exit = $LASTEXITCODE
Log "step 8/10: exit=$cdetail_exit"

Log "step 9/10: fetch_naver_realtors_direct.py --only-missing (신규 realtor 정보)"
& $py -u (Join-Path $root "scripts\fetch_naver_realtors_direct.py") --only-missing --parallel 8 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$nrealtor_exit = $LASTEXITCODE
Log "step 9/10: exit=$nrealtor_exit"

Log "step 10/11: match_clean.py (realtor 매칭 갱신)"
& $py -u (Join-Path $root "scripts\match_clean.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$match_exit = $LASTEXITCODE
Log "step 10/11: exit=$match_exit"

# step 10b: 중개사 전화 → realtor_id 통합 인덱스(라운지 전화매칭용). naver 연락처 +
# vworld 등록전화(한 필드 여러 번호) 둘 다 인덱싱 → 매칭 풀스캔(143ms) 대신 인덱스(<1ms).
# realtor_match 갱신(step 10) 직후여야 vworld→naver 연결이 반영됨.
Log "step 10b: build_vworld_phone_index.py (전화매칭 인덱스 재빌드)"
& $py -u (Join-Path $root "scripts\build_vworld_phone_index.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
Log "step 10b: exit=$LASTEXITCODE"

# step 11: 실거래 ↔ 단지 재매칭. 매칭 파이프라인 개선(브랜드 prefix, 본번
# fallback, substring 강화) 이후 4 테이블 전부 새 로직으로 재계산.
# 새로 들어온 transactions 도 day-0 매칭 결과가 raw match logic 으로 들어가지만
# 신뢰도 낮게 떨어진 매칭(특히 substr/bonbun)을 매일 한 번 재정리해서 정확도
# 끌어올림. manual_override=1 은 절대 안 건드림. 약 8분 소요.
Log "step 11/12: rematch_all_realprice (실거래 매칭 재계산)"
& $py -u (Join-Path $root "scripts\rematch_all_realprice.py") --tables apt rent offi offi_rent --concurrency 4 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$rematch_exit = $LASTEXITCODE
Log "step 11/12: exit=$rematch_exit"

# step 11.5: 실거래 평형평균 사전집계(tx_avg_rollup) 재빌드 (~1분).
# 재매칭(step 11) 이후·캐시(step 12) 이전이어야 함 — quick_deals 등이 이 테이블로
# 평균을 재구성하므로, 캐시 빌드가 어젯밤 rollup 을 쓰면 하루 어긋난다.
Log "step 11.5: build_tx_rollups.py (실거래 평형평균 일단위 사전집계)"
& $py -u (Join-Path $root "scripts\build_tx_rollups.py") 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$rollup_exit = $LASTEXITCODE
Log "step 11.5: exit=$rollup_exit"

# step 12: 모든 stat 엔드포인트 응답을 cache.sqlite 에 사전 계산.
# local_api.py 가 캐시 미들웨어로 즉시 반환 → 페이지 로딩 5초 → <100ms.
Log "step 12/12: build_api_cache.py --default-only (각 페이지 기본화면 캐시)"
# default-only: 각 페이지·탭 기본 화면 61개만 캐시(~3분). 전체 필터조합(4837개)은
# 이 머신 RAM(여유 1.4GB ≪ DB 9.57GB)에서 디스크 thrash 로 ~5~6h+ 라 야간 시간창을
# 넘겨 오전 내내 캐시 없이 느려짐. 전체조합은 필요 시 수동(--workers 8, RAM 여유 시).
& $py -u (Join-Path $root "scripts\build_api_cache.py") --default-only 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$cache_exit = $LASTEXITCODE
Log "step 12/12: exit=$cache_exit"

# step 12b: 시군구별 급매 캐시 (255 시군구 x 매매/전세 x AI와이드/페이지키 = 1,020개).
# 콜드 디스크에서 시군구당 30~76s 걸리던 유일한 페이지 구멍 + AI find_quick_deals 가
# 이 캐시를 선조회(후필터). 실측 8워커 ~5.5분. --no-wipe 라 default 캐시 위에 덧쌓음.
Log "step 12b: build_api_cache.py --quick-deals-sgg (시군구별 급매 캐시)"
& $py -u (Join-Path $root "scripts\build_api_cache.py") --quick-deals-sgg --no-wipe --workers 8 2>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$sggcache_exit = $LASTEXITCODE
Log "step 12b: exit=$sggcache_exit"

Log "daily run done  collect=$collect_exit  upload=$upload_exit  archive=$archive_exit  realprice=$realprice_exit  rentals=$rentals_exit  offi=$offi_exit  supply=$supply_exit  cdetail=$cdetail_exit  nrealtor=$nrealtor_exit  match=$match_exit  rematch=$rematch_exit  rollup=$rollup_exit  cache=$cache_exit  sggcache=$sggcache_exit"
