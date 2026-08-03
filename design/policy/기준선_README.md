# 2026 세제개편안 발표 직전 기준선 (2026-08-03)

## 왜 이 폴더가 있나

2026-08-03(월) **18:00 KST** 기획재정부가 「2026년 세제개편안」을 발표했다.
부동산 관련 내용이 커서(장특공제 거주 전환, 종부세 강화, 다주택 중과 한시 완화,
일시적 2주택 특례기간 단축) 발표 전후 매물·거래 흐름을 비교할 필요가 생겼다.

문제는 **콕집의 매물 데이터가 매일 덮어써진다**는 점이다.

| 데이터 | 보존 방식 | 발표 전 상태가 남나 |
|---|---|---|
| `listings_current` (단지형) | 매일 전량 교체 | 일별 parquet 아카이브에만 |
| 비단지 10종 `listings` | **3일치만** 롤링 | 일별 parquet 아카이브에만 |
| `special_deals` (급매 플래그) | 매일 재계산 | 아니오 |
| `transactions` 등 실거래 | 누적 | 예(단, *신고 시점* 상태는 남지 않음) |
| `article_events` | 누적(2026-05-19~) | 예 |

일별 parquet 아카이브는 로컬 30일 회수 후 오프박스로 넘어간다. 8/3은 그 순환에서
빼내 **영구 보관**해야 하는 날이다. 그래서 이 폴더를 만들었다.

`/mnt/backup/20*/`만 회전 삭제되므로 `policy_2026_tax_reform/` 이름은 안전하다.

## 무엇이 들었나

```
2026-08-03_pre/
├── parquet/                     ← 매물 원본. 이것이 정본이다.
│   ├── listings_2026-08-03.parquet     단지형 174.9만 건 (raw JSON 포함, 02:24 확정분)
│   └── {10종}_2026-08-03.parquet       비단지 178.7만 건 (13:54 수집분)
│        villa oneroom house sangga office knowledge redev building factory land
├── baseline.sqlite              ← SQL로 바로 비교할 것들
│   ├── transactions/rentals/silv/rh/offi/sh/nrg   2025-01-01 이후 (발표 시점 신고 상태)
│   ├── special_deals            급매·주인·세입자 플래그 (매일 재계산되므로 여기만 남는다)
│   ├── complexes / complex_areas 단지 마스터
│   ├── article_events           2026-08-01~08-03 원본
│   ├── article_events_daily     2026-05-19~08-03 일자×유형 집계
│   └── listings_summary         시군구×유형×거래 매물 집계(빠른 비교용)
└── MANIFEST.txt                 행수 + parquet sha256
```

두 매물 스냅샷 모두 **발표(18:00) 이전** 상태다. 이 점은 그냥 되는 게 아니라 확인이
필요했다 — 아래 참고.

## ⚠ 수집 시각 때문에 조심할 것

`collection_log` 를 보면 **8/3 단지형 수집은 12:06~20:36에 돌았다.** 즉 발표(18:00)
이후까지 이어졌고, 그 결과가 `listings_current` 에 계속 반영됐다.

| 무엇 | 시각 | 발표 전인가 |
|---|---|---|
| `parquet/listings_2026-08-03.parquet` | 02:24 확정 (174.9만) | **예** ← 기준선 |
| 라이브 `listings_current` (20:28) | 오늘 수집 반영 중 (180.4만) | 아니오(혼재) |

그래서 `baseline.sqlite` 의 `listings_summary` 는 **parquet 에서 다시 계산**해 넣었다
(처음엔 `listings_current` 로 만들었다가 3.6% 어긋나는 것을 보고 잡았다).
**단지형 매물의 발표 전 기준은 언제나 parquet 이다.**

내일(8/4) 새벽 아카이브가 담을 `listings_2026-08-04.parquet` 은 *발표 당일 수집분*
(12:06~20:36, 전후 혼재)이다. 발표 직후 반응을 볼 첫 데이터라 그것도 보관한다.

## 실거래는 왜 "신고 시점"이 중요한가

부동산 거래는 계약 후 **30일 이내 신고**다. 그래서 오늘 DB에 있는 8월 계약분은
아직 극히 일부다. 나중에 같은 쿼리를 다시 돌려 이 기준선과 비교하면
**"발표 전까지 신고된 것" vs "발표 후 추가로 신고된 것"** 을 가를 수 있다.

특히 **일시적 2주택 경과조치가 '26.8.3. 이전 계약** 기준이라, `deal_ymd = 2026-08-03`
전후의 계약 건수 변화가 정책 효과를 직접 보여준다. 이 판단은 9월 초는 되어야
가능하므로 기준선 없이는 영영 못 한다.

## 앞으로

`scripts/policy_keep_daily.sh` 가 매일 23:40에 두 가지를 한다.

1. 그날의 매물 parquet 11개를 `daily/YYYY-MM-DD/` 로 빼돌린다 — 로컬 아카이브는
   30일 뒤 회수되므로, 몇 달 걸릴 정책 효과를 보려면 여기 남겨야 한다.
   (하루 ~120MB. `policy_2026_tax_reform` 폴더가 15GB에 닿으면 자동 중단하고 알린다.)
2. `scripts/policy_watch.py` 로 기준선 대비 관측 리포트를 `watch/YYYY-MM-DD.md` 에 쓴다.

## 쓰는 법

```bash
sqlite3 baseline.sqlite "SELECT * FROM listings_summary WHERE sgg LIKE '11%';"

python3 -c "
import pyarrow.parquet as pq
t = pq.read_table('parquet/listings_2026-08-03.parquet')
print(t.num_rows, t.schema.names)
"
```

정책 요약은 `design/policy/2026_세제개편안_부동산.md`(레포)에 있다.
검증할 가설 H1~H9도 거기 5절에 정리돼 있다.

## 주의

- 개정 **안**이다. 국회 통과 전이라 확정이 아니다.
- 발표 직후 실거래로 "거래가 줄었다"고 말하면 안 된다(30일 신고제). 초기 관측은
  **매물(호가)** 로만 한다.
- 이 폴더를 만들면서 본서버 `/` 디스크가 한때 100%가 됐다. 원인은 27GB 본DB에 건
  장시간 읽기 트랜잭션이 WAL 체크포인트를 막은 것. 이후 스크립트는 테이블마다
  커넥션을 새로 연다(`scripts/policy_baseline_snapshot.py`). 같은 작업을 반복할 때
  주의할 것.
