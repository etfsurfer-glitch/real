# 김미미시티오씨엘공인중개사사무소 — Naver vs vworld 비교

Naver realtor_id: `24mi23810`  ·  vworld sys_regno: `281772020000001`

## [1] listings_current — 김미미 realtor의 매물 1건

| 컬럼 | 값 |
|------|-----|
| `article_no` | 2624806077 |
| `complex_no` | 163618 |
| `trade_type` | B1 |
| `real_estate_type` | ABYG |
| `area_name` | 100B |
| `area1_m2` | 100.0 |
| `area2_m2` | 74.0 |
| `floor_info` | 8/28 |
| `direction` | 남동향 |
| `deal_or_warrant_price_text` | 2억 9,000 |
| `deal_or_warrant_price` | 290000000 |
| `rent_price_text` | _(null)_ |
| `rent_price` | _(null)_ |
| `article_confirm_ymd` | 20260507 |
| `realtor_name` | 김미미시티오씨엘공인중개사사무소 |
| `realtor_id` | 24mi23810 |
| `cp_name` | 매경부동산 |
| `verification_type` | NDOC1 |
| `building_name` | 104동 |
| `tag_list_json` | ["2년이내", "방세개", "화장실두개", "세대당1대"] |
| `same_addr_cnt` | 5 |
| `latitude` | 37.460482 |
| `longitude` | 126.657453 |
| `raw` | _(null)_ |
| `snapshot_date` | 2026-05-18 |
| `same_addr_min_price` | 290000000 |
| `same_addr_max_price` | 290000000 |
| `price_change_state` | SAME |
| `is_price_modification` | 0 |
| `article_status` | R0 |
| `article_feature_desc` | O 김미미 O 에어컨 4대, 쿡탑 O 사전점검 집보고 결정가능 O |
| `cp_pc_article_url` | http://land.mk.co.kr/rd/rd.php?UID=2624806077 |

## [2] complexes — 김미미 매물 단지 (시티오씨엘6단지)

| 컬럼 | 값 |
|------|-----|
| `complex_no` | 173348 |
| `complex_name` | 시티오씨엘6단지 |
| `cortar_no` | 2817710300 |
| `real_estate_type` | ABYG |
| `real_estate_type_name` | 아파트분양권 |
| `detail_address` | 용현.학익1블럭 공동5BL |
| `latitude` | 37.435877 |
| `longitude` | 126.644491 |
| `total_household_count` | 1734 |
| `total_building_count` | 9 |
| `high_floor` | 47 |
| `low_floor` | 33 |
| `use_approve_ymd` | 202804 |
| `raw` | {"complexNo": "173348", "complexName": "시티오씨엘6단지", "cortarNo": "2817710300", "realEstateTypeCode": "ABYG", "realEstateTypeName": "아파트분양권", "detailAddress": "용현.학익1블럭 공동5BL", "latitude": 37.435877, "longitude": 126.644491, "totalHouseholdCount": 1734, "totalBuildingCount": 9, "highFloor": 47, "lowFlo... |
| `first_seen_date` | 2026-05-18 |
| `last_seen_date` | 2026-05-20 |

## [3] vworld_brokers — 김미미 사무소

| 컬럼 | 값 |
|------|-----|
| `sys_regno` | 281772020000001 |
| `ra_regno` | 28177-2020-00001 |
| `sgg_cd` | 28177 |
| `business_name` | 김미미시티오씨엘공인중개사사무소 |
| `address` | 인천광역시 미추홀구 학익로80번길 11 , 362동 5-107호 |
| `representative` | 김미미 |
| `registered_ymd` | 2020.01.02 |
| `status` | 영업 |
| `phone` | 032-863-1166 |
| `classification` | 공인중개사 |
| `detail_fetched_at` | 2026-05-21T16:15:32 |
| `list_fetched_at` | 2026-05-21T14:04:32 |
| `normalized_name` | 김미미시티오씨엘 |
| `dong_name` | _(null)_ |
| `normalized_loose` | 김미미시티오씨엘 |

## [4] vworld_employees — 김미미 사무소 직원 4명

| sys_regno | 성명 | 구분 | 직위 | 상태 |
|-----------|------|------|------|------|
| `281772020000001` | 김윤정 | 공인중개사 | 일반 | 영업 |
| `281772020000001` | 이원희 | 공인중개사 | 일반 | 영업 |
| `281772020000001` | 김미미 | 공인중개사 | 대표 | 영업 |
| `281772020000001` | 김지인 | 공인중개사 | 일반 | 영업 |

## [5] realtor_match — 매칭 row

| 컬럼 | 값 |
|------|-----|
| `realtor_id` | 24mi23810 |
| `naver_name` | 김미미시티오씨엘공인중개사사무소 |
| `primary_sgg_cd` | 28177 |
| `primary_sgg_count` | 1083 |
| `total_listings` | 1083 |
| `sys_regno` | 281772020000001 |
| `vworld_name` | 김미미시티오씨엘공인중개사사무소 |
| `vworld_rep` | 김미미 |
| `match_type` | exact_sgg |
| `candidates_json` | [{"sys_regno": "281772020000001", "name": "김미미시티오씨엘공인중개사사무소", "rep": "김미미"}] |
| `matched_at` | 2026-05-21T22:02:32 |

## 매칭에 사용 가능한 데이터 정리

### Naver 측 (사용 안 한 시그널)

- `realtor_name` = "**김미미**시티오씨엘공인중개사사무소" — 대표자 이름 포함 (vworld.representative와 매칭 가능)
- `article_feature_desc` = "O 김미미 O 에어컨..." — 매물 본문에 대표자/담당자 이름 패턴
- `latitude`, `longitude` — 매물 단지 좌표
- `cp_pc_article_url` — 외부 사이트 (매경부동산 등) URL
- `cp_name` = "매경부동산" — 매물 제공 플랫폼

### vworld 측 (현재 매칭에 사용)

- `business_name` (정규화 후) — exact_sgg / fuzzy_sgg
- `dong_name` (주소에서 추출) — multi 분별
- `phone` — phone_in_name 매칭

### vworld 측 (안 쓰는 강한 키)

- `representative` (대표자명) — multi 분별에 매우 강력
- `address` 전체 — 단지명/번지 추출
- `vworld_employees` — 사무소별 소속 직원 명단

