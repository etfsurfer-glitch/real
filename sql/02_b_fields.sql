-- 02_b_fields.sql
-- Pull select metadata fields out of the raw JSONB into typed columns,
-- then drop the raw column. Cuts per-row storage from ~1.9 KB to ~270 B
-- (~85%), so nationwide listings_current fits Supabase free tier.
-- Idempotent: safe to re-apply.

alter table listings_current add column if not exists price_change_state     text;
alter table listings_current add column if not exists is_price_modification  boolean;
alter table listings_current add column if not exists article_status         text;
alter table listings_current add column if not exists article_feature_desc   text;
alter table listings_current add column if not exists cp_pc_article_url      text;

-- raw 컬럼은 더이상 collector가 채우지 않음.
alter table listings_current drop column if exists raw;

-- 변화추적용: 가격 변동 매물만 빠르게 찾는 partial index.
create index if not exists listings_price_change_idx
    on listings_current(price_change_state)
    where price_change_state in ('INCREASE', 'DECREASE');
