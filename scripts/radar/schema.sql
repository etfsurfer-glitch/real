-- ══════════════════════════════════════════════════════════════════════════
-- SNS 소재 레이더 — Threads 바이럴 소재 발굴
--
--   Supabase/Postgres 대신 SQLite 를 쓴다. 콕집의 다른 DB 가 전부 SQLite 이고,
--   이 작업은 단일 프로세스가 30분마다 쓰는 정도라 Postgres 를 세울 이유가 없다.
--   nfind 박스에 격리 보관한다(/opt/koczip-radar/radar.sqlite).
-- ══════════════════════════════════════════════════════════════════════════

-- 검색 키워드 — 활성화·우선순위를 DB 에서 관리한다
CREATE TABLE IF NOT EXISTS keywords (
    id          INTEGER PRIMARY KEY,
    keyword     TEXT NOT NULL UNIQUE,
    category    TEXT NOT NULL DEFAULT 'etc',   -- realestate / life / money / work …
    enabled     INTEGER NOT NULL DEFAULT 1,
    priority    INTEGER NOT NULL DEFAULT 5,    -- 클수록 자주 돈다
    every_min   INTEGER NOT NULL DEFAULT 30,   -- 이 키워드를 몇 분마다 볼지
    last_run_at TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','+9 hours'))
);

-- 수집 게시물. 같은 글이 여러 키워드에 걸리므로 post_key 로 중복을 막는다
CREATE TABLE IF NOT EXISTS posts (
    id             INTEGER PRIMARY KEY,
    post_key       TEXT NOT NULL UNIQUE,       -- /@author/post/XXXX (Threads 경로)
    author         TEXT,
    text           TEXT,
    url            TEXT,

    like_count     INTEGER NOT NULL DEFAULT 0,
    reply_count    INTEGER NOT NULL DEFAULT 0,
    repost_count   INTEGER NOT NULL DEFAULT 0,
    quote_count    INTEGER NOT NULL DEFAULT 0,

    -- 게시 시각은 카드의 상대표기("3시간")를 환산한 추정치다. 정확한 시각이 아니라
    -- 반응 속도를 재기 위한 근사이므로 별도 칸에 둔다.
    posted_at      TEXT,
    age_min        INTEGER,                    -- 수집 시점 기준 경과(분)
    first_seen_at  TEXT NOT NULL DEFAULT (datetime('now','+9 hours')),
    collected_at   TEXT NOT NULL DEFAULT (datetime('now','+9 hours')),
    -- 밈·짤은 사진이 본체다. 목록에서 바로 보이도록 대표 이미지를 들고 있는다.
    image_url      TEXT,
    n_media        INTEGER NOT NULL DEFAULT 0,
    has_video      INTEGER NOT NULL DEFAULT 0,

    keyword        TEXT,                       -- 처음 걸린 키워드
    keywords_all   TEXT,                       -- 걸린 키워드 전부(쉼표)

    -- 반응 기반 점수
    engagement     REAL NOT NULL DEFAULT 0,
    velocity       REAL NOT NULL DEFAULT 0,    -- 시간당 반응
    time_weight    REAL NOT NULL DEFAULT 1,

    -- AI 분석(1차 필터를 통과한 글만 채워진다)
    analyzed_at    TEXT,
    humor          INTEGER, satire      INTEGER, gossip     INTEGER,
    controversy    INTEGER, surprise    INTEGER, empathy    INTEGER,
    hook           INTEGER, realestate  INTEGER,
    ai_score       REAL,
    categories     TEXT,                       -- 쉼표 구분(풍자,팩폭,공감)
    ai_reason      TEXT,
    content_idea   TEXT,

    final_score    REAL NOT NULL DEFAULT 0,

    -- 사람이 손댄 표시
    saved          INTEGER NOT NULL DEFAULT 0, -- ⭐ 저장
    excluded       INTEGER NOT NULL DEFAULT 0, -- 🗑 제외
    notified       INTEGER NOT NULL DEFAULT 0  -- 알림 보냈나
);

CREATE INDEX IF NOT EXISTS posts_final_idx    ON posts(final_score DESC);
CREATE INDEX IF NOT EXISTS posts_collected_idx ON posts(collected_at DESC);
CREATE INDEX IF NOT EXISTS posts_analyzed_idx ON posts(analyzed_at);
CREATE INDEX IF NOT EXISTS posts_saved_idx    ON posts(saved) WHERE saved = 1;

-- 반응 추이 — 같은 글을 다시 만났을 때 얼마나 늘었는지(속도의 근거)
CREATE TABLE IF NOT EXISTS post_snapshots (
    post_key   TEXT NOT NULL,
    seen_at    TEXT NOT NULL DEFAULT (datetime('now','+9 hours')),
    like_count INTEGER, reply_count INTEGER, repost_count INTEGER, quote_count INTEGER,
    PRIMARY KEY (post_key, seen_at)
);

-- 수집 실행 기록
CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT (datetime('now','+9 hours')),
    ended_at   TEXT,
    keywords   INTEGER DEFAULT 0,
    found      INTEGER DEFAULT 0,
    fresh      INTEGER DEFAULT 0,
    analyzed   INTEGER DEFAULT 0,
    error      TEXT
);
