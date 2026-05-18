-- 03_articles_history.sql
-- Accumulating article master + change events.
--   articles        : one row per article_no, with first_seen_date / last_seen_date
--                     and is_active flag. Static fields preserved across snapshots.
--   article_events  : append-only log of NEW / PRICE_CHANGE / DELISTED / RELISTED.
-- listings_current stays for now (backward compat with uploader/frontend);
-- a later migration will replace it with a view over articles.
-- Idempotent: safe to re-apply.

create table if not exists articles (
    article_no                 text primary key,
    complex_no                 text,
    trade_type                 text not null,
    real_estate_type           text,
    area_name                  text,
    area1_m2                   numeric,
    area2_m2                   numeric,
    floor_info                 text,
    direction                  text,
    building_name              text,
    realtor_name               text,
    realtor_id                 text,
    cp_name                    text,
    cp_pc_article_url          text,
    verification_type          text,
    latitude                   double precision,
    longitude                  double precision,
    tag_list                   text[],
    same_addr_cnt              integer,
    same_addr_min_price        bigint,
    same_addr_max_price        bigint,
    -- mutable fields (latest snapshot value)
    deal_or_warrant_price      bigint,
    deal_or_warrant_price_text text,
    rent_price                 bigint,
    rent_price_text            text,
    price_change_state         text,
    is_price_modification      boolean,
    article_status             text,
    article_feature_desc       text,
    article_confirm_ymd        text,
    -- lifecycle
    first_seen_date            date not null default current_date,
    last_seen_date             date not null default current_date,
    is_active                  boolean not null default true,
    updated_at                 timestamptz not null default now()
);
create index if not exists articles_complex_trade_idx on articles(complex_no, trade_type);
create index if not exists articles_active_idx        on articles(is_active);
create index if not exists articles_last_seen_idx     on articles(last_seen_date);
create index if not exists articles_price_change_idx  on articles(price_change_state)
    where price_change_state in ('INCREASE', 'DECREASE');

create table if not exists article_events (
    event_id   bigserial primary key,
    event_date date    not null default current_date,
    article_no text    not null,
    complex_no text,
    trade_type text,
    event_type text    not null,    -- NEW / RELISTED / PRICE_CHANGE / DELISTED
    old_price  bigint,
    new_price  bigint,
    old_rent   bigint,
    new_rent   bigint,
    details    jsonb
);
create index if not exists article_events_date_idx         on article_events(event_date);
create index if not exists article_events_complex_date_idx on article_events(complex_no, event_date);
create index if not exists article_events_article_idx      on article_events(article_no);
create index if not exists article_events_type_date_idx    on article_events(event_type, event_date);

-- One-shot backfill from listings_current → articles. Only seeds rows that
-- don't exist yet, so safe to re-run. first_seen_date and last_seen_date
-- both set to the snapshot we have on hand.
insert into articles(
    article_no, complex_no, trade_type, real_estate_type,
    area_name, area1_m2, area2_m2, floor_info, direction, building_name,
    realtor_name, realtor_id, cp_name, cp_pc_article_url, verification_type,
    latitude, longitude, tag_list, same_addr_cnt,
    same_addr_min_price, same_addr_max_price,
    deal_or_warrant_price, deal_or_warrant_price_text,
    rent_price,
    price_change_state, is_price_modification, article_status, article_feature_desc,
    article_confirm_ymd, first_seen_date, last_seen_date, is_active
)
select
    l.article_no, l.complex_no, l.trade_type, l.real_estate_type,
    l.area_name, l.area1_m2, l.area2_m2, l.floor_info, l.direction, l.building_name,
    l.realtor_name, l.realtor_id, l.cp_name, l.cp_pc_article_url, l.verification_type,
    l.latitude, l.longitude, l.tag_list, l.same_addr_cnt,
    l.same_addr_min_price, l.same_addr_max_price,
    l.deal_or_warrant_price, l.deal_or_warrant_price_text,
    l.rent_price,
    l.price_change_state, l.is_price_modification, l.article_status, l.article_feature_desc,
    l.article_confirm_ymd, l.snapshot_date, l.snapshot_date, true
from listings_current l
on conflict (article_no) do nothing;

-- RLS (anon read)
alter table articles       enable row level security;
alter table article_events enable row level security;
drop policy if exists "anon_read" on articles;
create policy "anon_read" on articles       for select to anon using (true);
drop policy if exists "anon_read" on article_events;
create policy "anon_read" on article_events for select to anon using (true);
