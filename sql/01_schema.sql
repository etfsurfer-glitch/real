-- naverreal: Naver real estate tracker schema for Supabase Postgres.
-- Designed for daily nighttime snapshots from a local Python collector.
-- Strategy: raw historical articles live in a local SQLite/parquet store;
-- Supabase holds (a) current-day listings, (b) daily aggregates, (c) events.
--
-- Apply by pasting into Supabase Studio → SQL Editor, or via psql with the
-- pooler connection string.

-- pg_trgm for fuzzy complex_name search. Must precede any index using gin_trgm_ops.
create extension if not exists pg_trgm;

-- ---------------------------------------------------------------------------
-- regions: 시/도 > 시군구 > 법정동
-- ---------------------------------------------------------------------------
create table if not exists regions (
    cortar_no        text primary key,
    cortar_name      text not null,
    cortar_type      text,               -- city / dvsn / sec
    parent_cortar_no text references regions(cortar_no),
    center_lat       double precision,
    center_lon       double precision,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);
create index if not exists regions_parent_idx on regions(parent_cortar_no);
create index if not exists regions_type_idx   on regions(cortar_type);

-- ---------------------------------------------------------------------------
-- complexes: 단지 마스터
-- ---------------------------------------------------------------------------
create table if not exists complexes (
    complex_no            text primary key,
    complex_name          text not null,
    cortar_no             text references regions(cortar_no),
    real_estate_type      text,            -- APT / OBYG / JGC / ...
    real_estate_type_name text,
    detail_address        text,
    latitude              double precision,
    longitude             double precision,
    total_household_count integer,
    total_building_count  integer,
    high_floor            integer,
    low_floor             integer,
    use_approve_ymd       text,            -- "YYYYMMDD"
    raw                   jsonb,
    first_seen_date       date not null default current_date,
    last_seen_date        date not null default current_date,
    updated_at            timestamptz not null default now()
);
create index if not exists complexes_cortar_idx on complexes(cortar_no);
create index if not exists complexes_name_trgm  on complexes using gin (complex_name gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- listings_current: 가장 최근 스냅샷의 매물 (article_no PK)
-- 매 수집마다 (snapshot_date 갱신 + upsert) 방식. 어제까지 있었는데 오늘 없는
-- 매물은 listing_events에 DELISTED 로 기록한 뒤 이 테이블에서 삭제.
-- ---------------------------------------------------------------------------
create table if not exists listings_current (
    article_no                 text primary key,
    complex_no                 text references complexes(complex_no),
    trade_type                 text not null,     -- A1=매매 B1=전세 B2=월세
    real_estate_type           text,
    article_real_estate_type   text,
    area_name                  text,              -- "34B" 등 평형 변종
    area1_m2                   numeric,           -- 공급면적
    area2_m2                   numeric,           -- 전용면적
    floor_info                 text,              -- "13/19"
    direction                  text,
    deal_or_warrant_price_text text,
    deal_or_warrant_price      bigint,            -- 원 단위 정수
    rent_price                 bigint,            -- 월세 (원/월)
    premium_price              bigint,
    article_confirm_ymd        text,
    realtor_name               text,
    realtor_id                 text,
    cp_name                    text,
    verification_type          text,
    building_name              text,
    tag_list                   text[],
    same_addr_cnt              integer,
    same_addr_min_price        bigint,
    same_addr_max_price        bigint,
    latitude                   double precision,
    longitude                  double precision,
    raw                        jsonb,
    snapshot_date              date not null default current_date,
    updated_at                 timestamptz not null default now()
);
create index if not exists listings_complex_trade_idx on listings_current(complex_no, trade_type);
create index if not exists listings_snapshot_idx      on listings_current(snapshot_date);
create index if not exists listings_area_name_idx     on listings_current(complex_no, area_name);

-- ---------------------------------------------------------------------------
-- complex_daily_agg: 단지 × 평형 × 거래유형 × 날짜
-- 시계열 차트의 핵심 소스. 시계열 영구 보관.
-- ---------------------------------------------------------------------------
create table if not exists complex_daily_agg (
    snapshot_date  date    not null,
    complex_no     text    not null,
    area_name      text    not null,
    trade_type     text    not null,
    listing_count  integer not null,
    price_min      bigint,
    price_max      bigint,
    price_avg      bigint,
    price_median   bigint,
    rent_min       bigint,
    rent_max       bigint,
    rent_median    bigint,
    primary key (snapshot_date, complex_no, area_name, trade_type)
);
create index if not exists complex_agg_complex_date_idx
    on complex_daily_agg(complex_no, snapshot_date);

-- ---------------------------------------------------------------------------
-- region_daily_agg: 지역 × 거래유형 × 날짜
-- ---------------------------------------------------------------------------
create table if not exists region_daily_agg (
    snapshot_date  date    not null,
    cortar_no      text    not null references regions(cortar_no),
    trade_type     text    not null,
    listing_count  integer not null,
    complex_count  integer not null,
    price_median   bigint,
    rent_median    bigint,
    primary key (snapshot_date, cortar_no, trade_type)
);
create index if not exists region_agg_date_idx on region_daily_agg(snapshot_date);

-- ---------------------------------------------------------------------------
-- listing_events: 신규/소멸/가격변경 이벤트 (변화 피드용, 90일 보존)
-- ---------------------------------------------------------------------------
create table if not exists listing_events (
    event_id   bigserial primary key,
    event_date date not null default current_date,
    article_no text not null,
    complex_no text,
    event_type text not null,        -- NEW / DELISTED / PRICE_CHANGE
    trade_type text,
    old_price  bigint,
    new_price  bigint,
    details    jsonb
);
create index if not exists events_date_idx        on listing_events(event_date);
create index if not exists events_complex_idx     on listing_events(complex_no, event_date);
create index if not exists events_article_idx     on listing_events(article_no);

-- ---------------------------------------------------------------------------
-- RLS: anon은 SELECT만, 쓰기는 service_role 전용
-- ---------------------------------------------------------------------------
alter table regions             enable row level security;
alter table complexes           enable row level security;
alter table listings_current    enable row level security;
alter table complex_daily_agg   enable row level security;
alter table region_daily_agg    enable row level security;
alter table listing_events      enable row level security;

do $$
declare t text;
begin
    foreach t in array array[
        'regions','complexes','listings_current',
        'complex_daily_agg','region_daily_agg','listing_events'
    ] loop
        execute format($f$
            drop policy if exists "anon_read" on %I;
            create policy "anon_read" on %I for select to anon using (true);
        $f$, t, t);
    end loop;
end $$;
