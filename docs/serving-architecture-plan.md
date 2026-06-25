# 콕집 서빙 아키텍처 계획 — "무조건 3초" (노트북 창고 → iwinv 서빙)

작성: 2026-06-14. 6배 데이터 재수집(전 기간 37개월) 이후 콜드 성능 전수 실측 기반.

## 0. 목표
모든 사이트 엔드포인트가 **콜드 상태에서도 무조건 3초 이내** 로딩.

## 1. 아키텍처
- **노트북 (데이터 창고)**: 전체 DB(현재 17.2GB, 계속 증가)·매일 수집·롤업·캐시·서빙DB 빌드. 사용자 트래픽 안 받음.
- **iwinv (서빙 서버)**: 노트북이 만든 **슬림 서빙DB + api_cache**만 매일 전송받아 프론트에 서빙. 데이터가 RAM에 올라가 전부 워밍 → <3초.

## 2. 성능 진단 결과 (콜드 vs 웜, 2026-06-14 실측)
원인: 17GB DB가 RAM보다 커서 OS 페이지캐시가 불안정 → 워밍이던 것도 다시 콜드가 됨.

| 부류 | 예시 | 콜드 | 웜 | 처방 |
|---|---|---|---|---|
| A. 웜도 느림(≥3s) | tx-low-price 23s, listing-trend 25s, tx-asking-vs-real 15s, quick-deals전국 2~67s | 느림 | 느림 | **캐시 or 롤업전환** |
| B. 콜드만 느림 | tx-gap/yield/평당가/record-high/cancelled-summary/region-compare/tx-region-pulse 등 | 6~25s | 0.5~2s | **롤업 RAM 상주로 해결** |
| C. 항상 <3s | 단지상세·중개사·검색·취소거래·신고가 등 ~20개 | <1.4s | - | 조치 불필요 |

### 발견·수정한 버그
- **recent-tx**: SQLite가 rentals에서 `monthly_rent` 인덱스 오선택 → 월세 100만행 풀스캔(128s). `+monthly_rent` 관용구로 deal_ymd 인덱스 강제 → 0.93s. **수정 완료.**
- **freshness**: 전체 재수집으로 270만 rentals가 같은 날 inserted → "오늘 신규" 150만건 오집계 + 15s. 정상 daily 1회 후 자동 정상화(평소 ~3,400건/일). raw무관, 일시적.

## 3. 서빙 DB 구성 (raw 3GB·불필요 인덱스 제외 → 서버엔 ~5.5GB만)
| 구성 | 용량 |
|---|---|
| 롤업 3종 (tx_avg_rollup·tx_area_rollup·tx_record_rollup, 8.6M행) | ~2.0 GB |
| transactions/rentals (raw 제외; 단지 실거래이력·취소·지역집계용) | ~2.5 GB |
| listings_current (핵심컬럼) | ~0.5 GB |
| complex_daily_agg | ~0.3 GB |
| 룩업 complexes/regions/complex_areas | ~0.1 GB |
| api_cache (전국/시도 무거운 ~150개) | ~30 MB |
| **합계** | **~5.5 GB** |

※ raw 컬럼 합계 측정치: rentals 1.69 + transactions 0.96 + offi_rentals 0.28 + offi_tx 0.04 = **2.97GB** (listings는 raw 없음). raw·불필요 인덱스 제외가 슬림화 핵심.

## 4. 캐시 전략 (전수 캐시 ❌ → 표적 캐시 ✅)
구버전: 3,682 타깃(per-시군구 포함) 전수 캐시 → 콜드 I/O로 빌드 7시간. **폐기.**

신버전 3메커니즘:
1. **롤업 RAM 상주** — `_open_db`에 `PRAGMA mmap_size≈3GB` + 기동/주기(10분) 워머 쿼리로 롤업 3종 고정 → B군 항상 <3s.
2. **비롤업 무거운 A군만 캐시** — tx-low-price·listing-trend·tx-asking-vs-real·quick-deals(전국/시도)·freshness 등 **전국/시도 조합만 ~150개**.
3. **per-시군구/per-단지 캐시 제거** — 스코프 작아 <3s. (이게 7시간 빌드의 원인)

추가 옵션: A군 중 tx-asking-vs-real·region-compare·tx-region-pulse는 tx_area_rollup으로 전환하면 캐시 없이도 빠름(더 깔끔, 작업량↑).

## 5. 리소스 산정
### 소요시간
- **구현 1회: ~1~1.5일** (서빙DB 빌더 3h, mmap+워머+캐시슬림 4h, iwinv 셋업·전송 파이프라인 3h, 검증 2h)
- **매일 야간 배치: ~30분** (수집 + 롤업 7분 + 서빙DB 5분 + 캐시 10분 + 증분전송 수분)
- 초기 서빙DB 업로드 1회: 5.5GB (회선따라 10~60분)

### 디스크
- 노트북: 17GB + 매일 증가 (창고)
- **iwinv: ~10GB VPS면 충분** (서빙DB 5.5GB + 프론트 + 여유)

### RAM (iwinv)
- 핫 워킹셋(롤업+인덱스) ~2~3GB 상주
- **권장 8GB** (서빙DB 5.5GB 통째 RAM 상주 → 전부 <3s). 4GB 가능하나 빠듯.

### 전송량 (iwinv 트래픽 과금)
- 초기 1회 ~5.5GB
- 매일 증분(롤업 + 신규 listings + 최근 거래) ~수백MB/일 → 부담 적음

## 6. 진행 순서 (확정 시)
1. 서빙DB 빌더(노트북: raw 제외 + 필요컬럼 추출 → serving.sqlite 생성)
2. `_open_db` mmap_size + 기동/주기 워머
3. build_api_cache 슬림화(전국/시도 ~150개, per-시군구 제거)
4. (옵션) A군 일부 롤업전환
5. 전수 콜드 <3s 검증
6. iwinv 셋업 + 전송 파이프라인(증분 rsync/scp)

## 참고 (현재 상태)
- 롤업 7종 엔드포인트 전환 완료(tx-gap/jeonse-rate/price-change/평당가/회전율/수익률/신고가) — 콜드 0.1~1s, 라이브 정확성 검증 완료.
- tx_area_rollup(4.59M, area_key 기준) + tx_record_rollup(202K, 신고가) 신설, build_tx_rollups에 통합(야간 자동).
- 캐시는 현재 비워둔 상태(라이브 폴백). 위 신버전 캐시전략 적용 전.
