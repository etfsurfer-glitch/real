"""Local FastAPI server — mirrors the Supabase read API the frontend uses,
served from the local SQLite snapshot. Lets us run the PWA without Supabase.

POST /q  { table, select, filters[], order, limit, single }
  → { data, error }

Identifiers (table/column names) are checked against a whitelist derived from
sqlite_master. Values are bound as placeholders.

Run:
  python scripts/local_api.py
  # or with reload:
  uvicorn scripts.local_api:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
import pickle
import sqlite3
import sys
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi import Form as FastapiForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collector.config import settings  # noqa: E402

DB_PATH: Path = settings.local_db_path

ALLOWED_TABLES = {
    "regions",
    "complexes",
    "listings_current",
    "complex_daily_agg",
    "region_daily_agg",
}


def _columns_of(table: str) -> set[str]:
    with sqlite3.connect(DB_PATH) as c:
        return {r[1] for r in c.execute(f'PRAGMA table_info("{table}")')}


TABLE_COLUMNS: dict[str, set[str]] = {t: _columns_of(t) for t in ALLOWED_TABLES}


app = FastAPI(title="naverreal local API")


@app.on_event("startup")
def _warm_ranks_on_startup():
    # Build the realtor rank tables in a background thread so the HTTP port
    # opens immediately. While collect is writing heavily, this can take ~30s
    # the first time; without warming, the first search request pays that cost.
    import threading
    threading.Thread(target=_rank_tables, daemon=True).start()
    threading.Thread(target=_warmer_loop, daemon=True).start()


# 핫셋 워머: 롤업 3종 + 자주 스캔되는 핵심 테이블을 주기적으로 풀스캔해
# OS 페이지캐시에 상주시킨다(8GB RAM 박스, 17GB DB → 핫셋만 메모리 유지).
# 기동 직후 1회 + 이후 10분마다. 롤업기반 엔드포인트는 캐시 미스여도 <3s 보장.
_WARM_SQL = [
    "SELECT COUNT(*) FROM tx_avg_rollup",
    "SELECT COUNT(*) FROM tx_area_rollup",
    "SELECT COUNT(*) FROM tx_record_rollup",
    "SELECT COUNT(*) FROM complex_daily_agg",
    "SELECT COUNT(*) FROM listings_current",
    "SELECT COUNT(*) FROM transactions",
    "SELECT COUNT(*) FROM rentals",
]


def _warmer_loop():
    import time
    while True:
        try:
            with _open_db() as c:
                for q in _WARM_SQL:
                    try:
                        c.execute(q).fetchone()
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(600)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # X-Process-Time 헤더를 브라우저 JS 가 읽을 수 있도록 노출.
    expose_headers=["X-Process-Time"],
)


# ─── 요청 처리 시간 측정 미들웨어 ─────────────────────────
# 모든 응답에 X-Process-Time(초 단위) 헤더 추가 + 느린 요청(>500ms) 콘솔 로깅.
import time as _time
import sys as _sys
import json as _json
@app.middleware("http")
async def _timing_middleware(request, call_next):
    t0 = _time.perf_counter()
    response = await call_next(request)
    elapsed = _time.perf_counter() - t0
    response.headers["X-Process-Time"] = f"{elapsed:.3f}"
    # 느린 요청은 stderr 로 한 줄 로그 (uvicorn access log 와 별도)
    if elapsed >= 0.5:
        path = request.url.path
        qs = ("?" + request.url.query) if request.url.query else ""
        print(f"[slow] {elapsed*1000:>6.0f}ms  {request.method} {path}{qs}",
              file=_sys.stderr, flush=True)
    return response


# ─── 사전 빌드 캐시 미들웨어 ─────────────────────────────
# scripts/build_api_cache.py 가 매일 미리 계산해 둔 응답을 cache.sqlite 에서
# 즉시 반환. 캐시 미스면 정상 핸들러로 흘려보냄 → 라이브 계산.
# 캐시 키 = (path, sorted query_string). POST /q 등은 캐시 안 함.
_CACHE_DB_PATH = DB_PATH.parent / "api_cache.sqlite"
_NO_CACHE_PATHS = {"/health", "/q"}

def _cache_key(path: str, query: str) -> str:
    if not query:
        return path
    # 파라미터 순서 무관하도록 정렬.
    parts = sorted(query.split("&"))
    return f"{path}?{'&'.join(parts)}"

def cache_get(path: str, params: dict | None = None):
    """사전 빌드 캐시 직접 조회 (AI 도구 등 비-HTTP 소비자용).
    미들웨어와 동일한 키 규칙(path + 정렬된 쿼리). 미스/오류 시 None."""
    if not _CACHE_DB_PATH.exists():
        return None
    qs = "&".join(f"{k}={v}" for k, v in sorted((params or {}).items())
                  if v is not None and v != "")
    key = f"{path}?{qs}" if qs else path
    try:
        with sqlite3.connect(_CACHE_DB_PATH) as cc:
            row = cc.execute(
                "SELECT response FROM api_cache WHERE cache_key=?", (key,)).fetchone()
        return _json.loads(row[0]) if row else None
    except (sqlite3.Error, ValueError):
        return None


@app.middleware("http")
async def _prebuilt_cache_middleware(request, call_next):
    if request.method != "GET":
        return await call_next(request)
    path = request.url.path
    if path in _NO_CACHE_PATHS or not _CACHE_DB_PATH.exists():
        return await call_next(request)
    t0 = _time.perf_counter()
    key = _cache_key(path, request.url.query)
    try:
        with sqlite3.connect(_CACHE_DB_PATH) as cc:
            row = cc.execute(
                "SELECT response, computed_at FROM api_cache WHERE cache_key=?",
                (key,),
            ).fetchone()
    except sqlite3.Error:
        row = None
    if row is None:
        return await call_next(request)
    from fastapi.responses import Response
    elapsed = _time.perf_counter() - t0
    resp = Response(content=row[0], media_type="application/json")
    resp.headers["X-Cache"] = "HIT"
    resp.headers["X-Cache-Computed"] = str(row[1] or "")
    resp.headers["X-Process-Time"] = f"{elapsed:.3f}"
    return resp


# ─── 활동 로그 시스템 ────────────────────────────────────────
# 로그인·조회·AI질문 등 모든 활동을 logs.sqlite(WAL)에 남긴다. 로컬 SQLite 사용:
# 매 요청마다 원격(Supabase free-tier)에 쓰면 지연·쿼터 부담이 크기 때문.
# 로그 기록 실패는 절대 요청을 깨뜨리지 않는다(전부 try/except).
import base64 as _b64
LOGS_DB: Path = DB_PATH.parent / "logs.sqlite"


def _init_logs_db() -> None:
    with sqlite3.connect(LOGS_DB) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS event_log (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              ts          TEXT NOT NULL DEFAULT (datetime('now')),  -- UTC
              kind        TEXT NOT NULL,         -- login | view_complex | view_realtor | view | ai_ask | admin | account | api
              user_id     TEXT,                  -- Supabase uid (비로그인 NULL)
              member_no   INTEGER,               -- 내부 회원번호(있을 때)
              email       TEXT,
              provider    TEXT,
              path        TEXT,
              method      TEXT,
              query       TEXT,
              ref         TEXT,                  -- 대상 id (complex_no / realtor_id 등)
              status      INTEGER,
              duration_ms INTEGER,
              ip          TEXT,
              user_agent  TEXT,
              detail      TEXT                   -- JSON (AI 질문/답변/도구/토큰 등)
            );
            CREATE INDEX IF NOT EXISTS ev_ts_idx   ON event_log(ts);
            CREATE INDEX IF NOT EXISTS ev_kind_idx ON event_log(kind, ts);
            CREATE INDEX IF NOT EXISTS ev_user_idx ON event_log(user_id, ts);
            CREATE INDEX IF NOT EXISTS ev_ref_idx  ON event_log(kind, ref);
            """
        )


_init_logs_db()


def _logs_db() -> sqlite3.Connection:
    c = sqlite3.connect(LOGS_DB, timeout=3)
    c.row_factory = sqlite3.Row
    return c


def _jwt_user(authorization: str | None) -> tuple[str | None, str | None]:
    """Authorization 헤더의 Supabase JWT payload를 *검증 없이* 디코드해 (uid, email) 추출.
    로그 귀속용이라 서명검증 불필요(보호 엔드포인트는 current_user가 별도 검증). 네트워크 0."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None, None
    try:
        tok = authorization.split(" ", 1)[1].strip()
        payload = tok.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # base64url 패딩 보정
        data = _authjson.loads(_b64.urlsafe_b64decode(payload).decode("utf-8"))
        return data.get("sub"), (data.get("email") or None)
    except Exception:  # noqa: BLE001
        return None, None


def _client_ip(request) -> str | None:
    h = request.headers
    for k in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        v = h.get(k)
        if v:
            return v.split(",")[0].strip()
    return request.client.host if request.client else None


def _log_event(kind: str, **f) -> None:
    """이벤트 한 건 기록. 어떤 예외도 호출부로 전파하지 않는다."""
    try:
        with _logs_db() as c:
            c.execute(
                "INSERT INTO event_log(kind,user_id,member_no,email,provider,path,method,"
                "query,ref,status,duration_ms,ip,user_agent,detail) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (kind, f.get("user_id"), f.get("member_no"), f.get("email"),
                 f.get("provider"), f.get("path"), f.get("method"), f.get("query"),
                 f.get("ref"), f.get("status"), f.get("duration_ms"), f.get("ip"),
                 f.get("user_agent"),
                 _authjson.dumps(f["detail"], ensure_ascii=False) if f.get("detail") is not None else None))
            c.commit()
    except Exception:  # noqa: BLE001
        pass


def _member_no(user_id: str | None):
    """user_id → 내부 회원번호(없으면 None). 로그 귀속용."""
    if not user_id:
        return None
    try:
        with _reviews_db() as c:
            r = c.execute("SELECT member_no FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
            return r[0] if r else None
    except Exception:  # noqa: BLE001
        return None


def _classify_path(method: str, path: str):
    """요청 경로 → (kind, ref). None이면 로그 생략(노이즈)."""
    if method == "OPTIONS":
        return None
    if path in ("/health", "/favicon.ico", "/perf"):
        return None
    if path.startswith("/ai/ask"):
        return None  # AI는 핸들러에서 질문/답변까지 상세 기록
    parts = path.split("/")
    if path.startswith("/complex/") and len(parts) > 2:
        return "view_complex", parts[2]
    if path.startswith("/realtor/") and len(parts) > 2:
        return "view_realtor", parts[2]
    if path.startswith("/admin/"):
        return "admin", None
    if path.startswith("/ai/region"):
        return "ai_region", None
    if path == "/me" or path.startswith("/me/") or path.startswith("/events"):
        return "account", None
    if method == "GET":
        return "view", None
    return "api", None


@app.middleware("http")
async def _activity_log_middleware(request, call_next):
    t0 = _time.perf_counter()
    response = await call_next(request)
    try:
        cls = _classify_path(request.method, request.url.path)
        if cls:
            kind, ref = cls
            uid, email = _jwt_user(request.headers.get("authorization"))
            _log_event(
                kind, user_id=uid, email=email,
                path=request.url.path, method=request.method,
                query=(request.url.query or None), ref=ref,
                status=response.status_code,
                duration_ms=int((_time.perf_counter() - t0) * 1000),
                ip=_client_ip(request), user_agent=request.headers.get("user-agent"))
    except Exception:  # noqa: BLE001
        pass
    return response


class Filter(BaseModel):
    op: Literal["eq", "in", "ilike"]
    col: str
    val: Any


class Order(BaseModel):
    col: str
    ascending: bool = True


class QueryReq(BaseModel):
    table: str
    select: str = "*"
    filters: list[Filter] = Field(default_factory=list)
    order: Order | None = None
    limit: int | None = None
    single: bool = False


def _open_db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    # 서빙 성능: DB 파일을 memory-map 해 OS 페이지캐시에 핫셋(롤업·인덱스) 상주 →
    # 콜드/캐시미스 쿼리도 디스크바운드 탈출. 워머(_warmer_loop)가 주기적으로 데움.
    try:
        c.execute("PRAGMA mmap_size=6000000000")   # ~6GB memory-map
        c.execute("PRAGMA cache_size=-65536")       # 64MB per-conn page cache
        # temp_store=MEMORY 는 quick-deals 등 대형 GROUP BY 의 temp B-tree 를 RAM 에
        # 쌓아 OOM(6GB+) 유발 → 기본값(파일 temp) 유지. mmap 으로 충분히 빠름.
        c.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass
    return c


# 실거래 평형평균 사전집계(tx_avg_rollup, build_tx_rollups.py) 사용 여부.
# False 면 quick_deals 가 레거시(라이브 매칭) 경로로 돌아간다 — 검증/비상용.
USE_TX_ROLLUP = True
_rollup_ok: bool | None = None


def _rollup_ready() -> bool:
    """tx_avg_rollup 존재+비어있지 않음 확인(성공 시 메모이즈)."""
    global _rollup_ok
    if _rollup_ok:
        return True
    try:
        with _open_db() as c:
            r = c.execute("SELECT EXISTS(SELECT 1 FROM tx_avg_rollup LIMIT 1)").fetchone()
        _rollup_ok = bool(r and r[0])
    except sqlite3.Error:
        _rollup_ok = False
    return _rollup_ok


# ── Supabase 카카오 로그인 세션 검증 + 관리자 식별 ──────────────────
# 관리자 엔드포인트들이 admin_user 의존성을 쓰므로 파일 앞부분에 정의한다.
# 프런트는 Supabase Auth(카카오)로 로그인하고 access_token(JWT)을 Bearer 로 보냄.
# JWT 시크릿을 직접 다루지 않고 Supabase /auth/v1/user 로 위임 검증.
import json as _authjson
import urllib.error as _urlerr
import urllib.request as _urlreq


def _kakao_display_name(user: dict) -> str:
    meta = user.get("user_metadata") or {}
    for k in ("name", "full_name", "nickname", "user_name", "preferred_username"):
        v = meta.get(k)
        if v:
            return str(v)[:40]
    email = user.get("email")
    if email:
        return email.split("@")[0][:40]
    return "익명"


def _admin_email_set() -> set:
    return {e.strip().lower() for e in (settings.admin_emails or "").split(",") if e.strip()}


def _is_admin(email: str | None) -> bool:
    return bool(email) and email.lower() in _admin_email_set()


def _admin_uid_set() -> set:
    return {u.strip() for u in (settings.admin_user_ids or "").split(",") if u.strip()}


def _is_admin_uid(user_id: str | None) -> bool:
    """user_id 기준 관리자 여부 — 글/리뷰 작성자에 '관리자' 뱃지 표시용."""
    return bool(user_id) and user_id in _admin_uid_set()


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """로그인 필수 엔드포인트용 의존성. 유효한 Supabase 세션이면 사용자 정보 반환."""
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(503, "로그인 서버(Supabase)가 설정되지 않았습니다")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "로그인이 필요합니다")
    token = authorization.split(" ", 1)[1].strip()
    req = _urlreq.Request(
        f"{settings.supabase_url}/auth/v1/user",
        headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key},
    )
    try:
        with _urlreq.urlopen(req, timeout=8) as resp:
            user = _authjson.loads(resp.read().decode("utf-8"))
    except _urlerr.HTTPError:
        raise HTTPException(401, "유효하지 않은 세션입니다. 다시 로그인해주세요.")
    except _urlerr.URLError:
        raise HTTPException(502, "로그인 서버에 연결할 수 없습니다")
    uid = user.get("id")
    if not uid:
        raise HTTPException(401, "유효하지 않은 세션입니다")
    email = (user.get("email") or "").lower()
    meta = user.get("user_metadata") or {}
    app_meta = user.get("app_metadata") or {}
    return {
        "id": uid,
        "name": _kakao_display_name(user),
        "email": email,
        "phone": user.get("phone") or meta.get("phone") or meta.get("phone_number"),
        "avatar": meta.get("avatar_url") or meta.get("picture"),
        "provider": app_meta.get("provider"),  # kakao | google | email ...
        "is_admin": _is_admin(email),
    }


def current_user_optional(authorization: str | None = Header(default=None)) -> dict | None:
    """로그인 선택 엔드포인트용 — 토큰 없거나 무효면 None(401 대신). 토론장 읽기 등."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        return current_user(authorization)
    except HTTPException:
        return None


def admin_user(user: dict = Depends(current_user)) -> dict:
    """관리자 전용 엔드포인트 의존성. 로그인 + ADMIN_EMAILS 목록에 있어야 통과."""
    if not user.get("is_admin"):
        raise HTTPException(403, "관리자 전용 기능입니다.")
    return user


def verified_user(user: dict = Depends(current_user)) -> dict:
    """전화번호 인증 완료 사용자만 통과. AI 등 인증 필수 기능용.

    미인증이면 403(code=phone_required) — 프런트는 전화번호 인증 안내로 유도.
    """
    with _reviews_db() as c:
        row = c.execute("SELECT phone_verified FROM user_profiles WHERE user_id=?",
                        (user["id"],)).fetchone()
    if not (row and row[0]):
        raise HTTPException(403, detail={
            "code": "phone_required",
            "message": "AI 서비스는 전화번호 인증 후 이용할 수 있어요.",
        })
    return user


def _validate_cols(table: str, cols_str: str) -> str:
    s = cols_str.strip()
    if s == "*":
        return "*"
    parts = [p.strip() for p in s.split(",")]
    allowed = TABLE_COLUMNS[table]
    for p in parts:
        if p not in allowed:
            raise HTTPException(400, f"unknown column '{p}' on {table}")
    return ", ".join(f'"{p}"' for p in parts)


# SQLite caps bound parameters at 32766. Stay well under for IN filters so
# we don't hit the limit when other filters also bind params.
IN_CHUNK = 20000


def _build_where(
    table: str,
    other: list[Filter],
    extra_in: tuple[str, list[Any]] | None,
) -> tuple[str, list[Any]]:
    where_parts: list[str] = []
    params: list[Any] = []
    for f in other:
        if f.op == "eq":
            where_parts.append(f'"{f.col}" = ?')
            params.append(f.val)
        elif f.op == "in":
            ph = ",".join(["?"] * len(f.val))
            where_parts.append(f'"{f.col}" IN ({ph})')
            params.extend(f.val)
        elif f.op == "ilike":
            # SQLite LIKE is ASCII case-insensitive, fine for Korean.
            where_parts.append(f'"{f.col}" LIKE ?')
            params.append(f.val)
    if extra_in is not None:
        col, vals = extra_in
        ph = ",".join(["?"] * len(vals))
        where_parts.append(f'"{col}" IN ({ph})')
        params.extend(vals)
    where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    return where_sql, params


@app.post("/q")
def query(req: QueryReq):
    # 느린 /q 진단용 — POST 본문은 미들웨어 로그에 안 남아 테이블을 알 수 없었음.
    # 1초 초과 시에만 kind=slow_q 로 테이블·필터를 기록한다.
    _q_t0 = _time.perf_counter()
    try:
        return _query_impl(req)
    finally:
        _q_ms = int((_time.perf_counter() - _q_t0) * 1000)
        if _q_ms >= 1000:
            _log_event("slow_q", path="/q", method="POST", duration_ms=_q_ms,
                       detail={"table": req.table,
                               "filters": [{"op": f.op, "col": f.col,
                                            "val": (f.val if not isinstance(f.val, list)
                                                    else f"[{len(f.val)} items]")}
                                           for f in req.filters],
                               "order": (req.order.col if req.order else None),
                               "limit": req.limit, "single": req.single})


def _query_impl(req: QueryReq):
    if req.table not in ALLOWED_TABLES:
        raise HTTPException(400, f"table not allowed: {req.table}")
    col_sql = _validate_cols(req.table, req.select)
    for f in req.filters:
        if f.col not in TABLE_COLUMNS[req.table]:
            raise HTTPException(400, f"filter on unknown column '{f.col}'")
        if f.op == "in" and not isinstance(f.val, list):
            raise HTTPException(400, "'in' value must be a list")

    # An IN filter with too many values is split into per-chunk queries;
    # ordering + limit are then applied in memory after the union.
    big_in: Filter | None = None
    other: list[Filter] = []
    for f in req.filters:
        if f.op == "in" and not f.val:
            return {"data": (None if req.single else []), "error": None}
        if f.op == "in" and isinstance(f.val, list) and len(f.val) > IN_CHUNK and big_in is None:
            big_in = f
        else:
            other.append(f)

    order_sql = ""
    if req.order:
        if req.order.col not in TABLE_COLUMNS[req.table]:
            raise HTTPException(400, f"order on unknown column '{req.order.col}'")
        order_sql = f' ORDER BY "{req.order.col}" {"ASC" if req.order.ascending else "DESC"}'
    if req.single:
        limit_sql = " LIMIT 1"
    elif req.limit is not None:
        if req.limit < 0 or req.limit > 200000:
            raise HTTPException(400, "limit out of range")
        limit_sql = f" LIMIT {int(req.limit)}"
    else:
        limit_sql = ""

    with _open_db() as c:
        if big_in is None:
            where_sql, params = _build_where(req.table, other, None)
            sql = f'SELECT {col_sql} FROM "{req.table}"{where_sql}{order_sql}{limit_sql}'
            rows = c.execute(sql, params).fetchall()
        else:
            rows = []
            vals_all: list[Any] = big_in.val
            for i in range(0, len(vals_all), IN_CHUNK):
                where_sql, params = _build_where(
                    req.table, other, (big_in.col, vals_all[i:i + IN_CHUNK])
                )
                sql = f'SELECT {col_sql} FROM "{req.table}"{where_sql}'
                rows.extend(c.execute(sql, params).fetchall())
            if req.order:
                col_name = req.order.col
                rows.sort(
                    key=lambda r: (r[col_name] is None, r[col_name]),
                    reverse=not req.order.ascending,
                )
            if req.single:
                rows = rows[:1]
            elif req.limit is not None:
                rows = rows[: req.limit]

    data = [dict(r) for r in rows]
    if req.single:
        return {"data": data[0] if data else None, "error": None}
    return {"data": data, "error": None}


@app.get("/stats/top-complexes")
def top_complexes(days: int = 7, limit: int = 5):
    """Top-N complexes by recent (deal_ymd >= today-days) filing count,
    split by trade type. Same contract-date window as /stats/recent-tx.
    Unmatched rows are skipped — the rank is over identified complexes only.
    """
    if days < 1 or days > 365:
        raise HTTPException(400, "days out of range")
    if limit < 1 or limit > 50:
        raise HTTPException(400, "limit out of range")

    cutoff = f"-{days} days"
    result = {"days": days, "sale": [], "jeonse": [], "wolse": []}
    with _open_db() as c:
        existing = {
            r[0]
            for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

        def _run(unions: list[str], params: list) -> list[dict]:
            if not unions:
                return []
            sql = (
                "WITH agg AS (SELECT matched_complex_no AS cno, COUNT(*) AS n "
                "FROM (" + " UNION ALL ".join(unions) + ") "
                "WHERE matched_complex_no IS NOT NULL "
                "GROUP BY matched_complex_no) "
                "SELECT agg.cno, c.complex_name, agg.n "
                "FROM agg LEFT JOIN complexes c ON c.complex_no = agg.cno "
                "ORDER BY agg.n DESC LIMIT ?"
            )
            rows = c.execute(sql, [*params, limit]).fetchall()
            return [{"complex_no": r[0], "complex_name": r[1], "count": r[2]} for r in rows]

        sale_u, sale_p = [], []
        if "transactions" in existing:
            sale_u.append("SELECT matched_complex_no FROM transactions WHERE deal_ymd >= date('now', ?) AND is_cancelled = 0")
            sale_p.append(cutoff)
        if "offi_transactions" in existing:
            sale_u.append("SELECT matched_complex_no FROM offi_transactions WHERE deal_ymd >= date('now', ?) AND is_cancelled = 0")
            sale_p.append(cutoff)
        result["sale"] = _run(sale_u, sale_p)

        jeonse_u, jeonse_p = [], []
        if "rentals" in existing:
            jeonse_u.append("SELECT matched_complex_no FROM rentals WHERE deal_ymd >= date('now', ?) AND +monthly_rent = 0")
            jeonse_p.append(cutoff)
        if "offi_rentals" in existing:
            jeonse_u.append("SELECT matched_complex_no FROM offi_rentals WHERE deal_ymd >= date('now', ?) AND +monthly_rent = 0")
            jeonse_p.append(cutoff)
        result["jeonse"] = _run(jeonse_u, jeonse_p)

        wolse_u, wolse_p = [], []
        if "rentals" in existing:
            wolse_u.append("SELECT matched_complex_no FROM rentals WHERE deal_ymd >= date('now', ?) AND +monthly_rent > 0")
            wolse_p.append(cutoff)
        if "offi_rentals" in existing:
            wolse_u.append("SELECT matched_complex_no FROM offi_rentals WHERE deal_ymd >= date('now', ?) AND +monthly_rent > 0")
            wolse_p.append(cutoff)
        result["wolse"] = _run(wolse_u, wolse_p)

    return result


@app.get("/stats/listing-trend")
def listing_trend(days: int = 60):
    """일별 매물 수 추이 (snapshot_date × trade_type).
    complex_daily_agg를 SUM해서 [{snapshot_date, A1, B1, B2}, ...] 형태로.
    """
    if days < 1 or days > 365:
        raise HTTPException(400, "days out of range")
    with _open_db() as c:
        rows = c.execute(
            """
            SELECT snapshot_date, trade_type, SUM(listing_count) AS n
            FROM complex_daily_agg
            WHERE snapshot_date >= date('now', ?)
            GROUP BY snapshot_date, trade_type
            ORDER BY snapshot_date ASC
            """,
            (f"-{days} days",),
        ).fetchall()
    by_date: dict[str, dict] = {}
    for d, t, n in rows:
        by_date.setdefault(d, {"snapshot_date": d, "A1": 0, "B1": 0, "B2": 0})[t] = n
    return {"days": days, "series": list(by_date.values())}


@app.get("/stats/avg-price-trend")
def avg_price_trend(days: int = 60, sido: str | None = None, sigungu: str | None = None, dong: str | None = None, asset: str | None = None):
    """일별 평균 호가 추이 (snapshot_date × trade_type), 지역·자산(apt/offi) 필터 가능.

    /stats/changes/summary 의 avg_price 계산식을 시계열로 확장.
    각 일자의 거래유형별 가중평균(weights=listing_count)을 원 단위로 반환.
    - A1/B1/B2: price_avg (매매가, 전세금, 월세 보증금) — sane bound 컷
    - B2R: B2 행의 rent_avg (월세) — 별 키로 추가. 보증금과 스케일이 100배 차이라
           프런트에서 차트를 분리해 그리기 좋도록 따로 노출.
    """
    if days < 1 or days > 365:
        raise HTTPException(400, "days out of range")

    # 지역 필터 (summary 와 동일 패턴)
    region_join = ""
    region_clause = ""
    region_filter_params: list[Any] = []
    if sigungu:
        region_join = " JOIN complexes cx ON cx.complex_no = a.complex_no"
        region_clause = " AND substr(cx.cortar_no,1,5) = substr(?,1,5)"
        region_filter_params.append(sigungu)
    elif sido:
        region_join = " JOIN complexes cx ON cx.complex_no = a.complex_no"
        region_clause = " AND substr(cx.cortar_no,1,2) = substr(?,1,2)"
        region_filter_params.append(sido)
    asset_clause = _asset_type_clause(asset)
    if asset_clause and not region_join:
        region_join = " JOIN complexes cx ON cx.complex_no = a.complex_no"
    region_clause += asset_clause

    parts = []
    params: list[Any] = []
    # 보증금/매매가/전세금: price_avg
    for t in ("A1", "B1", "B2"):
        lo = _PRICE_LO.get(t, 1_000_000)
        parts.append(
            f"SELECT a.snapshot_date, ? AS k, "
            f"       SUM(a.price_avg*a.listing_count)*1.0/SUM(a.listing_count) AS avg_p, "
            f"       SUM(a.listing_count) AS cnt "
            f"FROM complex_daily_agg a{region_join} "
            f"WHERE a.snapshot_date >= date('now', ?) "
            f"  AND a.trade_type = ? "
            f"  AND a.price_avg BETWEEN ? AND ?{region_clause} "
            f"GROUP BY a.snapshot_date"
        )
        params.extend([t, f"-{days} days", t, lo, _PRICE_HI, *region_filter_params])
    # 월세 (B2 의 rent_avg) — 시군구별 '실거래 월세 상한'(rent_ref_sgg, 깨끗한 실거래
    # p99×1.5)을 넘는 그룹은 보증금 오입력·제주 년세 등으로 보고 제외(지역 적응).
    parts.append(
        f"SELECT a.snapshot_date, 'B2R' AS k, "
        f"       SUM(a.rent_avg*a.listing_count)*1.0/SUM(a.listing_count) AS avg_p, "
        f"       SUM(a.listing_count) AS cnt "
        f"FROM complex_daily_agg a "
        f"JOIN complexes cr ON cr.complex_no = a.complex_no "
        f"LEFT JOIN rent_ref_sgg rr ON rr.sgg5 = substr(cr.cortar_no,1,5)"
        f"{region_join} "
        f"WHERE a.snapshot_date >= date('now', ?) "
        f"  AND a.trade_type = 'B2' "
        f"  AND a.rent_avg BETWEEN ? AND COALESCE(rr.rent_cap, ?)"
        f"{region_clause} "
        f"GROUP BY a.snapshot_date"
    )
    params.extend([f"-{days} days", _RENT_LO, _RENT_HI, *region_filter_params])
    sql = " UNION ALL ".join(parts) + " ORDER BY snapshot_date ASC"
    with _open_db() as c:
        rows = c.execute(sql, params).fetchall()
    # 라인(k)별 최대 매물수 → 그 30% 미만인 날은 커버리지 빈약(예: 오피스텔 수집이
    # 5/21 에 42→8,185단지로 확대된 온보딩 구간, 부분 스냅샷)으로 보고 추이에서 제외.
    maxcnt: dict[str, int] = {}
    for _d, k, p, cnt in rows:
        if p is not None and cnt:
            maxcnt[k] = max(maxcnt.get(k, 0), cnt)
    by_date: dict[str, dict] = {}
    for d, k, p, cnt in rows:
        if p is None:
            continue
        if cnt and maxcnt.get(k) and cnt < maxcnt[k] * 0.3:
            continue  # 커버리지 빈약 점 제외
        by_date.setdefault(
            d, {"snapshot_date": d, "A1": None, "B1": None, "B2": None, "B2R": None}
        )[k] = p
    return {"days": days, "series": list(by_date.values())}


@app.get("/stats/top-listings")
def top_listings(limit: int = 5):
    """최신 snapshot의 단지별 매물 수 top-N (거래유형별).
    각 항목 = {complex_no, complex_name, count}.
    """
    if limit < 1 or limit > 50:
        raise HTTPException(400, "limit out of range")
    out = {"snapshot_date": None, "A1": [], "B1": [], "B2": []}
    with _open_db() as c:
        row = c.execute("SELECT MAX(snapshot_date) FROM complex_daily_agg").fetchone()
        snap = row[0] if row else None
        if not snap:
            return out
        out["snapshot_date"] = snap
        for t in ("A1", "B1", "B2"):
            rs = c.execute(
                """
                SELECT a.complex_no, c.complex_name, SUM(a.listing_count) AS n
                FROM complex_daily_agg a
                LEFT JOIN complexes c ON c.complex_no = a.complex_no
                WHERE a.snapshot_date = ? AND a.trade_type = ?
                GROUP BY a.complex_no
                ORDER BY n DESC
                LIMIT ?
                """,
                (snap, t, limit),
            ).fetchall()
            out[t] = [{"complex_no": r[0], "complex_name": r[1], "count": r[2]} for r in rs]
    return out


@app.get("/complexes/cluster")
def complexes_cluster(swlat: float, swlng: float, nelat: float, nelng: float,
                      cols: int = 7, rows: int = 7):
    """지도 축소 시 단지 군집 — bbox를 cols×rows 격자로 나눠 셀별 단지수+중심좌표 반환.
    캡 없이 영역 내 전체 단지를 집계(축소 화면에서 핀 폭주 방지)."""
    if not (swlat < nelat and swlng < nelng):
        raise HTTPException(400, "bad bounds")
    cols = max(2, min(cols, 16)); rows = max(2, min(rows, 16))
    dlat = (nelat - swlat) / rows or 1e-9
    dlng = (nelng - swlng) / cols or 1e-9
    with _open_db() as c:
        cells = c.execute(
            "SELECT CAST((latitude-?)/? AS INT) gy, CAST((longitude-?)/? AS INT) gx, "
            "COUNT(*) n, AVG(latitude) clat, AVG(longitude) clng "
            "FROM complexes WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? "
            "AND latitude IS NOT NULL AND longitude IS NOT NULL GROUP BY gy, gx",
            (swlat, dlat, swlng, dlng, swlat, nelat, swlng, nelng)).fetchall()
    return {"cells": [{"lat": r[3], "lng": r[4], "count": r[2]} for r in cells if r[2]]}


@app.get("/complexes/in-bounds")
def complexes_in_bounds(swlat: float, swlng: float, nelat: float, nelng: float,
                        limit: int = 1000):
    """지도 보이는 영역(bbox) 안의 단지 — 지도보기 탭용. 매물수 포함, 세대수 큰 순.
    너무 많으면 limit 으로 컷(프론트는 더 줌인하면 줄어듦). too_many 플래그로 안내."""
    if not (swlat < nelat and swlng < nelng):
        raise HTTPException(400, "bad bounds")
    with _open_db() as c:
        total = c.execute(
            "SELECT COUNT(*) FROM complexes WHERE latitude BETWEEN ? AND ? "
            "AND longitude BETWEEN ? AND ?",
            (swlat, nelat, swlng, nelng),
        ).fetchone()[0]
        rows = c.execute(
            """
            SELECT cx.complex_no, cx.complex_name, cx.latitude, cx.longitude,
                   cx.total_household_count,
                   (SELECT COUNT(*) FROM listings_current l
                    WHERE l.complex_no = cx.complex_no AND l.trade_type='A1') AS c_sale,
                   (SELECT COUNT(*) FROM listings_current l
                    WHERE l.complex_no = cx.complex_no AND l.trade_type='B1') AS c_jeonse,
                   (SELECT COUNT(*) FROM listings_current l
                    WHERE l.complex_no = cx.complex_no AND l.trade_type='B2') AS c_wol,
                   (SELECT MAX(l.deal_or_warrant_price) FROM listings_current l
                    WHERE l.complex_no = cx.complex_no AND l.trade_type='A1') AS max_sale,
                   (SELECT MAX(t.deal_amount) FROM transactions t
                    WHERE t.matched_complex_no = cx.complex_no AND t.is_cancelled = 0) AS max_tx
            FROM complexes cx
            WHERE cx.latitude BETWEEN ? AND ? AND cx.longitude BETWEEN ? AND ?
            ORDER BY cx.total_household_count DESC
            LIMIT ?
            """,
            (swlat, nelat, swlng, nelng, limit),
        ).fetchall()
    return {
        "total": total,
        "too_many": total > limit,
        "items": [
            {"complex_no": r[0], "name": r[1], "lat": r[2], "lng": r[3],
             "households": r[4],
             "c_sale": r[5], "c_jeonse": r[6], "c_wol": r[7],
             "listings": (r[5] or 0) + (r[6] or 0) + (r[7] or 0),
             "max_sale": r[8], "max_tx": r[9]}
            for r in rows
        ],
    }


@app.get("/complex/{complex_no}/seo")
def complex_seo(complex_no: str):
    """검색봇 동적 렌더링용 단지 기본정보(이름·지역·주소·세대수·준공). 공개."""
    with _open_db() as c:
        row = c.execute(
            "SELECT complex_name, dong_name, road_address, detail_address, "
            "total_household_count, use_approve_ymd, real_estate_type_name "
            "FROM complexes WHERE complex_no=?", (complex_no,)).fetchone()
    if not row:
        raise HTTPException(404, "not found")
    name, dong, road, addr, hh, approve, kind = row
    approve_y = (approve or "")[:4] if approve else None
    return {
        "complex_no": complex_no, "name": name, "dong": dong,
        "address": road or addr or "", "households": hh,
        "approve_year": approve_y, "kind": kind or "아파트",
    }


@app.get("/complex/{complex_no}/transactions")
def complex_transactions(complex_no: str, months: int = 24, limit: int = 500):
    """단지별 실거래 이력. 매매(transactions + offi_transactions) /
    전세 (rentals + offi_rentals, monthly_rent=0) /
    월세 (rentals + offi_rentals, monthly_rent>0)
    각 deal_ymd DESC로 정렬.
    """
    if months < 1 or months > 240:
        raise HTTPException(400, "months out of range")
    if limit < 1 or limit > 5000:
        raise HTTPException(400, "limit out of range")
    cutoff = f"-{months} months"
    out: dict = {
        "complex_no": complex_no,
        "months": months,
        "sale": [],
        "jeonse": [],
        "wolse": [],
        "silv": [],   # 분양권/입주권 전매
    }
    with _open_db() as c:
        existing = {
            r[0]
            for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

        # 매매: transactions + offi_transactions (union)
        sale_parts: list[str] = []
        sale_params: list = []
        if "transactions" in existing:
            # 아파트 매매만 동(aptDong)·등기여부(rgstDate) 제공. registered=등기완료.
            sale_parts.append(
                "SELECT deal_ymd, deal_amount, excl_use_ar, floor, dealing_gbn, build_year, 'apt' AS asset, "
                "json_extract(raw,'$.aptDong') AS dong, "
                "(TRIM(COALESCE(json_extract(raw,'$.rgstDate'),''))<>'') AS registered "
                "FROM transactions WHERE matched_complex_no = ? AND deal_ymd >= date('now', ?) AND is_cancelled = 0"
            )
            sale_params.extend([complex_no, cutoff])
        if "offi_transactions" in existing:
            # 오피스텔 매매 API엔 동/등기 필드 없음 → NULL.
            sale_parts.append(
                "SELECT deal_ymd, deal_amount, excl_use_ar, floor, dealing_gbn, build_year, 'offi' AS asset, "
                "NULL AS dong, 0 AS registered "
                "FROM offi_transactions WHERE matched_complex_no = ? AND deal_ymd >= date('now', ?) AND is_cancelled = 0"
            )
            sale_params.extend([complex_no, cutoff])
        if sale_parts:
            sql = " UNION ALL ".join(sale_parts) + " ORDER BY deal_ymd DESC LIMIT ?"
            for row in c.execute(sql, [*sale_params, limit]):
                out["sale"].append({
                    "deal_ymd": row[0], "deal_amount": row[1],
                    "excl_use_ar": row[2], "floor": row[3],
                    "dealing_gbn": row[4], "build_year": row[5], "asset": row[6],
                    "dong": row[7], "registered": bool(row[8]),
                })

        # 전세 + 월세는 rentals/offi_rentals를 한 번에 뽑고 monthly_rent로 나눔
        rent_parts: list[str] = []
        rent_params: list = []
        if "rentals" in existing:
            rent_parts.append(
                "SELECT deal_ymd, deposit, monthly_rent, excl_use_ar, floor, build_year, "
                "contract_type, contract_term, use_rr_right, pre_deposit, pre_monthly_rent, 'apt' AS asset "
                "FROM rentals WHERE matched_complex_no = ? AND deal_ymd >= date('now', ?)"
            )
            rent_params.extend([complex_no, cutoff])
        if "offi_rentals" in existing:
            rent_parts.append(
                "SELECT deal_ymd, deposit, monthly_rent, excl_use_ar, floor, build_year, "
                "contract_type, contract_term, use_rr_right, pre_deposit, pre_monthly_rent, 'offi' AS asset "
                "FROM offi_rentals WHERE matched_complex_no = ? AND deal_ymd >= date('now', ?)"
            )
            rent_params.extend([complex_no, cutoff])
        if rent_parts:
            sql = " UNION ALL ".join(rent_parts) + " ORDER BY deal_ymd DESC LIMIT ?"
            for row in c.execute(sql, [*rent_params, limit]):
                item = {
                    "deal_ymd": row[0], "deposit": row[1], "monthly_rent": row[2],
                    "excl_use_ar": row[3], "floor": row[4], "build_year": row[5],
                    "contract_type": row[6], "contract_term": row[7],
                    "use_rr_right": row[8],
                    "pre_deposit": row[9], "pre_monthly_rent": row[10],
                    "asset": row[11],
                }
                if (row[2] or 0) > 0:
                    out["wolse"].append(item)
                else:
                    out["jeonse"].append(item)

        # 분양권/입주권 전매 (silv_transactions). 해제건 제외(시세 오염 방지).
        if "silv_transactions" in existing:
            sql = (
                "SELECT deal_ymd, deal_amount, excl_use_ar, floor, dealing_gbn, ownership_gbn "
                "FROM silv_transactions "
                "WHERE matched_complex_no = ? AND deal_ymd >= date('now', ?) AND is_cancelled = 0 "
                "ORDER BY deal_ymd DESC LIMIT ?"
            )
            for row in c.execute(sql, [complex_no, cutoff, limit]):
                out["silv"].append({
                    "deal_ymd": row[0], "deal_amount": row[1],
                    "excl_use_ar": row[2], "floor": row[3],
                    "dealing_gbn": row[4],
                    # ownership_gbn: '입'=입주권, 그 외/빈값=분양권
                    "kind": "입주권" if (row[5] or "").strip() == "입" else "분양권",
                })

    return out


# 중개사 랭킹 — listings_current 전체 스캔이라 1~2s 걸려서 짧게 캐시.
import time as _time
_realtor_cache: dict[str, tuple[float, object]] = {}
# realtor 캐시 백스톱 TTL = 24h. 실제 신선도는 랭킹 파일 mtime 으로 관리한다(아래):
# daily_run(매일 아침, 목표 7시까지)이 파일을 새로 쓰면 서버가 mtime 변화를 감지해
# 캐시를 비우고 새 데이터를 반영. 즉 '보존기간'은 매일 아침 파이프라인 완료 기준.
_REALTOR_TTL_S = 86400.0


def _cache_get(key: str):
    hit = _realtor_cache.get(key)
    if hit and _time.monotonic() - hit[0] < _REALTOR_TTL_S:
        return hit[1]
    return None


def _cache_put(key: str, val):
    _realtor_cache[key] = (_time.monotonic(), val)


@app.get("/stats/realtors/national")
def realtors_national(limit: int = 20):
    """전국 매물 보유 상위 N개 중개사. realtor_id 기준 (이름은 지역별 중복 多)."""
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit out of range")
    ck = f"national:{limit}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached
    with _open_db() as c:
        rows = c.execute(
            """
            SELECT realtor_id,
                   MAX(realtor_name) AS realtor_name,
                   COUNT(*) AS n
            FROM listings_current
            WHERE realtor_id IS NOT NULL
            GROUP BY realtor_id
            ORDER BY n DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        # 상위 N개에만 소재지(시도)·소속인원·개업연도를 붙인다. naver_realtors →
        # realtor_match(sys_regno) → vworld_brokers(개업일)/vworld_employees(인원).
        ids = [r[0] for r in rows]
        info: dict[str, dict] = {}
        if ids:
            ph = ",".join("?" * len(ids))
            sido_names = {
                r[0][:2]: r[1]
                for r in c.execute(
                    "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city'"
                )
            }
            for er in c.execute(
                f"""
                SELECT nr.realtor_id, nr.realtor_name, nr.cortar_no,
                       vb.registered_ymd,
                       (SELECT COUNT(*) FROM vworld_employees ve
                        WHERE ve.sys_regno = rm.sys_regno) AS emp
                FROM naver_realtors nr
                LEFT JOIN realtor_match rm ON rm.realtor_id = nr.realtor_id
                LEFT JOIN vworld_brokers vb ON vb.sys_regno = rm.sys_regno
                WHERE nr.realtor_id IN ({ph})
                """,
                ids,
            ):
                cortar = er[2] or ""
                reg = er[3] or ""
                info[er[0]] = {
                    "office_name": er[1],
                    "sido": sido_names.get(cortar[:2]) if cortar else None,
                    "established_year": reg[:4] if len(reg) >= 4 else None,
                    "staff_count": er[4] or None,
                }
    items = []
    for r in rows:
        e = info.get(r[0], {})
        items.append({
            "realtor_id": r[0],
            "realtor_name": e.get("office_name") or r[1],
            "count": r[2],
            "sido": e.get("sido"),
            "staff_count": e.get("staff_count"),
            "established_year": e.get("established_year"),
        })
    out = {"limit": limit, "items": items}
    _cache_put(ck, out)
    return out


def _realtor_enrich(c, ids: list) -> dict:
    """realtor_id 목록 → {id: {office_name, sido, established_year, staff_count, count}}.
    naver_realtors → realtor_match(sys_regno) → vworld_brokers(개업일)/vworld_employees(인원)."""
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    sido_names = {r[0][:2]: r[1] for r in c.execute(
        "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city'")}
    cnt = {r[0]: r[1] for r in c.execute(
        f"SELECT realtor_id, COUNT(*) FROM listings_current "
        f"WHERE realtor_id IN ({ph}) GROUP BY realtor_id", ids)}
    out: dict[str, dict] = {}
    for er in c.execute(
        f"""
        SELECT nr.realtor_id, nr.realtor_name, nr.cortar_no, vb.registered_ymd,
               (SELECT COUNT(*) FROM vworld_employees ve WHERE ve.sys_regno = rm.sys_regno) AS emp
        FROM naver_realtors nr
        LEFT JOIN realtor_match rm ON rm.realtor_id = nr.realtor_id
        LEFT JOIN vworld_brokers vb ON vb.sys_regno = rm.sys_regno
        WHERE nr.realtor_id IN ({ph})
        """, ids,
    ):
        cortar = er[2] or ""
        reg = er[3] or ""
        out[er[0]] = {
            "office_name": er[1],
            "sido": sido_names.get(cortar[:2]) if cortar else None,
            "established_year": reg[:4] if len(reg) >= 4 else None,
            "staff_count": er[4] or None,
            "count": cnt.get(er[0], 0),
        }
    return out


def _sgg_prefix(region: str) -> str:
    """지역 필터용 sgg_cd 접두 검증(2=시도 / 4=통합시 / 5=시군구)."""
    region = (region or "").strip()
    if region and (not region.isdigit() or len(region) not in (2, 4, 5)):
        raise HTTPException(400, "region must be 2/4/5-digit sgg prefix")
    return region


@app.get("/stats/realtors/by-staff")
def realtors_by_staff(limit: int = 20, region: str = ""):
    """직원수(소속 인원) 상위 N개 중개사. vworld_employees 기준.
    region: sgg_cd 접두(2/4/5자리). 주면 그 지역 안에서 순위."""
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit out of range")
    region = _sgg_prefix(region)
    ck = f"realtor_staff:{limit}:{region}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached
    with _open_db() as c:
        # V-World 등록 인원 전체 기준(네이버 매칭 여부와 무관) — 대형 중개법인도 포함.
        if region:
            rows = c.execute(
                """
                SELECT e.sys_regno, e.emp, e.bn
                FROM (SELECT sys_regno, COUNT(*) AS emp, MAX(business_name) AS bn
                      FROM vworld_employees WHERE sys_regno IS NOT NULL
                      GROUP BY sys_regno) e
                JOIN vworld_brokers vb ON vb.sys_regno = e.sys_regno
                WHERE substr(vb.sgg_cd, 1, ?) = ?
                ORDER BY e.emp DESC
                LIMIT ?
                """, (len(region), region, limit),
            ).fetchall()
        else:
            rows = c.execute(
                """
                SELECT sys_regno, COUNT(*) AS emp, MAX(business_name) AS bn
                FROM vworld_employees
                WHERE sys_regno IS NOT NULL
                GROUP BY sys_regno
                ORDER BY emp DESC
                LIMIT ?
                """, (limit,),
            ).fetchall()
        cities = {r[0][:2]: r[1] for r in c.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city'")}
        items = []
        for rg, emp, bn in rows:
            m = c.execute(
                "SELECT realtor_id, total_listings FROM realtor_match WHERE sys_regno=? LIMIT 1",
                (rg,)).fetchone()
            br = c.execute(
                "SELECT sgg_cd, registered_ymd FROM vworld_brokers WHERE sys_regno=? LIMIT 1",
                (rg,)).fetchone()
            sgg = br[0] if br else None
            items.append({
                "realtor_id": (m[0] if m else None),     # 매칭된 곳만 상세링크
                "realtor_name": bn,
                "count": (m[1] if m else None),
                "sido": (cities.get((sgg or "")[:2]) if sgg else None),
                "staff_count": emp,
                "established_year": (br[1][:4] if (br and br[1] and len(br[1]) >= 4) else None),
            })
    out = {"limit": limit, "items": items}
    _cache_put(ck, out)
    return out


@app.get("/stats/realtors/by-tenure")
def realtors_by_tenure(limit: int = 20, region: str = ""):
    """업력(개업일 빠른 순) 상위 N개 중개사. vworld_brokers.registered_ymd 기준(V-World 전체,
    네이버 매칭 여부 무관). region: sgg_cd 접두(2/4/5자리). 주면 그 지역 안에서 순위."""
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit out of range")
    region = _sgg_prefix(region)
    ck = f"realtor_tenure:{limit}:{region}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached
    with _open_db() as c:
        where = ["registered_ymd IS NOT NULL", "length(registered_ymd) >= 8",
                 "registered_ymd > '1900'", "(status IS NULL OR status NOT LIKE '%폐업%')"]
        params: list = []
        if region:
            where.insert(0, "substr(sgg_cd, 1, ?) = ?")
            params += [len(region), region]
        params.append(limit)
        rows = c.execute(
            f"""
            SELECT sys_regno, registered_ymd, business_name, sgg_cd
            FROM vworld_brokers
            WHERE {' AND '.join(where)}
            ORDER BY registered_ymd ASC
            LIMIT ?
            """, params,
        ).fetchall()
        cities = {r[0][:2]: r[1] for r in c.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city'")}
        items = []
        for rg, reg, bn, sgg in rows:
            m = c.execute(
                "SELECT realtor_id, total_listings FROM realtor_match WHERE sys_regno=? LIMIT 1",
                (rg,)).fetchone()
            emp = c.execute(
                "SELECT COUNT(*) FROM vworld_employees WHERE sys_regno=?", (rg,)).fetchone()
            items.append({
                "realtor_id": (m[0] if m else None),   # 매칭된 곳만 상세링크
                "realtor_name": bn,
                "count": (m[1] if m else None),
                "sido": (cities.get((sgg or "")[:2]) if sgg else None),
                "staff_count": (emp[0] if emp else None),
                # registered_ymd 는 'YYYY.MM.DD' 형식 → 연도만으론 순서가 모호해 월·일까지 표기.
                "established_year": reg[:4] if reg and len(reg) >= 4 else None,
                "established_date": reg if reg and len(reg) >= 8 else None,
            })
    out = {"limit": limit, "items": items}
    _cache_put(ck, out)
    return out


@app.get("/stats/realtors/by-sido")
def realtors_by_sido(limit: int = 10):
    """시도별 상위 N개 중개사. 단지 cortar_no 앞 2자리로 시도 묶음."""
    if limit < 1 or limit > 50:
        raise HTTPException(400, "limit out of range")
    ck = f"sido:{limit}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached
    with _open_db() as c:
        sido_names = {
            r[0][:2]: r[1]
            for r in c.execute(
                "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city'"
            )
        }
        rows = c.execute(
            """
            WITH per_sido AS (
                SELECT substr(c.cortar_no, 1, 2) AS sido,
                       l.realtor_id,
                       l.realtor_name,
                       COUNT(*) AS n
                FROM listings_current l
                JOIN complexes c ON c.complex_no = l.complex_no
                WHERE l.realtor_id IS NOT NULL AND c.cortar_no IS NOT NULL
                GROUP BY sido, l.realtor_id
            ),
            ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (PARTITION BY sido ORDER BY n DESC) AS rk
                FROM per_sido
            )
            SELECT sido, realtor_id, realtor_name, n
            FROM ranked
            WHERE rk <= ?
            ORDER BY sido, n DESC
            """,
            (limit,),
        ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for sido, rid, rname, n in rows:
        name = sido_names.get(sido, sido)
        grouped.setdefault(name, []).append(
            {"realtor_id": rid, "realtor_name": rname, "count": n}
        )
    out = {"limit": limit, "groups": grouped}
    _cache_put(ck, out)
    return out


@app.get("/stats/realtors/search")
def realtors_search(q: str = "", sido: str = "", limit: int = 30):
    """중개사 검색 — 이름 부분일치 + 선택적 시도 필터. 매물 보유 내림차순.
    sido는 cortar_no 앞 2자리 (예: '11'=서울).
    캐시된 rank 테이블(51k row)에서 in-memory 필터 — listings_current 풀스캔 회피.
    """
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit out of range")
    q = q.strip()
    sido = sido.strip()
    if len(q) < 1 and not sido:
        return {"items": []}
    if sido and (len(sido) != 2 or not sido.isdigit()):
        raise HTTPException(400, "sido must be 2-digit")
    ranks = _rank_tables()
    q_low = q.lower()
    items: list[tuple[str, str | None, int]] = []  # (rid, name, count)
    if sido:
        for (s, rid), (_rk, n, name) in ranks["sido_rank"].items():
            if s != sido:
                continue
            if q and (not name or q_low not in name.lower()):
                continue
            items.append((rid, name, n))
    else:
        for rid, (_rk, n, name) in ranks["national"].items():
            if q and (not name or q_low not in name.lower()):
                continue
            items.append((rid, name, n))
    # 매물이 없어 랭킹 인덱스에 없는 사무소(신규/합성 등)도 이름으로 찾게 보강.
    if q:
        seen = {rid for rid, _n, _c in items}
        with _open_db() as c:
            cond, params = "realtor_name LIKE ?", [f"%{q}%"]
            if sido:
                cond += " AND substr(cortar_no,1,2)=?"; params.append(sido)
            for rid, name in c.execute(
                    f"SELECT realtor_id, realtor_name FROM naver_realtors WHERE {cond} LIMIT 50", params):
                if rid not in seen:
                    seen.add(rid); items.append((rid, name, 0))
    items.sort(key=lambda r: -r[2])
    items = items[:limit]
    # 동명 중개사무소가 많아 이름만으론 구분 불가 → 소재지(주소)·대표자명을 함께 준다.
    info: dict = {}
    ids = [rid for rid, _n, _c in items]
    if ids:
        with _open_db() as c:
            qm = ",".join("?" * len(ids))
            for rid, rep, addr in c.execute(
                f"SELECT realtor_id, representative_name, address "
                f"FROM naver_realtors WHERE realtor_id IN ({qm})", ids):
                info[rid] = (rep, addr)

    def _loc(addr: str | None) -> str | None:
        if not addr:
            return None
        toks = addr.split()
        return " ".join(toks[:3]) if toks else None  # 시도 시군구 읍면동까지

    return {
        "q": q, "sido": sido,
        "items": [
            {"realtor_id": rid, "realtor_name": name, "count": n,
             "representative": (info.get(rid) or (None, None))[0],
             "location": _loc((info.get(rid) or (None, None))[1]),
             "address": (info.get(rid) or (None, None))[1]}
            for rid, name, n in items
        ],
    }


# 랭킹 영속 파일. listings 는 하루 1회(수집)만 바뀌므로, 매 요청·재시작마다 414만
# 행을 GROUP BY 하지 않고 파일에서 즉시 로드한다. daily_run(build_api_cache)이 매일
# persist_ranks() 로 새로 빌드해 갱신.
_RANK_FILE = DB_PATH.parent / "realtor_ranks.pkl"
_rank_loaded_mtime: float | None = None  # 마지막으로 로드한 파일의 수정시각


def _rank_tables() -> dict:
    """랭킹 테이블. 메모리캐시 → 영속파일 → (없으면) 라이브 빌드 순.
    national: id->(rank,count,name), sido_rank: (sido,id)->(rank,count,name),
    sido_totals, sido_names, national_total."""
    global _rank_loaded_mtime
    # 매일 아침 daily_run 이 랭킹 파일을 새로 쓰면 mtime 이 바뀐다 → 모든 realtor
    # 캐시를 비워 새 데이터를 즉시 반영('보존기간'을 아침 파이프라인 완료 기준으로).
    try:
        mtime = _RANK_FILE.stat().st_mtime
    except OSError:
        mtime = None
    if mtime is not None and mtime != _rank_loaded_mtime:
        _realtor_cache.clear()
        _rank_loaded_mtime = mtime
    cached = _cache_get("ranks")
    if cached is not None:
        return cached
    out = None
    if _RANK_FILE.exists():
        try:
            with open(_RANK_FILE, "rb") as f:
                out = pickle.load(f)
        except Exception:
            out = None
    if out is None:
        out = _build_ranks()            # 파일 없으면 라이브 빌드(느림) 후 저장
        try:
            with open(_RANK_FILE, "wb") as f:
                pickle.dump(out, f)
        except OSError:
            pass
    _cache_put("ranks", out)
    return out


def persist_ranks() -> None:
    """랭킹을 새로 빌드해 영속 파일에 저장. daily_run(build_api_cache)에서 호출 —
    서버는 이 파일을 즉시 로드하므로 realtor 페이지가 항상 빠르다."""
    out = _build_ranks()
    with open(_RANK_FILE, "wb") as f:
        pickle.dump(out, f)


def _build_ranks() -> dict:
    """listings_current 를 GROUP BY 해 랭킹을 라이브 계산(35~112s). 직접 호출 금지 —
    _rank_tables()/persist_ranks() 를 통해서만."""
    with _open_db() as c:
        nat_rows = c.execute(
            """
            SELECT realtor_id, MAX(realtor_name) AS realtor_name, COUNT(*) AS n
            FROM listings_current WHERE realtor_id IS NOT NULL
            GROUP BY realtor_id
            """
        ).fetchall()
        sido_rows = c.execute(
            """
            SELECT substr(c.cortar_no,1,2) AS sido,
                   l.realtor_id, MAX(l.realtor_name) AS realtor_name, COUNT(*) AS n
            FROM listings_current l
            JOIN complexes c ON c.complex_no = l.complex_no
            WHERE l.realtor_id IS NOT NULL AND c.cortar_no IS NOT NULL
            GROUP BY sido, l.realtor_id
            """
        ).fetchall()
        sido_names = {
            r[0][:2]: r[1]
            for r in c.execute(
                "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city'"
            )
        }
    nat_sorted = sorted(nat_rows, key=lambda r: -r[2])
    national: dict[str, tuple[int, int, str]] = {
        rid: (i + 1, n, name) for i, (rid, name, n) in enumerate(nat_sorted)
    }
    by_sido: dict[str, list[tuple[str, str, int]]] = {}
    for sido, rid, name, n in sido_rows:
        by_sido.setdefault(sido, []).append((rid, name, n))
    sido_rank: dict[tuple[str, str], tuple[int, int, str]] = {}
    sido_totals: dict[str, int] = {}
    for sido, items in by_sido.items():
        items.sort(key=lambda r: -r[2])
        sido_totals[sido] = len(items)
        for i, (rid, name, n) in enumerate(items):
            sido_rank[(sido, rid)] = (i + 1, n, name)
    out = {
        "national": national,
        "sido_rank": sido_rank,
        "sido_totals": sido_totals,
        "sido_names": sido_names,
        "national_total": len(nat_sorted),
    }
    return out


@app.get("/realtor/{realtor_id}")
def realtor_detail(realtor_id: str):
    """중개사 상세: 전국 등수, 시도별 등수, 단지별 매물 집계."""
    ranks = _rank_tables()
    nat = ranks["national"].get(realtor_id)
    if not nat:
        raise HTTPException(404, "realtor not found")
    nat_rank, total_count, realtor_name = nat
    by_sido_out = []
    for (sido, rid), (rk, n, _name) in ranks["sido_rank"].items():
        if rid == realtor_id:
            by_sido_out.append({
                "sido_code": sido,
                "sido_name": ranks["sido_names"].get(sido, sido),
                "count": n,
                "rank": rk,
                "total_in_sido": ranks["sido_totals"].get(sido, 0),
            })
    by_sido_out.sort(key=lambda r: -r["count"])

    with _open_db() as c:
        cx_rows = c.execute(
            """
            SELECT l.complex_no, c.complex_name, l.trade_type, COUNT(*) AS n
            FROM listings_current l
            LEFT JOIN complexes c ON c.complex_no = l.complex_no
            WHERE l.realtor_id = ?
            GROUP BY l.complex_no, l.trade_type
            """,
            (realtor_id,),
        ).fetchall()
    by_complex_map: dict[str, dict] = {}
    for cno, cname, t, n in cx_rows:
        key = cno or "__none__"
        e = by_complex_map.setdefault(key, {
            "complex_no": cno, "complex_name": cname,
            "A1": 0, "B1": 0, "B2": 0, "total": 0,
        })
        if t in ("A1", "B1", "B2"):
            e[t] += n
        e["total"] += n
    by_complex = sorted(by_complex_map.values(), key=lambda r: -r["total"])

    # Naver 중개사 정보 (naver_realtors)
    naver_info = None
    with _open_db() as c:
        nr = c.execute(
            """
            SELECT realtor_name, representative_name, address,
                   representative_tel_no, cell_phone_no, home_page_url,
                   latitude, longitude, deal_count, lease_count, rent_count
            FROM naver_realtors WHERE realtor_id = ?
            """,
            (realtor_id,),
        ).fetchone()
        if nr:
            naver_info = {
                "name": nr[0], "representative": nr[1], "address": nr[2],
                "tel": nr[3], "cell": nr[4], "homepage": nr[5],
                "latitude": nr[6], "longitude": nr[7],
                "deal_count": nr[8], "lease_count": nr[9], "rent_count": nr[10],
            }

    # vworld 매칭 정보 (realtor_match 테이블) + 직원 카운트
    vworld_match = None
    with _open_db() as c:
        row = c.execute(
            """
            SELECT m.match_type, m.sys_regno, m.vworld_name, m.vworld_rep,
                   m.candidates_json, b.address, b.phone, b.status,
                   b.registered_ymd, b.ra_regno
            FROM realtor_match m
            LEFT JOIN vworld_brokers b ON b.sys_regno = m.sys_regno
            WHERE m.realtor_id = ?
            """,
            (realtor_id,),
        ).fetchone()
        if row:
            import json as _json
            cands = _json.loads(row[4]) if row[4] else []
            sys_regno = row[1]
            # 직원 카운트 (개인 이름 노출 안 함)
            licensed = assistant = 0
            if sys_regno:
                emp_rows = c.execute(
                    "SELECT role, COUNT(*) FROM vworld_employees "
                    "WHERE sys_regno=? GROUP BY role",
                    (sys_regno,),
                ).fetchall()
                for role, n in emp_rows:
                    if role in ("공인중개사", "중개인", "법인"):
                        licensed += n
                    elif role == "중개보조원":
                        assistant += n
            vworld_match = {
                "match_type": row[0],
                "sys_regno": sys_regno,
                "name": row[2],
                "representative": row[3],
                "address": row[5],
                "phone": row[6],
                "status": row[7],
                "registered_ymd": row[8],
                "ra_regno": row[9],
                "candidates": cands,
                "employees": {
                    "licensed": licensed,
                    "assistant": assistant,
                    "total": licensed + assistant,
                },
            }

    return {
        "realtor_id": realtor_id,
        "realtor_name": realtor_name,
        "total_count": total_count,
        "national_rank": nat_rank,
        "national_total": ranks["national_total"],
        "by_sido": by_sido_out,
        "by_complex": by_complex,
        "vworld": vworld_match,
        "naver": naver_info,
    }


@app.get("/complex/{complex_no}/summary")
def complex_summary(complex_no: str):
    """단지 종합 대시보드 — 역대최고가·최근실거래(최고가표시)·평형별 호가(최저/최고)·매물수."""
    with _open_db() as d:
        cx = d.execute(
            "SELECT complex_name, total_household_count, use_approve_ymd, construction_company, "
            "dong_name, real_estate_type_name, total_building_count, parking_per_household, "
            "latitude, longitude FROM complexes WHERE complex_no=?", (complex_no,)).fetchone()
        if not cx:
            raise HTTPException(404, "complex not found")
        reg = d.execute(
            "SELECT rsi.cortar_name, rsg.cortar_name, rdo.cortar_name FROM complexes cx "
            "LEFT JOIN regions rsi ON rsi.cortar_no=substr(cx.cortar_no,1,2)||'00000000' "
            "LEFT JOIN regions rsg ON rsg.cortar_no=substr(cx.cortar_no,1,5)||'00000' "
            "LEFT JOIN regions rdo ON rdo.cortar_no=cx.cortar_no WHERE cx.complex_no=?", (complex_no,)).fetchone()
        region = " ".join(x for x in [
            (_SIDO_SHORT.get(reg[0], reg[0]) if reg else None), (reg[1] if reg else None), (reg[2] if reg else None)] if x)
        # 역대 최고가 = 매매계열(매매+분양권)만. 전세/월세 record 혼입 방지.
        rec = d.execute("SELECT area_key, record_price, record_date, prev_high FROM tx_record_rollup "
                        "WHERE complex_no=? AND kind IN ('sale','silv','offi_sale') ORDER BY record_price DESC LIMIT 1",
                        (complex_no,)).fetchone()
        record_high = {"area_key": rec[0], "price": rec[1], "date": rec[2], "prev_high": rec[3]} if rec else None
        # 최근 실거래 = 매매 + 분양권 통합(신축 분양권 단지는 매매가 없어 비어 보이던 문제 수정).
        rtx = d.execute(
            "SELECT deal_ymd, deal_amount, excl_use_ar, floor, 0 AS is_silv FROM transactions "
            "WHERE matched_complex_no=? AND is_cancelled=0 "
            "UNION ALL "
            "SELECT deal_ymd, deal_amount, excl_use_ar, floor, 1 AS is_silv FROM silv_transactions "
            "WHERE matched_complex_no=? AND is_cancelled=0 "
            "ORDER BY deal_ymd DESC LIMIT 8", (complex_no, complex_no)).fetchall()
        recent_tx = [{"date": r[0], "price": r[1], "area": r[2], "floor": r[3], "is_silv": bool(r[4])} for r in rtx]
        cnt = {"A1": 0, "B1": 0, "B2": 0}
        for t, n in d.execute("SELECT trade_type, COUNT(*) FROM listings_current WHERE complex_no=? GROUP BY trade_type", (complex_no,)):
            if t in cnt:
                cnt[t] = n
        cnt["total"] = cnt["A1"] + cnt["B1"] + cnt["B2"]
        rows = d.execute(
            "SELECT area_name, trade_type, COUNT(*), MIN(deal_or_warrant_price), MAX(deal_or_warrant_price) "
            "FROM listings_current WHERE complex_no=? AND deal_or_warrant_price>0 AND deal_or_warrant_price<1000000000000 "
            "GROUP BY area_name, trade_type", (complex_no,)).fetchall()
        # 타입명(area_name) → 전용/공급 면적·세대수 (complex_areas: pyeong_name == listings.area_name)
        areas_map = {pn: (sup, exc, hh) for pn, sup, exc, hh in d.execute(
            "SELECT pyeong_name, supply_area, exclusive_area, household_count FROM complex_areas WHERE complex_no=?",
            (complex_no,)).fetchall()}
    types: dict = {}
    for area, t, n, mn, mx in rows:
        e = types.setdefault(area, {"area_name": area, "sale_count": 0, "sale_min": None, "sale_max": None,
                                    "jeonse_count": 0, "jeonse_min": None, "jeonse_max": None, "rent_count": 0,
                                    "supply_area": None, "exclusive_area": None, "type_households": None})
        am = areas_map.get(area)
        if am:
            e["supply_area"], e["exclusive_area"], e["type_households"] = am[0], am[1], am[2]
        if t == "A1":
            e["sale_count"], e["sale_min"], e["sale_max"] = n, mn, mx
        elif t == "B1":
            e["jeonse_count"], e["jeonse_min"], e["jeonse_max"] = n, mn, mx
        elif t == "B2":
            e["rent_count"] = n
    by_type = sorted(types.values(), key=lambda x: -(x["sale_max"] or x["jeonse_max"] or 0))
    return {
        "complex_no": complex_no, "complex_name": cx[0], "region": region, "households": cx[1],
        "use_approve_ymd": cx[2], "builder": cx[3], "dong_name": cx[4], "asset_type": cx[5],
        "building_count": cx[6], "parking_per_household": cx[7],
        "latitude": cx[8], "longitude": cx[9],
        "record_high": record_high,
        "recent_tx": recent_tx, "recent_high": max((x["price"] for x in recent_tx), default=None),
        "listing_counts": cnt, "by_type": by_type,
    }


@app.get("/complex/{complex_no}/areas")
def complex_areas_endpoint(complex_no: str):
    """단지 면적타입별 구성 (Naver 단지 detail 기반): 면적타입/공급/전용/세대수."""
    with _open_db() as c:
        rows = c.execute(
            """
            SELECT pyeong_name, supply_area, exclusive_area, household_count
            FROM complex_areas WHERE complex_no = ?
            ORDER BY supply_area
            """,
            (complex_no,),
        ).fetchall()
    return {
        "complex_no": complex_no,
        "items": [
            {"pyeong_name": r[0], "supply_area": r[1],
             "exclusive_area": r[2], "household_count": r[3]}
            for r in rows
        ],
    }


@app.get("/complex/{complex_no}/realtors")
def complex_realtors(complex_no: str, limit: int = 10):
    """단지별 매물 보유 상위 N개 중개사 + 거래종류 분포 / 사무소 정보 / 전화번호."""
    if limit < 1 or limit > 50:
        raise HTTPException(400, "limit out of range")
    with _open_db() as c:
        rows = c.execute(
            """
            SELECT realtor_id,
                   MAX(realtor_name) AS realtor_name,
                   COUNT(*) AS n,
                   SUM(CASE WHEN trade_type='A1' THEN 1 ELSE 0 END) AS n_sale,
                   SUM(CASE WHEN trade_type='B1' THEN 1 ELSE 0 END) AS n_jeonse,
                   SUM(CASE WHEN trade_type='B2' THEN 1 ELSE 0 END) AS n_wolse,
                   AVG(CASE WHEN trade_type='A1' AND deal_or_warrant_price>0
                            THEN deal_or_warrant_price END) AS avg_sale_price
            FROM listings_current
            WHERE complex_no = ? AND realtor_id IS NOT NULL
            GROUP BY realtor_id
            ORDER BY n DESC
            LIMIT ?
            """,
            (complex_no, limit),
        ).fetchall()

        # 사무소 정보 (national 엔드포인트와 같은 enrichment).
        info: dict[str, dict] = {}
        ids = [r[0] for r in rows]
        if ids:
            ph = ",".join("?" * len(ids))
            sido_names = {
                r[0][:2]: r[1]
                for r in c.execute(
                    "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city'"
                )
            }
            for er in c.execute(
                f"""
                SELECT nr.realtor_id, nr.realtor_name, nr.cortar_no,
                       vb.registered_ymd,
                       (SELECT COUNT(*) FROM vworld_employees ve
                        WHERE ve.sys_regno = rm.sys_regno) AS emp,
                       nr.representative_tel_no, nr.cell_phone_no
                FROM naver_realtors nr
                LEFT JOIN realtor_match rm ON rm.realtor_id = nr.realtor_id
                LEFT JOIN vworld_brokers vb ON vb.sys_regno = rm.sys_regno
                WHERE nr.realtor_id IN ({ph})
                """,
                ids,
            ):
                cortar = er[2] or ""
                reg = er[3] or ""
                info[er[0]] = {
                    "office_name": er[1],
                    "sido": sido_names.get(cortar[:2]) if cortar else None,
                    "established_year": reg[:4] if len(reg) >= 4 else None,
                    "staff_count": er[4] or None,
                    "tel": er[5] or er[6] or None,
                }

        # 각 중개사의 전국 총 매물 수
        total_by_id: dict[str, int] = {}
        if ids:
            ph = ",".join("?" * len(ids))
            for tid, n in c.execute(
                f"""
                SELECT realtor_id, COUNT(*)
                FROM listings_current
                WHERE realtor_id IN ({ph})
                GROUP BY realtor_id
                """,
                ids,
            ):
                total_by_id[tid] = n

    items = []
    for r in rows:
        e = info.get(r[0], {})
        items.append({
            "realtor_id": r[0],
            "realtor_name": e.get("office_name") or r[1],
            "count": r[2],
            "n_sale": r[3],
            "n_jeonse": r[4],
            "n_wolse": r[5],
            "avg_sale_price": r[6],
            "sido": e.get("sido"),
            "established_year": e.get("established_year"),
            "staff_count": e.get("staff_count"),
            "tel": e.get("tel"),
            "total_listings": total_by_id.get(r[0]),
        })
    return {"complex_no": complex_no, "items": items}


@app.get("/complex/{complex_no}/quick-deals")
def complex_quick_deals(
    complex_no: str,
    days: int = 90,
    trade_type: str = "A1",       # A1=매매 | B1=전세
    min_discount: float = 0.05,   # 최근 실거래 평균 대비 N% 이상 저렴
    max_discount: float = 0.5,    # 극단치 컷
    min_samples: int = 3,         # 평형별 실거래 N건 이상이어야 기준 인정
    limit: int = 50,
):
    """단지 내 급매 매물 + 보유 중개사 연락처.
    평형(area_name)별 최근 N일 실거래 평균을 기준으로, 호가가 그 평균보다
    min_discount 이상 싼 개별 매물을 골라 중개사 전화번호와 함께 반환."""
    if trade_type not in ("A1", "B1"):
        raise HTTPException(400, "trade_type must be A1|B1")
    if trade_type == "A1":
        tx_tbl, amount_col = "transactions", "tx.deal_amount"
        extra = "AND COALESCE(tx.dealing_gbn,'') <> '직거래' AND tx.is_cancelled = 0"
    else:
        tx_tbl, amount_col = "rentals", "tx.deposit"
        extra = "AND COALESCE(tx.monthly_rent,0) = 0"
    cutoff = f"-{days} days"
    area_tol = 5.0

    with _open_db() as c:
        # 평형(area_name)별 실거래 평균 — 단지 1개라 가볍다
        real = c.execute(
            f"""
            SELECT pyeong, AVG(amount) AS avg_real, COUNT(*) AS n_real FROM (
              SELECT ca.pyeong_name AS pyeong, {amount_col} AS amount,
                     ROW_NUMBER() OVER (PARTITION BY tx.rowid
                       ORDER BY ABS(ca.exclusive_area - tx.excl_use_ar)) AS rn
              FROM {tx_tbl} tx
              JOIN complex_areas ca ON ca.complex_no = tx.matched_complex_no
                AND ca.exclusive_area IS NOT NULL
                AND ABS(ca.exclusive_area - tx.excl_use_ar) <= {area_tol}
              WHERE tx.matched_complex_no = ?
                AND tx.deal_ymd >= date('now', ?)
                AND tx.excl_use_ar IS NOT NULL {extra}
                AND tx.matched_score >= 0.85
            ) WHERE rn = 1 AND pyeong IS NOT NULL
            GROUP BY pyeong HAVING COUNT(*) >= ?
            """,
            (complex_no, cutoff, min_samples),
        ).fetchall()
        avg_by_area = {r[0]: (r[1], r[2]) for r in real}
        if not avg_by_area:
            return {"complex_no": complex_no, "count": 0, "items": []}

        listings = c.execute(
            """
            SELECT article_no, area_name, floor_info, direction,
                   deal_or_warrant_price, deal_or_warrant_price_text,
                   realtor_id, realtor_name, article_confirm_ymd, cp_pc_article_url
            FROM listings_current
            WHERE complex_no = ? AND trade_type = ? AND deal_or_warrant_price > 0
              AND area_name IS NOT NULL
            """,
            (complex_no, trade_type),
        ).fetchall()

        ids = list({r[6] for r in listings if r[6]})
        contact: dict[str, dict] = {}
        if ids:
            ph = ",".join("?" * len(ids))
            for er in c.execute(
                f"""SELECT realtor_id, realtor_name, representative_tel_no,
                          cell_phone_no, address
                   FROM naver_realtors WHERE realtor_id IN ({ph})""",
                ids,
            ):
                contact[er[0]] = {"office": er[1], "tel": er[2] or er[3], "addr": er[4]}

        # realtor_id 가 NULL 인 매물(전국 매매의 ~5.6%) → 이름+지역으로 안전 역매칭.
        # 같은 시군구 단일 매칭이거나 전국에서 이름이 고유할 때만 연결(동명 다수는 미연결).
        null_names = list({r[7] for r in listings if not r[6] and r[7]})
        name_fallback: dict[str, dict] = {}
        if null_names:
            crow = c.execute("SELECT cortar_no FROM complexes WHERE complex_no=?",
                             (complex_no,)).fetchone()
            sgg = ((crow[0] or "")[:5]) if crow else ""
            ph2 = ",".join("?" * len(null_names))
            cand: dict[str, list] = {}
            for er in c.execute(
                f"""SELECT realtor_name, realtor_id, representative_tel_no, cell_phone_no, cortar_no
                    FROM naver_realtors WHERE realtor_name IN ({ph2})""", null_names):
                cand.setdefault(er[0], []).append((er[1], er[2] or er[3], er[4] or ""))
            for nm, lst in cand.items():
                same = [x for x in lst if x[2][:5] == sgg]
                pick = same[0] if len(same) == 1 else (lst[0] if len(lst) == 1 else None)
                if pick:
                    name_fallback[nm] = {"realtor_id": pick[0], "tel": pick[1]}

    items = []
    for r in listings:
        ar = avg_by_area.get(r[1])
        if not ar:
            continue
        avg_real, n_real = ar
        disc = (r[4] - avg_real) / avg_real
        if disc > -abs(min_discount) or disc < -abs(max_discount):
            continue
        ct = contact.get(r[6], {})
        rid, tel = r[6], ct.get("tel")
        office, addr = ct.get("office") or r[7], ct.get("addr")
        if not rid and r[7] in name_fallback:        # realtor_id 없으면 이름 역매칭 결과 사용
            rid, tel = name_fallback[r[7]]["realtor_id"], name_fallback[r[7]]["tel"]
        items.append({
            "article_no": r[0], "area_name": r[1], "floor_info": r[2],
            "direction": r[3], "price": r[4], "price_text": r[5],
            "discount": disc, "avg_real": avg_real, "n_real": n_real,
            "realtor_id": rid, "realtor_name": office,
            "tel": tel, "addr": addr,
            "confirm_ymd": r[8], "article_url": r[9],
            # 네이버 정식 매물 딥링크 (article_no 로 구성). CP(매경 등) 리다이렉트 대신 네이버로.
            "naver_url": f"https://new.land.naver.com/complexes/{complex_no}?articleNo={r[0]}",
        })
    items.sort(key=lambda x: x["discount"])
    return {"complex_no": complex_no, "count": len(items), "items": items[:limit]}


# 공급면적 평형 bucket (㎡ 단위로 환산)
# 공급면적 = 전용면적 × 1.33 (일반 아파트 전용율 ~0.77)
# 10평 = 33㎡, 20평 = 66㎡, 30평 = 99㎡, 40평 = 132㎡, 50평 = 165㎡
_AREA_BUCKETS_SUPPLY = {
    "under10": (None, 33),
    "10s": (33, 66),
    "20s": (66, 99),
    "30s": (99, 132),
    "40s": (132, 165),
    "over50": (165, None),
}


def _area_cond(col_excl: str, area_class: str | None, col_supply: str | None = "supply_area") -> tuple[str, list]:
    """col_excl = 전용면적, col_supply = listings 매핑으로 채워진 공급면적.
    정확도 위해 supply_area NULL인 행은 평형 필터 시 제외 (특히 오피스텔 전용율 가변).
    """
    if not area_class or area_class == "all":
        return "", []
    rng = _AREA_BUCKETS_SUPPLY.get(area_class)
    if not rng:
        return "", []
    lo, hi = rng
    if col_supply:
        # supply_area 있는 행만 필터 적용
        conds = [f"{col_supply} IS NOT NULL"]
        expr = col_supply
    else:
        conds = []
        expr = f"{col_excl} * 1.33"
    params: list = []
    if lo is not None:
        conds.append(f"{expr} >= ?")
        params.append(lo)
    if hi is not None:
        conds.append(f"{expr} < ?")
        params.append(hi)
    if not conds:
        return "", []
    return " AND " + " AND ".join(conds), params


# tx_area_rollup(area_key=ROUND(전용면적 m2)) 평형 버킷. 공급면적 버킷을 전용율 ~0.76 로
# 환산해 전용 m2 경계로. (랭킹 엔드포인트가 area_key 기준이라 전용 기준이 자연스럽다.)
_AREA_BUCKETS_KEY = {
    "under10": (None, 25), "10s": (25, 50), "20s": (50, 75),
    "30s": (75, 100), "40s": (100, 125), "over50": (125, None),
}


def _area_cond_key(area_class: str | None) -> tuple[str, list]:
    """tx_area_rollup.area_key(전용 m2) 평형 필터. (' AND area_key ...', params)."""
    if not area_class or area_class == "all":
        return "", []
    rng = _AREA_BUCKETS_KEY.get(area_class)
    if not rng:
        return "", []
    lo, hi = rng
    conds, params = [], []
    if lo is not None:
        conds.append("area_key >= ?"); params.append(lo)
    if hi is not None:
        conds.append("area_key < ?"); params.append(hi)
    return (" AND " + " AND ".join(conds), params) if conds else ("", [])


_area_rollup_ok: bool | None = None


def _area_rollup_ready() -> bool:
    """tx_area_rollup 존재+비어있지 않음(메모이즈)."""
    global _area_rollup_ok
    if _area_rollup_ok:
        return True
    try:
        with _open_db() as c:
            r = c.execute("SELECT EXISTS(SELECT 1 FROM tx_area_rollup LIMIT 1)").fetchone()
        _area_rollup_ok = bool(r and r[0])
    except Exception:  # noqa: BLE001
        _area_rollup_ok = False
    return _area_rollup_ok


_ASSET_TYPES = {
    "apt": ("APT", "JGC", "ABYG"),       # 아파트(재건축·분양권 포함)
    "offi": ("OPST", "OBYG"),            # 오피스텔(분양권 포함)
}


def _asset_type_clause(asset: str | None, alias: str = "cx") -> str:
    """asset(apt/offi) → complexes.real_estate_type 필터 SQL(' AND cx.real_estate_type IN (...)').
    타입값은 하드코딩 상수라 인젝션 안전. all/None 이면 빈 문자열."""
    t = _ASSET_TYPES.get(asset or "")
    if not t:
        return ""
    return f" AND {alias}.real_estate_type IN (" + ",".join(f"'{x}'" for x in t) + ")"


def _roll_region_clause(sido: str | None, sigungu: str | None,
                        dong: str | None = None) -> tuple[str, list]:
    """area 롤업용 지역 필터 — complex_no IN (해당 지역 단지)."""
    if dong:
        return (" AND complex_no IN (SELECT complex_no FROM complexes "
                "WHERE cortar_no = ?)", [dong])
    if sigungu:
        return (" AND complex_no IN (SELECT complex_no FROM complexes "
                "WHERE substr(cortar_no,1,5)=substr(?,1,5))", [sigungu])
    if sido:
        return (" AND complex_no IN (SELECT complex_no FROM complexes "
                "WHERE substr(cortar_no,1,2)=substr(?,1,2))", [sido])
    return "", []


def _mcn_region_clause(sido: str | None, sigungu: str | None,
                       dong: str | None = None) -> tuple[str, list]:
    """transactions/rentals 의 matched_complex_no 컬럼용 지역필터."""
    cond, params = _roll_region_clause(sido, sigungu, dong)
    return (cond.replace("complex_no IN", "matched_complex_no IN", 1), params)


def _cx_region_clause(sido: str | None, sigungu: str | None,
                      dong: str | None = None) -> tuple[str, list]:
    """complexes 별칭 cx 가 JOIN 된 쿼리용 지역필터 (cx.cortar_no 직접 비교)."""
    if dong:
        return (" AND cx.cortar_no = ?", [dong])
    if sigungu:
        return (" AND substr(cx.cortar_no,1,5)=substr(?,1,5)", [sigungu])
    if sido:
        return (" AND substr(cx.cortar_no,1,2)=substr(?,1,2)", [sido])
    return "", []


# 단지(cx) → 시도/시군구/동 3단계 지역명. SQL에 complexes 별칭 cx가 이미 JOIN돼 있어야 함.
_REGION_JOINS = (
    " LEFT JOIN regions rs ON rs.cortar_no = substr(cx.cortar_no,1,2)||'00000000'"
    " LEFT JOIN regions rg ON rg.cortar_no = substr(cx.cortar_no,1,5)||'00000'"
    " LEFT JOIN regions rd ON rd.cortar_no = cx.cortar_no"
)
_REGION_NAME_COL = (
    "TRIM(COALESCE(rs.cortar_name,'')||' '||COALESCE(rg.cortar_name,'')"
    "||' '||COALESCE(rd.cortar_name,'')) AS region_name"
)


@app.get("/stats/tx-top-price")
def tx_top_price(days: int = 30, trade: str = "A1", asset: str = "all",
                 dealing: str = "all", area_class: str = "all", sido: str | None = None,
                 sigungu: str | None = None, dong: str | None = None, limit: int = 100):
    """실거래 최고가 top N.
    trade: A1(매매)/B1(전세)/B2(월세)  asset: apt/offi/all  days: 1=하루, 365=1년, 0=전체"""
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit out of range")
    if days < 0 or days > 3650:
        raise HTTPException(400, "days out of range")
    cutoff = f"-{days} days"
    # dealing 필터 (매매만): all / broker(중개거래) / direct(직거래)
    dg_filter = ""
    if dealing == "broker":
        dg_filter = " AND dealing_gbn='중개거래'"
    elif dealing == "direct":
        dg_filter = " AND dealing_gbn='직거래'"
    # area_class 공급면적 평형 필터
    ac_filter, ac_params = _area_cond("excl_use_ar", area_class, col_supply=None)  # silv union 호환

    with _open_db() as c:
        existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        unions = []
        params: list = []
        # 거래 유형별 source 결정
        if trade == "A1":
            # 매매: deal_amount + dealing_gbn
            if asset in ("apt", "all") and "transactions" in existing:
                unions.append(
                    "SELECT deal_ymd, deal_amount AS price, NULL AS monthly_rent, "
                    "excl_use_ar, floor, build_year, matched_complex_no, dealing_gbn, 'apt' AS asset "
                    "FROM transactions WHERE matched_complex_no IS NOT NULL AND is_cancelled=0" + dg_filter + ac_filter
                    + (f" AND deal_ymd >= date('now', ?)" if days > 0 else "")
                )
                params.extend(ac_params)
                if days > 0: params.append(cutoff)
            # 분양권(silv): 매매 최고가와 통합(거래총액=실거래총액). 거래방식 필터 시 제외.
            if asset in ("apt", "all") and dealing == "all" and "silv_transactions" in existing:
                unions.append(
                    "SELECT deal_ymd, deal_amount AS price, NULL AS monthly_rent, "
                    "excl_use_ar, floor, NULL AS build_year, matched_complex_no, dealing_gbn, 'silv' AS asset "
                    "FROM silv_transactions WHERE matched_complex_no IS NOT NULL AND is_cancelled=0" + ac_filter
                    + (f" AND deal_ymd >= date('now', ?)" if days > 0 else "")
                )
                params.extend(ac_params)
                if days > 0: params.append(cutoff)
            if asset in ("offi", "all") and "offi_transactions" in existing:
                unions.append(
                    "SELECT deal_ymd, deal_amount AS price, NULL AS monthly_rent, "
                    "excl_use_ar, floor, build_year, matched_complex_no, dealing_gbn, 'offi' AS asset "
                    "FROM offi_transactions WHERE matched_complex_no IS NOT NULL AND is_cancelled=0" + dg_filter + ac_filter
                    + (f" AND deal_ymd >= date('now', ?)" if days > 0 else "")
                )
                params.extend(ac_params)
                if days > 0: params.append(cutoff)
        elif trade == "B1":
            # 전세: deposit (monthly_rent=0) — 전월세는 dealing_gbn 없음
            if asset in ("apt", "all") and "rentals" in existing:
                unions.append(
                    "SELECT deal_ymd, deposit AS price, monthly_rent, "
                    "excl_use_ar, floor, build_year, matched_complex_no, NULL AS dealing_gbn, 'apt' AS asset "
                    "FROM rentals WHERE matched_complex_no IS NOT NULL AND monthly_rent=0" + ac_filter
                    + (f" AND deal_ymd >= date('now', ?)" if days > 0 else "")
                )
                params.extend(ac_params)
                if days > 0: params.append(cutoff)
            if asset in ("offi", "all") and "offi_rentals" in existing:
                unions.append(
                    "SELECT deal_ymd, deposit AS price, monthly_rent, "
                    "excl_use_ar, floor, build_year, matched_complex_no, NULL AS dealing_gbn, 'offi' AS asset "
                    "FROM offi_rentals WHERE matched_complex_no IS NOT NULL AND monthly_rent=0" + ac_filter
                    + (f" AND deal_ymd >= date('now', ?)" if days > 0 else "")
                )
                params.extend(ac_params)
                if days > 0: params.append(cutoff)
        elif trade == "B2":
            # 월세: monthly_rent 우선
            if asset in ("apt", "all") and "rentals" in existing:
                unions.append(
                    "SELECT deal_ymd, deposit AS price, monthly_rent, "
                    "excl_use_ar, floor, build_year, matched_complex_no, NULL AS dealing_gbn, 'apt' AS asset "
                    "FROM rentals WHERE matched_complex_no IS NOT NULL AND monthly_rent>0" + ac_filter
                    + (f" AND deal_ymd >= date('now', ?)" if days > 0 else "")
                )
                params.extend(ac_params)
                if days > 0: params.append(cutoff)
            if asset in ("offi", "all") and "offi_rentals" in existing:
                unions.append(
                    "SELECT deal_ymd, deposit AS price, monthly_rent, "
                    "excl_use_ar, floor, build_year, matched_complex_no, NULL AS dealing_gbn, 'offi' AS asset "
                    "FROM offi_rentals WHERE matched_complex_no IS NOT NULL AND monthly_rent>0" + ac_filter
                    + (f" AND deal_ymd >= date('now', ?)" if days > 0 else "")
                )
                params.extend(ac_params)
                if days > 0: params.append(cutoff)
        else:
            raise HTTPException(400, "trade must be A1/B1/B2")
        if not unions:
            return {"items": []}

        order_col = "monthly_rent" if trade == "B2" else "price"
        reg_cond, reg_params = _cx_region_clause(sido, sigungu, dong)
        sql = (
            "SELECT t.*, cx.complex_name, " + _REGION_NAME_COL + " FROM ("
            + " UNION ALL ".join(unions) + ") t "
            "LEFT JOIN complexes cx ON cx.complex_no = t.matched_complex_no"
            + _REGION_JOINS +
            " WHERE 1=1" + reg_cond +
            f" ORDER BY t.{order_col} DESC LIMIT ?"
        )
        rows = c.execute(sql, [*params, *reg_params, limit]).fetchall()
    # 카드 스파크라인용 월별 추이 (단지×ROUND(전용)) — 매매/전세만
    tmap = _price_trend_map([r["matched_complex_no"] for r in rows], trade)
    items = []
    for r in rows:
        ar = r["excl_use_ar"]
        items.append({
            "deal_ymd": r["deal_ymd"],
            "price": r["price"], "monthly_rent": r["monthly_rent"],
            "excl_use_ar": ar, "floor": r["floor"],
            "build_year": r["build_year"],
            "complex_no": r["matched_complex_no"],
            "complex_name": r["complex_name"],
            "region_name": r["region_name"],
            "dealing_gbn": r["dealing_gbn"],
            "asset": r["asset"],
            "trend": tmap.get((r["matched_complex_no"], round(ar)), []) if ar is not None else [],
        })
    return {"trade": trade, "asset": asset, "days": days, "dealing": dealing, "items": items}


def _price_trend_map(complex_nos: list, trade: str | None, months: int = 18) -> dict:
    """단지들의 (complex_no, ROUND(전용면적))별 월별 실거래 평균 추이 — 카드 스파크라인용.
    tx_record_high 의 area_key(=CAST(ROUND(excl_use_ar))) 그룹핑과 동일하게 묶어 매칭.
    소수 단지로 스코핑돼 빠르다. trade 미지원이면 빈 dict."""
    nos = list({n for n in complex_nos if n})
    table, amt, extra = ({"A1": ("transactions", "deal_amount", " AND is_cancelled=0"),
                          "B1": ("rentals", "deposit", " AND monthly_rent=0"),
                          "B2": ("rentals", "monthly_rent", " AND monthly_rent>0")}
                         ).get(trade or "", (None, None, None))
    if not nos or not table:
        return {}
    out: dict = {}
    ph = ",".join("?" * len(nos))
    with _open_db() as c:
        rows = c.execute(
            f"SELECT matched_complex_no, CAST(ROUND(excl_use_ar) AS INTEGER) ak, "
            f"  substr(deal_ymd,1,7) ym, ROUND(AVG({amt})) avg "
            f"FROM {table} WHERE matched_complex_no IN ({ph}) "
            f"  AND excl_use_ar IS NOT NULL AND matched_score>=0.85 "
            f"  AND deal_ymd>=date('now', ?){extra} "
            f"GROUP BY 1, 2, ym ORDER BY ym",
            (*nos, f"-{months} months")).fetchall()
    for r in rows:
        out.setdefault((r[0], r[1]), []).append({"ym": r[2], "avg": r[3]})
    return out


@app.get("/stats/tx-record-high")
def tx_record_high(days: int = 90, trade: str = "A1", asset: str = "all",
                   area_class: str = "all", min_prior: int = 1,
                   sido: str | None = None, sigungu: str | None = None, dong: str | None = None,
                   max_gap_months: float = 0, order: str = "premium", limit: int = 200):
    """단지×타입(전용면적)별 신고가 경신.
    - 그룹(단지×전용면적)의 역대 최고가(record)가 최근 days일 내에 나왔고, 직전
      최고가(prev_high)를 초과한 = '신고가 경신' 케이스만 반환.
    - months_since: 직전 고가 거래일 → 신고가 거래일까지 걸린 개월 수.
    - trade A1(매매)/B1(전세)/B2(월세), asset apt/offi/all.
    - order: premium(상승률 큰 순, default) / recent(경신일 최신 순) / price(거래가격 높은 순)."""
    if limit < 1 or limit > 1000:
        raise HTTPException(400, "limit out of range")
    if days < 1 or days > 3650:
        raise HTTPException(400, "days out of range")
    if not _area_rollup_ready():
        raise HTTPException(503, "tx_area_rollup 미빌드 — build_tx_rollups.py 실행 필요")
    ackey_cond, ackey_params = _area_cond_key(area_class)
    reg_cond, reg_params = _cx_region_clause(sido, sigungu, dong)

    # trade → 롤업 kind(매매/전세/월세) + floor 룩업용 라이브 소스(테이블·가격컬럼·조건).
    if trade == "A1":
        cand = [("transactions", "deal_amount", "is_cancelled=0", "apt", "sale"),
                ("silv_transactions", "deal_amount", "is_cancelled=0", "apt", "silv"),
                ("offi_transactions", "deal_amount", "is_cancelled=0", "offi", "offi_sale")]
    elif trade == "B1":
        cand = [("rentals", "deposit", "monthly_rent=0", "apt", "jeonse"),
                ("offi_rentals", "deposit", "monthly_rent=0", "offi", "offi_jeonse")]
    elif trade == "B2":
        cand = [("rentals", "monthly_rent", "monthly_rent>0", "apt", "wolse"),
                ("offi_rentals", "monthly_rent", "monthly_rent>0", "offi", "offi_wolse")]
    else:
        raise HTTPException(400, "trade must be A1/B1/B2")

    with _open_db() as c:
        existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        sources = [(t, px, ex) for (t, px, ex, ag, _k) in cand
                   if asset in (ag, "all") and t in existing]
        kinds = [k for (t, px, ex, ag, k) in cand if asset in (ag, "all") and t in existing]
        if not sources:
            return {"items": []}

        # 신고가 거래의 층수: 최종 결과(rec) 행에 대해서만 라이브 인덱스로 조회. 결과 행 수만.
        def _floor_lookup(date_col: str, price_col: str) -> str:
            subqs = [
                f"(SELECT floor FROM {tbl} WHERE matched_complex_no = base.cno "
                f"AND CAST(ROUND(excl_use_ar) AS INTEGER) = base.area_key "
                f"AND deal_ymd = base.{date_col} AND {price_expr} = base.{price_col}"
                f"{(' AND ' + extra) if extra else ''} LIMIT 1)"
                for tbl, price_expr, extra in sources
            ]
            if not subqs:
                return "NULL"
            if len(subqs) == 1:
                return subqs[0]  # COALESCE는 인자 2개 미만이면 SQL 에러
            return "COALESCE(" + ", ".join(subqs) + ")"

        floor_expr = _floor_lookup("record_date", "record_price")       # 신고가 거래 층
        prev_floor_expr = _floor_lookup("prev_date", "prev_high")        # 직전고가 거래 층

        order_sql = ({"recent": "record_date DESC", "price": "record_price DESC",
                      "premium": "premium DESC"}).get(order, "premium DESC")
        # 경신 간격(직전 신고가 최초 수립일 → 새 신고가) 상한 필터. 0/음수면 제한 없음.
        gap_cond, gap_params = "", []
        if max_gap_months and max_gap_months > 0:
            gap_cond = " AND (julianday(rr.record_date) - julianday(rr.prev_date)) <= ?"
            gap_params = [max_gap_months * 30.44]
        # 단지×평형당 1행짜리 record 사전집계(tx_record_rollup)에서 바로 필터·정렬.
        # floor(층)만 결과 행에 대해 라이브 인덱스로 룩업(정렬·LIMIT 후 base 바깥).
        kph = ",".join("?" * len(kinds))
        sql = f"""
        SELECT base.*, {floor_expr} AS floor, {prev_floor_expr} AS prev_floor FROM (
          SELECT rr.complex_no AS cno, rr.area_key, rr.record_price, rr.record_date, rr.n_total,
                 rr.prev_high, rr.n_prior, rr.prev_date, rr.kind AS rec_kind,
                 (rr.record_price - rr.prev_high) * 1.0 / rr.prev_high AS premium,
                 (julianday(rr.record_date) - julianday(rr.prev_date)) AS days_since,
                 cx.complex_name, cx.cortar_no, cx.total_household_count,
                 TRIM(COALESCE(rs.cortar_name,'')||' '||COALESCE(rg.cortar_name,'')
                      ||' '||COALESCE(rd.cortar_name,'')) AS region_name
          FROM tx_record_rollup rr
          LEFT JOIN complexes cx ON cx.complex_no = rr.complex_no
          LEFT JOIN regions rs ON rs.cortar_no = substr(cx.cortar_no,1,2)||'00000000'
          LEFT JOIN regions rg ON rg.cortar_no = substr(cx.cortar_no,1,5)||'00000'
          LEFT JOIN regions rd ON rd.cortar_no = cx.cortar_no
          WHERE rr.kind IN ({kph}){ackey_cond}{reg_cond}
            AND rr.record_date >= date('now', ?)
            AND rr.n_prior >= ?
            AND rr.prev_high > 0
            AND rr.record_price > rr.prev_high{gap_cond}
          ORDER BY {order_sql} LIMIT ?
        ) base
        """
        params = [*kinds, *ackey_params, *reg_params, f"-{days} days", min_prior, *gap_params, limit]
        rows = c.execute(sql, params).fetchall()

    # 카드 스파크라인용 월별 실거래 추이 (단지×ROUND(전용면적))
    tmap = _price_trend_map([r["cno"] for r in rows], trade)

    items = []
    for r in rows:
        ds = r["days_since"]
        items.append({
            "complex_no": r["cno"],
            "complex_name": r["complex_name"],
            "cortar_no": r["cortar_no"],
            "region_name": r["region_name"],
            "households": r["total_household_count"],
            "area_key": r["area_key"],
            "asset": "silv" if r["rec_kind"] == "silv" else ("offi" if str(r["rec_kind"]).startswith("offi") else "apt"),
            "floor": r["floor"],
            "prev_floor": r["prev_floor"],
            "record_price": r["record_price"],
            "record_date": r["record_date"],
            "prev_high": r["prev_high"],
            "prev_date": r["prev_date"],
            "premium": r["premium"],
            "months_since": round(ds / 30.44, 1) if ds is not None else None,
            "n_total": r["n_total"],
            "n_prior": r["n_prior"],
            "trend": tmap.get((r["cno"], r["area_key"]), []),
        })
    return {"trade": trade, "asset": asset, "days": days, "order": order, "items": items}


@app.get("/stats/tx-top-volume")
def tx_top_volume(days: int = 30, trade: str = "A1", asset: str = "all",
                  dealing: str = "all", area_class: str = "all",
                  sido: str | None = None, sigungu: str | None = None, dong: str | None = None, limit: int = 100):
    """단지별 거래량 top N."""
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit out of range")
    if days < 0 or days > 3650:
        raise HTTPException(400, "days out of range")
    cutoff = f"-{days} days"
    reg_cond, reg_params = _cx_region_clause(sido, sigungu, dong)
    dg_extra = ""
    if dealing == "broker":
        dg_extra = "dealing_gbn='중개거래'"
    elif dealing == "direct":
        dg_extra = "dealing_gbn='직거래'"
    ac_cond, ac_params = _area_cond("excl_use_ar", area_class, col_supply=None)  # silv union 호환(전용*1.33로 평형필터)

    with _open_db() as c:
        existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        unions = []
        params: list = []
        def _src(tbl, asset_tag, extra=""):
            cond = "matched_complex_no IS NOT NULL"
            if extra: cond += f" AND {extra}"
            cond += ac_cond  # ' AND excl_use_ar * 1.33 >= ?' 형식, 이미 leading AND 포함
            extra_params = list(ac_params)
            if days > 0:
                cond += " AND deal_ymd >= date('now', ?)"
                extra_params.append(cutoff)
            return (
                f"SELECT matched_complex_no, '{asset_tag}' AS asset FROM {tbl} WHERE {cond}",
                extra_params,
            )

        if trade == "A1":
            # 매매: 해제거래 제외 + (선택) 거래방식 필터
            sale_extra = "is_cancelled=0" + (f" AND {dg_extra}" if dg_extra else "")
            if asset in ("apt", "all") and "transactions" in existing:
                s, p = _src("transactions", "apt", sale_extra); unions.append(s); params.extend(p)
            # 분양권(silv): 매매 실거래와 통합 집계(사용자 멘탈모델). 거래방식 필터 시엔 제외(분양권엔 무의미).
            if asset in ("apt", "all") and dealing == "all" and "silv_transactions" in existing:
                s, p = _src("silv_transactions", "silv", "is_cancelled=0"); unions.append(s); params.extend(p)
            if asset in ("offi", "all") and "offi_transactions" in existing:
                s, p = _src("offi_transactions", "offi", sale_extra); unions.append(s); params.extend(p)
        elif trade == "B1":
            if asset in ("apt", "all") and "rentals" in existing:
                s, p = _src("rentals", "apt", "monthly_rent=0"); unions.append(s); params.extend(p)
            if asset in ("offi", "all") and "offi_rentals" in existing:
                s, p = _src("offi_rentals", "offi", "monthly_rent=0"); unions.append(s); params.extend(p)
        elif trade == "B2":
            if asset in ("apt", "all") and "rentals" in existing:
                s, p = _src("rentals", "apt", "monthly_rent>0"); unions.append(s); params.extend(p)
            if asset in ("offi", "all") and "offi_rentals" in existing:
                s, p = _src("offi_rentals", "offi", "monthly_rent>0"); unions.append(s); params.extend(p)
        else:
            raise HTTPException(400, "trade must be A1/B1/B2")
        if not unions:
            return {"items": []}

        sql = (
            "WITH agg AS (SELECT matched_complex_no AS cno, COUNT(*) AS n, "
            "SUM(CASE WHEN asset='silv' THEN 1 ELSE 0 END) AS silv_n "
            "FROM (" + " UNION ALL ".join(unions) + ") "
            "GROUP BY matched_complex_no) "
            "SELECT agg.cno, agg.n, agg.silv_n, cx.complex_name, cx.cortar_no, cx.total_household_count, "
            + _REGION_NAME_COL +
            " FROM agg LEFT JOIN complexes cx ON cx.complex_no = agg.cno"
            + _REGION_JOINS +
            " WHERE 1=1" + reg_cond +
            " ORDER BY agg.n DESC LIMIT ?"
        )
        rows = c.execute(sql, [*params, *reg_params, limit]).fetchall()
    return {
        "trade": trade, "asset": asset, "days": days, "dealing": dealing,
        "items": [
            {
                "complex_no": r["cno"],
                "complex_name": r["complex_name"],
                "cortar_no": r["cortar_no"],
                "region_name": r["region_name"],
                "households": r["total_household_count"],
                "count": r["n"],
                "silv_count": r["silv_n"] or 0,   # 이 중 분양권 건수(투명 표기용)
            }
            for r in rows
        ],
    }


@app.get("/stats/tx-low-price")
def tx_low_price(days: int = 180, discount: float = 0.20, min_samples: int = 3,
                 asset: str = "all", area_class: str = "all", sido: str | None = None,
                 sigungu: str | None = None, dong: str | None = None, limit: int = 200):
    """단지×평형 평균보다 N% 이상 저렴한 매매 거래 (증여 의심 등 시세차이).
    - days: 최근 N일 기간 (default 180일 = 6개월)
    - discount: 평균 대비 할인율 (default 0.20 = 20%)
    - min_samples: (단지×평형) 그룹 평균 신뢰도용 최소 거래 건수
    """
    if not (0.0 <= discount <= 0.9):
        raise HTTPException(400, "discount must be 0.0~0.9")
    if days < 30 or days > 3650:
        raise HTTPException(400, "days out of range")
    if min_samples < 1 or min_samples > 100:
        raise HTTPException(400, "min_samples out of range")
    if limit < 1 or limit > 1000:
        raise HTTPException(400, "limit out of range")
    cutoff = f"-{days} days"
    ac_cond, ac_params = _area_cond("excl_use_ar", area_class, col_supply=None)  # silv union 호환(전용*1.33로 평형필터)
    reg_cond, reg_params = _mcn_region_clause(sido, sigungu, dong)   # 지역 좁힘(동필터 시 빠름)

    with _open_db() as c:
        existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        unions = []
        params: list = []
        if asset in ("apt", "all") and "transactions" in existing:
            unions.append("SELECT deal_ymd, deal_amount, excl_use_ar, floor, dealing_gbn, "
                          "matched_complex_no, 'apt' AS asset FROM transactions "
                          "WHERE matched_complex_no IS NOT NULL AND is_cancelled=0 AND deal_ymd >= date('now', ?)" + ac_cond + reg_cond)
            params.append(cutoff); params.extend(ac_params); params.extend(reg_params)
        if asset in ("apt", "all") and "silv_transactions" in existing:
            unions.append("SELECT deal_ymd, deal_amount, excl_use_ar, floor, dealing_gbn, "
                          "matched_complex_no, 'silv' AS asset FROM silv_transactions "
                          "WHERE matched_complex_no IS NOT NULL AND is_cancelled=0 AND deal_ymd >= date('now', ?)" + ac_cond + reg_cond)
            params.append(cutoff); params.extend(ac_params); params.extend(reg_params)
        if asset in ("offi", "all") and "offi_transactions" in existing:
            unions.append("SELECT deal_ymd, deal_amount, excl_use_ar, floor, dealing_gbn, "
                          "matched_complex_no, 'offi' AS asset FROM offi_transactions "
                          "WHERE matched_complex_no IS NOT NULL AND is_cancelled=0 AND deal_ymd >= date('now', ?)" + ac_cond + reg_cond)
            params.append(cutoff); params.extend(ac_params); params.extend(reg_params)
        if not unions:
            return {"items": []}
        src = " UNION ALL ".join(unions)

        # (단지, 면적_정수) 그룹별 평균 + 각 거래 할인율
        sql = f"""
        WITH tx AS ({src}),
        grp AS (
            SELECT matched_complex_no AS cno,
                   CAST(ROUND(excl_use_ar) AS INTEGER) AS area_key,
                   AVG(deal_amount) AS avg_price,
                   COUNT(*) AS n
            FROM tx
            WHERE excl_use_ar IS NOT NULL
            GROUP BY cno, area_key
            HAVING COUNT(*) >= ?
        )
        SELECT t.deal_ymd, t.deal_amount, t.excl_use_ar, t.floor, t.dealing_gbn,
               t.matched_complex_no AS cno, t.asset,
               g.avg_price, g.n AS group_size,
               (g.avg_price - t.deal_amount) * 1.0 / g.avg_price AS discount_rate,
               cx.complex_name, {_REGION_NAME_COL}
        FROM tx t
        JOIN grp g ON g.cno = t.matched_complex_no
                  AND g.area_key = CAST(ROUND(t.excl_use_ar) AS INTEGER)
        LEFT JOIN complexes cx ON cx.complex_no = t.matched_complex_no{_REGION_JOINS}
        WHERE g.avg_price > 0
          AND (g.avg_price - t.deal_amount) * 1.0 / g.avg_price >= ?
        ORDER BY discount_rate DESC
        LIMIT ?
        """
        rows = c.execute(sql, [*params, min_samples, discount, limit]).fetchall()
    return {
        "days": days, "discount": discount, "min_samples": min_samples, "asset": asset,
        "items": [
            {
                "deal_ymd": r["deal_ymd"],
                "deal_amount": r["deal_amount"],
                "avg_price": r["avg_price"],
                "discount_rate": r["discount_rate"],
                "excl_use_ar": r["excl_use_ar"],
                "floor": r["floor"],
                "dealing_gbn": r["dealing_gbn"],
                "complex_no": r["cno"],
                "complex_name": r["complex_name"],
                "region_name": r["region_name"],
                "group_size": r["group_size"],
                "asset": r["asset"],
            }
            for r in rows
        ],
    }


@app.get("/stats/tx-inventory-pressure")
def tx_inventory_pressure(trade: str = "A1", min_listings: int = 10,
                          min_households: int = 50, area_class: str = "all", limit: int = 100):
    """매물 적체 단지: (현재 매물수 / 세대수) 비율 높은 순.
    매도 압력 지표 — 거래 안 되는 단지 식별."""
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit out of range")
    if trade not in ("A1", "B1", "B2", "all"):
        raise HTTPException(400, "trade must be A1/B1/B2/all")
    with _open_db() as c:
        trade_cond = "" if trade == "all" else "AND l.trade_type=?"
        params: list = []
        if trade != "all":
            params.append(trade)
        # area_class for listings_current 의 area1_m2는 공급면적이므로 ×1.33 환산 불필요
        ac_cond = ""
        if area_class != "all":
            rng = _AREA_BUCKETS_SUPPLY.get(area_class)
            if rng:
                lo, hi = rng
                if lo is not None:
                    ac_cond += " AND l.area1_m2 >= ?"
                    params.append(lo)
                if hi is not None:
                    ac_cond += " AND l.area1_m2 < ?"
                    params.append(hi)
        # 성능: ①매물수를 먼저 단지별 집계(lc) ②세대수·비율로 top N 컷(ranked) ③region join은
        # 최종 N행에만 적용. (기존엔 전체 단지에 region join을 걸고 정렬 → 전국 17s)
        sql = (
            "WITH lc AS ("
            "  SELECT l.complex_no AS cno, COUNT(l.article_no) AS n "
            "  FROM listings_current l "
            f"  WHERE 1=1 {trade_cond} {ac_cond} "
            "  GROUP BY l.complex_no HAVING COUNT(l.article_no) >= ? "
            "), ranked AS ("
            "  SELECT c.complex_no, c.complex_name, c.cortar_no, "
            "         c.total_household_count AS households, lc.n AS listings, "
            "         lc.n * 1.0 / c.total_household_count AS ratio "
            "  FROM lc JOIN complexes c ON c.complex_no = lc.cno "
            "  WHERE c.total_household_count >= ? "
            "  ORDER BY ratio DESC LIMIT ? "
            ") "
            "SELECT ranked.complex_no, ranked.complex_name, ranked.households, ranked.listings, ranked.ratio, "
            "TRIM(COALESCE(rs.cortar_name,'')||' '||COALESCE(rg.cortar_name,'')"
            "||' '||COALESCE(rd.cortar_name,'')) AS region_name "
            "FROM ranked "
            "LEFT JOIN regions rs ON rs.cortar_no = substr(ranked.cortar_no,1,2)||'00000000' "
            "LEFT JOIN regions rg ON rg.cortar_no = substr(ranked.cortar_no,1,5)||'00000' "
            "LEFT JOIN regions rd ON rd.cortar_no = ranked.cortar_no "
            "ORDER BY ranked.ratio DESC"
        )
        rows = c.execute(sql, [*params, min_listings, min_households, limit]).fetchall()
    return {
        "trade": trade,
        "items": [
            {"complex_no": r[0], "complex_name": r[1], "households": r[2],
             "listings": r[3], "ratio": r[4], "region_name": r[5]}
            for r in rows
        ],
    }


@app.get("/stats/tx-gap-rank")
def tx_gap_rank(days: int = 365, asset: str = "apt", min_samples: int = 3,
                area_class: str = "all", sido: str | None = None,
                sigungu: str | None = None, dong: str | None = None, limit: int = 100, order: str = "asc"):
    """갭투자 순위: 같은 단지·평형 평균 매매가 - 평균 전세가.
    order='asc' = 갭 작은 순 (적은 자본 투자), 'desc' = 갭 큰 순.
    """
    if not days or days < 30 or days > 3650:
        raise HTTPException(400, "days out of range")
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit out of range")
    if not _area_rollup_ready():
        raise HTTPException(503, "tx_area_rollup 미빌드 — build_tx_rollups.py 실행 필요")
    cutoff = f"-{days} days"
    sk = "offi_sale" if asset == "offi" else "sale"
    jk = "offi_jeonse" if asset == "offi" else "jeonse"
    direction = "ASC" if order == "asc" else "DESC"
    ac_cond, ac_params = _area_cond_key(area_class)
    reg_cond, reg_params = _roll_region_clause(sido, sigungu, dong)
    cte_filter = reg_cond + ac_cond
    fp = reg_params + ac_params  # per-CTE filter params (reg, ac 순)
    with _open_db() as c:
        rows = c.execute(
            f"""
            WITH sale AS (
              SELECT complex_no AS cno, area_key,
                     SUM(sum_amt)*1.0/SUM(n) AS avg_sale, SUM(n) AS n_sale
              FROM tx_area_rollup
              WHERE kind=? AND deal_ymd >= date('now', ?){cte_filter}
              GROUP BY cno, area_key HAVING SUM(n) >= ?
            ),
            jeonse AS (
              SELECT complex_no AS cno, area_key,
                     SUM(sum_amt)*1.0/SUM(n) AS avg_jeonse, SUM(n) AS n_jeonse
              FROM tx_area_rollup
              WHERE kind=? AND deal_ymd >= date('now', ?){cte_filter}
              GROUP BY cno, area_key HAVING SUM(n) >= ?
            )
            SELECT s.cno, s.area_key, s.avg_sale, j.avg_jeonse,
                   s.avg_sale - j.avg_jeonse AS gap,
                   j.avg_jeonse * 1.0 / s.avg_sale AS jeonse_rate,
                   s.n_sale, j.n_jeonse, cx.complex_name, {_REGION_NAME_COL}
            FROM sale s
            JOIN jeonse j ON j.cno = s.cno AND j.area_key = s.area_key
            LEFT JOIN complexes cx ON cx.complex_no = s.cno{_REGION_JOINS}
            WHERE s.avg_sale > j.avg_jeonse
            ORDER BY gap {direction} LIMIT ?
            """,
            (sk, cutoff, *fp, min_samples, jk, cutoff, *fp, min_samples, limit),
        ).fetchall()
    return {
        "days": days, "asset": asset, "order": order,
        "items": [
            {"complex_no": r[0], "area_key": r[1], "avg_sale": r[2],
             "avg_jeonse": r[3], "gap": r[4], "jeonse_rate": r[5],
             "n_sale": r[6], "n_jeonse": r[7], "complex_name": r[8], "region_name": r[9]}
            for r in rows
        ],
    }


@app.get("/stats/tx-jeonse-rate")
def tx_jeonse_rate(days: int = 365, asset: str = "apt", min_samples: int = 3,
                   area_class: str = "all", sido: str | None = None,
                   sigungu: str | None = None, dong: str | None = None,
                   limit: int = 100, order: str = "desc"):
    """전세율 (전세가/매매가) 순위. desc = 전세가 비중 높은 단지(갭투자 매력)."""
    if not _area_rollup_ready():
        raise HTTPException(503, "tx_area_rollup 미빌드 — build_tx_rollups.py 실행 필요")
    cutoff = f"-{days} days"
    sk = "offi_sale" if asset == "offi" else "sale"
    jk = "offi_jeonse" if asset == "offi" else "jeonse"
    direction = "ASC" if order == "asc" else "DESC"
    ac_cond, ac_params = _area_cond_key(area_class)
    reg_cond, reg_params = _roll_region_clause(sido, sigungu, dong)   # CTE 안에서 지역 좁힘 → 빠름
    cte = ac_cond + reg_cond
    cte_p = [*ac_params, *reg_params]
    with _open_db() as c:
        rows = c.execute(
            f"""
            WITH sale AS (
              SELECT complex_no AS cno, area_key,
                     SUM(sum_amt)*1.0/SUM(n) AS avg_sale, SUM(n) AS n_sale
              FROM tx_area_rollup
              WHERE kind=? AND deal_ymd >= date('now', ?){cte}
              GROUP BY cno, area_key HAVING SUM(n) >= ?
            ),
            jeonse AS (
              SELECT complex_no AS cno, area_key,
                     SUM(sum_amt)*1.0/SUM(n) AS avg_jeonse, SUM(n) AS n_jeonse
              FROM tx_area_rollup
              WHERE kind=? AND deal_ymd >= date('now', ?){cte}
              GROUP BY cno, area_key HAVING SUM(n) >= ?
            )
            SELECT s.cno, s.area_key, s.avg_sale, j.avg_jeonse,
                   j.avg_jeonse * 1.0 / s.avg_sale AS jeonse_rate,
                   s.n_sale, j.n_jeonse, cx.complex_name, {_REGION_NAME_COL}
            FROM sale s
            JOIN jeonse j ON j.cno = s.cno AND j.area_key = s.area_key
            LEFT JOIN complexes cx ON cx.complex_no = s.cno{_REGION_JOINS}
            WHERE s.avg_sale > 0
            ORDER BY jeonse_rate {direction} LIMIT ?
            """,
            (sk, cutoff, *cte_p, min_samples, jk, cutoff, *cte_p, min_samples, limit),
        ).fetchall()
    return {
        "days": days, "asset": asset, "order": order,
        "items": [
            {"complex_no": r[0], "area_key": r[1], "avg_sale": r[2],
             "avg_jeonse": r[3], "jeonse_rate": r[4],
             "n_sale": r[5], "n_jeonse": r[6], "complex_name": r[7], "region_name": r[8]}
            for r in rows
        ],
    }


@app.get("/stats/tx-price-change")
def tx_price_change(window_days: int = 90, asset: str = "apt", min_samples: int = 3,
                    area_class: str = "all", sido: str | None = None,
                    sigungu: str | None = None, dong: str | None = None,
                    limit: int = 100, order: str = "desc"):
    """가격 변동률 — 최근 window_days 평균 vs 이전 window_days 평균.
    order='desc' = 상승률 높은 순, 'asc' = 하락률 큰 순."""
    if window_days < 30 or window_days > 365:
        raise HTTPException(400, "window_days out of range")
    if not _area_rollup_ready():
        raise HTTPException(503, "tx_area_rollup 미빌드 — build_tx_rollups.py 실행 필요")
    sks = _sale_kinds(asset)
    kph = ",".join("?" * len(sks))
    direction = "ASC" if order == "asc" else "DESC"
    recent_cutoff = f"-{window_days} days"
    prev_cutoff = f"-{window_days * 2} days"
    ac_cond, ac_params = _area_cond_key(area_class)
    reg_cond, reg_params = _roll_region_clause(sido, sigungu, dong)
    cte = ac_cond + reg_cond
    cte_p = [*ac_params, *reg_params]
    with _open_db() as c:
        rows = c.execute(
            f"""
            WITH recent AS (
              SELECT complex_no AS cno, area_key,
                     SUM(sum_amt)*1.0/SUM(n) AS recent_avg, SUM(n) AS n_recent
              FROM tx_area_rollup
              WHERE kind IN ({kph}) AND deal_ymd >= date('now', ?){cte}
              GROUP BY cno, area_key HAVING SUM(n) >= ?
            ),
            prev AS (
              SELECT complex_no AS cno, area_key,
                     SUM(sum_amt)*1.0/SUM(n) AS prev_avg, SUM(n) AS n_prev
              FROM tx_area_rollup
              WHERE kind IN ({kph}) AND deal_ymd >= date('now', ?) AND deal_ymd < date('now', ?){cte}
              GROUP BY cno, area_key HAVING SUM(n) >= ?
            )
            SELECT r.cno, r.area_key, r.recent_avg, p.prev_avg,
                   (r.recent_avg - p.prev_avg) * 1.0 / p.prev_avg AS change_rate,
                   r.n_recent, p.n_prev, cx.complex_name, {_REGION_NAME_COL}
            FROM recent r
            JOIN prev p ON p.cno = r.cno AND p.area_key = r.area_key
            LEFT JOIN complexes cx ON cx.complex_no = r.cno{_REGION_JOINS}
            WHERE p.prev_avg > 0
            ORDER BY change_rate {direction} LIMIT ?
            """,
            (*sks, recent_cutoff, *cte_p, min_samples, *sks, prev_cutoff, recent_cutoff, *cte_p, min_samples, limit),
        ).fetchall()
    return {
        "window_days": window_days, "asset": asset, "order": order,
        "items": [
            {"complex_no": r[0], "area_key": r[1], "recent_avg": r[2],
             "prev_avg": r[3], "change_rate": r[4],
             "n_recent": r[5], "n_prev": r[6], "complex_name": r[7], "region_name": r[8]}
            for r in rows
        ],
    }


@app.get("/stats/tx-asking-vs-real")
def tx_asking_vs_real(days: int = 90, min_samples: int = 3, area_class: str = "all",
                      limit: int = 100, order: str = "desc"):
    """호가(매물) vs 실거래가 갭. asking/real ratio 큰 순 (호가가 더 비쌈)."""
    cutoff = f"-{days} days"
    direction = "ASC" if order == "asc" else "DESC"
    # 호가는 공급면적(area1_m2), 실거래는 전용면적(supply_area 매핑) 기준으로 각각 필터
    ac_ask, ac_ask_p = _area_cond("area1_m2", area_class, col_supply="area1_m2")
    ac_real, ac_real_p = _area_cond("excl_use_ar", area_class)
    with _open_db() as c:
        rows = c.execute(
            f"""
            WITH asking AS (
              SELECT complex_no,
                     CAST(ROUND(area1_m2) AS INTEGER) AS area_key,
                     AVG(deal_or_warrant_price) AS avg_asking,
                     COUNT(*) AS n_asking
              FROM listings_current
              WHERE trade_type='A1' AND deal_or_warrant_price > 0
                AND complex_no IS NOT NULL AND area1_m2 IS NOT NULL{ac_ask}
              GROUP BY complex_no, area_key HAVING COUNT(*) >= ?
            ),
            real_tx AS (
              SELECT matched_complex_no AS cno,
                     CAST(ROUND(excl_use_ar) AS INTEGER) AS area_key,
                     AVG(deal_amount) AS avg_real, COUNT(*) AS n_real
              FROM transactions
              WHERE matched_complex_no IS NOT NULL AND is_cancelled = 0
                AND deal_ymd >= date('now', ?) AND excl_use_ar IS NOT NULL{ac_real}
              GROUP BY cno, area_key HAVING COUNT(*) >= ?
            )
            SELECT a.complex_no, a.area_key, a.avg_asking, t.avg_real,
                   (a.avg_asking - t.avg_real) * 1.0 / t.avg_real AS gap_rate,
                   a.n_asking, t.n_real, cx.complex_name, {_REGION_NAME_COL}
            FROM asking a
            JOIN real_tx t ON t.cno = a.complex_no AND t.area_key = a.area_key
            LEFT JOIN complexes cx ON cx.complex_no = a.complex_no{_REGION_JOINS}
            WHERE t.avg_real > 0
            ORDER BY gap_rate {direction} LIMIT ?
            """,
            (*ac_ask_p, min_samples, cutoff, *ac_real_p, min_samples, limit),
        ).fetchall()
    return {
        "days": days, "order": order,
        "items": [
            {"complex_no": r[0], "area_key": r[1], "avg_asking": r[2],
             "avg_real": r[3], "gap_rate": r[4],
             "n_asking": r[5], "n_real": r[6], "complex_name": r[7], "region_name": r[8]}
            for r in rows
        ],
    }


def _sale_kinds(asset: str) -> list[str]:
    """매매 통계 = 일반매매(sale) + 분양권(silv) 통합(사용자 멘탈모델). 분양권 거래금액은
    실거래 총액이라 매매와 같은 scale. 오피스텔은 분양권 분리 데이터 없어 offi_sale만."""
    return ["offi_sale"] if asset == "offi" else ["sale", "silv"]


@app.get("/stats/tx-pyeong-price")
def tx_pyeong_price(days: int = 365, asset: str = "apt", min_samples: int = 3,
                    area_class: str = "all", sido: str | None = None,
                    sigungu: str | None = None, dong: str | None = None, limit: int = 100, order: str = "desc"):
    """평당가 순위 — 거래가 ÷ 면적(평). 단지×평형 그룹 평균.
    order='desc' = 비싼 순, 'asc' = 싼 순."""
    if not _area_rollup_ready():
        raise HTTPException(503, "tx_area_rollup 미빌드 — build_tx_rollups.py 실행 필요")
    cutoff = f"-{days} days"
    sks = _sale_kinds(asset)
    kph = ",".join("?" * len(sks))
    direction = "ASC" if order == "asc" else "DESC"
    ac_cond, ac_params = _area_cond_key(area_class)
    reg_cond, reg_params = _roll_region_clause(sido, sigungu, dong)
    cte_filter = reg_cond + ac_cond
    with _open_db() as c:
        # 평당가 = 가중평균(Σ금액 / Σ전용평). area_key 그룹 내 전용면적이 거의 일정해
        # 원본 AVG(금액/평) 과 사실상 동일(롤업쪽이 면적가중이라 더 견고).
        rows = c.execute(
            f"""
            SELECT cno, area_key, avg_price, pyeong_price, n,
                   cx.complex_name, {_REGION_NAME_COL}
            FROM (
              SELECT complex_no AS cno, area_key,
                     SUM(sum_amt)*1.0/SUM(n) AS avg_price,
                     SUM(sum_amt) * 3.3058 / SUM(sum_excl) AS pyeong_price,
                     SUM(n) AS n
              FROM tx_area_rollup
              WHERE kind IN ({kph}) AND deal_ymd >= date('now', ?){cte_filter}
              GROUP BY complex_no, area_key HAVING SUM(n) >= ?
            ) t
            LEFT JOIN complexes cx ON cx.complex_no = t.cno{_REGION_JOINS}
            ORDER BY pyeong_price {direction}
            LIMIT ?
            """,
            (*sks, cutoff, *reg_params, *ac_params, min_samples, limit),
        ).fetchall()
    return {
        "days": days, "asset": asset, "order": order,
        "items": [
            {"complex_no": r[0], "area_key": r[1], "avg_price": r[2],
             "pyeong_price": r[3], "n": r[4], "complex_name": r[5], "region_name": r[6]}
            for r in rows
        ],
    }


@app.get("/stats/tx-turnover")
def tx_turnover(days: int = 365, trade: str = "A1", asset: str = "apt",
                min_households: int = 50, area_class: str = "all",
                sido: str | None = None, sigungu: str | None = None, dong: str | None = None, limit: int = 100):
    """거래회전율 — 거래량 / 세대수. trade=A1 매매, B1 전세."""
    if not _area_rollup_ready():
        raise HTTPException(503, "tx_area_rollup 미빌드 — build_tx_rollups.py 실행 필요")
    cutoff = f"-{days} days"
    if trade == "A1":
        kinds = _sale_kinds(asset)   # 매매+분양권 통합
    elif trade == "B1":
        kinds = ["offi_jeonse" if asset == "offi" else "jeonse"]
    else:
        raise HTTPException(400, "trade must be A1 or B1")
    kph = ",".join("?" * len(kinds))
    ac_cond, ac_params = _area_cond_key(area_class)
    reg_cond, reg_params = _roll_region_clause(sido, sigungu, dong)
    src = (f"SELECT complex_no AS cno, SUM(n) AS n FROM tx_area_rollup "
           f"WHERE kind IN ({kph}) AND deal_ymd >= date('now', ?){reg_cond}{ac_cond} GROUP BY complex_no")
    with _open_db() as c:
        rows = c.execute(
            f"""
            WITH agg AS ({src})
            SELECT cx.complex_no, cx.complex_name, cx.total_household_count AS households,
                   agg.n AS tx_count,
                   agg.n * 1.0 / cx.total_household_count AS turnover_rate,
                   {_REGION_NAME_COL}
            FROM complexes cx
            JOIN agg ON agg.cno = cx.complex_no{_REGION_JOINS}
            WHERE cx.total_household_count >= ?
            ORDER BY turnover_rate DESC LIMIT ?
            """,
            (*kinds, cutoff, *reg_params, *ac_params, min_households, limit),
        ).fetchall()
    return {
        "days": days, "trade": trade, "asset": asset,
        "items": [
            {"complex_no": r[0], "complex_name": r[1], "households": r[2],
             "tx_count": r[3], "turnover_rate": r[4], "region_name": r[5]}
            for r in rows
        ],
    }


@app.get("/stats/tx-yield")
def tx_yield(days: int = 365, asset: str = "apt", area_class: str = "all",
             sido: str | None = None, sigungu: str | None = None,
             dong: str | None = None, min_samples: int = 3, limit: int = 100):
    """월세수익률 — 연 월세 / 매매가 × 100. 단지×평형 그룹.
    월세 거래의 (deposit + monthly_rent×100) ÷ 매매가 (보증금 환산은 ×100 approx).
    area_class: 평형(공급면적) 버킷, sido: 시도(시군구코드 앞 2자리)로 거른다."""
    if not _area_rollup_ready():
        raise HTTPException(503, "tx_area_rollup 미빌드 — build_tx_rollups.py 실행 필요")
    cutoff = f"-{days} days"
    sk = "offi_sale" if asset == "offi" else "sale"
    wk = "offi_wolse" if asset == "offi" else "wolse"
    # 평형·지역 필터 — sale/wolse 두 CTE 에 동일 적용 (롤업: area_key + complex_no IN 지역).
    reg_cond, reg_params = _roll_region_clause(sido, sigungu, dong)
    ac_cond, ac_params = _area_cond_key(area_class)
    cte_filter = reg_cond + ac_cond
    fp = reg_params + ac_params  # per-CTE filter params

    with _open_db() as c:
        rows = c.execute(
            f"""
            WITH sale AS (
              SELECT complex_no AS cno, area_key,
                     SUM(sum_amt)*1.0/SUM(n) AS avg_sale, SUM(n) AS n_sale
              FROM tx_area_rollup
              WHERE kind=? AND deal_ymd >= date('now', ?){cte_filter}
              GROUP BY cno, area_key HAVING SUM(n) >= ?
            ),
            wolse AS (
              SELECT complex_no AS cno, area_key,
                     SUM(sum_amt2)*1.0/SUM(n) AS avg_deposit,
                     SUM(sum_amt)*1.0/SUM(n) AS avg_monthly,
                     SUM(n) AS n_wolse
              FROM tx_area_rollup
              WHERE kind=? AND deal_ymd >= date('now', ?){cte_filter}
              GROUP BY cno, area_key HAVING SUM(n) >= ?
            )
            SELECT s.cno, s.area_key, s.avg_sale, w.avg_deposit, w.avg_monthly,
                   (w.avg_monthly * 12) * 1.0 / s.avg_sale AS yield_rate,
                   s.n_sale, w.n_wolse, cx.complex_name,
                   cx.total_household_count,
                   TRIM(COALESCE(rg.cortar_name,'')||' '||COALESCE(rd.cortar_name,'')) AS region_name
            FROM sale s
            JOIN wolse w ON w.cno = s.cno AND w.area_key = s.area_key
            LEFT JOIN complexes cx ON cx.complex_no = s.cno
            LEFT JOIN regions rg ON rg.cortar_no = substr(cx.cortar_no,1,5)||'00000'
            LEFT JOIN regions rd ON rd.cortar_no = cx.cortar_no
            WHERE s.avg_sale > 0
            ORDER BY yield_rate DESC LIMIT ?
            """,
            (sk, cutoff, *fp, min_samples, wk, cutoff, *fp, min_samples, limit),
        ).fetchall()
    return {
        "days": days, "asset": asset, "area_class": area_class, "sido": sido,
        "items": [
            {"complex_no": r[0], "area_key": r[1], "avg_sale": r[2],
             "avg_deposit": r[3], "avg_monthly": r[4], "yield_rate": r[5],
             "n_sale": r[6], "n_wolse": r[7], "complex_name": r[8],
             "households": r[9], "region_name": r[10]}
            for r in rows
        ],
    }


@app.get("/admin/suspicious-realtors")
def suspicious_realtors(_admin: dict = Depends(admin_user), limit: int = 200):
    """vworld 영업 등록이 안 된 채 Naver에 광고 올리는 의심 사무소.
    match_type='none'이고 현재 매물이 있는 realtor 목록.
    """
    if limit < 1 or limit > 2000:
        raise HTTPException(400, "limit out of range")
    import re as _re
    _STD_RE = _re.compile(r"^\d{4,5}-\d{4}-\d{4,6}(?:-\d{3})?$")

    def _categorize(regno: str | None) -> str:
        if not regno:
            return "B"  # 등록번호 없음
        # normalize 시도
        import sys as _sys
        from pathlib import Path as _P
        _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
        from collector.realtor_matching import normalize_regno
        nr = normalize_regno(regno)
        if not nr or not _STD_RE.match(nr):
            return "C"  # 옛/이상 포맷
        return "D"  # 표준이지만 vworld 미등록 = 폐업/이전 의심

    with _open_db() as c:
        # 매칭 안 됐거나 vworld_status가 있는 (정지/휴업) 케이스 모두
        rows = c.execute(
            """
            SELECT m.realtor_id, m.naver_name, m.primary_sgg_cd, m.total_listings,
                   m.vworld_status, m.match_type,
                   nr.representative_name, nr.address,
                   nr.representative_tel_no, nr.cell_phone_no,
                   nr.establish_registration_no
            FROM realtor_match m
            LEFT JOIN naver_realtors nr ON nr.realtor_id = m.realtor_id
            WHERE (m.match_type='none' OR m.vworld_status IS NOT NULL)
              AND COALESCE(m.total_listings, 0) > 0
            ORDER BY m.total_listings DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    out: list[dict] = []
    for r in rows:
        regno = r["establish_registration_no"]
        vws = r["vworld_status"]
        if vws:
            cat = "E"  # vworld 정지/휴업 — 직원 검색으로 확인됨
        elif r["representative_name"] is None and r["address"] is None:
            cat = "A"
        else:
            cat = _categorize(regno)
        out.append({
            "realtor_id": r["realtor_id"],
            "naver_name": r["naver_name"],
            "sgg_cd": r["primary_sgg_cd"],
            "listings": r["total_listings"],
            "representative": r["representative_name"],
            "address": r["address"],
            "phone": r["representative_tel_no"],
            "cell": r["cell_phone_no"],
            "registration_no": regno,
            "category": cat,
            "vworld_status": vws,
        })
    return {"items": out, "total": len(out)}


# ===========================================================================
# 가격 변동 대시보드 (전국 매물 가격 변동을 집계 관점에서 본다)
#
# complex_daily_agg.price_avg 는 오타 호가(예: 8억을 800억으로 입력)에 오염될 수
# 있어 — 실제로 max 가 1.7조원까지 찍힌다 — 모든 집계에 sane bound 를 건다.
# 지역(시도/시군구)은 complexes.cortar_no 의 앞자리로 도출한다:
#   시도   = substr(cortar_no,1,2) || '00000000'   (예: 11→서울시)
#   시군구 = substr(cortar_no,1,5) || '00000'        (예: 11680→강남구)
# ===========================================================================

# 매물 호가 sane 범위 (원). 거래유형별 하한, 공통 상한.
_PRICE_LO = {"A1": 20_000_000, "B1": 5_000_000, "B2": 1_000_000}
_PRICE_HI = 500_000_000_000  # 5천억 — 이 이상은 입력 오류로 본다
# 월세료(B2 rent_avg) sane 범위 (원/월). 상한은 시군구별 실거래 기준(rent_ref_sgg)을
# 우선 쓰고, 기준이 없는 시군구만 _RENT_HI(1천만/월) fallback. 하한은 공통 3만원.
_RENT_LO = 30_000
_RENT_HI = 10_000_000


def _consecutive_days(prev: str | None, latest: str | None) -> bool:
    """prev 가 latest 의 정확히 하루 전(연속일)이면 True. 수집 누락으로 며칠
    건너뛰면 False → '전일 대비' 라벨을 실제 날짜로 바꾸기 위함."""
    from datetime import date as _date
    try:
        return bool(prev and latest) and (
            _date.fromisoformat(latest) - _date.fromisoformat(prev)).days == 1
    except Exception:
        return False


@app.get("/stats/changes/summary")
def changes_summary(sido: str | None = None, sigungu: str | None = None, dong: str | None = None, asset: str | None = None):
    """지역별 요약: 최신 스냅샷의 거래유형별 매물 수 + 전일 대비 증감, 단지 수,
    그리고 최신 일자 가격 변동 이벤트(상승/하락) 건수.

    sido/sigungu 미지정 시 전국. asset(apt/offi)로 아파트/오피스텔 구분.
    필터는 complexes.cortar_no/real_estate_type 로 적용 (complex_daily_agg ⨝ complexes).
    """
    # 지역 필터 SQL fragment. complexes 를 join 해서 cortar_no prefix 로 거름.
    region_join = ""
    region_clause = ""
    region_params: list[Any] = []
    if sigungu:
        region_join = " JOIN complexes cx ON cx.complex_no = a.complex_no"
        region_clause = " AND substr(cx.cortar_no,1,5) = substr(?,1,5)"
        region_params.append(sigungu)
    elif sido:
        region_join = " JOIN complexes cx ON cx.complex_no = a.complex_no"
        region_clause = " AND substr(cx.cortar_no,1,2) = substr(?,1,2)"
        region_params.append(sido)
    # 자산(아파트/오피스텔) 필터 — complexes join 필요시 추가.
    asset_clause = _asset_type_clause(asset)
    if asset_clause and not region_join:
        region_join = " JOIN complexes cx ON cx.complex_no = a.complex_no"
    region_clause += asset_clause

    with _open_db() as c:
        dates = [
            r[0]
            for r in c.execute(
                "SELECT DISTINCT snapshot_date FROM complex_daily_agg "
                "ORDER BY snapshot_date DESC LIMIT 2"
            )
        ]
        latest = dates[0] if dates else None
        prev = dates[1] if len(dates) > 1 else None

        def totals(d):
            if not d:
                return {}, 0
            by = {
                t: n
                for t, n in c.execute(
                    f"SELECT a.trade_type, SUM(a.listing_count) FROM complex_daily_agg a"
                    f"{region_join} WHERE a.snapshot_date=?{region_clause}"
                    f" GROUP BY a.trade_type",
                    (d, *region_params),
                )
            }
            cplx = c.execute(
                f"SELECT COUNT(DISTINCT a.complex_no) FROM complex_daily_agg a"
                f"{region_join} WHERE a.snapshot_date=?{region_clause}",
                (d, *region_params),
            ).fetchone()[0]
            return by, cplx

        cur, cur_cplx = totals(latest)
        old, _ = totals(prev)

        def avg_price(d, t):
            """거래유형별 가중 평균 호가 (지역 필터 적용 + sane bound)."""
            if not d:
                return None
            lo = _PRICE_LO.get(t, 1_000_000)
            row = c.execute(
                f"SELECT SUM(a.price_avg*a.listing_count)*1.0/SUM(a.listing_count) "
                f"FROM complex_daily_agg a{region_join} "
                f"WHERE a.snapshot_date=? AND a.trade_type=? "
                f"  AND a.price_avg BETWEEN ? AND ?{region_clause}",
                (d, t, lo, _PRICE_HI, *region_params),
            ).fetchone()
            return row[0] if row and row[0] is not None else None

        def avg_monthly_rent(d):
            """B2 (월세) 행의 rent_avg 가중평균 — 월세 평균."""
            if not d:
                return None
            row = c.execute(
                f"SELECT SUM(a.rent_avg*a.listing_count)*1.0/SUM(a.listing_count) "
                f"FROM complex_daily_agg a "
                f"JOIN complexes cr ON cr.complex_no = a.complex_no "
                f"LEFT JOIN rent_ref_sgg rr ON rr.sgg5 = substr(cr.cortar_no,1,5)"
                f"{region_join} "
                f"WHERE a.snapshot_date=? AND a.trade_type='B2' "
                f"  AND a.rent_avg BETWEEN ? AND COALESCE(rr.rent_cap, ?)"
                f"{region_clause}",
                (d, _RENT_LO, _RENT_HI, *region_params),
            ).fetchone()
            return row[0] if row and row[0] is not None else None

        avg_cur = {t: avg_price(latest, t) for t in ("A1", "B1", "B2")}
        avg_old = {t: avg_price(prev, t) for t in ("A1", "B1", "B2")}
        rent_cur = avg_monthly_rent(latest)
        rent_old = avg_monthly_rent(prev)

        # 가격 변동 이벤트도 지역 필터. article_events 에는 complex_no 가 있으면
        # complexes join 으로 지역 거름 (없으면 전국 기본).
        ev_region_join = ""
        if region_join:
            # article_events 의 complex_no 와 직접 join
            ev_region_join = " JOIN complexes cx ON cx.complex_no = ae.complex_no"
        ev_date = c.execute(
            f"SELECT MAX(ae.event_date) FROM article_events ae{ev_region_join} "
            f"WHERE ae.event_type='PRICE_CHANGE'"
            f"{region_clause}",
            tuple(region_params),
        ).fetchone()[0]
        up = down = 0
        if ev_date:
            for dr, n in c.execute(
                f"SELECT CASE WHEN ae.new_price>ae.old_price THEN 'up' ELSE 'down' END, COUNT(*) "
                f"FROM article_events ae{ev_region_join} "
                f"WHERE ae.event_type='PRICE_CHANGE' AND ae.event_date=? "
                f"  AND ae.old_price BETWEEN 1000000 AND 500000000000 "
                f"  AND ae.new_price BETWEEN 1000000 AND 500000000000 "
                f"  AND ae.old_price<>ae.new_price{region_clause} "
                f"GROUP BY 1",
                (ev_date, *region_params),
            ):
                if dr == "up":
                    up = n
                else:
                    down = n

    def _change(now, was):
        if now is None or was is None or was == 0:
            return None
        return (now - was) / was

    trades = {
        t: {
            "count": cur.get(t, 0),
            "prev": old.get(t, 0),
            "delta": cur.get(t, 0) - old.get(t, 0),
            "avg_price": avg_cur[t],
            "avg_prev": avg_old[t],
            "avg_change": _change(avg_cur[t], avg_old[t]),
        }
        for t in ("A1", "B1", "B2")
    }
    # B2(월세) 행의 월세 평균 — 보증금(avg_price)과 따로.
    trades["B2"]["rent_avg"] = rent_cur
    trades["B2"]["rent_prev"] = rent_old
    trades["B2"]["rent_change"] = _change(rent_cur, rent_old)
    return {
        "latest_date": latest,
        "prev_date": prev,
        # prev 가 latest 의 바로 전날(연속일)인지 — 수집 누락으로 며칠 건너뛴 경우
        # 프런트가 "전일 대비" 대신 실제 날짜를 표기하도록(거짓 전일 비교 방지).
        "prev_is_yesterday": _consecutive_days(prev, latest),
        "complex_count": cur_cplx,
        "total": sum(cur.values()),
        "trades": trades,
        "event_date": ev_date,
        "events_up": up,
        "events_down": down,
        "sido": sido,
        "sigungu": sigungu,
    }


@app.get("/stats/changes/sido-list")
def changes_sido_list():
    """시도 드롭다운용 목록 (regions.cortar_type='city')."""
    with _open_db() as c:
        rows = c.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city' "
            "ORDER BY cortar_no"
        ).fetchall()
    return {"items": [{"code": r[0], "name": r[1]} for r in rows]}


@app.get("/stats/changes/region-rank")
def changes_region_rank(
    level: str = "sido",
    trade: str = "A1",
    order: str = "desc",
    sido: str | None = None,
    sigungu: str | None = None, dong: str | None = None,
    asset: str | None = None,
    min_listings: int = 10,
    area_class: str = "all",
    limit: int = 100,
):
    """지역별 평균 매물가 순위 (최신 스냅샷). level=sido|sigungu|dong. asset=apt/offi.
    평균은 단지·평형별 price_avg 를 listing_count 로 가중 평균한 값.
    area_class: 평형 필터 — complex_areas.supply_area(공급면적) 기준 버킷.
    complexes.cortar_no 는 동(sec) 레벨 코드라, dong 은 코드 전체로 그룹화한다."""
    if level not in ("sido", "sigungu", "dong"):
        raise HTTPException(400, "level must be sido|sigungu|dong")
    if trade not in ("A1", "B1", "B2"):
        raise HTTPException(400, "bad trade")
    if limit < 1 or limit > 1000:
        raise HTTPException(400, "limit out of range")
    direction = "ASC" if order == "asc" else "DESC"
    cut, pad = {"sido": (2, "00000000"), "sigungu": (5, "00000"), "dong": (10, "")}[level]
    lo = _PRICE_LO.get(trade, 1_000_000)

    # 평형 필터 — complex_areas 를 (complex_no, pyeong_name=area_name) 로 조인해
    # 공급면적 버킷으로 거른다. area_name↔pyeong_name 커버리지는 사실상 100%.
    ac_cond, ac_params = _area_cond("ca.exclusive_area", area_class, col_supply="ca.supply_area")
    area_join = (
        " JOIN complex_areas ca ON ca.complex_no=a.complex_no AND ca.pyeong_name=a.area_name"
        if ac_cond else ""
    )

    params: list[Any] = [trade, lo, _PRICE_HI]
    sido_clause = ""
    if sigungu:
        sido_clause = " AND substr(cx.cortar_no,1,5)=substr(?,1,5)"
        params.append(sigungu)
    elif sido:
        sido_clause = " AND substr(cx.cortar_no,1,2)=substr(?,1,2)"
        params.append(sido)
    params += ac_params
    params += [min_listings, limit]
    asset_clause = _asset_type_clause(asset)  # cx 항상 조인됨

    # 지역명은 "동구·강서구"처럼 시군구 단독이면 어느 시·도인지 모호하다. 레벨에 따라
    # 시도(+시군구)를 접두로 붙여 명확하게 만든다. r 은 그룹 레벨 지역, rs=시도, rg=시군구.
    if level == "sido":
        label_joins = ""
        label_expr = "MAX(r.cortar_name)"
    elif level == "sigungu":
        label_joins = " LEFT JOIN regions rs ON rs.cortar_no=substr(cx.cortar_no,1,2)||'00000000'"
        label_expr = "TRIM(COALESCE(MAX(rs.cortar_name),'')||' '||COALESCE(MAX(r.cortar_name),''))"
    else:  # dong
        label_joins = (
            " LEFT JOIN regions rs ON rs.cortar_no=substr(cx.cortar_no,1,2)||'00000000'"
            " LEFT JOIN regions rg ON rg.cortar_no=substr(cx.cortar_no,1,5)||'00000'"
        )
        label_expr = (
            "TRIM(COALESCE(MAX(rs.cortar_name),'')||' '||COALESCE(MAX(rg.cortar_name),'')"
            "||' '||COALESCE(MAX(r.cortar_name),''))"
        )

    # 최신·직전 두 스냅샷을 한 번에 스캔해 지역별 가중 평균과 전일 대비 변동을 함께 낸다.
    # 필터(거래·가격범위·시도·평형)는 양일에 동일 적용되므로 CASE 피벗으로 파라미터를
    # 늘리지 않는다.
    sql = f"""
        WITH dts AS (
          SELECT MAX(snapshot_date) AS hi,
                 (SELECT MAX(snapshot_date) FROM complex_daily_agg
                  WHERE snapshot_date < (SELECT MAX(snapshot_date) FROM complex_daily_agg)) AS lo
          FROM complex_daily_agg
        )
        SELECT substr(cx.cortar_no,1,{cut})||'{pad}' AS rc, {label_expr} AS cortar_name,
               SUM(CASE WHEN a.snapshot_date=d.hi THEN a.price_avg*a.listing_count ELSE 0 END)*1.0
                 / NULLIF(SUM(CASE WHEN a.snapshot_date=d.hi THEN a.listing_count ELSE 0 END),0) AS avg_price,
               SUM(CASE WHEN a.snapshot_date=d.lo THEN a.price_avg*a.listing_count ELSE 0 END)*1.0
                 / NULLIF(SUM(CASE WHEN a.snapshot_date=d.lo THEN a.listing_count ELSE 0 END),0) AS prev_avg,
               SUM(CASE WHEN a.snapshot_date=d.hi THEN a.listing_count ELSE 0 END) AS listings,
               COUNT(DISTINCT CASE WHEN a.snapshot_date=d.hi THEN a.complex_no END) AS complexes
        FROM complex_daily_agg a
        JOIN complexes cx ON cx.complex_no=a.complex_no
        JOIN dts d ON a.snapshot_date IN (d.hi, d.lo){area_join}
        LEFT JOIN regions r ON r.cortar_no=substr(cx.cortar_no,1,{cut})||'{pad}'{label_joins}
        WHERE a.trade_type=? AND a.price_avg BETWEEN ? AND ?
          AND cx.cortar_no IS NOT NULL{sido_clause}{asset_clause}{ac_cond}
        GROUP BY rc HAVING listings>=?
        ORDER BY avg_price {direction} LIMIT ?
    """
    with _open_db() as c:
        rows = c.execute(sql, params).fetchall()
        dpair = c.execute(
            "SELECT MAX(snapshot_date), (SELECT MAX(snapshot_date) FROM complex_daily_agg "
            "WHERE snapshot_date < (SELECT MAX(snapshot_date) FROM complex_daily_agg)) "
            "FROM complex_daily_agg"
        ).fetchone()
    latest_d, prev_d = (dpair[0], dpair[1]) if dpair else (None, None)

    def _change(now, was):
        if now is None or was is None or was == 0:
            return None
        return (now - was) / was

    return {
        "level": level,
        "trade": trade,
        "order": order,
        "latest_date": latest_d,
        "prev_date": prev_d,
        "prev_is_yesterday": _consecutive_days(prev_d, latest_d),
        "items": [
            {
                "region_code": r[0],
                "region_name": r[1],
                "avg_price": r[2],
                "prev_avg": r[3],
                "change": _change(r[2], r[3]),
                "listings": r[4],
                "complexes": r[5],
            }
            for r in rows
        ],
    }


@app.get("/stats/changes/movers")
def changes_movers(
    trade: str = "A1",
    sido: str | None = None,
    sigungu: str | None = None, dong: str | None = None,
    asset: str | None = None,
    min_listings: int = 2,
    min_complex_listings: int = 50,
    limit: int = 5,
):
    """상승 / 하락 top — 단지·평형별 최신 스냅샷 vs 가장 오래된 스냅샷 price_avg 비교.
    데이터가 6일치뿐이라 변동폭은 작지만, 데이터가 쌓이면 같은 쿼리가 의미를 갖는다.
    rate 는 ±급변(오타) 컷을 위해 -80%~+100% 로 클램프.
    min_complex_listings: 최신 스냅샷에서 단지 전체 매물(전 거래유형 합)이 이 값 이상인
    단지만 — 소형/유령 단지의 노이즈를 거른다."""
    if trade not in ("A1", "B1", "B2"):
        raise HTTPException(400, "bad trade")
    if limit < 1 or limit > 50:
        raise HTTPException(400, "limit out of range")
    lo = _PRICE_LO.get(trade, 1_000_000)
    if sigungu:
        sido_clause = " AND substr(cx.cortar_no,1,5)=substr(?,1,5)"
    elif sido:
        sido_clause = " AND substr(cx.cortar_no,1,2)=substr(?,1,2)"
    else:
        sido_clause = ""
    asset_clause = _asset_type_clause(asset)  # cx LEFT JOIN 됨

    def _sql(direction: str) -> str:
        return f"""
            WITH d AS (
              SELECT MIN(snapshot_date) lo, MAX(snapshot_date) hi FROM complex_daily_agg
            ),
            ct AS (
              SELECT complex_no, SUM(listing_count) AS total
              FROM complex_daily_agg
              WHERE snapshot_date = (SELECT hi FROM d)
              GROUP BY complex_no
            )
            SELECT a.complex_no, cx.complex_name, a.area_name,
                   TRIM(COALESCE(rs.cortar_name,'')||' '||COALESCE(r.cortar_name,'')) AS region_name,
                   p.price_avg AS old_p, a.price_avg AS new_p,
                   (a.price_avg-p.price_avg)*1.0/p.price_avg AS rate,
                   a.listing_count, ct.total
            FROM complex_daily_agg a
            JOIN d ON a.snapshot_date=d.hi
            JOIN complex_daily_agg p ON p.complex_no=a.complex_no
                 AND p.area_name=a.area_name AND p.trade_type=a.trade_type
                 AND p.snapshot_date=d.lo
            JOIN ct ON ct.complex_no=a.complex_no
            LEFT JOIN complexes cx ON cx.complex_no=a.complex_no
            LEFT JOIN regions rs ON rs.cortar_no=substr(cx.cortar_no,1,2)||'00000000'
            LEFT JOIN regions r ON r.cortar_no=substr(cx.cortar_no,1,5)||'00000'
            WHERE a.trade_type=? AND a.price_avg BETWEEN ? AND ?
              AND p.price_avg BETWEEN ? AND ?
              AND a.listing_count>=? AND p.listing_count>=?
              AND ct.total>=?
              AND (a.price_avg-p.price_avg)*1.0/p.price_avg BETWEEN -0.8 AND 1.0
              AND a.price_avg<>p.price_avg{sido_clause}{asset_clause}
            ORDER BY rate {direction} LIMIT ?
        """

    def _params() -> list[Any]:
        p: list[Any] = [
            trade, lo, _PRICE_HI, lo, _PRICE_HI,
            min_listings, min_listings, min_complex_listings,
        ]
        if sigungu:
            p.append(sigungu)
        elif sido:
            p.append(sido)
        p.append(limit)
        return p

    def _fmt(rows):
        return [
            {
                "complex_no": r[0],
                "complex_name": r[1],
                "area_name": r[2],
                "region_name": r[3],
                "old_avg": r[4],
                "new_avg": r[5],
                "rate": r[6],
                "listing_count": r[7],
                "complex_listings": r[8],
            }
            for r in rows
        ]

    with _open_db() as c:
        up = c.execute(_sql("DESC"), _params()).fetchall()
        down = c.execute(_sql("ASC"), _params()).fetchall()
    return {"trade": trade, "up": _fmt(up), "down": _fmt(down)}


@app.get("/stats/changes/events")
def changes_events(trade: str = "A1", limit: int = 40):
    """최근 가격 변동 이벤트 피드 (article_events PRICE_CHANGE). 오타 정정 노이즈를
    줄이기 위해 변동률 ±50% 이내, sane price 범위만."""
    if trade not in ("A1", "B1", "B2", "all"):
        raise HTTPException(400, "bad trade")
    if limit < 1 or limit > 200:
        raise HTTPException(400, "limit out of range")
    where_trade = "" if trade == "all" else " AND e.trade_type=?"
    params: list[Any] = [1_000_000, _PRICE_HI, 1_000_000, _PRICE_HI]
    if trade != "all":
        params.append(trade)
    params.append(limit)
    sql = f"""
        SELECT e.event_date, e.complex_no, cx.complex_name, e.trade_type,
               e.old_price, e.new_price,
               TRIM(COALESCE(rs.cortar_name,'')||' '||COALESCE(r.cortar_name,'')) AS region_name,
               (e.new_price-e.old_price)*1.0/e.old_price AS rate
        FROM article_events e
        LEFT JOIN complexes cx ON cx.complex_no=e.complex_no
        LEFT JOIN regions rs ON rs.cortar_no=substr(cx.cortar_no,1,2)||'00000000'
        LEFT JOIN regions r ON r.cortar_no=substr(cx.cortar_no,1,5)||'00000'
        WHERE e.event_type='PRICE_CHANGE'
          AND e.old_price BETWEEN ? AND ? AND e.new_price BETWEEN ? AND ?
          AND (e.new_price-e.old_price)*1.0/e.old_price BETWEEN -0.5 AND 0.5
          AND e.old_price<>e.new_price{where_trade}
        ORDER BY e.event_date DESC, abs(e.new_price-e.old_price) DESC LIMIT ?
    """
    with _open_db() as c:
        rows = c.execute(sql, params).fetchall()
    return {
        "trade": trade,
        "items": [
            {
                "event_date": r[0],
                "complex_no": r[1],
                "complex_name": r[2],
                "trade_type": r[3],
                "old_price": r[4],
                "new_price": r[5],
                "region_name": r[6],
                "rate": r[7],
            }
            for r in rows
        ],
    }


@app.get("/health")
def health():
    return {"ok": True, "db": str(DB_PATH), "tables": sorted(ALLOWED_TABLES)}


@app.get("/stats/recent-tx")
def recent_tx(days: int = 7):
    """Counts of real-estate filings in the last `days` days, indexed by
    contract date (`deal_ymd`). Contract date is used (not inserted_at)
    because inserted_at spikes during back-fills; contract date gives a
    stable trailing flow. Note: filings can be registered up to 30 days
    after the contract, so the most recent 1-2 weeks are partially
    under-estimated until late filings catch up.
    """
    if days < 1 or days > 365:
        raise HTTPException(400, "days out of range")
    cutoff = f"-{days} days"
    out = {"days": days, "sale": 0, "jeonse": 0, "wolse": 0}
    with _open_db() as c:
        existing = {
            r[0]
            for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "transactions" in existing:
            out["sale"] += c.execute(
                "SELECT COUNT(*) FROM transactions WHERE deal_ymd >= date('now', ?) AND is_cancelled = 0",
                (cutoff,),
            ).fetchone()[0]
        if "offi_transactions" in existing:
            out["sale"] += c.execute(
                "SELECT COUNT(*) FROM offi_transactions WHERE deal_ymd >= date('now', ?) AND is_cancelled = 0",
                (cutoff,),
            ).fetchone()[0]
        # 주의: '+monthly_rent' 는 SQLite 가 monthly_rent 인덱스(비선택적, 풀스캔 128s)를
        # 못 쓰게 막아 deal_ymd 인덱스(7일치 시크, 0.01s)를 쓰게 강제하는 관용구다. 빼지 말 것.
        if "rentals" in existing:
            out["jeonse"] += c.execute(
                "SELECT COUNT(*) FROM rentals WHERE deal_ymd >= date('now', ?) AND +monthly_rent = 0",
                (cutoff,),
            ).fetchone()[0]
            out["wolse"] += c.execute(
                "SELECT COUNT(*) FROM rentals WHERE deal_ymd >= date('now', ?) AND +monthly_rent > 0",
                (cutoff,),
            ).fetchone()[0]
        if "offi_rentals" in existing:
            out["jeonse"] += c.execute(
                "SELECT COUNT(*) FROM offi_rentals WHERE deal_ymd >= date('now', ?) AND +monthly_rent = 0",
                (cutoff,),
            ).fetchone()[0]
            out["wolse"] += c.execute(
                "SELECT COUNT(*) FROM offi_rentals WHERE deal_ymd >= date('now', ?) AND +monthly_rent > 0",
                (cutoff,),
            ).fetchone()[0]
    return out


@app.get("/stats/freshness")
def freshness():
    """데이터 신선도 — '오늘 공개된 실거래' 배지용 (silgga 벤치마크).

    가장 최근 수집분(inserted_at 최신 날짜)에 새로 들어온 실거래 건수를 매매/전세/
    월세로 집계. inserted_at 은 UTC 저장이라 date() 비교도 UTC 로 일관되게 한다.
    last_updated 는 전체 테이블 중 가장 최근 inserted 시각(UTC ISO).
    """
    out = {"new_sale": 0, "new_jeonse": 0, "new_wolse": 0, "last_updated": None}
    with _open_db() as c:
        existing = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}

        def latest(tbl: str) -> str | None:
            if tbl not in existing:
                return None
            # MAX(date(inserted_at)) 는 date(inserted_at) 표현식 인덱스를 쓴다.
            # raw MAX(inserted_at) 는 일부 테이블에 raw 인덱스가 없어 풀스캔(느림).
            return c.execute(f"SELECT MAX(date(inserted_at)) FROM {tbl}").fetchone()[0]

        def new_on_latest(tbl: str, extra: str = "") -> int:
            if tbl not in existing:
                return 0
            return c.execute(
                f"SELECT COUNT(*) FROM {tbl} "
                f"WHERE date(inserted_at)=(SELECT MAX(date(inserted_at)) FROM {tbl}){extra}"
            ).fetchone()[0]

        # 매매 = 아파트 + 오피스텔 거래
        out["new_sale"] = (new_on_latest("transactions", " AND is_cancelled=0")
                           + new_on_latest("offi_transactions", " AND is_cancelled=0"))
        # 전세 = 보증금만(monthly_rent=0), 월세 = monthly_rent>0
        # +monthly_rent: monthly_rent 인덱스(풀스캔) 대신 date(inserted_at) 인덱스 강제(위 recent_tx 참조)
        out["new_jeonse"] = (new_on_latest("rentals", " AND +monthly_rent=0")
                             + new_on_latest("offi_rentals", " AND +monthly_rent=0"))
        out["new_wolse"] = (new_on_latest("rentals", " AND +monthly_rent>0")
                           + new_on_latest("offi_rentals", " AND +monthly_rent>0"))
        # 가장 최근 갱신 시각(UTC) — 테이블별 max 중 최대
        ups = [u for u in (latest("transactions"), latest("rentals"),
                           latest("offi_transactions"), latest("offi_rentals")) if u]
        out["last_updated"] = max(ups) if ups else None
    return out


@app.get("/stats/tx-recovery")
def tx_recovery(days: int = 90, min_samples: int = 3, order: str = "asc",
                sido: str | None = None, sigungu: str | None = None, dong: str | None = None, limit: int = 200):
    """전고점 대비 회복률 — '저평가 단지 발굴' (apt2 반등지수/회복률 벤치마크).

    단지×평형(매칭평형)별 [역대 최고 실거래가] 대비 [최근 days일 평균가] 비율.
    회복률 100% = 전고점 회복, 낮을수록 전고점 대비 저평가.
    tx_avg_rollup(매일 빌드, [[verify_tx_rollup]] 검증) 의 일별 max_amt/sum_amt 로
    빠르게 재구성. order=asc(저평가순)/desc(회복순). 지역 스코핑으로 콜드도 빠름.
    """
    if order not in ("asc", "desc"):
        raise HTTPException(400, "order must be asc|desc")
    if not (USE_TX_ROLLUP and _rollup_ready()):
        raise HTTPException(503, "tx_avg_rollup 미빌드 — build_tx_rollups.py 실행 필요")
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit out of range")

    reg_clause, reg_params = "", []
    if dong:
        reg_clause = (" AND complex_no IN (SELECT complex_no FROM complexes "
                      "WHERE cortar_no = ?)")
        reg_params = [dong]
    elif sigungu:
        reg_clause = (" AND complex_no IN (SELECT complex_no FROM complexes "
                      "WHERE substr(cortar_no,1,5)=substr(?,1,5))")
        reg_params = [sigungu]
    elif sido:
        reg_clause = (" AND complex_no IN (SELECT complex_no FROM complexes "
                      "WHERE substr(cortar_no,1,2)=substr(?,1,2))")
        reg_params = [sido]

    # 전고점 이상치 방어: 국토부 원본의 금액 오류(5.2억→52억 오타)와, 지방 구축의
    # 단발 고가(검증 안 된 1건)가 전고점을 오염시켜 회복률을 비정상적으로 낮게 만든다.
    # 전고점은 "2위 거래가 뒷받침해야 신뢰" → 일별 최고가 1위가 2위의 2배를 넘으면
    # 단발(미검증)로 보고 2위를 전고점으로 쓴다. 진짜 전고점은 근처에 다른 거래가 있어
    # 1·2위가 2배씩 벌어지지 않는다. (오염 사례: 호매실 99A 52억, 익산 아름드리 2.15억)
    sql = f"""
        WITH ranked AS (
          SELECT complex_no cno, pyeong, max_amt,
                 ROW_NUMBER() OVER (PARTITION BY complex_no, pyeong ORDER BY max_amt DESC) rn
          FROM tx_avg_rollup WHERE kind='sale'{reg_clause}
        ),
        peak AS (
          SELECT cno, pyeong,
                 CASE WHEN m2 IS NOT NULL AND m1 > 2.0*m2 THEN m2 ELSE m1 END AS peak_amt
          FROM (SELECT cno, pyeong,
                       MAX(CASE WHEN rn=1 THEN max_amt END) m1,
                       MAX(CASE WHEN rn=2 THEN max_amt END) m2
                FROM ranked WHERE rn<=2 GROUP BY cno, pyeong)
        ),
        recent AS (
          SELECT complex_no cno, pyeong, SUM(sum_amt)*1.0/SUM(n) cur, SUM(n) n,
                 MAX(deal_ymd) last_ymd
          FROM tx_avg_rollup WHERE kind='sale' AND deal_ymd>=date('now', ?){reg_clause}
          GROUP BY complex_no, pyeong HAVING SUM(n) >= ?
        )
        SELECT cx.complex_name, {_REGION_NAME_COL}, r.pyeong,
               p.peak_amt, r.cur, r.n, r.last_ymd, r.cno,
               r.cur*100.0/p.peak_amt AS recovery
        FROM recent r
        JOIN peak p ON p.cno=r.cno AND p.pyeong=r.pyeong
        JOIN complexes cx ON cx.complex_no=r.cno
        {_REGION_JOINS}
        WHERE p.peak_amt > 0
        ORDER BY recovery {order.upper()}
        LIMIT ?
    """
    params = [*reg_params, f"-{days} days", *reg_params, min_samples, limit]
    with _open_db() as c:
        rows = c.execute(sql, params).fetchall()
    items = [{
        "complex_no": r[7], "complex_name": r[0], "region_name": r[1],
        "pyeong": r[2], "peak_amt": r[3], "cur_avg": round(r[4]),
        "n": r[5], "last_ymd": r[6], "recovery_rate": round(r[8], 1),
        "gap_from_peak": round(r[3] - r[4]),
    } for r in rows]
    return {"days": days, "order": order, "count": len(items), "items": items}


@app.get("/stats/region-compare")
def region_compare(days: int = 30, trade: str = "A1"):
    """시도별 실거래 비교표 — 거래건수 + 국민평형(59/84㎡) 평균가 (silgga 벤치마크).

    표준면적: 전용 59㎡=58~62, 84㎡=83~86 밴드. 매매(A1)/전세(B1) 지원.
    거래건수 많은 순. SIDO_NAMES 로 코드→이름.
    """
    if days < 1 or days > 365:
        raise HTTPException(400, "days out of range")
    if trade not in ("A1", "B1"):
        raise HTTPException(400, "trade must be A1|B1")
    if trade == "A1":
        tbl, amt, extra = "transactions", "deal_amount", " AND tx.is_cancelled=0"
    else:
        tbl, amt, extra = "rentals", "deposit", " AND tx.monthly_rent=0"
    sql = f"""
        SELECT substr(cx.cortar_no,1,2) AS sido, COUNT(*) AS n,
          ROUND(AVG(CASE WHEN tx.excl_use_ar BETWEEN 58 AND 62 THEN tx.{amt} END)) AS avg59,
          COUNT(CASE WHEN tx.excl_use_ar BETWEEN 58 AND 62 THEN 1 END) AS n59,
          ROUND(AVG(CASE WHEN tx.excl_use_ar BETWEEN 83 AND 86 THEN tx.{amt} END)) AS avg84,
          COUNT(CASE WHEN tx.excl_use_ar BETWEEN 83 AND 86 THEN 1 END) AS n84
        FROM {tbl} tx JOIN complexes cx ON cx.complex_no=tx.matched_complex_no
        WHERE tx.deal_ymd>=date('now', ?) AND tx.matched_complex_no IS NOT NULL{extra}
        GROUP BY 1 ORDER BY 2 DESC
    """
    # 전국 집계(코드 '00') — 분위기 카드의 전국 big 카드와 병합되도록 동일 평형 밴드.
    nat_sql = f"""
        SELECT COUNT(*) n,
          ROUND(AVG(CASE WHEN tx.excl_use_ar BETWEEN 58 AND 62 THEN tx.{amt} END)) avg59,
          COUNT(CASE WHEN tx.excl_use_ar BETWEEN 58 AND 62 THEN 1 END) n59,
          ROUND(AVG(CASE WHEN tx.excl_use_ar BETWEEN 83 AND 86 THEN tx.{amt} END)) avg84,
          COUNT(CASE WHEN tx.excl_use_ar BETWEEN 83 AND 86 THEN 1 END) n84
        FROM {tbl} tx
        WHERE tx.deal_ymd>=date('now', ?) AND tx.matched_complex_no IS NOT NULL{extra}
    """
    with _open_db() as c:
        rows = c.execute(sql, (f"-{days} days",)).fetchall()
        nat = c.execute(nat_sql, (f"-{days} days",)).fetchone()
    items = [{
        "sido_code": "00", "sido_name": "전국",
        "n": nat[0], "avg59": nat[1], "n59": nat[2], "avg84": nat[3], "n84": nat[4],
    }] if nat else []
    items += [{
        "sido_code": r[0], "sido_name": SIDO_NAMES.get(r[0], r[0]),
        "n": r[1], "avg59": r[2], "n59": r[3], "avg84": r[4], "n84": r[5],
    } for r in rows if r[0] in SIDO_NAMES]
    return {"days": days, "trade": trade, "items": items}


@app.get("/stats/today-deals")
def today_deals(trade: str = "A1", min_discount: float = 0.05, limit: int = 24,
                sort: str = "price"):
    """오늘 신규 등록 매물 중 '급매' — 오늘의매물 카드뉴스용.

    article_confirm_ymd(네이버 매물 확인일)가 최신일자인 매물 중, 같은 단지·평형의
    최근 180일 실거래 평균(tx_avg_rollup) 대비 min_discount 이상 싼 것.
    sort: price(호가 높은 순, 기본) / discount(할인율 큰 순).
    """
    if trade not in ("A1", "B1", "B2"):
        raise HTTPException(400, "trade must be A1|B1|B2")
    if sort not in ("price", "discount"):
        raise HTTPException(400, "sort must be price|discount")
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit out of range")
    kind = {"A1": "sale", "B1": "jeonse", "B2": "wolse"}[trade]
    md = abs(min_discount)
    order_sql = "price DESC" if sort == "price" else "disc ASC"
    # 월세(B2)는 '가격'이 월세료(rent_price)고 rollup wolse도 monthly_rent 기준.
    # 매매/전세는 deal_or_warrant_price(매매가/보증금). trade별로 비교 컬럼을 맞춘다.
    pcol = "l.rent_price" if trade == "B2" else "l.deal_or_warrant_price"
    # av(실거래평균) CTE 를 '오늘 신규 매물이 있는 단지'로 스코핑 → 전국 전체 집계(콜드 38s)
    # 회피. today_cx 가 작아 rollup 조회가 인덱스 시크로 빨라진다.
    sql = f"""
        WITH today_cx AS (
          SELECT DISTINCT complex_no FROM listings_current
          WHERE article_confirm_ymd=(SELECT MAX(article_confirm_ymd) FROM listings_current)
            AND trade_type=? AND complex_no IS NOT NULL
        ),
        av AS (
          SELECT complex_no, pyeong, SUM(sum_amt)*1.0/SUM(n) avg_real, SUM(n) n_real
          FROM tx_avg_rollup
          WHERE kind=? AND deal_ymd>=date('now','-180 days')
            AND complex_no IN (SELECT complex_no FROM today_cx)
          GROUP BY complex_no, pyeong HAVING SUM(n) >= 3
        )
        SELECT l.article_no, l.complex_no, cx.complex_name, l.area_name, l.area1_m2,
               {pcol} AS price, l.floor_info, l.direction,
               av.avg_real, av.n_real,
               ({pcol} - av.avg_real)*1.0/av.avg_real AS disc,
               l.realtor_name, {_REGION_NAME_COL}
        FROM listings_current l
        JOIN av ON av.complex_no=l.complex_no AND av.pyeong=l.area_name
        JOIN complexes cx ON cx.complex_no=l.complex_no
        {_REGION_JOINS}
        WHERE l.article_confirm_ymd = (SELECT MAX(article_confirm_ymd) FROM listings_current)
          AND l.trade_type=? AND {pcol} > 0
          AND ({pcol} - av.avg_real)*1.0/av.avg_real <= -?
        ORDER BY {order_sql}
        LIMIT ?
    """
    with _open_db() as c:
        rows = c.execute(sql, (trade, kind, trade, md, limit)).fetchall()
    items = [{
        "article_no": r[0], "complex_no": r[1], "complex_name": r[2],
        "area_name": r[3], "area1_m2": r[4], "price": r[5],
        "floor_info": r[6], "direction": r[7], "avg_real": round(r[8]),
        "n_real": r[9], "discount": round(r[10], 3), "realtor_name": r[11],
        "region_name": r[12],
        "naver_url": f"https://new.land.naver.com/complexes/{r[1]}?articleNo={r[0]}",
    } for r in rows]
    return {"trade": trade, "min_discount": md, "count": len(items), "items": items}


@app.get("/stats/today-listings-stats")
def today_listings_stats():
    """오늘 신규 등록 매물 통계 — 오늘의매물 하단용.
    최신 article_confirm_ymd 기준 신규 매물의 거래유형별 건수·지역 분포·가격대."""
    with _open_db() as c:
        ymd = c.execute("SELECT MAX(article_confirm_ymd) FROM listings_current").fetchone()[0]
        by_trade = {r[0]: r[1] for r in c.execute(
            "SELECT trade_type, COUNT(*) FROM listings_current WHERE article_confirm_ymd=? "
            "GROUP BY 1", (ymd,)).fetchall()}
        total = sum(by_trade.values())
        by_sido = [{"sido_name": SIDO_NAMES.get(r[0], r[0]), "n": r[1]} for r in c.execute(
            "SELECT substr(cx.cortar_no,1,2) sido, COUNT(*) n FROM listings_current l "
            "JOIN complexes cx ON cx.complex_no=l.complex_no "
            "WHERE l.article_confirm_ymd=? GROUP BY 1 ORDER BY 2 DESC LIMIT 10", (ymd,)).fetchall()
            if r[0] in SIDO_NAMES]
        # 매매 가격대 분포(억 단위 버킷)
        price_bands = [{"band": r[0], "n": r[1]} for r in c.execute(
            """SELECT CASE
                  WHEN deal_or_warrant_price < 300000000 THEN '3억 미만'
                  WHEN deal_or_warrant_price < 500000000 THEN '3~5억'
                  WHEN deal_or_warrant_price < 700000000 THEN '5~7억'
                  WHEN deal_or_warrant_price < 1000000000 THEN '7~10억'
                  WHEN deal_or_warrant_price < 1500000000 THEN '10~15억'
                  ELSE '15억 이상' END band, COUNT(*) n
               FROM listings_current WHERE article_confirm_ymd=? AND trade_type='A1'
                 AND deal_or_warrant_price>0 GROUP BY 1""", (ymd,)).fetchall()]
    # 표준 정렬(가격대)
    order = ['3억 미만', '3~5억', '5~7억', '7~10억', '10~15억', '15억 이상']
    price_bands.sort(key=lambda x: order.index(x["band"]) if x["band"] in order else 99)
    return {"ymd": ymd, "total": total,
            "sale": by_trade.get("A1", 0), "jeonse": by_trade.get("B1", 0),
            "wolse": by_trade.get("B2", 0),
            "by_sido": by_sido, "price_bands": price_bands}


@app.get("/stats/sigungu-list")
def sigungu_list(sido: str | None = None):
    """시군구 드롭다운용 목록 (regions.cortar_type='dvsn').
    sido 지정 시 해당 시도(2자리 prefix)로 필터.
    """
    with _open_db() as c:
        if sido:
            rows = c.execute(
                "SELECT cortar_no, cortar_name FROM regions "
                "WHERE cortar_type='dvsn' AND substr(cortar_no,1,2)=substr(?,1,2) "
                "ORDER BY cortar_name",
                (sido,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT cortar_no, cortar_name FROM regions "
                "WHERE cortar_type='dvsn' ORDER BY cortar_no"
            ).fetchall()
    return {"items": [{"code": r[0], "name": r[1]} for r in rows]}


@app.get("/stats/dong-list")
def dong_list(sigungu: str | None = None, dong: str | None = None):
    """동(읍면동) 드롭다운용 목록 (regions.cortar_type='sec').
    sigungu(시군구 코드) 지정 시 해당 시군구(5자리 prefix)로 필터. 지도 지역 이동용.
    """
    if not sigungu:
        return {"items": []}
    with _open_db() as c:
        rows = c.execute(
            "SELECT cortar_no, cortar_name FROM regions "
            "WHERE cortar_type='sec' AND substr(cortar_no,1,5)=substr(?,1,5) "
            "ORDER BY cortar_name",
            (sigungu,),
        ).fetchall()
    return {"items": [{"code": r[0], "name": r[1]} for r in rows]}


@app.get("/stats/quick-deals")
def quick_deals(
    days: int = 90,
    min_samples: int = 5,
    asset: str = "apt",  # apt | offi | all
    trade_type: str = "A1",  # A1=매매 | B1=전세
    pyeong: int | None = None,  # 10/20/30 → 평대 / 40 → 40평 이상 (40·50 통합)
    sido: str | None = None,
    sigungu: str | None = None, dong: str | None = None,
    min_discount: float = 0.0,  # 최소 할인율 (0.05 → 5% 이상 저렴한 매물만)
    max_discount: float = 0.5,  # 최대 할인율 (0.5 → -50%까지만, 그 이상은 데이터 오류로 컷)
    min_listings: int = 3,      # (단지, area_name) 안에 매물 N개 이상이어야 결과에 포함
    limit: int = 200,
):
    """급매찾기: 단지·평형(layout)별 최근 N개월 실거래 평균 대비 저렴한 매물.

    매칭 방식 (옛 area_key=ROUND(공급면적) 정수 매칭의 한계 보완):
    - listings.area_name (예: "67A") 은 그대로 complex_areas.pyeong_name 과 매핑됨
    - transactions.excl_use_ar(전용) 는 같은 단지 안 complex_areas.exclusive_area 와
      가장 가까운 pyeong 으로 분류 → 즉, area_name 단위로 그룹화
    - 같은 공급면적이라도 layout(67A/67B) 가 다르면 별 평형으로 취급

    기준:
    - 단지×layout(area_name)별로 최근 `days`일 **중개거래** 실거래 평균 (직거래 제외)
    - `min_samples` 건 이상 거래된 (단지, layout) 만 평균 산출 → 3개월 거래 없는
      단지·평형은 자동 제외
    - 현재 매물 호가 < 평균 실거래가, 할인율 절댓값 ≥ min_discount
    - 시군구/시도 필터: complexes.cortar_no 앞자리 prefix
    """
    if limit < 1 or limit > 1000:
        raise HTTPException(400, "limit out of range")
    if days < 1 or days > 3650:
        raise HTTPException(400, "days out of range")
    if asset not in ("apt", "offi", "all"):
        raise HTTPException(400, "asset must be apt|offi|all")
    if trade_type not in ("A1", "B1"):
        raise HTTPException(400, "trade_type must be A1|B1")
    if min_samples < 1:
        raise HTTPException(400, "min_samples must be >= 1")

    if trade_type == "A1":
        sale_tables = (
            ["transactions"] if asset == "apt"
            else ["offi_transactions"] if asset == "offi"
            else ["transactions", "offi_transactions"]
        )
        amount_col = "tx.deal_amount"
        # 해제거래 제외 — build_tx_rollups.KINDS['sale'/'offi_sale'] 와 글자까지 동일해야
        # rollup↔live 검증(verify_tx_rollup)이 통과한다.
        extra_filter = "AND COALESCE(tx.dealing_gbn,'') <> '직거래' AND tx.is_cancelled = 0"
    else:  # B1 전세
        sale_tables = (
            ["rentals"] if asset == "apt"
            else ["offi_rentals"] if asset == "offi"
            else ["rentals", "offi_rentals"]
        )
        amount_col = "tx.deposit"
        extra_filter = "AND COALESCE(tx.monthly_rent,0) = 0"
    cutoff = f"-{days} days"

    # 시군구 필터: 5자리 + 5'0' 형태로 cortar_no 매핑.
    region_clause = ""
    region_params: list[Any] = []
    if dong:
        region_clause = " AND cx.cortar_no = ?"
        region_params.append(dong)
    elif sigungu:
        region_clause = " AND substr(cx.cortar_no,1,5)=substr(?,1,5)"
        region_params.append(sigungu)
    elif sido:
        region_clause = " AND substr(cx.cortar_no,1,2)=substr(?,1,2)"
        region_params.append(sido)

    # 평형(공급면적 기준) 필터: 10/20/30 → [N0, N0+10)평, 40 → 40평 이상.
    # (40·50평대 통합 — 40평 이상은 상한 없음). 1평 = 3.3058㎡. area1_m2 = 공급면적.
    pyeong_clause = ""
    pyeong_params: list[Any] = []
    if pyeong is not None:
        if pyeong not in (10, 20, 30, 40):
            raise HTTPException(400, "pyeong must be 10|20|30|40 (40=40평 이상)")
        lo = pyeong * 3.3058
        if pyeong >= 40:  # 40평 이상 (상한 없음)
            pyeong_clause = " AND area1_m2 >= ?"
            pyeong_params.append(lo)
        else:
            hi = (pyeong + 10) * 3.3058
            pyeong_clause = " AND area1_m2 >= ? AND area1_m2 < ?"
            pyeong_params.extend([lo, hi])

    # 거래 → pyeong 매핑: 단지 안에서 |excl_use_ar - exclusive_area| 가 최소인
    # pyeong_name 을 선택. 같은 단지 안 동일 전용 변형(예: 84A/84B) 이 있으면
    # 둘 다 같은 정도로 가까워 임의 1개로 떨어지는데, 그 경우 어차피 실거래가도
    # 유사해 그룹 차이가 거의 없어 무방.
    # SQLite 는 correlated subquery 의 ORDER BY 안에서 외부 컬럼 참조를 못해
    # ROW_NUMBER + JOIN 으로 가장 가까운 pyeong 을 찾음. PARTITION BY 는
    # tx.rowid (테이블 내 유일).
    #
    # 허용 오차(area_tol) 가 핵심: complex_areas 가 부실하게 등록된 단지
    # (예: 100㎡대 거래가 활발한데 pyeong 은 "48" 하나만 등록된 경우) 에서는
    # "가장 가까운" 매칭이 큰 오차를 일으켜 평균을 왜곡시킨다. 따라서 차이가
    # 5㎡(=약 1.5평) 보다 크면 매칭에서 제외 → 결과적으로 그 거래는 사라지고
    # 평균에도 안 들어감. 동시에 그 layout 매물도 매칭 안 돼 결과에서 빠짐.
    area_tol = 5.0

    # ── 사전집계(rollup) 경로 ─────────────────────────────────────────
    # build_tx_rollups.py 가 위 매칭+집계를 일단위로 미리 계산해 둔 경우,
    # 143만행 라이브 매칭 대신 tx_avg_rollup 에서 SUM/SUM 으로 재구성한다.
    # 금액이 정수라 SUM(sum_amt)*1.0/SUM(n) == AVG(amount) 가 부동소수점까지
    # 동일(합계 < 2^53). MIN/MAX/COUNT 도 exact. avg_excl(REAL 합산순서)만
    # 마지막 ulp 차이 가능. 검증: scripts/verify_tx_rollup.py 전수비교.
    if USE_TX_ROLLUP and _rollup_ready():
        _kind_of = {"transactions": "sale", "rentals": "jeonse",
                    "offi_transactions": "offi_sale", "offi_rentals": "offi_jeonse"}
        kinds = [_kind_of[t] for t in sale_tables]
        roll_region = ""
        roll_region_params: list[Any] = []
        if dong:
            roll_region = (" AND complex_no IN (SELECT complex_no FROM complexes "
                           "WHERE cortar_no = ?)")
            roll_region_params = [dong]
        elif sigungu:
            roll_region = (" AND complex_no IN (SELECT complex_no FROM complexes "
                           "WHERE substr(cortar_no,1,5)=substr(?,1,5))")
            roll_region_params = [sigungu]
        elif sido:
            roll_region = (" AND complex_no IN (SELECT complex_no FROM complexes "
                           "WHERE substr(cortar_no,1,2)=substr(?,1,2))")
            roll_region_params = [sido]
        real_tx_sql = f"""
          SELECT complex_no AS cno, pyeong,
                 SUM(sum_amt) * 1.0 / SUM(n) AS avg_real,
                 MIN(min_amt) AS min_real,
                 MAX(max_amt) AS max_real,
                 SUM(sum_excl) * 1.0 / SUM(n) AS avg_excl,
                 SUM(n) AS n_real
          FROM tx_avg_rollup INDEXED BY txr_kind_ymd_idx
          WHERE kind IN ({",".join("?" * len(kinds))})
            AND deal_ymd >= date('now', ?){roll_region}
          GROUP BY complex_no, pyeong
          HAVING SUM(n) >= ?
        """
        real_tx_params: list[Any] = [*kinds, cutoff, *roll_region_params, min_samples]
    else:
        real_tx_sql = None  # 레거시 경로 사용
    # 실거래 집계 자체를 선택 지역으로 좁힌다. 안 그러면 시군구를 골라도 전국 거래를
    # 다 집계(ROW_NUMBER 윈도우 + GROUP BY)한 뒤 매물만 거르므로 작은 시군구도 ~20s.
    # matched_complex_no 를 그 지역 단지로 제한 → 거래량 급감 → 빠름.
    tx_region_clause = ""
    tx_region_params: list[Any] = []
    if sigungu:
        tx_region_clause = (" AND tx.matched_complex_no IN (SELECT complex_no FROM "
                            "complexes WHERE substr(cortar_no,1,5)=substr(?,1,5))")
        tx_region_params = [sigungu]
    elif sido:
        tx_region_clause = (" AND tx.matched_complex_no IN (SELECT complex_no FROM "
                            "complexes WHERE substr(cortar_no,1,2)=substr(?,1,2))")
        tx_region_params = [sido]
    union_real = " UNION ALL ".join(
        f"""SELECT cno, pyeong, tx_excl, amount FROM (
            SELECT tx.matched_complex_no AS cno,
                   ca.pyeong_name AS pyeong,
                   tx.excl_use_ar AS tx_excl,
                   {amount_col} AS amount,
                   ROW_NUMBER() OVER (
                     PARTITION BY tx.rowid
                     ORDER BY ABS(ca.exclusive_area - tx.excl_use_ar)
                   ) AS rn
            FROM {tbl} tx
            JOIN complex_areas ca
              ON ca.complex_no = tx.matched_complex_no
             AND ca.exclusive_area IS NOT NULL
             AND ABS(ca.exclusive_area - tx.excl_use_ar) <= {area_tol}
            WHERE tx.matched_complex_no IS NOT NULL
              AND tx.deal_ymd >= date('now', ?)
              AND tx.excl_use_ar IS NOT NULL
              {extra_filter}
              AND tx.matched_score >= 0.85{tx_region_clause}
        ) WHERE rn = 1"""
        for tbl in sale_tables
    )
    real_params: list[Any] = []
    for _ in sale_tables:
        real_params.append(cutoff)
        real_params.extend(tx_region_params)

    # 단지×평형 단위로 집계: 같은 (단지, area_name) 안 매물들을 한 행으로 묶고
    # 호가 min/max, 할인율 min/max 를 표시. 한 행 = "단지 X의 Y 평형에서 N개
    # 매물이 호가 a억~b억으로 나와있고, 실거래평균 대비 c%~d% 저렴" 구조.
    # min_discount: 그룹 안에 한 매물이라도 그 할인 폭 이상이면 노출 (discount_min ≤ -min_discount).
    # max_discount: 가장 큰 할인 폭(discount_min)이 -max_discount 이상이어야 — 너무 극단치 데이터 컷.
    if real_tx_sql is not None:
        # rollup 경로: real_tx 를 사전집계에서 재구성 (수치 동일 — 위 주석 참조)
        with_head = f"WITH real_tx AS ({real_tx_sql}),"
        head_params: list[Any] = real_tx_params
    else:
        with_head = f"""
        WITH tx_p AS ({union_real}),
        real_tx AS (
          SELECT cno, pyeong,
                 AVG(amount) AS avg_real,
                 MIN(amount) AS min_real,
                 MAX(amount) AS max_real,
                 AVG(tx_excl) AS avg_excl,
                 COUNT(*)    AS n_real
          FROM tx_p
          WHERE pyeong IS NOT NULL
          GROUP BY cno, pyeong
          HAVING COUNT(*) >= ?
        ),"""
        head_params = [*real_params, min_samples]

    sql = f"""
        {with_head}
        listing_groups AS (
          SELECT complex_no, area_name,
                 COUNT(*) AS n_listings,
                 MIN(deal_or_warrant_price) AS asking_min,
                 MAX(deal_or_warrant_price) AS asking_max,
                 AVG(deal_or_warrant_price) AS asking_avg,
                 MIN(area1_m2)              AS area1_m2
          FROM listings_current
          WHERE trade_type=? AND deal_or_warrant_price > 0
            AND complex_no IS NOT NULL AND area_name IS NOT NULL
            {pyeong_clause}
          GROUP BY complex_no, area_name
          HAVING COUNT(*) >= ?
        )
        SELECT
          lg.complex_no, lg.area_name, lg.area1_m2,
          lg.n_listings, lg.asking_min, lg.asking_max, lg.asking_avg,
          rx.avg_real, rx.min_real, rx.max_real, rx.n_real, rx.avg_excl,
          (lg.asking_min - rx.avg_real) * 1.0 / rx.avg_real AS discount_min,
          (lg.asking_max - rx.avg_real) * 1.0 / rx.avg_real AS discount_max,
          (lg.asking_avg - rx.avg_real) * 1.0 / rx.avg_real AS discount_avg,
          cx.complex_name, cx.cortar_no, {_REGION_NAME_COL}
        FROM listing_groups lg
        JOIN real_tx rx
          ON rx.cno = lg.complex_no
         AND rx.pyeong = lg.area_name
        LEFT JOIN complexes cx ON cx.complex_no = lg.complex_no
        {_REGION_JOINS}
        WHERE (lg.asking_min - rx.avg_real) * 1.0 / rx.avg_real <= ?
          AND (lg.asking_min - rx.avg_real) * 1.0 / rx.avg_real >= ?
          {region_clause}
        ORDER BY discount_min ASC
        LIMIT ?
    """
    params = [
        *head_params, trade_type, *pyeong_params, min_listings,
        -abs(min_discount), -abs(max_discount),
        *region_params, limit,
    ]
    with _open_db() as c:
        rows = c.execute(sql, params).fetchall()

    items = [
        {
            "complex_no": r[0],
            "area_name": r[1],
            "area1_m2": r[2],
            "n_listings": r[3],
            "asking_min": r[4],
            "asking_max": r[5],
            "asking_avg": r[6],
            "avg_real": r[7],
            "min_real": r[8],
            "max_real": r[9],
            "n_real": r[10],
            "avg_excl": r[11],
            "discount_min": r[12],   # 가장 저렴한 매물의 할인율 (가장 음수)
            "discount_max": r[13],   # 가장 비싼 매물의 할인율
            "discount_avg": r[14],   # 평균 호가의 할인율
            "complex_name": r[15],
            "cortar_no": r[16],
            "region_name": r[17],
            # 단지 페이지 / Naver 검증
            "naver_complex_url": f"https://new.land.naver.com/complexes/{r[0]}",
        }
        for r in rows
    ]
    return {
        "days": days, "min_samples": min_samples, "asset": asset,
        "trade_type": trade_type, "pyeong": pyeong,
        "sido": sido, "sigungu": sigungu,
        "min_discount": min_discount, "max_discount": max_discount,
        "min_listings": min_listings,
        "count": len(items), "items": items,
    }


@app.get("/stats/quick-deals-map")
def quick_deals_map(
    swlat: float, swlng: float, nelat: float, nelng: float,
    days: int = 90,
    trade_type: str = "A1",       # A1=매매 | B1=전세
    asset: str = "apt",           # apt | offi | all
    pyeong: int | None = None,    # 10/20/30/40(이상)
    min_discount: float = 0.05,   # 최소 할인율 (0.05 → 5% 이상 저렴)
    max_discount: float = 0.5,    # 극단치 컷
    min_samples: int = 5,         # (단지,평형) 실거래 N건 이상
    min_listings: int = 1,        # (단지,평형) 매물 N개 이상
    limit: int = 600,
):
    """지도용 급매찾기: bbox 안 단지×평형별 최근 N일 실거래 평균 대비
    min_discount 이상 저렴한 매물이 있는 단지를 단지당 '가장 큰 할인 1건'으로 축약.
    로직은 /stats/quick-deals 와 동일하되 지역 필터를 위경도 bbox 로 대체."""
    if not (swlat < nelat and swlng < nelng):
        raise HTTPException(400, "bad bounds")
    if trade_type not in ("A1", "B1"):
        raise HTTPException(400, "trade_type must be A1|B1")
    if asset not in ("apt", "offi", "all"):
        raise HTTPException(400, "asset must be apt|offi|all")

    with _open_db() as c:
        n_cx = c.execute(
            "SELECT COUNT(*) FROM complexes WHERE latitude BETWEEN ? AND ? "
            "AND longitude BETWEEN ? AND ?", (swlat, nelat, swlng, nelng)).fetchone()[0]
        # 너무 넓으면 실거래 집계가 무거워짐 → 줌인 유도
        if n_cx > 6000:
            return {"too_wide": True, "n_complexes": n_cx, "count": 0, "items": []}

        if trade_type == "A1":
            sale_tables = (["transactions"] if asset == "apt"
                           else ["offi_transactions"] if asset == "offi"
                           else ["transactions", "offi_transactions"])
            amount_col = "tx.deal_amount"
            extra_filter = "AND COALESCE(tx.dealing_gbn,'') <> '직거래' AND tx.is_cancelled = 0"
        else:
            sale_tables = (["rentals"] if asset == "apt"
                           else ["offi_rentals"] if asset == "offi"
                           else ["rentals", "offi_rentals"])
            amount_col = "tx.deposit"
            extra_filter = "AND COALESCE(tx.monthly_rent,0) = 0"
        cutoff = f"-{days} days"

        pyeong_clause = ""
        pyeong_params: list[Any] = []
        if pyeong is not None:
            if pyeong not in (10, 20, 30, 40):
                raise HTTPException(400, "pyeong must be 10|20|30|40")
            lo = pyeong * 3.3058
            if pyeong >= 40:
                pyeong_clause = " AND area1_m2 >= ?"; pyeong_params.append(lo)
            else:
                hi = (pyeong + 10) * 3.3058
                pyeong_clause = " AND area1_m2 >= ? AND area1_m2 < ?"
                pyeong_params.extend([lo, hi])

        area_tol = 5.0
        bbox_sub = ("SELECT complex_no FROM complexes WHERE latitude BETWEEN ? AND ? "
                    "AND longitude BETWEEN ? AND ?")
        bbox_params = [swlat, nelat, swlng, nelng]

        union_real = " UNION ALL ".join(
            f"""SELECT cno, pyeong, amount FROM (
                SELECT tx.matched_complex_no AS cno, ca.pyeong_name AS pyeong,
                       {amount_col} AS amount,
                       ROW_NUMBER() OVER (PARTITION BY tx.rowid
                         ORDER BY ABS(ca.exclusive_area - tx.excl_use_ar)) AS rn
                FROM {tbl} tx
                JOIN complex_areas ca ON ca.complex_no = tx.matched_complex_no
                  AND ca.exclusive_area IS NOT NULL
                  AND ABS(ca.exclusive_area - tx.excl_use_ar) <= {area_tol}
                WHERE tx.matched_complex_no IN ({bbox_sub})
                  AND tx.deal_ymd >= date('now', ?)
                  AND tx.excl_use_ar IS NOT NULL {extra_filter}
                  AND tx.matched_score >= 0.85
            ) WHERE rn = 1"""
            for tbl in sale_tables
        )
        real_params: list[Any] = []
        for _ in sale_tables:
            real_params.extend(bbox_params)
            real_params.append(cutoff)

        sql = f"""
            WITH tx_p AS ({union_real}),
            real_tx AS (
              SELECT cno, pyeong, AVG(amount) AS avg_real, COUNT(*) AS n_real
              FROM tx_p WHERE pyeong IS NOT NULL
              GROUP BY cno, pyeong HAVING COUNT(*) >= ?
            ),
            listing_groups AS (
              SELECT complex_no, area_name, COUNT(*) AS n_listings,
                     MIN(deal_or_warrant_price) AS asking_min,
                     MIN(area1_m2) AS area1_m2
              FROM listings_current
              WHERE trade_type=? AND deal_or_warrant_price > 0
                AND complex_no IS NOT NULL AND area_name IS NOT NULL
                AND complex_no IN ({bbox_sub})
                {pyeong_clause}
              GROUP BY complex_no, area_name HAVING COUNT(*) >= ?
            )
            SELECT lg.complex_no, lg.area_name, lg.area1_m2, lg.n_listings,
                   lg.asking_min, rx.avg_real, rx.n_real,
                   (lg.asking_min - rx.avg_real)*1.0/rx.avg_real AS discount,
                   cx.complex_name, cx.latitude, cx.longitude
            FROM listing_groups lg
            JOIN real_tx rx ON rx.cno = lg.complex_no AND rx.pyeong = lg.area_name
            LEFT JOIN complexes cx ON cx.complex_no = lg.complex_no
            WHERE (lg.asking_min - rx.avg_real)*1.0/rx.avg_real <= ?
              AND (lg.asking_min - rx.avg_real)*1.0/rx.avg_real >= ?
            ORDER BY discount ASC
            LIMIT ?
        """
        params = [
            *real_params, min_samples, trade_type, *bbox_params, *pyeong_params,
            min_listings, -abs(min_discount), -abs(max_discount), limit,
        ]
        rows = c.execute(sql, params).fetchall()

    # 단지당 '가장 큰 할인 1건' 으로 축약 (markers = 단지 단위)
    best: dict[str, dict] = {}
    for r in rows:
        cno, lat, lng = r[0], r[9], r[10]
        if lat is None or lng is None:
            continue
        prev = best.get(cno)
        if prev is None or r[7] < prev["discount"]:
            best[cno] = {
                "complex_no": cno, "complex_name": r[8],
                "lat": lat, "lng": lng,
                "area_name": r[1], "area1_m2": r[2],
                "n_listings": r[3], "asking_min": r[4],
                "avg_real": r[5], "n_real": r[6], "discount": r[7],
            }
    items = sorted(best.values(), key=lambda x: x["discount"])
    return {"too_wide": False, "n_complexes": n_cx, "count": len(items), "items": items}


def _norm_cdeal_date(s: str | None) -> str | None:
    """국토부 cdealDay 'YY.MM.DD' → 'YYYY-MM-DD'."""
    if not s:
        return None
    s = s.strip()
    parts = s.split(".")
    if len(parts) == 3 and len(parts[0]) == 2:
        return f"20{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    return s


def _cdeal_cutoff(months: int) -> str | None:
    """해제일(cdealDay 'YY.MM.DD') 비교용 cutoff 문자열. months<=0 → 제한없음(최대).
    cdealDay 가 전부 zero-pad 된 'YY.MM.DD' 라 문자열 비교가 시간순과 일치."""
    if not months or months <= 0:
        return None
    import calendar
    from datetime import date
    t = date.today()
    m, y = t.month - months, t.year
    while m <= 0:
        m += 12; y -= 1
    d = min(t.day, calendar.monthrange(y, m)[1])
    return f"{y % 100:02d}.{m:02d}.{d:02d}"


def _twin_sql(is_apt: bool) -> str:
    """이중신고 쌍둥이 키(금액 제외): 같은 호실(단지·전용·층) + 같은 계약일.
    - sgg_cd 필수: apt_seq/offi_nm 은 시군구 간 값이 겹쳐 false positive 유발.
    - deal_amount 제외: 이중신고는 보통 금액 정정해 재신고하므로 금액까지 같길 요구하면
      정정 케이스를 놓침. 한 호실은 같은 계약일에 두 번 거래될 수 없어 동일거래로 본다.
    (금액 동일 여부로 '이중신고취소' vs '금액정정신고' 를 구분한다.)"""
    return (
        ("t2.apt_seq=t.apt_seq" if is_apt
         else "t2.offi_nm=t.offi_nm AND t2.umd_nm=t.umd_nm")
        + " AND t2.sgg_cd=t.sgg_cd AND t2.deal_ymd=t.deal_ymd"
        + " AND t2.excl_use_ar=t.excl_use_ar AND t2.floor=t.floor")


def _cancel_tables(asset: str) -> list[str]:
    return (["transactions"] if asset == "apt"
            else ["offi_transactions"] if asset == "offi"
            else ["transactions", "offi_transactions"])


def _silv_where(sido, sigungu, months, kind=None):
    where = ["is_cancelled = 0"]
    params: list = []
    if sigungu:
        where.append("sgg_cd = ?"); params.append(sigungu)
    elif sido:
        where.append("substr(sgg_cd,1,2) = substr(?,1,2)"); params.append(sido)
    if months and months > 0:
        where.append("deal_ymd >= date('now', ?)"); params.append(f"-{months} months")
    if kind == "입주권":
        where.append("ownership_gbn = '입'")
    elif kind == "분양권":
        where.append("(ownership_gbn IS NULL OR ownership_gbn <> '입')")
    return " AND ".join(where), params


def _has_silv(c) -> bool:
    return "silv_transactions" in {
        r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


@app.get("/stats/presale-transactions")
def presale_transactions(
    sido: str | None = None, sigungu: str | None = None, dong: str | None = None,
    kind: str | None = None,       # 분양권 | 입주권
    months: int = 6, limit: int = 50, offset: int = 0,
):
    """분양권/입주권 전매 실거래 목록(해제건 제외). 신축·재건축 신규공급 세그먼트."""
    if limit < 1 or limit > 200:
        raise HTTPException(400, "limit out of range")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    if kind is not None and kind not in ("분양권", "입주권"):
        raise HTTPException(400, "kind must be 분양권|입주권")
    wsql, params = _silv_where(sido, sigungu, months, kind)
    with _open_db() as c:
        if not _has_silv(c):
            return {"total": 0, "offset": offset, "limit": limit, "count": 0, "items": []}
        total = c.execute(
            f"SELECT COUNT(*) FROM silv_transactions WHERE {wsql}", params).fetchone()[0]
        rows = c.execute(
            f"SELECT apt_nm, sgg_cd, umd_nm, excl_use_ar, floor, deal_amount, deal_ymd, "
            f"ownership_gbn, dealing_gbn, matched_complex_no "
            f"FROM silv_transactions WHERE {wsql} ORDER BY deal_ymd DESC LIMIT ? OFFSET ?",
            [*params, limit, offset]).fetchall()
    items = []
    for r in rows:
        sido_cd = (r[1] or "")[:2]
        items.append({
            "name": r[0], "sgg_cd": r[1],
            "region": " ".join(filter(None, [SIDO_NAMES.get(sido_cd), r[2]])),
            "umd_nm": r[2],
            "excl_use_ar": r[3], "pyeong": round(r[3] / 3.3058, 1) if r[3] else None,
            "floor": r[4], "deal_amount": r[5], "deal_ymd": r[6],
            "kind": "입주권" if (r[7] or "").strip() == "입" else "분양권",
            "dealing_gbn": r[8], "complex_no": r[9],
        })
    return {"sido": sido, "sigungu": sigungu, "kind": kind, "months": months,
            "total": total, "offset": offset, "limit": limit,
            "count": len(items), "items": items}


@app.get("/stats/presale-summary")
def presale_summary(sido: str | None = None, sigungu: str | None = None, dong: str | None = None, months: int = 6):
    """분양권/입주권 전매 요약: 총건수·분양권/입주권 분포·평균가."""
    wsql, params = _silv_where(sido, sigungu, months)
    with _open_db() as c:
        if not _has_silv(c):
            return {"total": 0, "n_bunyang": 0, "n_ipju": 0, "avg_amount": None}
        row = c.execute(
            f"SELECT COUNT(*), SUM(CASE WHEN ownership_gbn='입' THEN 1 ELSE 0 END), "
            f"AVG(deal_amount) FROM silv_transactions WHERE {wsql}", params).fetchone()
    total, n_ipju = row[0] or 0, row[1] or 0
    return {"total": total, "n_bunyang": total - n_ipju, "n_ipju": n_ipju,
            "avg_amount": round(row[2]) if row[2] else None}


@app.get("/stats/cancelled-transactions")
def cancelled_transactions(
    asset: str = "apt",            # apt | offi | all
    sido: str | None = None,       # 2자리(앞자리) 시도 코드
    sigungu: str | None = None, dong: str | None = None,    # 5자리 시군구 코드
    dealing: str | None = None,    # 중개거래 | 직거래
    months: int = 0,               # 해제일 기준 최근 N개월 (0=최대)
    limit: int = 50,
    offset: int = 0,
):
    """실거래 취소(해제) 조회. 국토부 신고 후 해제(cdealType='O')된 거래.
    - dealing_gbn(직거래/중개거래) 표기
    - cancel_type: 같은 호실+계약일에 살아있는 비취소 신고가 또 있으면
        * 그 신고와 금액이 같으면  'double'      → 이중신고 취소 (양쪽 동시신고)
        * 금액이 다르면           'correction'  → 금액정정 신고
      살아있는 쌍둥이가 없으면     'plain'       → 단순 취소 (거래 무산)
    - months: 해제일(cdealDay) 기준 최근 N개월. 0 이면 전체.
    """
    if asset not in ("apt", "offi", "all"):
        raise HTTPException(400, "asset must be apt|offi|all")
    if limit < 1 or limit > 200:
        raise HTTPException(400, "limit out of range")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    if dealing is not None and dealing not in ("중개거래", "직거래"):
        raise HTTPException(400, "dealing must be 중개거래|직거래")

    cutoff = _cdeal_cutoff(months)
    tables = _cancel_tables(asset)

    def filt(alias: str) -> tuple[str, list]:
        cl, p = "", []
        if sigungu:
            cl += f" AND {alias}.sgg_cd = ?"; p.append(sigungu)
        elif sido:
            cl += f" AND substr({alias}.sgg_cd,1,2) = substr(?,1,2)"; p.append(sido)
        if dealing:
            cl += f" AND {alias}.dealing_gbn = ?"; p.append(dealing)
        if cutoff:
            cl += f" AND json_extract({alias}.raw,'$.cdealDay') >= ?"; p.append(cutoff)
        return cl, p

    branches, params, count_total = [], [], 0
    with _open_db() as c:
        for tbl in tables:
            is_apt = tbl == "transactions"
            name_col = "apt_nm" if is_apt else "offi_nm"
            twin = _twin_sql(is_apt)
            live = ("AND t2.rowid<>t.rowid "
                    "AND COALESCE(json_extract(t2.raw,'$.cdealType'),'')<>'O'")
            fc, fp = filt("t")
            dong_col = ("json_extract(t.raw,'$.aptDong')" if is_apt else "NULL")
            reg_col = ("(TRIM(COALESCE(json_extract(t.raw,'$.rgstDate'),''))<>'')"
                       if is_apt else "0")
            branches.append(f"""
                SELECT '{'apt' if is_apt else 'offi'}' AS src,
                       t.{name_col} AS name, t.sgg_cd, t.umd_nm,
                       t.excl_use_ar, t.floor, t.deal_amount, t.deal_ymd,
                       json_extract(t.raw,'$.cdealDay') AS cday,
                       t.dealing_gbn, t.build_year, t.matched_complex_no,
                       EXISTS(SELECT 1 FROM {tbl} t2 WHERE {twin} {live}
                              AND t2.deal_amount=t.deal_amount) AS is_same,
                       EXISTS(SELECT 1 FROM {tbl} t2 WHERE {twin} {live}
                              AND t2.deal_amount<>t.deal_amount) AS is_diff,
                       {dong_col} AS dong, {reg_col} AS registered
                FROM {tbl} t
                WHERE json_extract(t.raw,'$.cdealType')='O'{fc}
            """)
            params.extend(fp)
            fc2, fp2 = filt("t")
            count_total += c.execute(
                f"SELECT COUNT(*) FROM {tbl} t "
                f"WHERE json_extract(t.raw,'$.cdealType')='O'{fc2}", fp2
            ).fetchone()[0]

        sql = (f"SELECT * FROM ({' UNION ALL '.join(branches)}) "
               f"ORDER BY cday DESC LIMIT ? OFFSET ?")
        rows = c.execute(sql, [*params, limit, offset]).fetchall()

    items = []
    for r in rows:
        is_same, is_diff = bool(r[12]), bool(r[13])
        ctype = "double" if is_same else "correction" if is_diff else "plain"
        sido_cd = (r[2] or "")[:2]
        items.append({
            "asset": r[0],
            "name": r[1],
            "sgg_cd": r[2],
            "region": " ".join(filter(None, [SIDO_NAMES.get(sido_cd), r[3]])),
            "umd_nm": r[3],
            "excl_use_ar": r[4],
            "pyeong": round(r[4] / 3.3058, 1) if r[4] else None,
            "floor": r[5],
            "deal_amount": r[6],
            "deal_ymd": r[7],
            "cdeal_date": _norm_cdeal_date(r[8]),
            "dealing_gbn": r[9],            # 직거래 | 중개거래
            "build_year": r[10],
            "complex_no": r[11],
            "cancel_type": ctype,          # double | correction | plain
            "is_double": is_same or is_diff,
            "dong": r[14],                 # 동 (아파트 매매만)
            "registered": bool(r[15]),     # 등기완료 여부
        })
    return {
        "asset": asset, "sido": sido, "sigungu": sigungu, "dealing": dealing,
        "months": months,
        "total": count_total, "offset": offset, "limit": limit,
        "count": len(items), "items": items,
    }


@app.get("/stats/cancelled-summary")
def cancelled_summary(
    asset: str = "apt",
    sido: str | None = None,
    sigungu: str | None = None, dong: str | None = None,
    months: int = 0,
):
    """실거래 취소 통계 (상단 표). 거래유형 토글과 무관하게 전체 분포를 집계.
    전체 / 중개거래 / 직거래 / 이중신고취소(동일금액) / 금액정정신고(다른금액) / 단순취소."""
    if asset not in ("apt", "offi", "all"):
        raise HTTPException(400, "asset must be apt|offi|all")
    cutoff = _cdeal_cutoff(months)
    tables = _cancel_tables(asset)

    def filt(alias: str) -> tuple[str, list]:
        cl, p = "", []
        if sigungu:
            cl += f" AND {alias}.sgg_cd = ?"; p.append(sigungu)
        elif sido:
            cl += f" AND substr({alias}.sgg_cd,1,2) = substr(?,1,2)"; p.append(sido)
        if cutoff:
            cl += f" AND json_extract({alias}.raw,'$.cdealDay') >= ?"; p.append(cutoff)
        return cl, p

    agg = {"total": 0, "n_junggae": 0, "n_jikgeo": 0,
           "n_double": 0, "n_correction": 0, "n_plain": 0}
    with _open_db() as c:
        for tbl in tables:
            is_apt = tbl == "transactions"
            twin = _twin_sql(is_apt)
            live = ("AND t2.rowid<>t.rowid "
                    "AND COALESCE(json_extract(t2.raw,'$.cdealType'),'')<>'O'")
            fc, fp = filt("t")
            row = c.execute(f"""
                SELECT COUNT(*),
                       SUM(CASE WHEN dealing_gbn='중개거래' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN dealing_gbn='직거래' THEN 1 ELSE 0 END),
                       SUM(has_same),
                       SUM(CASE WHEN has_diff=1 AND has_same=0 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN has_same=0 AND has_diff=0 THEN 1 ELSE 0 END)
                FROM (
                  SELECT t.dealing_gbn,
                    EXISTS(SELECT 1 FROM {tbl} t2 WHERE {twin} {live}
                           AND t2.deal_amount=t.deal_amount) AS has_same,
                    EXISTS(SELECT 1 FROM {tbl} t2 WHERE {twin} {live}
                           AND t2.deal_amount<>t.deal_amount) AS has_diff
                  FROM {tbl} t WHERE json_extract(t.raw,'$.cdealType')='O'{fc}
                )
            """, fp).fetchone()
            agg["total"] += row[0] or 0
            agg["n_junggae"] += row[1] or 0
            agg["n_jikgeo"] += row[2] or 0
            agg["n_double"] += row[3] or 0
            agg["n_correction"] += row[4] or 0
            agg["n_plain"] += row[5] or 0

    return {"asset": asset, "sido": sido, "sigungu": sigungu, "months": months, **agg}


@app.get("/ai/ask")
def ai_ask(q: str, _user: dict = Depends(current_user)):
    """부동산 전문 AI 질의. 기존 엔드포인트를 도구로 호출해 자연어로 답한다.
    전화번호 인증 완료(verified_user) 사용자만 호출 가능."""
    q = (q or "").strip()
    if not q:
        raise HTTPException(400, "질문(q)이 비어있습니다")
    if len(q) > 500:
        raise HTTPException(400, "질문이 너무 깁니다 (최대 500자)")
    # TODO(출시): _ai_quota_check(user) — 로그인 사용자 일일 쿼터/포인트 차감
    try:
        from scripts.ai_agent import run_agent
        return run_agent(q)
    except Exception as e:
        raise HTTPException(500, f"AI 처리 실패: {e}")


_SIDO_EN = {
    "seoul": "서울", "busan": "부산", "daegu": "대구", "incheon": "인천", "gwangju": "광주",
    "daejeon": "대전", "ulsan": "울산", "sejong": "세종", "gyeonggi": "경기", "gangwon": "강원",
    "chungcheongbuk": "충북", "chungcheongnam": "충남", "jeollabuk": "전북", "jeollanam": "전남",
    "gyeongsangbuk": "경북", "gyeongsangnam": "경남", "jeju": "제주",
    "north chungcheong": "충북", "south chungcheong": "충남",
    "north jeolla": "전북", "south jeolla": "전남",
    "north gyeongsang": "경북", "south gyeongsang": "경남",
}
_SEOUL_GU_EN = {
    "gangnam": "강남구", "gangdong": "강동구", "gangbuk": "강북구", "gangseo": "강서구",
    "gwanak": "관악구", "gwangjin": "광진구", "guro": "구로구", "geumcheon": "금천구",
    "nowon": "노원구", "dobong": "도봉구", "dongdaemun": "동대문구", "dongjak": "동작구",
    "mapo": "마포구", "seodaemun": "서대문구", "seocho": "서초구", "seongdong": "성동구",
    "seongbuk": "성북구", "songpa": "송파구", "yangcheon": "양천구", "yeongdeungpo": "영등포구",
    "yongsan": "용산구", "eunpyeong": "은평구", "jongno": "종로구", "jung": "중구", "jungnang": "중랑구",
}


def _kr_region_from_geo(region_name: str, city: str):
    """ip-api 영어 regionName/city → 한글 지역 문자열. (서울은 구 단위까지)"""
    rn = (region_name or "").lower().replace("-do", "").replace(" province", "").strip()
    sido = _SIDO_EN.get(rn)
    if not sido:
        return None
    if sido == "서울":
        cy = (city or "").lower().replace("-gu", "").replace("-si", "").strip()
        gu = _SEOUL_GU_EN.get(cy)
        return f"서울 {gu}" if gu else "서울"
    return sido


@app.get("/ai/region")
def ai_region(request: Request):
    """접속 IP로 대략 지역(시/구)을 추정해 AI 추천질문을 지역화한다.
    - Cloudflare/프록시 뒤에서는 CF-Connecting-IP 등 헤더의 실제 IP 사용.
    - 사설/로컬 IP면 ip-api에 IP 미지정으로 호출 → 서버 공인 IP 지역(=로컬 개발자 위치) 추정.
    - geo-IP(ip-api, 무료)만 사용하고 LLM 호출 없음(비용 0)."""
    ip = None
    for h in ("cf-connecting-ip", "x-real-ip"):
        v = request.headers.get(h)
        if v:
            ip = v.strip(); break
    if not ip:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            ip = xff.split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    private = (not ip) or ip in ("::1", "localhost") or ip.startswith(
        ("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31."))

    geo = {}
    try:
        import urllib.request as _u
        target = "" if private else ip
        url = (f"http://ip-api.com/json/{target}"
               "?fields=status,countryCode,regionName,city,query&lang=ko")
        with _u.urlopen(url, timeout=4) as resp:
            geo = _json.load(resp)
    except Exception:
        geo = {}

    region, examples = None, None
    if geo.get("status") == "success" and geo.get("countryCode") == "KR":
        region = _kr_region_from_geo(geo.get("regionName"), geo.get("city"))
        if region:
            examples = [
                f"{region} 급매 찾아줘",
                f"{region} 최근 신고가 단지 보여줘",
                f"{region} 요즘 거래 활발해?",
                f"{region} 직거래 취소거래 알려줘",
            ]
    return {"region": region, "examples": examples,
            "city": geo.get("city"), "region_name": geo.get("regionName")}


class AiAskBody(BaseModel):
    q: str
    history: list[dict] = []   # [{"role":"user"|"model","text":"..."}] 멀티턴 맥락


def _log_ai(user: dict, question: str, *, answer=None, tools=None, usage=None,
            status: int = 200, error=None, duration_ms=None, request=None) -> None:
    """AI 질문-답변을 상세 로그로 남긴다(질문/답변/사용도구/토큰/소요시간)."""
    detail: dict = {"question": question}
    if answer is not None:
        detail["answer"] = answer[:8000]
    if tools is not None:
        detail["tools"] = tools
    if usage is not None:
        detail["usage"] = usage
    if error is not None:
        detail["error"] = str(error)[:500]
    _log_event(
        "ai_ask", user_id=user.get("id"), email=user.get("email"),
        provider=user.get("provider"), member_no=_member_no(user.get("id")),
        path="/ai/ask", method="POST", status=status, duration_ms=duration_ms,
        ip=(_client_ip(request) if request else None),
        user_agent=(request.headers.get("user-agent") if request else None),
        detail=detail)


@app.post("/ai/ask")
def ai_ask_post(body: AiAskBody, request: Request, user: dict = Depends(current_user)):
    """부동산 AI 질의(멀티턴). history 로 이전 대화를 넘기면 '거기서 30평대만' 같은 후속 질문 가능.
    전화번호 인증 완료 사용자만 호출 가능."""
    q = (body.q or "").strip()
    if not q:
        raise HTTPException(400, "질문(q)이 비어있습니다")
    if len(q) > 500:
        raise HTTPException(400, "질문이 너무 깁니다 (최대 500자)")
    _spend_ai(user["id"])   # 포인트 차감(부족 시 402)
    with _reviews_db() as c:
        nick = _nickname(c, user["id"])
    t0 = _time.perf_counter()
    try:
        from scripts.ai_agent import run_agent
        res = run_agent(q, history=body.history, nickname=nick)
        _log_ai(user, q, answer=(res or {}).get("answer"),
                tools=(res or {}).get("tools_used") or (res or {}).get("tools"),
                usage=(res or {}).get("usage"),
                duration_ms=int((_time.perf_counter() - t0) * 1000), request=request)
        return res
    except Exception as e:
        _log_ai(user, q, status=500, error=e,
                duration_ms=int((_time.perf_counter() - t0) * 1000), request=request)
        raise HTTPException(500, f"AI 처리 실패: {e}")


@app.post("/ai/ask-stream")
def ai_ask_stream(body: AiAskBody, request: Request, user: dict = Depends(current_user)):
    """부동산 AI 질의(SSE 스트리밍). 진행 단계를 실시간 전송:
    질문분석중 → (도구별)조회중 → 데이터정리중 → 답변작성중 → done(최종답변).
    전화번호 인증 완료 사용자만 호출 가능."""
    from fastapi.responses import StreamingResponse
    q = (body.q or "").strip()
    if not q:
        raise HTTPException(400, "질문(q)이 비어있습니다")
    if len(q) > 500:
        raise HTTPException(400, "질문이 너무 깁니다 (최대 500자)")
    new_bal = _spend_ai(user["id"])   # 포인트 차감(부족 시 402, 스트리밍 시작 전)
    with _reviews_db() as c:
        nick = _nickname(c, user["id"])

    def gen():
        t0 = _time.perf_counter()
        fin = {"answer": None, "tools": None, "usage": None}
        err = None
        try:
            from scripts.ai_agent import run_agent_stream
            for ev in run_agent_stream(q, history=body.history, nickname=nick):
                if ev.get("type") == "done":
                    fin["answer"] = ev.get("answer")
                    fin["tools"] = ev.get("tools_used")
                    fin["usage"] = ev.get("usage")
                    ev["points"] = new_bal   # 차감 후 잔액 → 프런트 표시 갱신
                elif ev.get("type") == "error":
                    err = ev.get("error")
                yield f"data: {_json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:
            err = str(e)
            yield f"data: {_json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            _log_ai(user, q, answer=fin["answer"], tools=fin["tools"], usage=fin["usage"],
                    status=(500 if err else 200), error=err,
                    duration_ms=int((_time.perf_counter() - t0) * 1000), request=request)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ===========================================================================
# 관리자: naver 중개사 ↔ vworld 등록정보 수작업 매칭
# ===========================================================================
_VW_SEL = ("sys_regno, business_name, representative, address, status, "
           "registered_ymd, phone, sgg_cd")


def _vw_row(r):
    return {"sys_regno": r[0], "business_name": r[1], "representative": r[2],
            "address": r[3], "status": r[4], "registered_ymd": r[5],
            "phone": r[6], "sgg_cd": r[7]}


def _name_core(name: str) -> str:
    s = name or ""
    for w in ("공인중개사사무소", "공인중개사무소", "공인중개사", "중개사사무소", "부동산중개", "부동산", "중개사무소"):
        s = s.replace(w, "")
    return s.strip()


@app.get("/admin/realtor-match/unmatched")
def admin_match_unmatched(_admin: dict = Depends(admin_user), limit: int = 300):
    """vworld 미매칭 중개사 큐 (수작업 매칭용). match_type='none' 인 naver 중개사, 매물수 많은 순. 관리자 전용."""
    if limit < 1 or limit > 2000:
        raise HTTPException(400, "limit out of range")
    with _open_db() as c:
        rows = c.execute(
            """
            SELECT m.realtor_id, m.naver_name, m.primary_sgg_cd, m.total_listings,
                   n.address, n.representative_name, n.establish_registration_no,
                   COALESCE(n.representative_tel_no, n.cell_phone_no)
            FROM realtor_match m
            LEFT JOIN naver_realtors n ON n.realtor_id = m.realtor_id
            WHERE m.match_type = 'none'
            ORDER BY m.total_listings DESC
            LIMIT ?
            """, (limit,)).fetchall()
    items = [{
        "realtor_id": r[0], "naver_name": r[1], "sgg_cd": r[2],
        "sido": SIDO_NAMES.get((r[2] or "")[:2]),
        "total_listings": r[3], "address": r[4], "rep": r[5],
        "regno": (r[6] or "").strip() or None, "tel": r[7],
    } for r in rows]
    return {"count": len(items), "items": items}


@app.get("/admin/realtor-match/candidates")
def admin_match_candidates(realtor_id: str, _admin: dict = Depends(admin_user)):
    """해당 naver 중개사의 vworld 후보 자동 제안 (등록번호 / 지역+이름 / 지역+대표). 관리자 전용."""
    with _open_db() as c:
        nr = c.execute(
            "SELECT realtor_name, representative_name, establish_registration_no, cortar_no "
            "FROM naver_realtors WHERE realtor_id=?", (realtor_id,)).fetchone()
        mr = c.execute("SELECT naver_name, primary_sgg_cd FROM realtor_match WHERE realtor_id=?",
                       (realtor_id,)).fetchone()
        if not mr:
            raise HTTPException(404, "realtor not found")
        name = (nr[0] if nr else None) or mr[0] or ""
        rep = nr[1] if nr else None
        regno = (nr[2] or "").strip() if nr else ""
        sgg = mr[1] or ((nr[3] or "")[:5] if nr else "")
        cands: dict[str, dict] = {}

        def add(rs, reason):
            for r in rs:
                d = cands.setdefault(r[0], {**_vw_row(r), "reasons": []})
                if reason not in d["reasons"]:
                    d["reasons"].append(reason)

        if regno:
            add(c.execute(f"SELECT {_VW_SEL} FROM vworld_brokers WHERE ra_regno=? LIMIT 10", (regno,)), "등록번호")
        core = _name_core(name)[:6]
        if sgg and core:
            add(c.execute(f"SELECT {_VW_SEL} FROM vworld_brokers WHERE sgg_cd=? AND business_name LIKE ? LIMIT 25",
                          (sgg, "%" + core + "%")), "지역+이름")
        if sgg and rep:
            add(c.execute(f"SELECT {_VW_SEL} FROM vworld_brokers WHERE sgg_cd=? AND representative=? LIMIT 25",
                          (sgg, rep)), "지역+대표")
    return {"realtor_id": realtor_id,
            "naver": {"name": name, "rep": rep, "regno": regno or None, "sgg_cd": sgg},
            "count": len(cands), "candidates": list(cands.values())}


@app.get("/admin/vworld/search")
def admin_vworld_search(q: str = "", sgg: str = "", limit: int = 30,
                        _admin: dict = Depends(admin_user)):
    """vworld 중개사 자유 검색 (이름/대표/주소 부분일치 + 선택적 시군구). 관리자 전용."""
    q = q.strip()
    if len(q) < 2 and not sgg:
        return {"items": []}
    where, params = [], []
    if q:
        where.append("(business_name LIKE ? OR representative LIKE ? OR address LIKE ?)")
        params += ["%" + q + "%"] * 3
    if sgg:
        where.append("sgg_cd = ?"); params.append(sgg)
    params.append(min(max(limit, 1), 100))
    with _open_db() as c:
        rows = c.execute(
            f"SELECT {_VW_SEL} FROM vworld_brokers WHERE {' AND '.join(where)} LIMIT ?",
            params).fetchall()
    return {"items": [_vw_row(r) for r in rows]}


class MatchBody(BaseModel):
    sys_regno: str | None = None   # None/빈값이면 '매칭 없음'으로 확정


@app.post("/admin/realtor-match/{realtor_id}")
def admin_apply_match(realtor_id: str, body: MatchBody, _admin: dict = Depends(admin_user)):
    """수작업 매칭 적용. sys_regno 주면 그 vworld 사무소로 연결(match_type='manual'),
    없으면 '매칭 없음 확정'(match_type='manual_none')으로 큐에서 제외."""
    with _open_db() as c:
        if not c.execute("SELECT 1 FROM realtor_match WHERE realtor_id=?", (realtor_id,)).fetchone():
            raise HTTPException(404, "realtor not found")
        sr = (body.sys_regno or "").strip()
        if sr:
            v = c.execute("SELECT business_name, representative, status FROM vworld_brokers WHERE sys_regno=?",
                          (sr,)).fetchone()
            if not v:
                raise HTTPException(400, "sys_regno not found in vworld")
            c.execute(
                "UPDATE realtor_match SET sys_regno=?, vworld_name=?, vworld_rep=?, vworld_status=?, "
                "match_type='manual', matched_at=datetime('now') WHERE realtor_id=?",
                (sr, v[0], v[1], v[2], realtor_id))
            c.commit()
            return {"ok": True, "realtor_id": realtor_id, "sys_regno": sr, "vworld_name": v[0]}
        c.execute("UPDATE realtor_match SET match_type='manual_none', matched_at=datetime('now') "
                  "WHERE realtor_id=?", (realtor_id,))
        c.commit()
        return {"ok": True, "realtor_id": realtor_id, "sys_regno": None}


@app.get("/admin/users")
def admin_users(_admin: dict = Depends(admin_user), page: int = 1, per_page: int = 200):
    """가입 사용자 목록 (Supabase Admin API). SUPABASE_SECRET_KEY(service_role) 필요. 관리자 전용."""
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise HTTPException(503, "SUPABASE_SECRET_KEY 미설정 — 사용자 목록 조회 불가")
    per_page = min(max(int(per_page), 1), 1000)
    url = (f"{settings.supabase_url}/auth/v1/admin/users"
           f"?page={int(page)}&per_page={per_page}")
    req = _urlreq.Request(url, headers={
        "apikey": settings.supabase_secret_key,
        "Authorization": f"Bearer {settings.supabase_secret_key}",
    })
    try:
        with _urlreq.urlopen(req, timeout=10) as resp:
            data = _authjson.loads(resp.read().decode("utf-8"))
    except _urlerr.HTTPError as e:
        raise HTTPException(502, f"Supabase Admin API 오류({e.code}) — service_role 키 확인")
    except _urlerr.URLError:
        raise HTTPException(502, "Supabase에 연결할 수 없습니다")
    # 자체 인증한 휴대폰 번호·회원번호(user_profiles)를 병합 — Supabase 메타데이터보다 우선.
    with _reviews_db() as c:
        prof = {r[0]: (r[1], r[2]) for r in c.execute(
            "SELECT user_id, phone, member_no FROM user_profiles WHERE phone_verified=1").fetchall()}
    out = []
    for u in data.get("users", []):
        m = u.get("user_metadata") or {}
        am = u.get("app_metadata") or {}
        uid = u.get("id")
        vphone, member_no = prof.get(uid, (None, None))
        out.append({
            "id": uid,
            "member_no": member_no,
            "email": u.get("email"),
            "phone": vphone or u.get("phone") or m.get("phone_number"),
            "phone_verified": bool(vphone),
            "name": m.get("name") or m.get("nickname") or m.get("full_name"),
            "avatar": m.get("avatar_url") or m.get("picture"),
            "provider": am.get("provider"),
            "created_at": u.get("created_at"),
            "last_sign_in_at": u.get("last_sign_in_at"),
        })
    return {"count": len(out), "users": out}


# ===========================================================================
# 관리자: 활동 로그 조회 (로그인/조회/AI질문 — 개선 분석용)
# ===========================================================================
def _member_map(user_ids) -> dict:
    """user_id 목록 → {user_id: (member_no, phone)} (reviews.sqlite)."""
    ids = [u for u in {*user_ids} if u]
    if not ids:
        return {}
    try:
        with _reviews_db() as c:
            ph = ",".join("?" * len(ids))
            return {r[0]: (r[1], r[2]) for r in c.execute(
                f"SELECT user_id, member_no, phone FROM user_profiles WHERE user_id IN ({ph})", ids)}
    except Exception:  # noqa: BLE001
        return {}


@app.get("/admin/logs")
def admin_logs(_admin: dict = Depends(admin_user), kind: str = "", user_id: str = "",
               ref: str = "", q: str = "", since_hours: int = 0, limit: int = 200):
    """활동 로그 최근 N건 (필터: kind/user_id/ref/질문검색/기간). 관리자 전용."""
    limit = min(max(int(limit), 1), 2000)
    where, params = ["1=1"], []
    if kind:
        where.append("kind=?"); params.append(kind)
    if user_id:
        where.append("user_id=?"); params.append(user_id)
    if ref:
        where.append("ref=?"); params.append(ref)
    if q:
        where.append("detail LIKE ?"); params.append(f"%{q}%")
    if since_hours and since_hours > 0:
        where.append("ts >= datetime('now', ?)"); params.append(f"-{int(since_hours)} hours")
    with _logs_db() as c:
        rows = c.execute(
            f"SELECT * FROM event_log WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?",
            (*params, limit)).fetchall()
    mmap = _member_map([r["user_id"] for r in rows])
    out = []
    for r in rows:
        d = dict(r)
        mn, ph = mmap.get(r["user_id"], (r["member_no"], None))
        d["member_no"] = mn if mn is not None else r["member_no"]
        d["phone"] = ph
        if d.get("detail"):
            try:
                d["detail"] = _authjson.loads(d["detail"])
            except Exception:  # noqa: BLE001
                pass
        out.append(d)
    return {"count": len(out), "events": out}


@app.get("/admin/logs/stats")
def admin_logs_stats(_admin: dict = Depends(admin_user), days: int = 7):
    """활동 요약 — 일별 추이·종류별 건수·인기 단지·AI 질문수·활성 사용자. 관리자 전용."""
    days = min(max(int(days), 1), 90)
    since = f"-{days} days"
    with _logs_db() as c:
        by_kind = {r[0]: r[1] for r in c.execute(
            "SELECT kind, COUNT(*) FROM event_log WHERE ts>=datetime('now',?) GROUP BY kind",
            (since,)).fetchall()}
        by_day = [{"day": r[0], "n": r[1]} for r in c.execute(
            "SELECT substr(ts,1,10) d, COUNT(*) FROM event_log WHERE ts>=datetime('now',?) "
            "GROUP BY d ORDER BY d", (since,)).fetchall()]
        top_complex = [{"ref": r[0], "n": r[1]} for r in c.execute(
            "SELECT ref, COUNT(*) FROM event_log WHERE kind='view_complex' AND ref IS NOT NULL "
            "AND ts>=datetime('now',?) GROUP BY ref ORDER BY 2 DESC LIMIT 15", (since,)).fetchall()]
        top_realtor = [{"ref": r[0], "n": r[1]} for r in c.execute(
            "SELECT ref, COUNT(*) FROM event_log WHERE kind='view_realtor' AND ref IS NOT NULL "
            "AND ts>=datetime('now',?) GROUP BY ref ORDER BY 2 DESC LIMIT 15", (since,)).fetchall()]
        ai_total = c.execute(
            "SELECT COUNT(*) FROM event_log WHERE kind='ai_ask' AND ts>=datetime('now',?)",
            (since,)).fetchone()[0]
        logins = c.execute(
            "SELECT COUNT(*) FROM event_log WHERE kind='login' AND ts>=datetime('now',?)",
            (since,)).fetchone()[0]
        active_users = c.execute(
            "SELECT COUNT(DISTINCT user_id) FROM event_log WHERE user_id IS NOT NULL "
            "AND ts>=datetime('now',?)", (since,)).fetchone()[0]
        total = c.execute(
            "SELECT COUNT(*) FROM event_log WHERE ts>=datetime('now',?)", (since,)).fetchone()[0]
    return {"days": days, "total": total, "ai_total": ai_total, "logins": logins,
            "active_users": active_users, "by_kind": by_kind, "by_day": by_day,
            "top_complex": top_complex, "top_realtor": top_realtor}


@app.get("/admin/data-sources")
def admin_data_sources(_admin: dict = Depends(admin_user)):
    """수집 데이터 소스 현황 — 소스별 행수·최신 데이터·마지막 수집·신선도 상태. 관리자 전용.
    신선도 신호: 실거래=inserted_at(수집시각), 매물=snapshot_date, 중개사=fetched_at, vworld=list_fetched_at."""
    from datetime import datetime as _dt, timezone as _tz
    today = _dt.now(_tz.utc).date()

    def days_since(s):
        if not s:
            return None
        try:
            return (today - _dt.strptime(str(s)[:10], "%Y-%m-%d").date()).days
        except Exception:
            return None

    # (table, 친화이름, 분류, 출처, 수집주기, 정상주기일수, 마지막수집표현, 최신데이터표현)
    SRC = [
        ("transactions",      "아파트 매매 실거래",     "실거래 (국토부)", "국토교통부 실거래가",        "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
        ("offi_transactions", "오피스텔 매매 실거래",   "실거래 (국토부)", "국토교통부 실거래가",        "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
        ("rentals",           "아파트 전·월세 실거래",  "실거래 (국토부)", "국토교통부 실거래가",        "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
        ("offi_rentals",      "오피스텔 전·월세 실거래", "실거래 (국토부)", "국토교통부 실거래가",        "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
        ("silv_transactions", "분양권·입주권 전매 실거래", "실거래 (국토부)", "국토교통부 실거래가",      "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
        ("listings_current",  "현재 매물 (호가)",       "매물",           "부동산 매물 플랫폼",         "매일",            2,  "MAX(snapshot_date)",     "MAX(snapshot_date)"),
        ("complex_daily_agg", "단지별 일일 매물 집계",   "매물",           "내부 집계 (매물 보관)",       "매일",            2,  "MAX(snapshot_date)",     "MAX(snapshot_date)"),
        ("naver_realtors",    "중개사무소 정보",         "단지·중개사",    "부동산 매물 플랫폼",         "매일 (신규 보강)", 3,  "MAX(date(fetched_at))",  None),
        ("vworld_brokers",    "공인중개사 공식 등록",    "단지·중개사",    "브이월드 (국토교통부)",      "월 1회",          35, "MAX(date(list_fetched_at))", None),
        ("complexes",         "아파트·오피 단지 정보",   "단지·중개사",    "부동산 매물 플랫폼",         "매일 (매물과 함께)",  2, "_listings_snap",         None),
    ]
    out = []
    with _open_db() as c:
        existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, name, cat, source, cycle, cyd, fexpr, dexpr in SRC:
            if table not in existing:
                continue
            n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            # complexes는 자체 타임스탬프가 없음 — 매물 수집(listings snapshot)과 함께 갱신되므로 이를 신선도 proxy로 사용.
            if fexpr == "_listings_snap":
                last = c.execute("SELECT MAX(snapshot_date) FROM listings_current").fetchone()[0]
            elif fexpr:
                last = c.execute(f"SELECT {fexpr} FROM {table}").fetchone()[0]
            else:
                last = None
            latest = c.execute(f"SELECT {dexpr} FROM {table}").fetchone()[0] if dexpr else None
            da = days_since(last)
            if da is None:
                status = "unknown"
            elif da <= cyd:
                status = "ok"
            elif da <= cyd * 2:
                status = "delay"
            else:
                status = "stale"
            out.append({"key": table, "name": name, "category": cat, "source": source,
                        "cycle": cycle, "rows": n, "last_collected": last, "days_ago": da,
                        "latest_data": latest, "status": status})
    return {"checked_at": _dt.now(_tz.utc).isoformat(), "sources": out}


@app.get("/admin/overview")
def admin_overview(_admin: dict = Depends(admin_user)):
    """관리자 대시보드 종합 지표 — 회원·활동·검수대기·콘텐츠·스냅샷을 한 번에.
    각 섹션은 독립 try/except 라 한 DB/테이블이 없어도 나머지는 채워진다."""
    def _one(conn, sql, params=()):
        try:
            r = conn.execute(sql, params).fetchone()
            return r[0] if r and r[0] is not None else 0
        except Exception:  # noqa: BLE001
            return 0

    members = {"total": 0, "verified": 0, "with_nickname": 0, "points_total": 0}
    moderation = {"reviews_pending": 0, "resident_pending": 0, "realtors_unmatched": 0}
    content = {"forum_posts": 0, "forum_comments": 0, "complex_reviews": 0, "realtor_reviews": 0}
    try:
        with _reviews_db() as c:
            members["total"] = _one(c, "SELECT COUNT(*) FROM user_profiles")
            members["verified"] = _one(c, "SELECT COUNT(*) FROM user_profiles WHERE phone_verified=1")
            members["with_nickname"] = _one(c, "SELECT COUNT(*) FROM user_profiles WHERE nickname IS NOT NULL")
            members["points_total"] = _one(c, "SELECT COALESCE(SUM(points),0) FROM user_profiles")
            moderation["reviews_pending"] = _one(c, "SELECT COUNT(*) FROM realtor_reviews WHERE status='pending'")
            moderation["resident_pending"] = _one(c, "SELECT COUNT(*) FROM resident_verifications WHERE status='pending'")
            content["forum_posts"] = _one(c, "SELECT COUNT(*) FROM forum_posts WHERE status='published'")
            content["forum_comments"] = _one(c, "SELECT COUNT(*) FROM forum_comments WHERE status='published'")
            content["complex_reviews"] = _one(c, "SELECT COUNT(*) FROM complex_reviews WHERE status='published'")
            content["realtor_reviews"] = _one(c, "SELECT COUNT(*) FROM realtor_reviews")
    except Exception:  # noqa: BLE001
        pass

    activity = {"logins_today": 0, "logins_7d": 0, "ai_today": 0, "ai_7d": 0,
                "active_7d": 0, "events_today": 0}
    try:
        with _logs_db() as c:
            activity["logins_today"] = _one(c, "SELECT COUNT(*) FROM event_log WHERE kind='login' AND ts>=date('now')")
            activity["logins_7d"] = _one(c, "SELECT COUNT(*) FROM event_log WHERE kind='login' AND ts>=datetime('now','-7 days')")
            activity["ai_today"] = _one(c, "SELECT COUNT(*) FROM event_log WHERE kind='ai_ask' AND ts>=date('now')")
            activity["ai_7d"] = _one(c, "SELECT COUNT(*) FROM event_log WHERE kind='ai_ask' AND ts>=datetime('now','-7 days')")
            activity["active_7d"] = _one(c, "SELECT COUNT(DISTINCT user_id) FROM event_log WHERE user_id IS NOT NULL AND ts>=datetime('now','-7 days')")
            activity["events_today"] = _one(c, "SELECT COUNT(*) FROM event_log WHERE ts>=date('now')")
    except Exception:  # noqa: BLE001
        pass

    snapshot = {"date": None, "listings": 0}
    try:
        with _open_db() as c:
            moderation["realtors_unmatched"] = _one(c, "SELECT COUNT(*) FROM realtor_match WHERE match_type='none'")
            row = c.execute(
                "SELECT snapshot_date, SUM(listing_count) FROM complex_daily_agg "
                "WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM complex_daily_agg)"
            ).fetchone()
            if row and row[0]:
                snapshot = {"date": row[0], "listings": row[1] or 0}
    except Exception:  # noqa: BLE001
        pass

    return {"members": members, "activity": activity, "moderation": moderation,
            "content": content, "snapshot": snapshot}


class AdminPointsBody(BaseModel):
    delta: int
    reason: str = ""


@app.post("/admin/users/{user_id}/points")
def admin_grant_points(user_id: str, body: AdminPointsBody,
                       _admin: dict = Depends(admin_user)):
    """관리자 수동 포인트 지급/차감 (원장에 'admin' 사유로 기록). 새 잔액 반환."""
    if body.delta == 0 or abs(body.delta) > 1_000_000:
        raise HTTPException(400, "delta 는 0 이 아니고 ±1,000,000 이내여야 합니다")
    with _reviews_db() as c:
        new_bal = _award_points(c, user_id, "admin", delta=body.delta,
                                ref=(body.reason or "관리자 조정")[:100])
        c.commit()
    return {"ok": True, "user_id": user_id, "delta": body.delta, "balance": new_bal}


@app.post("/admin/users/{user_id}/unverify-phone")
def admin_unverify_phone(user_id: str, _admin: dict = Depends(admin_user)):
    """관리자: 사용자 전화번호 인증 해제. 번호를 비워 재인증·재사용 가능하게 한다.
    (회원번호·포인트는 유지. phone_bonus_awarded는 그대로 두어 재인증 시 중복지급 방지.)"""
    with _reviews_db() as c:
        row = c.execute("SELECT phone, phone_verified FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "사용자 프로필이 없습니다")
        c.execute("UPDATE user_profiles SET phone=NULL, phone_verified=0, updated_at=datetime('now') "
                  "WHERE user_id=?", (user_id,))
        c.commit()
    return {"ok": True, "user_id": user_id, "prev_phone": row[0], "phone_verified": False}


# ===========================================================================
# 시도 코드 → 이름 매핑 (2자리 prefix 기반)
# ===========================================================================
SIDO_NAMES = {
    "11": "서울시", "26": "부산시", "27": "대구시", "28": "인천시",
    "29": "광주시", "30": "대전시", "31": "울산시", "36": "세종시",
    "41": "경기도", "43": "충청북도", "44": "충청남도",
    "46": "전라남도", "47": "경상북도", "48": "경상남도",
    "50": "제주도", "51": "강원도", "52": "전라북도",
    # 45(전라북도)는 2024-01 전북특별자치도 출범으로 52로 대체된 죽은 코드.
    # 데이터는 전부 52로 적재됨 — 45를 넣으면 0건 유령 row가 생긴다.
}


@app.get("/stats/tx-region-pulse")
def tx_region_pulse(asset: str = "apt"):
    """시도별 + 전국 실거래 신고 펄스 (매매 기준).

    한 시도 row 당:
      - filed_total/current/prev: 어제 적재된 거래수 (계약일 이번달/지난달 split)
      - current_month_count:  이번 달 누적 거래 (계약일 기준)
      - prev_month_count:     지난 달 누적 거래
      - current_month_pred / prev_month_pred:
          작년 같은 달의 동일-일자 누적 vs 총합 비율로 보정한 예측 총합.
      - yoy_actual:    전년 동월 총 거래
      - avg3y_actual:  최근 3년 같은 달 평균 (가용한 만큼)
      - *_change: 예측 / 비교 기준 - 1

    PIVOT pattern + 인덱스(deal_ymd, date(inserted_at)) 활용해 단일 쿼리로
    전부 가져옴.
    """
    from datetime import date, timedelta
    if asset not in ("apt", "offi", "all"):
        raise HTTPException(400, "asset must be apt|offi|all")
    tables = {
        "apt": ["transactions"],
        "offi": ["offi_transactions"],
        "all": ["transactions", "offi_transactions"],
    }[asset]

    today = date.today()
    cur_y, cur_m = today.year, today.month
    if cur_m == 1:
        prev_y, prev_m = cur_y - 1, 12
    else:
        prev_y, prev_m = cur_y, cur_m - 1
    yesterday = (today - timedelta(days=1)).isoformat()
    yoy_y_cur, yoy_m_cur = cur_y - 1, cur_m
    yoy_y_prev, yoy_m_prev = prev_y - 1, prev_m
    years_3 = (cur_y - 1, cur_y - 2, cur_y - 3)
    try:
        ly_today_str = today.replace(year=cur_y - 1).isoformat()
    except ValueError:
        ly_today_str = (today - timedelta(days=365)).isoformat()

    # 단일 PIVOT 쿼리 — 필요한 deal_year/month 만 WHERE 로 좁히고 CASE 분기.
    needed_years = sorted(set([cur_y, prev_y, yoy_y_cur, yoy_y_prev, *years_3, prev_y - 1]))
    needed_months = sorted(set([cur_m, prev_m]))
    yr_placeholders = ",".join(["?"] * len(needed_years))
    mo_placeholders = ",".join(["?"] * len(needed_months))

    def pivot_sql(table: str) -> str:
        return f"""
        SELECT substr(sgg_cd,1,2) AS sido,
          SUM(CASE WHEN date(inserted_at)=? THEN 1 ELSE 0 END) AS filed_total,
          SUM(CASE WHEN date(inserted_at)=? AND deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS filed_cur,
          SUM(CASE WHEN date(inserted_at)=? AND deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS filed_prev,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS cum_cur,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS cum_prev,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS yoy_cur,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS yoy_prev,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS y1_cur,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS y2_cur,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS y3_cur,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS y1_prev,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS y2_prev,
          SUM(CASE WHEN deal_year=? AND deal_month=? THEN 1 ELSE 0 END) AS y3_prev,
          SUM(CASE WHEN deal_year=? AND deal_month=? AND date(inserted_at) <= ? THEN 1 ELSE 0 END) AS yoy_at_today
        FROM {table}
        WHERE sgg_cd IS NOT NULL
          AND is_cancelled = 0
          AND deal_year IN ({yr_placeholders})
          AND deal_month IN ({mo_placeholders})
        GROUP BY sido
        """

    # "어제 적재"는 야간수집이 자정 넘어 돌면 그 달력일에 적재가 0이 되어 카드가
    # 전부 0으로 보인다. 실제 가장 최근 적재일(date(inserted_at) 최댓값)을 기준으로
    # 삼아 항상 최신 신고분을 보여준다.
    with _open_db() as _c0:
        _dates = []
        for _t in tables:
            _r = _c0.execute(f"SELECT MAX(date(inserted_at)) FROM {_t}").fetchone()
            if _r and _r[0]:
                _dates.append(_r[0])
    filed_ref = max(_dates) if _dates else yesterday

    param_block = (
        filed_ref,                          # filed_total
        filed_ref, cur_y, cur_m,            # filed_cur
        filed_ref, prev_y, prev_m,          # filed_prev
        cur_y, cur_m,                       # cum_cur
        prev_y, prev_m,                     # cum_prev
        yoy_y_cur, yoy_m_cur,               # yoy_cur
        yoy_y_prev, yoy_m_prev,             # yoy_prev
        years_3[0], cur_m,                  # y1_cur
        years_3[1], cur_m,                  # y2_cur
        years_3[2], cur_m,                  # y3_cur
        years_3[0], prev_m,                 # y1_prev
        years_3[1], prev_m,                 # y2_prev
        years_3[2], prev_m,                 # y3_prev
        yoy_y_cur, yoy_m_cur, ly_today_str, # yoy_at_today
        *needed_years, *needed_months,
    )

    cols = ["sido","filed_total","filed_cur","filed_prev",
            "cum_cur","cum_prev","yoy_cur","yoy_prev",
            "y1_cur","y2_cur","y3_cur","y1_prev","y2_prev","y3_prev",
            "yoy_at_today"]

    agg: dict[str, dict] = {}  # sido → cols dict
    with _open_db() as c:
        for table in tables:
            for row in c.execute(pivot_sql(table), param_block).fetchall():
                sido = row[0]
                if not sido:
                    continue
                rec = agg.setdefault(sido, {k: 0.0 for k in cols if k != "sido"})
                for k, v in zip(cols[1:], row[1:]):
                    rec[k] += float(v or 0)

    def _change(now, was):
        if now is None or was is None or was == 0:
            return None
        return (now - was) / was

    # 신고 lag 모델: 거래 신고 의무 30일. M 일짜리 달의 거래는 1일~M+30일
    # 사이에 신고 들어옴. 오늘이 1일부터 cur_dom 일째인 경우,
    # 진행률 = (오늘까지 경과 일수) / (월 길이 + 30).
    # (균등 분포 + 균등 lag 가정. 실제는 직후/마감 직전 몰림 있지만 1차 근사로 OK)
    from calendar import monthrange
    def progress(year: int, month: int) -> float:
        month_len = monthrange(year, month)[1]
        total = month_len + 30
        # 해당 달의 1일부터 오늘까지 경과 일수 (cap month_len+30)
        first = date(year, month, 1)
        elapsed = (today - first).days + 1
        elapsed = max(0, min(elapsed, total))
        return elapsed / total
    prog_cur = progress(cur_y, cur_m)
    prog_prev = progress(prev_y, prev_m)

    def make_rec(sido: str, d: dict) -> dict:
        # 3년 평균 (해당 연도에 데이터 있으면 카운트)
        cur_vals = [d.get(k, 0) for k in ("y1_cur","y2_cur","y3_cur") if d.get(k, 0) > 0]
        prev_vals = [d.get(k, 0) for k in ("y1_prev","y2_prev","y3_prev") if d.get(k, 0) > 0]
        avg3_cur = sum(cur_vals)/len(cur_vals) if cur_vals else None
        avg3_prev = sum(prev_vals)/len(prev_vals) if prev_vals else None

        actual_cur = d.get("cum_cur", 0)
        actual_prev = d.get("cum_prev", 0)
        # 단순 비율 예측: actual / progress. progress<=0 보호.
        pred_cur = (actual_cur / prog_cur) if (actual_cur > 0 and prog_cur > 0) else None
        pred_prev = (actual_prev / prog_prev) if (actual_prev > 0 and prog_prev > 0) else None

        rec = {
            "region_code": sido,
            "region_name": SIDO_NAMES.get(sido, sido),
            "filed_total": int(d.get("filed_total", 0)),
            "filed_current": int(d.get("filed_cur", 0)),
            "filed_prev": int(d.get("filed_prev", 0)),
            "current_month_count": int(actual_cur),
            "prev_month_count": int(d.get("cum_prev", 0)),
            "yoy_cur_actual": int(d.get("yoy_cur", 0)) or None,
            "yoy_prev_actual": int(d.get("yoy_prev", 0)) or None,
            "avg3y_cur_actual": avg3_cur,
            "avg3y_prev_actual": avg3_prev,
            "current_month_pred": pred_cur,
            "prev_month_pred": pred_prev,
        }
        rec["yoy_cur_change"] = _change(pred_cur, rec["yoy_cur_actual"])
        rec["yoy_prev_change"] = _change(pred_prev, rec["yoy_prev_actual"])
        rec["avg3y_cur_change"] = _change(pred_cur, avg3_cur)
        rec["avg3y_prev_change"] = _change(pred_prev, avg3_prev)
        return rec

    # 전국 합계
    all_sidos = set(agg.keys()) | set(SIDO_NAMES.keys())
    items = []
    nat_agg = {k: 0.0 for k in cols if k != "sido"}
    for sido in sorted(all_sidos):
        d = agg.get(sido, {k: 0.0 for k in cols if k != "sido"})
        items.append(make_rec(sido, d))
        for k, v in d.items():
            nat_agg[k] += v
    nat = make_rec("00", nat_agg)
    nat["region_name"] = "전국"

    return {
        "asset": asset,
        "as_of": today.isoformat(),
        "filed_date": filed_ref,
        "current_month": f"{cur_y}-{cur_m:02d}",
        "prev_month": f"{prev_y}-{prev_m:02d}",
        "yoy_cur_month": f"{yoy_y_cur}-{yoy_m_cur:02d}",
        "yoy_prev_month": f"{yoy_y_prev}-{yoy_m_prev:02d}",
        "national": nat,
        "regions": items,
    }


# ===========================================================================
# 중개사무소 리뷰
#
# 두 종류:
#   - 일반리뷰(general): 의견(body)만. 로그인 회원이면 누구나. 바로 게시(published).
#                        별점 없음.
#   - 인증리뷰(verified): 거래 입증 서류(계약서/확인설명서 등)를 첨부 → 'pending'.
#                        관리자가 서류를 확인해 승인하면 'approved' = (거래인증) 뱃지 +
#                        별점이 평점 집계에 반영. 서류 파일은 승인/거부 시점에 삭제
#                        (민감 개인정보라 장기 보관 안 함). 평점 집계는 approved 인증
#                        리뷰만 대상.
#
# 로그인 시스템은 아직 없으므로 author_id 는 NULL, author_name 은 입력값(기본 '익명').
# 리뷰는 스크래핑 데이터와 라이프사이클이 달라 별도 DB(reviews.sqlite)에 보관 —
# collector 의 재수집/재생성에 영향받지 않게.
# ===========================================================================
REVIEWS_DB: Path = DB_PATH.parent / "reviews.sqlite"
REVIEW_DOCS_DIR: Path = DB_PATH.parent / "review_docs"
FORUM_IMG_DIR: Path = DB_PATH.parent / "forum_images"
_REVIEW_DOC_MAX_BYTES = 10 * 1024 * 1024  # 10MB
_REVIEW_DOC_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".heic"}


def _init_reviews_db() -> None:
    REVIEW_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    FORUM_IMG_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(REVIEWS_DB) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS realtor_reviews (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              realtor_id  TEXT NOT NULL,
              author_id   TEXT,                 -- 추후 로그인 사용자 id
              author_name TEXT NOT NULL DEFAULT '익명',
              review_type TEXT NOT NULL CHECK (review_type IN ('general','verified')),
              rating      INTEGER,              -- 인증리뷰만 (1~5)
              body        TEXT NOT NULL,
              status      TEXT NOT NULL,        -- general: published / verified: pending|approved|rejected
              doc_path    TEXT,                 -- 검수 대기 동안만 임시 보관, 결정 시 삭제
              doc_name    TEXT,
              reject_reason TEXT,
              created_at  TEXT NOT NULL DEFAULT (datetime('now')),
              decided_at  TEXT
            );
            CREATE INDEX IF NOT EXISTS rr_realtor_idx ON realtor_reviews(realtor_id, status);
            CREATE INDEX IF NOT EXISTS rr_status_idx  ON realtor_reviews(status);

            CREATE TABLE IF NOT EXISTS user_profiles (
              user_id        TEXT PRIMARY KEY,
              member_no      INTEGER,             -- 내부 회원번호(전화인증 시 발급, 100001~)
              phone          TEXT,
              phone_verified INTEGER NOT NULL DEFAULT 0,
              provider       TEXT,                -- 가입 경로: kakao | google | email ...
              updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS phone_otp (
              user_id    TEXT PRIMARY KEY,
              phone      TEXT NOT NULL,
              code       TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              attempts   INTEGER NOT NULL DEFAULT 0,
              sent_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- 포인트 거래 원장(감사용). 잔액은 user_profiles.points 에 캐시.
            CREATE TABLE IF NOT EXISTS point_ledger (
              id            INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id       TEXT NOT NULL,
              delta         INTEGER NOT NULL,
              reason        TEXT NOT NULL,   -- signup|ai_use|review|referral|resident|admin
              ref           TEXT,
              balance_after INTEGER,
              created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS pl_user_idx ON point_ledger(user_id, id);

            -- 아파트 단지 리뷰 (한 단지에 여러 건 허용 — 시간당 한도로 스팸 방지)
            CREATE TABLE IF NOT EXISTS complex_reviews (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              complex_no  TEXT NOT NULL,
              user_id     TEXT NOT NULL,
              author_name TEXT,
              rating      INTEGER,           -- 1~5
              body        TEXT NOT NULL,
              resident    INTEGER NOT NULL DEFAULT 0,  -- 작성시 입주민 인증 뱃지 여부
              status      TEXT NOT NULL DEFAULT 'published',
              created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS cr_complex_idx ON complex_reviews(complex_no, status);
            CREATE INDEX IF NOT EXISTS cr_user_recent_idx ON complex_reviews(user_id, created_at);

            -- 입주민 인증 (서류 → 관리자 승인 → 입주민 뱃지)
            CREATE TABLE IF NOT EXISTS resident_verifications (
              id            INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id       TEXT NOT NULL,
              complex_no    TEXT NOT NULL,
              doc_path      TEXT,
              doc_name      TEXT,
              status        TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
              reject_reason TEXT,
              created_at    TEXT NOT NULL DEFAULT (datetime('now')),
              decided_at    TEXT
            );
            CREATE INDEX IF NOT EXISTS rv_user_idx ON resident_verifications(user_id, complex_no);
            CREATE INDEX IF NOT EXISTS rv_status_idx ON resident_verifications(status);

            -- 토론장: 글
            CREATE TABLE IF NOT EXISTS forum_posts (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id     TEXT NOT NULL,
              nickname    TEXT NOT NULL,
              title       TEXT NOT NULL,
              body        TEXT NOT NULL DEFAULT '',
              image_path  TEXT,                          -- 첨부 이미지(공유→토론장 등)
              up          INTEGER NOT NULL DEFAULT 0,     -- 추천 수(캐시)
              down        INTEGER NOT NULL DEFAULT 0,     -- 비추천 수(캐시)
              comment_count INTEGER NOT NULL DEFAULT 0,   -- 댓글 수(캐시)
              status      TEXT NOT NULL DEFAULT 'published',  -- published|hidden
              created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS fp_created_idx ON forum_posts(status, created_at DESC);
            CREATE INDEX IF NOT EXISTS fp_user_idx ON forum_posts(user_id);

            -- 토론장: 댓글
            CREATE TABLE IF NOT EXISTS forum_comments (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              post_id     INTEGER NOT NULL,
              user_id     TEXT NOT NULL,
              nickname    TEXT NOT NULL,
              body        TEXT NOT NULL,
              up          INTEGER NOT NULL DEFAULT 0,
              down        INTEGER NOT NULL DEFAULT 0,
              status      TEXT NOT NULL DEFAULT 'published',
              created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS fc_post_idx ON forum_comments(post_id, status, created_at);

            -- 토론장: 추천/비추천 (사용자×대상 1표, 토글)
            CREATE TABLE IF NOT EXISTS forum_votes (
              user_id     TEXT NOT NULL,
              target_type TEXT NOT NULL,   -- post|comment
              target_id   INTEGER NOT NULL,
              value       INTEGER NOT NULL, -- +1 추천 / -1 비추천
              created_at  TEXT NOT NULL DEFAULT (datetime('now')),
              PRIMARY KEY (user_id, target_type, target_id)
            );

            -- ── 중개사 라운지 ──────────────────────────────────────────
            -- 계정 ↔ 중개사무소 1:1 연동(전화매칭 또는 서류승인). 여러 곳 매칭 시 사용자가
            -- 하나를 골라 여기 저장 → 라운지 입장 시 이 선택을 사용.
            CREATE TABLE IF NOT EXISTS realtor_members (
              user_id       TEXT PRIMARY KEY,
              realtor_id    TEXT NOT NULL,
              method        TEXT NOT NULL DEFAULT 'phone',  -- phone | doc
              matched_phone TEXT,
              created_at    TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at    TEXT
            );
            -- 정보수정요청 → 관리자 즉시 확인
            CREATE TABLE IF NOT EXISTS realtor_edit_requests (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id     TEXT NOT NULL,
              realtor_id  TEXT NOT NULL,
              member_no   INTEGER,
              content     TEXT NOT NULL,
              status      TEXT NOT NULL DEFAULT 'pending',  -- pending|done|rejected
              admin_note  TEXT,
              created_at  TEXT NOT NULL DEFAULT (datetime('now')),
              resolved_at TEXT
            );
            CREATE INDEX IF NOT EXISTS rer_status_idx ON realtor_edit_requests(status, created_at DESC);
            -- 전화매칭 실패 시 서류제출→관리자승인 보조 인증
            CREATE TABLE IF NOT EXISTS realtor_verifications (
              id           INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id      TEXT NOT NULL,
              realtor_id   TEXT,
              claimed_name TEXT,
              doc_path     TEXT,
              status       TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
              admin_note   TEXT,
              created_at   TEXT NOT NULL DEFAULT (datetime('now')),
              reviewed_at  TEXT
            );
            CREATE INDEX IF NOT EXISTS rvf_status_idx ON realtor_verifications(status, created_at DESC);
            -- 홈페이지 상담신청 리드(라운지·관리자에서 확인)
            CREATE TABLE IF NOT EXISTS consultation_leads (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              realtor_id  TEXT NOT NULL,
              name        TEXT,
              phone       TEXT,
              message     TEXT,
              source      TEXT DEFAULT 'homepage',
              status      TEXT NOT NULL DEFAULT 'new',  -- new|read|done
              created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS leads_realtor_idx ON consultation_leads(realtor_id, status, created_at DESC);
            -- 중개사 홈페이지(빌더 산출물) — Phase B
            CREATE TABLE IF NOT EXISTS realtor_homepages (
              realtor_id   TEXT PRIMARY KEY,
              user_id      TEXT NOT NULL,
              slug         TEXT,
              slogan       TEXT,
              intro        TEXT,
              specialties  TEXT,
              biz_hours    TEXT,
              kakao_url    TEXT,
              consult_tel  TEXT,
              map_memo     TEXT,
              photo_apt    TEXT,
              photo_rep    TEXT,
              photo_office TEXT,
              published    INTEGER NOT NULL DEFAULT 0,
              created_at   TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at   TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS rh_slug_unique
              ON realtor_homepages(slug) WHERE slug IS NOT NULL;
            CREATE TABLE IF NOT EXISTS realtor_fav_complexes (
              user_id      TEXT NOT NULL,
              complex_no   TEXT NOT NULL,
              complex_name TEXT,
              created_at   TEXT NOT NULL DEFAULT (datetime('now')),
              PRIMARY KEY (user_id, complex_no)
            );
            CREATE TABLE IF NOT EXISTS realtor_fav_offices (
              user_id      TEXT NOT NULL,
              realtor_id   TEXT NOT NULL,
              created_at   TEXT NOT NULL DEFAULT (datetime('now')),
              PRIMARY KEY (user_id, realtor_id)
            );
            CREATE TABLE IF NOT EXISTS push_subscriptions (
              user_id     TEXT NOT NULL,
              endpoint    TEXT NOT NULL,
              p256dh      TEXT NOT NULL,
              auth        TEXT NOT NULL,
              ua          TEXT,
              created_at  TEXT NOT NULL DEFAULT (datetime('now')),
              PRIMARY KEY (endpoint)
            );
            CREATE INDEX IF NOT EXISTS push_user_idx ON push_subscriptions(user_id);
            """
        )
        # 기존 테이블에 신규 컬럼 보강(있으면 무시) — 전화번호=유니크 비즈니스키, 회원번호=내부키
        for ddl in (
            "ALTER TABLE user_profiles ADD COLUMN member_no INTEGER",
            "ALTER TABLE user_profiles ADD COLUMN provider TEXT",
            "ALTER TABLE user_profiles ADD COLUMN points INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE user_profiles ADD COLUMN referred_by INTEGER",       # 추천인 member_no
            "ALTER TABLE user_profiles ADD COLUMN signup_awarded INTEGER NOT NULL DEFAULT 0",  # 가입(로그인) 30p
            "ALTER TABLE user_profiles ADD COLUMN phone_bonus_awarded INTEGER NOT NULL DEFAULT 0",  # 전화인증 100p
            "ALTER TABLE user_profiles ADD COLUMN nickname TEXT",             # 글·리뷰·AI 호칭용
            "ALTER TABLE user_profiles ADD COLUMN agreed_terms_at TEXT",      # 이용약관·개인정보 동의 시각
            "ALTER TABLE user_profiles ADD COLUMN consent_version TEXT",      # 동의한 약관/방침 버전
            "ALTER TABLE user_profiles ADD COLUMN marketing_opt_in INTEGER NOT NULL DEFAULT 0",  # 마케팅 수신(선택)
            "ALTER TABLE user_profiles ADD COLUMN marketing_opt_in_at TEXT",  # 마케팅 동의/철회 시각
            "ALTER TABLE user_profiles ADD COLUMN nickname_awarded INTEGER NOT NULL DEFAULT 0",  # 닉네임 20p 1회
        ):
            try:
                c.execute(ddl)
            except sqlite3.OperationalError:
                pass  # 이미 존재
        # 인증된 전화번호는 전 회원 통틀어 유일 (취소 시 phone=NULL 처리되어 재사용 가능)
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS up_phone_unique "
            "ON user_profiles(phone) WHERE phone IS NOT NULL AND phone_verified=1"
        )
        # 닉네임 전 회원 통틀어 유일 (대소문자 무시)
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS up_nickname_unique "
            "ON user_profiles(lower(nickname)) WHERE nickname IS NOT NULL"
        )
        # 단지리뷰 1인1건 제약 제거 — 여러 건 허용(시간당 한도로 스팸 방지).
        c.execute("DROP INDEX IF EXISTS cr_user_complex")
        c.commit()


_init_reviews_db()


# ─── 포인트 · 계급 시스템 ───────────────────────────────────
# 계급: 누적(획득) 포인트 임계값 기준. 사용으로 잔액이 줄어도 계급은 유지(획득 누계로 산정).
RANKS = [
    # 시장(4,000)까지는 완만, 그 위부터 가파르게 → 대통령 15만
    # 가입 인증만으로 100P → 부린이 유지. 임장러(200)부터 추가 활동 필요.
    # (임계 누적P, 계급명, 대표 이모지)
    (0, "부린이", "🐣"), (200, "임장러", "👟"), (400, "동대표", "🏠"),
    (700, "관리소장", "🧰"), (1100, "단지대표", "🏘️"), (1600, "통장", "🤝"),
    (2200, "주민센터장", "🏢"), (3000, "구청장", "🏛️"), (4000, "시장", "🎖️"),
    (8000, "도지사", "🗺️"), (15000, "장관", "💼"), (26000, "국무총리", "🎩"),
    (45000, "국회의원", "⚖️"), (85000, "국회의장", "🔨"), (150000, "대통령", "👑"),
    # "조물주 위에 건물주" 밈 — 대통령 위 조물주, 그 위 건물주(부동산 앱 최종 등급).
    (300000, "조물주", "🌌"), (500000, "건물주", "🏰"),
]
POINTS = {
    "signup": 30,          # 가입(첫 로그인) 즉시 지급
    "nickname": 20,        # 닉네임 최초 설정 시(활동 유도)
    "phone_verify": 100,   # 전화번호 인증 완료 시
    "ai_use": -10,         # AI 1회 사용
    "review": 5,           # 일반 리뷰 작성(중개사/단지)
    "review_verified": 100,# 인증 리뷰(서류 검증 → 관리자 승인 시)
    "comment": 1,          # 토론장 댓글
    "referral": 100,       # 추천으로 가입 1명 성사
    "resident": 50,        # 입주민 인증 승인
    "forum_post": 10,      # 토론장 글 작성
    "admin": 0,            # 관리자 수동 조정(금액은 호출 시 지정)
}
FORUM_POST_DAILY_CAP = 10     # 글 작성 포인트는 하루 최대 N건만(스팸 파밍 방지)
FORUM_COMMENT_DAILY_CAP = 20  # 댓글 포인트 일일 캡(스팸 파밍 방지)
AI_COST = -POINTS["ai_use"]  # AI 1회 비용(양수)


def _rank_for(earned: int) -> dict:
    """누적 획득 포인트 → 계급 정보."""
    idx = 0
    for i, (th, _nm, _em) in enumerate(RANKS):
        if earned >= th:
            idx = i
    nxt = RANKS[idx + 1] if idx + 1 < len(RANKS) else None
    return {"rank": RANKS[idx][1], "emoji": RANKS[idx][2], "level": idx,
            "next_rank": nxt[1] if nxt else None,
            "next_emoji": nxt[2] if nxt else None,
            "next_at": nxt[0] if nxt else None}


def _user_points(c: sqlite3.Connection, user_id: str) -> tuple[int, int]:
    """(현재 잔액, 누적 획득) — 누적은 ledger 의 양수 합."""
    bal = c.execute("SELECT points FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
    earned = c.execute(
        "SELECT COALESCE(SUM(delta),0) FROM point_ledger WHERE user_id=? AND delta>0",
        (user_id,)).fetchone()[0]
    return (bal[0] if bal else 0), earned


HOURLY_CREATE_CAP = 30  # 아이디별 시간당 작성 한도(리뷰·토론장 글). 댓글은 제한 없음.


def _enforce_hourly(c: sqlite3.Connection, table: str, user_col: str, user_id: str,
                    cap: int = HOURLY_CREATE_CAP) -> None:
    """최근 1시간 작성 건수가 cap 이상이면 429. 스팸/파밍 방지."""
    n = c.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {user_col}=? AND created_at >= datetime('now','-1 hour')",
        (user_id,)).fetchone()[0]
    if n >= cap:
        raise HTTPException(429, f"시간당 작성 한도({cap}건)를 초과했어요. 잠시 후 다시 시도해주세요.")


def _rank_map(c: sqlite3.Connection, user_ids: list[str]) -> dict:
    """user_id 목록 → {user_id: {rank, emoji, level}} (글·댓글 작성자 계급 표시용)."""
    ids = list({u for u in user_ids if u})
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    earned = {r[0]: r[1] for r in c.execute(
        f"SELECT user_id, SUM(delta) FROM point_ledger "
        f"WHERE delta>0 AND user_id IN ({ph}) GROUP BY user_id", ids).fetchall()}
    out = {}
    for u in ids:
        rk = _rank_for(earned.get(u, 0))
        out[u] = {"rank": rk["rank"], "emoji": rk["emoji"], "level": rk["level"],
                  "is_admin": _is_admin_uid(u)}
    return out


def _nick_map(c: sqlite3.Connection, user_ids: list[str]) -> dict:
    """user_id 목록 → {user_id: nickname}. 리뷰 등 작성자 표기를 항상 현재 별명으로
    덮어쓰기 위해 사용 (실명·이메일 등 개인정보는 타인에게 절대 노출 안 함)."""
    ids = list({u for u in user_ids if u})
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    return {r[0]: r[1] for r in c.execute(
        f"SELECT user_id, nickname FROM user_profiles "
        f"WHERE user_id IN ({ph}) AND nickname IS NOT NULL", ids).fetchall()}


def _award_points(c: sqlite3.Connection, user_id: str, reason: str,
                  delta: int | None = None, ref: str | None = None) -> int:
    """포인트 적립/차감 + 원장 기록. user_profiles 행이 없으면 생성. 새 잔액 반환.
    호출부가 트랜잭션(commit)을 책임진다."""
    d = POINTS.get(reason, 0) if delta is None else delta
    c.execute("INSERT INTO user_profiles(user_id, updated_at) VALUES(?, datetime('now')) "
              "ON CONFLICT(user_id) DO NOTHING", (user_id,))
    c.execute("UPDATE user_profiles SET points = points + ?, updated_at=datetime('now') "
              "WHERE user_id=?", (d, user_id))
    bal = c.execute("SELECT points FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()[0]
    c.execute("INSERT INTO point_ledger(user_id, delta, reason, ref, balance_after) "
              "VALUES(?,?,?,?,?)", (user_id, d, reason, ref, bal))
    return bal


def _points_block(user_id: str) -> dict:
    """/me·계정용 포인트+계급 묶음."""
    with _reviews_db() as c:
        bal, earned = _user_points(c, user_id)
    return {"points": bal, "earned": earned, "ai_cost": AI_COST, **_rank_for(earned)}


def _spend_ai(user_id: str) -> int:
    """AI 1회 비용 차감. 잔액 부족이면 402(insufficient_points). 새 잔액 반환."""
    with _reviews_db() as c:
        bal, _ = _user_points(c, user_id)
        if bal < AI_COST:
            raise HTTPException(402, detail={
                "code": "insufficient_points", "points": bal, "needed": AI_COST,
                "message": f"포인트가 부족해요. AI 1회에 {AI_COST}P가 필요한데 현재 {bal}P예요. "
                           "리뷰 작성·친구 추천으로 포인트를 모을 수 있어요.",
            })
        new_bal = _award_points(c, user_id, "ai_use")
        c.commit()
    return new_bal


# (인증/관리자 의존성 current_user·admin_user 는 파일 앞부분 _open_db 근처에 정의됨)


# 이용약관·개인정보처리방침 버전. 문서를 개정하면 이 값을 올려서 재동의를 유도한다.
CONSENT_VERSION = "2026-06-16"


@app.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    """로그인 사용자 본인 정보 + 관리자 여부 + 인증 전화번호 + 회원번호 + 포인트·계급."""
    with _reviews_db() as c:
        row = c.execute(
            "SELECT phone, phone_verified, member_no, nickname, agreed_terms_at, marketing_opt_in "
            "FROM user_profiles WHERE user_id=?",
            (user["id"],)).fetchone()
        bal, earned = _user_points(c, user["id"])
        is_realtor_member = bool(c.execute(
            "SELECT 1 FROM realtor_members WHERE user_id=?", (user["id"],)).fetchone())
    # 중개사 홍보: 인증번호가 중개사무소와 일치하는데 아직 라운지 미연결이면 안내 노출
    user["realtor_promo"] = None
    if row and row[1] and row[0] and not is_realtor_member:
        cands = _realtor_candidates_by_phone(row[0])
        if cands:
            user["realtor_promo"] = {"office_name": cands[0].get("realtor_name")}
    user["phone_verified"] = bool(row and row[1])
    user["member_no"] = row[2] if row else None
    if row and row[0]:
        user["phone"] = row[0]
    user["nickname"] = row[3] if row else None
    user["needs_nickname"] = not (row and row[3])   # 닉네임 미설정 → 최초 1회 선택 유도
    user["needs_consent"] = not (row and row[4])    # 약관·개인정보 미동의 → 최초 1회 동의 유도
    user["marketing_opt_in"] = bool(row and row[5])
    user["consent_version"] = CONSENT_VERSION
    user["points"] = bal
    user["points_earned"] = earned   # 누적 획득(등급·다음레벨 계산 기준)
    user["ai_cost"] = AI_COST
    rk = _rank_for(earned)
    user.update({k: v for k, v in rk.items()})  # rank, level, next_rank, next_at
    user["next_remaining"] = (rk["next_at"] - earned) if rk["next_at"] is not None else None
    return user


@app.post("/events/login")
def log_login(request: Request, user: dict = Depends(current_user)) -> dict:
    """프런트가 로그인(SIGNED_IN) 직후 호출 — 로그인 기록을 남긴다."""
    _log_event(
        "login", user_id=user["id"], email=user.get("email"),
        provider=user.get("provider"), member_no=_member_no(user["id"]),
        path="/events/login", method="POST", status=200,
        ip=_client_ip(request), user_agent=request.headers.get("user-agent"),
        detail={"name": user.get("name")})
    # 가입(첫 로그인) 즉시 30p — 최초 1회만(signup_awarded 플래그)
    awarded = 0
    with _reviews_db() as c:
        c.execute("INSERT INTO user_profiles(user_id, provider, updated_at) "
                  "VALUES(?,?,datetime('now')) ON CONFLICT(user_id) DO NOTHING",
                  (user["id"], user.get("provider")))
        sa = c.execute("SELECT signup_awarded FROM user_profiles WHERE user_id=?",
                       (user["id"],)).fetchone()
        if not (sa and sa[0]):
            _award_points(c, user["id"], "signup")
            c.execute("UPDATE user_profiles SET signup_awarded=1 WHERE user_id=?", (user["id"],))
            awarded = POINTS["signup"]
            c.commit()
    return {"ok": True, "awarded": awarded}


def _reviews_db() -> sqlite3.Connection:
    c = sqlite3.connect(REVIEWS_DB)
    c.row_factory = sqlite3.Row
    return c


# ─── 웹 푸시 알림 (TWA/PWA — VAPID) ─────────────────────────────────
def _vapid():
    """(private, public, subject) — env. 미설정이면 None."""
    priv = os.getenv("VAPID_PRIVATE_KEY")
    pub = os.getenv("VAPID_PUBLIC_KEY")
    if not priv or not pub:
        return None
    return priv, pub, os.getenv("VAPID_SUBJECT", "mailto:admin@koczip.com")


def _send_web_push(user_ids, title: str, body: str, url: str = "/", tag: str = "koczip",
                   icon: str = "https://koczip.com/icon-192.png") -> dict:
    """user_ids(list) 의 모든 구독에 웹푸시 발송. 죽은 구독(404/410)은 삭제. 발송 통계 반환."""
    v = _vapid()
    if not v:
        return {"sent": 0, "error": "VAPID not configured"}
    from pywebpush import webpush, WebPushException
    priv, _pub, subject = v
    payload = _json.dumps({"title": title, "body": body, "url": url, "tag": tag, "icon": icon},
                          ensure_ascii=False)
    sent = failed = 0
    dead = []
    ids = [user_ids] if isinstance(user_ids, str) else list(user_ids)
    if not ids:
        return {"sent": 0}
    ph = ",".join("?" * len(ids))
    with _reviews_db() as c:
        subs = c.execute(
            f"SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_id IN ({ph})",
            ids).fetchall()
        for s in subs:
            try:
                webpush(
                    subscription_info={"endpoint": s["endpoint"],
                                       "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}},
                    data=payload,
                    vapid_private_key=priv,
                    vapid_claims={"sub": subject},
                    timeout=10)
                sent += 1
            except WebPushException as e:
                failed += 1
                code = getattr(getattr(e, "response", None), "status_code", None)
                if code in (404, 410):       # 만료/해지 구독 → 정리
                    dead.append(s["endpoint"])
            except Exception:
                failed += 1
        for ep in dead:
            c.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (ep,))
    return {"sent": sent, "failed": failed, "pruned": len(dead)}


@app.get("/push/vapid-public-key")
def push_vapid_public_key():
    v = _vapid()
    return {"key": v[1] if v else None}


@app.post("/push/subscribe")
def push_subscribe(body: dict, request: Request, user: dict = Depends(current_user)):
    """브라우저 PushSubscription 저장(로그인 필요)."""
    sub = body.get("subscription") or body
    ep = sub.get("endpoint")
    keys = sub.get("keys") or {}
    if not ep or not keys.get("p256dh") or not keys.get("auth"):
        raise HTTPException(400, "invalid subscription")
    with _reviews_db() as c:
        c.execute(
            "INSERT INTO push_subscriptions(user_id,endpoint,p256dh,auth,ua) VALUES(?,?,?,?,?) "
            "ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id, p256dh=excluded.p256dh, "
            "auth=excluded.auth",
            (user["id"], ep, keys["p256dh"], keys["auth"],
             (request.headers.get("user-agent") or "")[:200]))
    return {"ok": True}


@app.post("/push/unsubscribe")
def push_unsubscribe(body: dict, user: dict = Depends(current_user)):
    ep = (body.get("endpoint") or "").strip()
    with _reviews_db() as c:
        if ep:
            c.execute("DELETE FROM push_subscriptions WHERE endpoint=? AND user_id=?", (ep, user["id"]))
        else:
            c.execute("DELETE FROM push_subscriptions WHERE user_id=?", (user["id"],))
    return {"ok": True}


class PushSendBody(BaseModel):
    title: str
    body: str
    url: str = "/"
    target: str = "all"      # all | user:<uid>


@app.post("/admin/push/send")
def admin_push_send(req: PushSendBody, _admin: dict = Depends(admin_user)):
    """관리자 수동 푸시 발송. target=all(구독 전체) 또는 user:<uid>."""
    if req.target.startswith("user:"):
        ids = [req.target.split(":", 1)[1]]
    else:
        with _reviews_db() as c:
            ids = [r[0] for r in c.execute("SELECT DISTINCT user_id FROM push_subscriptions").fetchall()]
    res = _send_web_push(ids, req.title.strip(), req.body.strip(), req.url or "/", tag="admin")
    return {"targets": len(ids), **res}


@app.get("/me/favorites")
def my_favorites(user: dict = Depends(current_user)):
    """내 관심단지 목록(일반 사용자 — 멤버십 불필요). 16시 알림 대상."""
    with _reviews_db() as c:
        rows = c.execute("SELECT complex_no, complex_name FROM realtor_fav_complexes "
                         "WHERE user_id=? ORDER BY created_at", (user["id"],)).fetchall()
    return {"items": [{"complex_no": r[0], "complex_name": r[1]} for r in rows]}


@app.post("/me/favorites")
def my_favorite_add(body: dict, user: dict = Depends(current_user)):
    cno = (body.get("complex_no") or "").strip()
    cname = (body.get("complex_name") or "").strip()
    if not cno:
        raise HTTPException(400, "complex_no required")
    with _reviews_db() as c:
        n = c.execute("SELECT COUNT(*) FROM realtor_fav_complexes WHERE user_id=?", (user["id"],)).fetchone()[0]
        exists = c.execute("SELECT 1 FROM realtor_fav_complexes WHERE user_id=? AND complex_no=?",
                           (user["id"], cno)).fetchone()
        if not exists and n >= 20:
            raise HTTPException(400, "관심단지는 최대 20개까지 등록할 수 있어요")
        c.execute("INSERT OR IGNORE INTO realtor_fav_complexes(user_id,complex_no,complex_name) VALUES(?,?,?)",
                  (user["id"], cno, cname or None))
    return {"ok": True}


@app.delete("/me/favorites/{complex_no}")
def my_favorite_remove(complex_no: str, user: dict = Depends(current_user)):
    with _reviews_db() as c:
        c.execute("DELETE FROM realtor_fav_complexes WHERE user_id=? AND complex_no=?",
                  (user["id"], complex_no))
    return {"ok": True}


@app.get("/admin/push/stats")
def admin_push_stats(_admin: dict = Depends(admin_user)):
    with _reviews_db() as c:
        subs = c.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0]
        users = c.execute("SELECT COUNT(DISTINCT user_id) FROM push_subscriptions").fetchone()[0]
    return {"subscriptions": subs, "users": users, "configured": _vapid() is not None}


# ─── 닉네임 (글·리뷰·AI 호칭) ───────────────────────────────────
import re as _re

_NICK_RE = _re.compile(r"^[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_]{2,12}$")
_NICK_BANNED = {"관리자", "운영자", "admin", "administrator", "콕집", "운영팀", "익명", "탈퇴"}


def _clean_nickname(raw: str | None) -> str:
    """닉네임 검증·정규화. 한/영/숫자/언더바 2~12자. 실패 시 HTTPException(400)."""
    name = (raw or "").strip()
    if not _NICK_RE.match(name):
        raise HTTPException(400, "닉네임은 한글·영문·숫자·_ 2~12자만 가능합니다")
    if name.lower() in _NICK_BANNED or "관리자" in name:
        raise HTTPException(400, "사용할 수 없는 닉네임입니다")
    return name


def _nickname(c: sqlite3.Connection, user_id: str) -> str | None:
    r = c.execute("SELECT nickname FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
    return r[0] if r else None


def _require_nickname(c: sqlite3.Connection, user_id: str) -> str:
    """글/리뷰 작성 전 닉네임 필수. 없으면 409 → 프런트가 닉네임 설정 유도."""
    nick = _nickname(c, user_id)
    if not nick:
        raise HTTPException(409, "닉네임을 먼저 설정해주세요")
    return nick


@app.get("/me/nickname/check")
def nickname_check(name: str, user: dict = Depends(current_user)) -> dict:
    """닉네임 사용 가능 여부(중복·형식). 본인 현재 닉네임은 available."""
    try:
        clean = _clean_nickname(name)
    except HTTPException as e:
        return {"available": False, "reason": e.detail}
    with _reviews_db() as c:
        taken = c.execute(
            "SELECT 1 FROM user_profiles WHERE lower(nickname)=lower(?) AND user_id<>?",
            (clean, user["id"])).fetchone()
    return {"available": not taken, "reason": "이미 사용 중인 닉네임이에요" if taken else None}


class NicknameBody(BaseModel):
    nickname: str


@app.post("/me/nickname")
def set_nickname(body: NicknameBody, user: dict = Depends(current_user)) -> dict:
    """닉네임 설정/변경 (최초 로그인 시 선택). 전 회원 유일."""
    clean = _clean_nickname(body.nickname)
    with _reviews_db() as c:
        # 행 없으면 생성(아직 전화인증 전이라 user_profiles 행이 없을 수 있음)
        c.execute("INSERT INTO user_profiles(user_id, updated_at) VALUES(?, datetime('now')) "
                  "ON CONFLICT(user_id) DO NOTHING", (user["id"],))
        try:
            c.execute("UPDATE user_profiles SET nickname=?, updated_at=datetime('now') WHERE user_id=?",
                      (clean, user["id"]))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "이미 사용 중인 닉네임이에요")
        # 최초 닉네임 설정 시 1회 20p (이후 변경은 미지급)
        awarded = 0
        na = c.execute("SELECT nickname_awarded FROM user_profiles WHERE user_id=?",
                       (user["id"],)).fetchone()
        if not (na and na[0]):
            _award_points(c, user["id"], "nickname")
            c.execute("UPDATE user_profiles SET nickname_awarded=1 WHERE user_id=?", (user["id"],))
            awarded = POINTS["nickname"]
        c.commit()
    return {"nickname": clean, "awarded": awarded}


class ConsentBody(BaseModel):
    agree_terms: bool      # 이용약관 동의 (필수)
    agree_privacy: bool    # 개인정보 수집·이용 동의 (필수)
    marketing: bool = False  # 마케팅·혜택 알림 수신 (선택)


@app.post("/me/consent")
def set_consent(body: ConsentBody, user: dict = Depends(current_user)) -> dict:
    """최초 로그인 시 약관·개인정보 동의 기록(동의 시각·버전 보관 — 감사 대비).
    필수 2개 미동의 시 거부."""
    if not (body.agree_terms and body.agree_privacy):
        raise HTTPException(400, "이용약관과 개인정보 수집·이용에 동의해야 이용할 수 있어요")
    mk = 1 if body.marketing else 0
    with _reviews_db() as c:
        c.execute("INSERT INTO user_profiles(user_id, updated_at) VALUES(?, datetime('now')) "
                  "ON CONFLICT(user_id) DO NOTHING", (user["id"],))
        c.execute(
            "UPDATE user_profiles SET agreed_terms_at=datetime('now'), consent_version=?, "
            "marketing_opt_in=?, marketing_opt_in_at=datetime('now'), updated_at=datetime('now') "
            "WHERE user_id=?",
            (CONSENT_VERSION, mk, user["id"]))
        c.commit()
    return {"ok": True, "consent_version": CONSENT_VERSION, "marketing_opt_in": bool(mk)}


@app.delete("/me")
def delete_me(user: dict = Depends(current_user)) -> dict:
    """회원 탈퇴 — 본인 데이터 영구 삭제 + 활동로그 비식별화 + Supabase 인증계정 삭제."""
    uid = user["id"]
    with _reviews_db() as c:
        for tbl in ("complex_reviews", "resident_verifications", "forum_votes",
                    "forum_comments", "forum_posts", "point_ledger", "phone_otp",
                    "user_profiles"):
            c.execute(f"DELETE FROM {tbl} WHERE user_id=?", (uid,))
        c.commit()
    # 활동로그: 통계 행은 남기되 개인정보(이메일·IP·UA·상세)만 제거
    try:
        with _logs_db() as c:
            c.execute("UPDATE event_log SET user_id=NULL, member_no=NULL, email=NULL, "
                      "ip=NULL, user_agent=NULL, detail=NULL WHERE user_id=?", (uid,))
            c.commit()
    except Exception:  # noqa: BLE001
        pass
    # Supabase 인증계정까지 삭제(서비스 키) — 완전 탈퇴
    try:
        if settings.supabase_url and settings.supabase_secret_key:
            req = _urlreq.Request(
                f"{settings.supabase_url}/auth/v1/admin/users/{uid}",
                method="DELETE",
                headers={"apikey": settings.supabase_secret_key,
                         "Authorization": f"Bearer {settings.supabase_secret_key}"})
            _urlreq.urlopen(req, timeout=10)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True}


# ─── 토론장 (forum) ───────────────────────────────────────────
def _vote_map(c: sqlite3.Connection, user_id: str | None, target_type: str, ids: list[int]) -> dict:
    """{target_id: my_vote(+1/-1)} — 로그인 사용자의 표."""
    if not user_id or not ids:
        return {}
    ph = ",".join("?" * len(ids))
    return {r[0]: r[1] for r in c.execute(
        f"SELECT target_id, value FROM forum_votes WHERE user_id=? AND target_type=? "
        f"AND target_id IN ({ph})", (user_id, target_type, *ids)).fetchall()}


def _recount_votes(c: sqlite3.Connection, target_type: str, target_id: int) -> tuple[int, int]:
    """forum_votes 집계 → 대상 테이블 up/down 캐시 갱신. (up, down) 반환."""
    up = c.execute("SELECT COUNT(*) FROM forum_votes WHERE target_type=? AND target_id=? AND value=1",
                   (target_type, target_id)).fetchone()[0]
    down = c.execute("SELECT COUNT(*) FROM forum_votes WHERE target_type=? AND target_id=? AND value=-1",
                     (target_type, target_id)).fetchone()[0]
    tbl = "forum_posts" if target_type == "post" else "forum_comments"
    c.execute(f"UPDATE {tbl} SET up=?, down=? WHERE id=?", (up, down, target_id))
    return up, down


@app.get("/forum/posts")
def forum_list(sort: str = "recent", q: str | None = None, limit: int = 30, offset: int = 0,
               user: dict = Depends(current_user_optional)) -> dict:
    """토론장 글 목록. sort: recent(최신)|hot(추천많고 최근). q: 제목·본문·닉네임 검색."""
    if limit < 1 or limit > 50:
        raise HTTPException(400, "limit out of range")
    order = ("(up - down) DESC, created_at DESC" if sort == "hot"
             else "created_at DESC")
    where = "status='published'"
    params: list = []
    kw = (q or "").strip()
    if kw:
        where += " AND (title LIKE ? OR body LIKE ? OR nickname LIKE ?)"
        like = f"%{kw}%"
        params += [like, like, like]
    with _reviews_db() as c:
        rows = c.execute(
            f"SELECT id, user_id, nickname, title, body, image_path, up, down, comment_count, created_at "
            f"FROM forum_posts WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
            (*params, limit, offset)).fetchall()
        total = c.execute(f"SELECT COUNT(*) FROM forum_posts WHERE {where}", params).fetchone()[0]
        rmap = _rank_map(c, [r["user_id"] for r in rows])
    items = [{
        "id": r["id"], "nickname": r["nickname"], "title": r["title"],
        "excerpt": (r["body"] or "")[:140],
        "has_image": bool(r["image_path"]),
        "up": r["up"], "down": r["down"], "score": r["up"] - r["down"],
        "comment_count": r["comment_count"], "created_at": r["created_at"],
        **(rmap.get(r["user_id"]) or {}),   # rank, emoji, level
    } for r in rows]
    return {"sort": sort, "q": kw, "total": total, "items": items}


@app.get("/forum/posts/{post_id}")
def forum_get(post_id: int, user: dict = Depends(current_user_optional)) -> dict:
    """글 상세 + 댓글 + (로그인 시) 내 표."""
    uid = user["id"] if user else None
    with _reviews_db() as c:
        p = c.execute("SELECT * FROM forum_posts WHERE id=? AND status='published'",
                      (post_id,)).fetchone()
        if not p:
            raise HTTPException(404, "글을 찾을 수 없습니다")
        comments = c.execute(
            "SELECT * FROM forum_comments WHERE post_id=? AND status='published' "
            "ORDER BY created_at ASC", (post_id,)).fetchall()
        pv = _vote_map(c, uid, "post", [post_id]).get(post_id, 0)
        cv = _vote_map(c, uid, "comment", [r["id"] for r in comments])
        rmap = _rank_map(c, [p["user_id"], *[r["user_id"] for r in comments]])
    post = {
        "id": p["id"], "nickname": p["nickname"], "title": p["title"], "body": p["body"],
        "has_image": bool(p["image_path"]), "up": p["up"], "down": p["down"],
        "score": p["up"] - p["down"], "comment_count": p["comment_count"],
        "created_at": p["created_at"], "my_vote": pv,
        "is_mine": bool(uid and uid == p["user_id"]),
        **(rmap.get(p["user_id"]) or {}),   # rank, emoji, level
    }
    cmts = [{
        "id": r["id"], "nickname": r["nickname"], "body": r["body"],
        "up": r["up"], "down": r["down"], "score": r["up"] - r["down"],
        "created_at": r["created_at"], "my_vote": cv.get(r["id"], 0),
        "is_mine": bool(uid and uid == r["user_id"]),
        **(rmap.get(r["user_id"]) or {}),   # rank, emoji, level
    } for r in comments]
    return {"post": post, "comments": cmts}


@app.get("/forum/posts/{post_id}/image")
def forum_image(post_id: int):
    """글 첨부 이미지."""
    from fastapi.responses import FileResponse
    with _reviews_db() as c:
        r = c.execute("SELECT image_path FROM forum_posts WHERE id=?", (post_id,)).fetchone()
    if not r or not r[0]:
        raise HTTPException(404, "이미지 없음")
    p = Path(r[0])
    if not p.exists():
        raise HTTPException(404, "이미지 파일 없음")
    return FileResponse(p)


@app.post("/forum/posts")
async def forum_create(
    title: str = FastapiForm(...),
    body: str = FastapiForm(""),
    image: UploadFile | None = File(None),
    user: dict = Depends(current_user),
):
    """글 작성. 닉네임 필수. 이미지(공유→토론장) 선택 첨부."""
    title = (title or "").strip()
    body = (body or "").strip()
    if len(title) < 2 or len(title) > 120:
        raise HTTPException(400, "제목은 2~120자")
    if len(body) > 8000:
        raise HTTPException(400, "본문이 너무 깁니다")
    with _reviews_db() as c:
        nick = _require_nickname(c, user["id"])
        _enforce_hourly(c, "forum_posts", "user_id", user["id"])  # 시간당 30건 한도
        cur = c.execute(
            "INSERT INTO forum_posts(user_id, nickname, title, body) VALUES(?,?,?,?)",
            (user["id"], nick, title, body))
        post_id = cur.lastrowid
        img_path = None
        if image is not None and (image.filename or ""):
            data = await image.read()
            if len(data) > 6_000_000:
                raise HTTPException(400, "이미지는 6MB 이하")
            ext = Path(image.filename).suffix.lower() or ".png"
            if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                ext = ".png"
            dest = FORUM_IMG_DIR / f"post_{post_id}{ext}"
            dest.write_bytes(data)
            img_path = str(dest)
            c.execute("UPDATE forum_posts SET image_path=? WHERE id=?", (img_path, post_id))
        # 글 작성 포인트(+10) — 스팸 파밍 방지로 하루 FORUM_POST_DAILY_CAP 건까지만 적립.
        awarded = 0
        today_n = c.execute(
            "SELECT COUNT(*) FROM point_ledger WHERE user_id=? AND reason='forum_post' "
            "AND date(created_at)=date('now')", (user["id"],)).fetchone()[0]
        bal = None
        if today_n < FORUM_POST_DAILY_CAP:
            bal = _award_points(c, user["id"], "forum_post", ref=f"post:{post_id}")
            awarded = POINTS["forum_post"]
        c.commit()
    return {"id": post_id, "nickname": nick, "has_image": bool(img_path),
            "awarded": awarded, "points": bal}


class CommentBody(BaseModel):
    body: str


@app.post("/forum/posts/{post_id}/comments")
def forum_comment(post_id: int, body: CommentBody, user: dict = Depends(current_user)) -> dict:
    """댓글 작성. 닉네임 필수."""
    text = (body.body or "").strip()
    if len(text) < 1 or len(text) > 2000:
        raise HTTPException(400, "댓글은 1~2000자")
    with _reviews_db() as c:
        nick = _require_nickname(c, user["id"])
        if not c.execute("SELECT 1 FROM forum_posts WHERE id=? AND status='published'",
                         (post_id,)).fetchone():
            raise HTTPException(404, "글을 찾을 수 없습니다")
        cur = c.execute(
            "INSERT INTO forum_comments(post_id, user_id, nickname, body) VALUES(?,?,?,?)",
            (post_id, user["id"], nick, text))
        c.execute("UPDATE forum_posts SET comment_count=comment_count+1 WHERE id=?", (post_id,))
        cid = cur.lastrowid
        # 댓글 포인트(+1) — 하루 FORUM_COMMENT_DAILY_CAP 건까지만(스팸 파밍 방지)
        awarded = 0; bal = None
        today_n = c.execute(
            "SELECT COUNT(*) FROM point_ledger WHERE user_id=? AND reason='comment' "
            "AND date(created_at)=date('now')", (user["id"],)).fetchone()[0]
        if today_n < FORUM_COMMENT_DAILY_CAP:
            bal = _award_points(c, user["id"], "comment", ref=f"comment:{cid}")
            awarded = POINTS["comment"]
        c.commit()
    return {"id": cid, "nickname": nick, "awarded": awarded, "points": bal}


class VoteBody(BaseModel):
    target_type: str   # post | comment
    target_id: int
    value: int         # 1 추천 / -1 비추천 / 0 취소(토글)


@app.post("/forum/vote")
def forum_vote(body: VoteBody, user: dict = Depends(current_user)) -> dict:
    """추천/비추천. 같은 값 다시 누르면 취소(토글). value=0 도 취소."""
    if body.target_type not in ("post", "comment"):
        raise HTTPException(400, "target_type must be post|comment")
    if body.value not in (-1, 0, 1):
        raise HTTPException(400, "value must be -1|0|1")
    tbl = "forum_posts" if body.target_type == "post" else "forum_comments"
    with _reviews_db() as c:
        if not c.execute(f"SELECT 1 FROM {tbl} WHERE id=?", (body.target_id,)).fetchone():
            raise HTTPException(404, "대상을 찾을 수 없습니다")
        cur = c.execute(
            "SELECT value FROM forum_votes WHERE user_id=? AND target_type=? AND target_id=?",
            (user["id"], body.target_type, body.target_id)).fetchone()
        prev = cur[0] if cur else 0
        new_val = 0 if (body.value == 0 or body.value == prev) else body.value  # 같은 값 → 토글 해제
        if new_val == 0:
            c.execute("DELETE FROM forum_votes WHERE user_id=? AND target_type=? AND target_id=?",
                      (user["id"], body.target_type, body.target_id))
        else:
            c.execute(
                "INSERT INTO forum_votes(user_id, target_type, target_id, value) VALUES(?,?,?,?) "
                "ON CONFLICT(user_id, target_type, target_id) DO UPDATE SET value=excluded.value",
                (user["id"], body.target_type, body.target_id, new_val))
        up, down = _recount_votes(c, body.target_type, body.target_id)
        c.commit()
    return {"my_vote": new_val, "up": up, "down": down, "score": up - down}


def _review_public(r: sqlite3.Row, nick: str | None = None) -> dict:
    """공개 노출용 직렬화 (서류 경로 등 민감 필드 제외).
    author_name 은 항상 현재 별명(nick)으로 노출 — 실명·이메일은 절대 내보내지 않음."""
    return {
        "id": r["id"],
        "realtor_id": r["realtor_id"],
        "author_name": nick or r["author_name"] or "회원",
        "is_admin": _is_admin_uid(r["author_id"]),
        "review_type": r["review_type"],
        "verified": r["review_type"] == "verified" and r["status"] == "approved",
        "rating": r["rating"] if r["review_type"] == "verified" else None,
        "body": r["body"],
        "created_at": r["created_at"],
    }


class ReviewCreate(BaseModel):
    body: str = Field(min_length=2, max_length=2000)


@app.get("/realtor/{realtor_id}/reviews")
def list_reviews(realtor_id: str):
    """공개 리뷰 목록 + 평점 요약. 게시된 일반리뷰 + 승인된 인증리뷰만 노출.
    평점(avg_rating)은 승인된 인증리뷰 기준."""
    with _reviews_db() as c:
        rows = c.execute(
            """
            SELECT * FROM realtor_reviews
            WHERE realtor_id = ?
              AND (status = 'published' OR status = 'approved')
            ORDER BY (review_type='verified' AND status='approved') DESC, created_at DESC
            """,
            (realtor_id,),
        ).fetchall()
        agg = c.execute(
            """
            SELECT COUNT(*) n, AVG(rating) avg_r
            FROM realtor_reviews
            WHERE realtor_id = ? AND review_type='verified'
              AND status='approved' AND rating IS NOT NULL
            """,
            (realtor_id,),
        ).fetchone()
        nmap = _nick_map(c, [r["author_id"] for r in rows])
    items = [_review_public(r, nmap.get(r["author_id"])) for r in rows]
    return {
        "realtor_id": realtor_id,
        "summary": {
            "avg_rating": round(agg["avg_r"], 2) if agg["avg_r"] is not None else None,
            "verified_count": agg["n"],
            "total_count": len(items),
        },
        "items": items,
    }


@app.post("/realtor/{realtor_id}/reviews")
def create_general_review(
    realtor_id: str, req: ReviewCreate, user: dict = Depends(current_user)
):
    """일반리뷰 — 의견만, 별점 없음, 즉시 게시. 로그인 회원만. 작성 시 포인트 적립."""
    with _reviews_db() as c:
        nick = _require_nickname(c, user["id"])
        _enforce_hourly(c, "realtor_reviews", "author_id", user["id"])  # 시간당 30건 한도
        cur = c.execute(
            """INSERT INTO realtor_reviews
               (realtor_id, author_id, author_name, review_type, body, status)
               VALUES (?, ?, ?, 'general', ?, 'published')""",
            (realtor_id, user["id"], nick, req.body.strip()),
        )
        rid = cur.lastrowid
        new_bal = _award_points(c, user["id"], "review", ref=f"realtor:{realtor_id}")
        c.commit()
    return {"ok": True, "id": rid, "status": "published", "points": new_bal,
            "awarded": POINTS["review"]}


@app.post("/realtor/{realtor_id}/reviews/verified")
async def create_verified_review(
    realtor_id: str,
    rating: int = FastapiForm(...),
    body: str = FastapiForm(...),
    document: UploadFile = File(...),
    user: dict = Depends(current_user),
):
    """인증리뷰 — 별점 + 의견 + 거래 입증 서류. 'pending' 으로 저장돼 관리자 승인 대기.
    로그인 회원만."""
    if not (1 <= rating <= 5):
        raise HTTPException(400, "rating must be 1..5")
    body = (body or "").strip()
    if len(body) < 2 or len(body) > 2000:
        raise HTTPException(400, "body length out of range")
    ext = Path(document.filename or "").suffix.lower()
    if ext not in _REVIEW_DOC_EXTS:
        raise HTTPException(400, f"허용되지 않는 파일 형식입니다 ({', '.join(sorted(_REVIEW_DOC_EXTS))})")
    data = await document.read()
    if len(data) > _REVIEW_DOC_MAX_BYTES:
        raise HTTPException(400, "파일이 너무 큽니다 (최대 10MB)")
    if not data:
        raise HTTPException(400, "빈 파일입니다")

    with _reviews_db() as c:
        nick = _require_nickname(c, user["id"])
        _enforce_hourly(c, "realtor_reviews", "author_id", user["id"])  # 시간당 30건 한도
        cur = c.execute(
            """INSERT INTO realtor_reviews
               (realtor_id, author_id, author_name, review_type, rating, body, status, doc_name)
               VALUES (?, ?, ?, 'verified', ?, ?, 'pending', ?)""",
            (realtor_id, user["id"], nick, rating, body, document.filename),
        )
        rid = cur.lastrowid
        # id 기반 파일명으로 저장 (원본명 노출 방지). 승인/거부 시 삭제.
        doc_path = REVIEW_DOCS_DIR / f"{rid}{ext}"
        doc_path.write_bytes(data)
        c.execute("UPDATE realtor_reviews SET doc_path=? WHERE id=?", (str(doc_path), rid))
        c.commit()
    return {"ok": True, "id": rid, "status": "pending"}


# ── 관리자 검수 (로그인/권한 시스템 연동 전까지 로컬 전용) ──────────────
def _delete_review_doc(row: sqlite3.Row) -> None:
    p = row["doc_path"]
    if p:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass


@app.get("/admin/reviews/pending")
def admin_pending_reviews(limit: int = 200, _admin: dict = Depends(admin_user)):
    """검수 대기중인 인증리뷰 목록 (관리자용)."""
    with _reviews_db() as c:
        rows = c.execute(
            """SELECT id, realtor_id, author_id, author_name, rating, body, doc_name, created_at
               FROM realtor_reviews WHERE status='pending'
               ORDER BY created_at ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        nmap = _nick_map(c, [r["author_id"] for r in rows])
    items = []
    for r in rows:
        d = dict(r)
        d["author_name"] = nmap.get(r["author_id"]) or r["author_name"] or "회원"
        d.pop("author_id", None)  # 작성자 식별자(개인정보) 미노출
        items.append(d)
    return {"items": items, "total": len(items)}


@app.get("/admin/reviews/{review_id}/document")
def admin_review_document(review_id: int, _admin: dict = Depends(admin_user)):
    """검수용 서류 원본 보기 (pending 상태에서만)."""
    from fastapi.responses import FileResponse
    with _reviews_db() as c:
        row = c.execute(
            "SELECT doc_path, doc_name, status FROM realtor_reviews WHERE id=?",
            (review_id,),
        ).fetchone()
    if not row or row["status"] != "pending" or not row["doc_path"]:
        raise HTTPException(404, "문서를 찾을 수 없습니다 (이미 검수 완료되었거나 폐기됨)")
    p = Path(row["doc_path"])
    if not p.exists():
        raise HTTPException(404, "문서 파일이 존재하지 않습니다")
    return FileResponse(p, filename=row["doc_name"] or p.name)


@app.post("/admin/reviews/{review_id}/approve")
def admin_approve_review(review_id: int, _admin: dict = Depends(admin_user)):
    """인증리뷰 승인 → approved + (거래인증) 노출. 서류는 즉시 폐기."""
    with _reviews_db() as c:
        row = c.execute("SELECT * FROM realtor_reviews WHERE id=?", (review_id,)).fetchone()
        if not row or row["status"] != "pending":
            raise HTTPException(404, "검수 대기중인 리뷰가 아닙니다")
        _delete_review_doc(row)
        c.execute(
            "UPDATE realtor_reviews SET status='approved', doc_path=NULL, "
            "decided_at=datetime('now') WHERE id=?",
            (review_id,),
        )
        # 인증리뷰 승인 보너스(+100) — 작성자에게. 승인은 pending→approved 1회뿐이라 중복 없음.
        if row["user_id"]:
            _award_points(c, row["user_id"], "review_verified", ref=f"review:{review_id}")
        c.commit()
    return {"ok": True, "id": review_id, "status": "approved"}


class ReviewReject(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


@app.post("/admin/reviews/{review_id}/reject")
def admin_reject_review(review_id: int, req: ReviewReject | None = None,
                        _admin: dict = Depends(admin_user)):
    """인증리뷰 거부 → rejected (비공개). 서류는 즉시 폐기."""
    with _reviews_db() as c:
        row = c.execute("SELECT * FROM realtor_reviews WHERE id=?", (review_id,)).fetchone()
        if not row or row["status"] != "pending":
            raise HTTPException(404, "검수 대기중인 리뷰가 아닙니다")
        _delete_review_doc(row)
        c.execute(
            "UPDATE realtor_reviews SET status='rejected', doc_path=NULL, "
            "reject_reason=?, decided_at=datetime('now') WHERE id=?",
            ((req.reason if req else None), review_id),
        )
        c.commit()
    return {"ok": True, "id": review_id, "status": "rejected"}


# ===========================================================================
# 전화번호 SMS 인증 (알리고) — 로그인 사용자 본인 번호 인증
# ===========================================================================
def _aligo_send_sms(receiver: str, msg: str):
    """알리고로 SMS 발송. 자격증명 미설정 시 None(=dev 모드, 코드 응답 노출)."""
    if not (settings.aligo_api_key and settings.aligo_user_id and settings.aligo_sender):
        return None
    import urllib.parse as _up
    data = _up.urlencode({
        "key": settings.aligo_api_key, "user_id": settings.aligo_user_id,
        "sender": settings.aligo_sender, "receiver": receiver,
        "msg": msg, "msg_type": "SMS",
    }).encode()
    try:
        req = _urlreq.Request("https://apis.aligo.in/send/", data=data, method="POST")
        with _urlreq.urlopen(req, timeout=10) as r:
            return _authjson.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"result_code": "-99", "message": str(e)}


_PROVIDER_KR = {"kakao": "카카오", "google": "구글", "email": "이메일", "apple": "애플"}


def _provider_kr(p: str | None) -> str:
    return _PROVIDER_KR.get((p or "").lower(), p or "다른 방법")


class PhoneSendBody(BaseModel):
    phone: str


class PhoneVerifyBody(BaseModel):
    code: str
    ref: int | None = None   # 추천인 회원번호(공유 링크 ?ref=)


@app.post("/me/phone/send-code")
def phone_send_code(body: PhoneSendBody, user: dict = Depends(current_user)):
    """본인 휴대폰으로 6자리 인증번호 SMS 발송 (5분 유효)."""
    import re as _re
    import secrets as _secrets
    phone = _re.sub(r"[^0-9]", "", body.phone or "")
    if not _re.match(r"^01[016789]\d{7,8}$", phone):
        raise HTTPException(400, "올바른 휴대폰 번호가 아닙니다 (예: 01012345678)")
    code = f"{_secrets.randbelow(900000) + 100000:06d}"
    with _reviews_db() as c:
        # 60초 내 재요청 방지
        prev = c.execute("SELECT sent_at>datetime('now','-60 seconds') FROM phone_otp WHERE user_id=?",
                         (user["id"],)).fetchone()
        if prev and prev[0]:
            raise HTTPException(429, "잠시 후 다시 요청해주세요 (1분에 한 번)")
        c.execute(
            "INSERT INTO phone_otp(user_id,phone,code,expires_at,attempts,sent_at) "
            "VALUES(?,?,?, datetime('now','+5 minutes'), 0, datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone, code=excluded.code, "
            "expires_at=datetime('now','+5 minutes'), attempts=0, sent_at=datetime('now')",
            (user["id"], phone, code))
        c.commit()
    res = _aligo_send_sms(phone, f"[콕집] 인증번호 [{code}] 를 입력해주세요. (5분 이내)")
    out = {"ok": True, "expires_in": 300}
    if res is None:
        out["dev_code"] = code   # 알리고 미설정 — 개발용으로 코드 노출
    elif str(res.get("result_code")) != "1":
        raise HTTPException(502, f"문자 발송 실패: {res.get('message')}")
    return out


@app.post("/me/phone/verify")
def phone_verify(body: PhoneVerifyBody, user: dict = Depends(current_user)):
    """인증번호 확인 → 성공 시 본인 번호로 저장(phone_verified=1)·회원번호 발급.

    전화번호는 전 회원 공통 유니크 키. 이미 다른 계정(카카오/구글)이 인증해 둔
    번호면 409로 막고, 어떤 경로로 가입돼 있는지 안내한다.
    """
    code = (body.code or "").strip()
    with _reviews_db() as c:
        row = c.execute(
            "SELECT phone, code, attempts, expires_at>datetime('now') FROM phone_otp WHERE user_id=?",
            (user["id"],)).fetchone()
        if not row:
            raise HTTPException(400, "먼저 인증번호를 요청해주세요")
        phone, real, attempts, not_expired = row
        if not not_expired:
            raise HTTPException(400, "인증번호가 만료됐습니다. 다시 요청해주세요")
        if attempts >= 5:
            raise HTTPException(429, "시도 횟수를 초과했습니다. 다시 요청해주세요")
        if code != real:
            c.execute("UPDATE phone_otp SET attempts=attempts+1 WHERE user_id=?", (user["id"],))
            c.commit()
            raise HTTPException(400, "인증번호가 일치하지 않습니다")

        # 전화번호 유니크 검사 — 다른 회원이 이미 이 번호로 인증돼 있으면 차단
        dup = c.execute(
            "SELECT user_id, provider, member_no FROM user_profiles "
            "WHERE phone=? AND phone_verified=1", (phone,)).fetchone()
        if dup and dup[0] != user["id"]:
            pv = _provider_kr(dup[1])
            raise HTTPException(409, detail={
                "code": "phone_taken",
                "provider": dup[1],
                "message": f"이미 가입된 번호입니다. 이 번호는 '{pv}' 계정으로 가입되어 있어요. "
                           f"{pv}(으)로 로그인해 이용해주세요.",
            })

        # 회원번호: 기존에 있으면 유지, 없으면 신규 발급(100001~)
        mine = c.execute("SELECT member_no FROM user_profiles WHERE user_id=?",
                         (user["id"],)).fetchone()
        member_no = mine[0] if (mine and mine[0]) else (
            (c.execute("SELECT COALESCE(MAX(member_no),100000) FROM user_profiles").fetchone()[0]) + 1)

        c.execute(
            "INSERT INTO user_profiles(user_id,member_no,phone,phone_verified,provider,updated_at) "
            "VALUES(?,?,?,1,?,datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET member_no=excluded.member_no, "
            "phone=excluded.phone, phone_verified=1, provider=excluded.provider, "
            "updated_at=datetime('now')",
            (user["id"], member_no, phone, user.get("provider")))
        c.execute("DELETE FROM phone_otp WHERE user_id=?", (user["id"],))

        # 전화인증 보너스(+100) + 추천 적립 — 최초 인증 1회만(phone_bonus_awarded)
        pb = c.execute("SELECT phone_bonus_awarded FROM user_profiles WHERE user_id=?",
                       (user["id"],)).fetchone()
        if not (pb and pb[0]):
            _award_points(c, user["id"], "phone_verify")
            c.execute("UPDATE user_profiles SET phone_bonus_awarded=1 WHERE user_id=?", (user["id"],))
            if body.ref:  # 추천인(member_no): 본인과 다르고 실존해야 적립
                rr = c.execute("SELECT user_id FROM user_profiles WHERE member_no=? AND member_no<>?",
                               (int(body.ref), member_no)).fetchone()
                if rr:
                    c.execute("UPDATE user_profiles SET referred_by=? WHERE user_id=?",
                              (int(body.ref), user["id"]))
                    _award_points(c, rr[0], "referral", ref=str(member_no))
        c.commit()
    return {"ok": True, "phone": phone, "phone_verified": True, "member_no": member_no}


@app.post("/me/phone/cancel")
def phone_cancel(user: dict = Depends(current_user)):
    """전화번호 인증 취소 — 번호를 비워 유니크 점유를 해제(회원번호는 유지).

    재인증 시 같은 회원번호를 다시 쓴다. 취소하면 AI 등 인증 필요 기능은 막힌다.
    """
    with _reviews_db() as c:
        c.execute(
            "UPDATE user_profiles SET phone=NULL, phone_verified=0, updated_at=datetime('now') "
            "WHERE user_id=?", (user["id"],))
        c.execute("DELETE FROM phone_otp WHERE user_id=?", (user["id"],))
        c.commit()
    return {"ok": True, "phone_verified": False}


# ===========================================================================
# 포인트 내역 · 단지 리뷰 · 입주민 인증
# ===========================================================================
REASON_KR = {"signup": "가입 보너스", "ai_use": "AI 사용", "review": "리뷰 작성",
             "referral": "친구 추천", "resident": "입주민 인증", "admin": "관리자 지급",
             "forum_post": "토론장 글 작성"}


# ─────────────────────────────────────────────────────────────
# 중개사 라운지 — 계정↔중개사무소 연동(전화매칭/서류), 정보수정요청, 상담리드
# ─────────────────────────────────────────────────────────────
import re as _re_lounge
LOUNGE_DOC_DIR: Path = DB_PATH.parent / "realtor_docs"
LOUNGE_DOC_DIR.mkdir(parents=True, exist_ok=True)


def _digits(s) -> str:
    return _re_lounge.sub(r"\D", "", s or "")


def _my_phone(c, user_id):
    r = c.execute("SELECT phone FROM user_profiles WHERE user_id=? AND phone_verified=1",
                  (user_id,)).fetchone()
    return r[0] if r else None


def _realtor_candidates_by_phone(phone) -> list[dict]:
    """인증 휴대폰과 일치하는 중개사무소 후보.
    ① naver_realtors 연락처(휴대폰/대표전화) ② vworld 등록전화(한 필드에 여러 번호 공백구분)
    → realtor_match로 naver realtor_id 연결. 사무소가 vworld에 등록한 여러 번호 중 어느 것으로
    인증해도 사무소를 찾도록 한다(naver엔 대표번호 1개만 있어 누락되던 케이스 보완)."""
    d = _digits(phone)
    if len(d) < 9:
        return []
    out, seen = [], set()
    with _open_db() as c:
        # 통합 사전 인덱스(realtor_phone_index = naver 연락처 + vworld 등록전화 다중번호 split).
        # 인덱스 조회 1회(<1ms). 인덱스 미생성 시에만 라이브 naver 스캔으로 폴백.
        try:
            rids = [r[0] for r in c.execute(
                "SELECT DISTINCT realtor_id FROM realtor_phone_index WHERE phone_digits=?", (d,)).fetchall()]
            for rid in rids:
                if not rid or rid in seen:
                    continue
                seen.add(rid)
                br = _office_brief(rid)
                out.append({"realtor_id": rid, "realtor_name": br.get("realtor_name"),
                            "address": br.get("address"), "representative": br.get("representative")})
            return out
        except sqlite3.OperationalError:
            pass  # 인덱스 테이블 미생성 → 라이브 폴백
        for rid, name, addr, rep in c.execute(
            "SELECT realtor_id, realtor_name, address, representative_name FROM naver_realtors "
            "WHERE replace(replace(IFNULL(cell_phone_no,''),'-',''),' ','')=? "
            "   OR replace(replace(IFNULL(representative_tel_no,''),'-',''),' ','')=?",
            (d, d)).fetchall():
            if rid in seen:
                continue
            seen.add(rid)
            out.append({"realtor_id": rid, "realtor_name": name, "address": addr, "representative": rep})
    return out


def _office_brief(realtor_id):
    with _open_db() as c:
        r = c.execute(
            "SELECT realtor_id, realtor_name, address, representative_name, "
            "representative_tel_no, cell_phone_no, latitude, longitude "
            "FROM naver_realtors WHERE realtor_id=?", (realtor_id,)).fetchone()
    if not r:
        return {"realtor_id": realtor_id, "realtor_name": None}
    return {"realtor_id": r[0], "realtor_name": r[1], "address": r[2],
            "representative": r[3], "tel": r[4], "cell": r[5],
            "latitude": r[6], "longitude": r[7]}


def _require_member(c, uid) -> str:
    m = c.execute("SELECT realtor_id FROM realtor_members WHERE user_id=?", (uid,)).fetchone()
    if not m:
        raise HTTPException(403, "중개사 인증이 필요합니다")
    return m[0]


@app.get("/lounge/status")
def lounge_status(user: dict = Depends(current_user)):
    """라운지 접근 상태: need_phone / select(후보 여러개) / no_match / doc_pending / linked."""
    uid = user["id"]
    with _reviews_db() as c:
        phone = _my_phone(c, uid)
        m = c.execute("SELECT realtor_id, method FROM realtor_members WHERE user_id=?",
                      (uid,)).fetchone()
        pend = c.execute("SELECT 1 FROM realtor_verifications WHERE user_id=? AND status='pending' "
                         "LIMIT 1", (uid,)).fetchone()
        has_hp = c.execute("SELECT 1 FROM realtor_homepages WHERE realtor_id=? LIMIT 1",
                           (m[0],)).fetchone() if m else None
    if m:
        return {"state": "linked", "phone_verified": bool(phone),
                "office": _office_brief(m[0]), "method": m[1],
                "has_homepage": bool(has_hp)}
    # 관리자는 인증 없이 입장 — 아무 사무소나 연결해 둘러볼 수 있다.
    if user.get("is_admin"):
        return {"state": "admin_pick", "phone_verified": bool(phone), "is_admin": True}
    if not phone:
        return {"state": "need_phone", "phone_verified": False}
    cands = _realtor_candidates_by_phone(phone)
    if cands:
        return {"state": "select", "phone_verified": True, "candidates": cands}
    if pend:
        return {"state": "doc_pending", "phone_verified": True}
    return {"state": "no_match", "phone_verified": True}


@app.post("/lounge/select")
def lounge_select(body: dict, user: dict = Depends(current_user)):
    """매칭 후보 중 하나 선택 → 연동 저장(기억). 다음 입장부터 이 사무소로 이어짐."""
    uid = user["id"]
    rid = (body.get("realtor_id") or "").strip()
    if not rid:
        raise HTTPException(400, "realtor_id required")
    with _reviews_db() as c:
        phone = _my_phone(c, uid)
        if not user.get("is_admin"):   # 관리자는 전화매칭 검증 없이 아무 사무소나 연결 가능
            if not phone:
                raise HTTPException(403, "전화인증이 필요합니다")
            if rid not in {x["realtor_id"] for x in _realtor_candidates_by_phone(phone)}:
                raise HTTPException(403, "전화와 일치하는 사무소가 아닙니다")
        c.execute(
            "INSERT INTO realtor_members(user_id,realtor_id,method,matched_phone,updated_at) "
            "VALUES(?,?,?,?,datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET realtor_id=excluded.realtor_id, "
            "method='phone', matched_phone=excluded.matched_phone, updated_at=datetime('now')",
            (uid, rid, "phone", phone))
        c.commit()
    return {"ok": True, "office": _office_brief(rid)}


@app.post("/lounge/unlink")
def lounge_unlink(user: dict = Depends(current_user)):
    """연동 해제(다른 사무소로 바꾸거나 선택 초기화)."""
    with _reviews_db() as c:
        c.execute("DELETE FROM realtor_members WHERE user_id=?", (user["id"],))
        c.commit()
    return {"ok": True}


@app.post("/lounge/edit-request")
def lounge_edit_request(body: dict, user: dict = Depends(current_user)):
    """본인 중개사무소 정보수정요청 → 관리자 즉시 확인."""
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(400, "내용을 입력하세요")
    if len(content) > 2000:
        raise HTTPException(400, "내용이 너무 깁니다(최대 2000자)")
    uid = user["id"]
    with _reviews_db() as c:
        rid = _require_member(c, uid)
        c.execute("INSERT INTO realtor_edit_requests(user_id,realtor_id,member_no,content) "
                  "VALUES(?,?,?,?)", (uid, rid, _member_no(uid), content))
        c.commit()
    return {"ok": True}


@app.get("/lounge/edit-requests")
def lounge_my_edit_requests(user: dict = Depends(current_user)):
    with _reviews_db() as c:
        _require_member(c, user["id"])
        rows = c.execute(
            "SELECT id, content, status, admin_note, created_at, resolved_at "
            "FROM realtor_edit_requests WHERE user_id=? ORDER BY id DESC LIMIT 50",
            (user["id"],)).fetchall()
    return {"items": [{"id": r[0], "content": r[1], "status": r[2], "admin_note": r[3],
                       "created_at": r[4], "resolved_at": r[5]} for r in rows]}


@app.get("/lounge/leads")
def lounge_leads(user: dict = Depends(current_user)):
    """내 사무소로 들어온 상담신청."""
    with _reviews_db() as c:
        rid = _require_member(c, user["id"])
        rows = c.execute(
            "SELECT id,name,phone,message,source,status,created_at "
            "FROM consultation_leads WHERE realtor_id=? ORDER BY id DESC LIMIT 100",
            (rid,)).fetchall()
    return {"items": [{"id": r[0], "name": r[1], "phone": r[2], "message": r[3],
                       "source": r[4], "status": r[5], "created_at": r[6]} for r in rows]}


@app.post("/lounge/leads/{lead_id}/status")
def lounge_lead_status(lead_id: int, body: dict, user: dict = Depends(current_user)):
    st = (body.get("status") or "").strip()
    if st not in ("new", "read", "done"):
        raise HTTPException(400, "bad status")
    with _reviews_db() as c:
        rid = _require_member(c, user["id"])
        c.execute("UPDATE consultation_leads SET status=? WHERE id=? AND realtor_id=?",
                  (st, lead_id, rid))
        c.commit()
    return {"ok": True}


@app.get("/lounge/dashboard")
def lounge_dashboard(user: dict = Depends(current_user)):
    """라운지 대시보드: 사무소·매물수·전국/지역 랭킹·신규리뷰·상담신청 요약을 한 번에."""
    uid = user["id"]
    with _reviews_db() as c:
        rid = _require_member(c, uid)
        rv = c.execute(
            "SELECT COUNT(*), AVG(rating) FROM realtor_reviews "
            "WHERE realtor_id=? AND status IN ('published','approved')", (rid,)).fetchone()
        rv_new = c.execute(
            "SELECT COUNT(*) FROM realtor_reviews WHERE realtor_id=? "
            "AND status IN ('published','approved') AND created_at >= datetime('now','-30 days')",
            (rid,)).fetchone()[0]
        rv_recent = c.execute(
            "SELECT review_type, rating, body, created_at FROM realtor_reviews "
            "WHERE realtor_id=? AND status IN ('published','approved') "
            "ORDER BY id DESC LIMIT 3", (rid,)).fetchall()
        ld_new = c.execute("SELECT COUNT(*) FROM consultation_leads WHERE realtor_id=? AND status='new'", (rid,)).fetchone()[0]
        ld_total = c.execute("SELECT COUNT(*) FROM consultation_leads WHERE realtor_id=?", (rid,)).fetchone()[0]
        ld_recent = c.execute(
            "SELECT id,name,phone,message,source,status,created_at FROM consultation_leads "
            "WHERE realtor_id=? ORDER BY id DESC LIMIT 5", (rid,)).fetchall()
        has_hp = c.execute("SELECT slug,published FROM realtor_homepages WHERE realtor_id=?", (rid,)).fetchone()
        fav_n = c.execute("SELECT COUNT(*) FROM realtor_fav_complexes WHERE user_id=?", (uid,)).fetchone()[0]

    office = _office_brief(rid)
    ranks = _rank_tables()
    nat = ranks["national"].get(rid)
    region = None
    best = None
    for (sido, r2), (rk, n, _nm) in ranks["sido_rank"].items():
        if r2 == rid and (best is None or n > best[1]):
            best = (sido, n, rk)
    if best:
        region = {"sido_name": ranks["sido_names"].get(best[0], best[0]),
                  "count": best[1], "rank": best[2], "total": ranks["sido_totals"].get(best[0], 0)}
    return {
        "office": office,
        "stats": {
            "total_listings": nat[1] if nat else 0,
            "national_rank": nat[0] if nat else None,
            "national_total": ranks["national_total"],
            "region": region,
        },
        "reviews": {
            "total": rv[0] or 0, "avg": round(rv[1], 1) if rv[1] else None, "new_count": rv_new,
            "recent": [{"type": x[0], "rating": x[1], "body": x[2], "created_at": x[3]} for x in rv_recent],
        },
        "leads": {
            "new_count": ld_new, "total": ld_total,
            "recent": [{"id": x[0], "name": x[1], "phone": x[2], "message": x[3],
                        "source": x[4], "status": x[5], "created_at": x[6]} for x in ld_recent],
        },
        "homepage": {"has": bool(has_hp), "slug": has_hp[0] if has_hp else None,
                     "published": bool(has_hp[1]) if has_hp else False},
        "favorites_count": fav_n,
    }


@app.get("/lounge/favorites")
def lounge_favorites(user: dict = Depends(current_user)):
    """관심단지 + 단지별 최근 신고가·신규매물(최근 7일 등록)·총매물수."""
    with _reviews_db() as c:
        _require_member(c, user["id"])
        favs = c.execute("SELECT complex_no, complex_name FROM realtor_fav_complexes "
                         "WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    def _bucket(rows):
        b = {"A1": 0, "B1": 0, "B2": 0}
        for t, n in rows:
            if t in b:
                b[t] += n
        b["sum"] = b["A1"] + b["B1"] + b["B2"]
        return b

    items = []
    if favs:
        with _open_db() as d:
            for cno, cname in favs:
                rec = d.execute(
                    "SELECT area_key, record_price, record_date FROM tx_record_rollup "
                    "WHERE complex_no=? ORDER BY record_date DESC LIMIT 1", (cno,)).fetchone()
                # 이번주 신규(매매/전세/월세) — listings_current.article_confirm_ymd 최근 7일
                new_week = _bucket(d.execute(
                    "SELECT trade_type, COUNT(*) FROM listings_current WHERE complex_no=? "
                    "AND article_confirm_ymd >= strftime('%Y%m%d','now','-7 days') "
                    "GROUP BY trade_type", (cno,)).fetchall())
                # 전체매물(거래유형별) + 오늘 변화량 — complex_daily_agg 일별 이력
                cda = d.execute(
                    "SELECT snapshot_date, trade_type, listing_count FROM complex_daily_agg "
                    "WHERE complex_no=? ORDER BY snapshot_date DESC", (cno,)).fetchall()
                dates, by_date = [], {}
                for sd, t, n in cda:
                    if sd not in by_date:
                        by_date[sd] = {"A1": 0, "B1": 0, "B2": 0}
                        dates.append(sd)
                    if t in by_date[sd]:
                        by_date[sd][t] += n
                if dates:
                    latest = by_date[dates[0]]
                    total = {**latest, "sum": latest["A1"] + latest["B1"] + latest["B2"]}
                else:
                    total = {"A1": 0, "B1": 0, "B2": 0, "sum": 0}
                today_change = 0
                if len(dates) >= 2:
                    today_change = sum(by_date[dates[0]].values()) - sum(by_date[dates[1]].values())
                nm = cname
                if not nm:
                    row = d.execute("SELECT complex_name FROM complexes WHERE complex_no=?", (cno,)).fetchone()
                    nm = row[0] if row else cno
                items.append({
                    "complex_no": cno, "complex_name": nm,
                    "record_high": {"area_key": rec[0], "price": rec[1], "date": rec[2]} if rec else None,
                    "total": total, "new_week": new_week, "today_change": today_change,
                })
    return {"items": items}


@app.post("/lounge/favorites")
def lounge_fav_add(body: dict, user: dict = Depends(current_user)):
    cno = str(body.get("complex_no") or "").strip()
    if not cno:
        raise HTTPException(400, "complex_no required")
    with _open_db() as d:
        row = d.execute("SELECT complex_name FROM complexes WHERE complex_no=?", (cno,)).fetchone()
    if not row:
        raise HTTPException(404, "complex not found")
    with _reviews_db() as c:
        _require_member(c, user["id"])
        n = c.execute("SELECT COUNT(*) FROM realtor_fav_complexes WHERE user_id=?", (user["id"],)).fetchone()[0]
        if n >= 12:
            raise HTTPException(400, "관심단지는 최대 12개까지 등록할 수 있어요")
        c.execute("INSERT OR IGNORE INTO realtor_fav_complexes(user_id, complex_no, complex_name) VALUES(?,?,?)",
                  (user["id"], cno, row[0]))
        c.commit()
    return {"ok": True}


@app.delete("/lounge/favorites/{complex_no}")
def lounge_fav_del(complex_no: str, user: dict = Depends(current_user)):
    with _reviews_db() as c:
        _require_member(c, user["id"])
        c.execute("DELETE FROM realtor_fav_complexes WHERE user_id=? AND complex_no=?",
                  (user["id"], complex_no))
        c.commit()
    return {"ok": True}


_SIDO_SHORT = {"서울특별시": "서울", "인천광역시": "인천", "부산광역시": "부산", "대구광역시": "대구",
               "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
               "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원", "충청북도": "충북", "충청남도": "충남",
               "전북특별자치도": "전북", "전라북도": "전북", "전라남도": "전남", "경상북도": "경북",
               "경상남도": "경남", "제주특별자치도": "제주"}


@app.get("/lounge/fav-offices")
def lounge_fav_offices(user: dict = Depends(current_user)):
    """관심중개사무소 + 사무소별 매물(매매/전세/월세)·오늘 증감·전국순위."""
    with _reviews_db() as c:
        _require_member(c, user["id"])
        favs = c.execute("SELECT realtor_id FROM realtor_fav_offices "
                         "WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    if not favs:
        return {"items": []}
    ranks = _rank_tables()
    items = []
    with _open_db() as d:
        for (rid,) in favs:
            rows = d.execute(
                "SELECT snapshot_date, a1, b1, b2, total FROM realtor_daily_count "
                "WHERE realtor_id=? ORDER BY snapshot_date DESC LIMIT 2", (rid,)).fetchall()
            if rows:
                lt = rows[0]
                total = {"A1": lt[1], "B1": lt[2], "B2": lt[3], "sum": lt[4]}
                today_change = (rows[0][4] - rows[1][4]) if len(rows) >= 2 else 0
            else:
                total = {"A1": 0, "B1": 0, "B2": 0, "sum": 0}
                today_change = 0
            office = _office_brief(rid)
            nat = ranks["national"].get(rid)
            items.append({
                "realtor_id": rid, "realtor_name": office.get("realtor_name"),
                "address": office.get("address"), "representative": office.get("representative"),
                "total": total, "today_change": today_change,
                "national_rank": nat[0] if nat else None,
            })
    return {"items": items}


@app.post("/lounge/fav-offices")
def lounge_fav_office_add(body: dict, user: dict = Depends(current_user)):
    rid = str(body.get("realtor_id") or "").strip()
    if not rid:
        raise HTTPException(400, "realtor_id required")
    with _open_db() as d:
        if not d.execute("SELECT 1 FROM naver_realtors WHERE realtor_id=?", (rid,)).fetchone():
            raise HTTPException(404, "office not found")
    with _reviews_db() as c:
        _require_member(c, user["id"])
        n = c.execute("SELECT COUNT(*) FROM realtor_fav_offices WHERE user_id=?", (user["id"],)).fetchone()[0]
        if n >= 12:
            raise HTTPException(400, "관심중개사무소는 최대 12개까지 등록할 수 있어요")
        c.execute("INSERT OR IGNORE INTO realtor_fav_offices(user_id, realtor_id) VALUES(?,?)",
                  (user["id"], rid))
        c.commit()
    return {"ok": True}


@app.delete("/lounge/fav-offices/{realtor_id}")
def lounge_fav_office_del(realtor_id: str, user: dict = Depends(current_user)):
    with _reviews_db() as c:
        _require_member(c, user["id"])
        c.execute("DELETE FROM realtor_fav_offices WHERE user_id=? AND realtor_id=?",
                  (user["id"], realtor_id))
        c.commit()
    return {"ok": True}


def _archive_files():
    base = DB_PATH.parent / "archive" / "listings"
    if not base.exists():
        return []
    return sorted(base.glob("**/listings_*.parquet"))


def _listing_changes(field: str, value: str, cap: int = 3000) -> dict:
    """최근 2개 매물 스냅샷(parquet)을 article 단위로 비교 → 신규/빠진 매물 상세."""
    import re
    files = _archive_files()
    if len(files) < 2:
        return {"added": [], "removed": [], "bumped": [], "dates": None, "note": "비교할 이전 스냅샷이 아직 없어요"}
    try:
        import pyarrow.parquet as pq
    except Exception:
        return {"added": [], "removed": [], "bumped": [], "dates": None, "note": "스냅샷 비교 모듈이 없습니다"}
    from collections import defaultdict
    f0, f1 = files[-1], files[-2]
    cols = ["article_no", "complex_no", "trade_type", "area_name", "floor_info",
            "deal_or_warrant_price_text", "rent_price_text", "deal_or_warrant_price", "rent_price",
            "building_name", "direction", "article_confirm_ymd", "realtor_id"]

    def load(p):
        try:
            return pq.read_table(str(p), columns=cols, filters=[(field, "==", value)]).to_pylist()
        except Exception:
            return []

    cur, prev = load(f0), load(f1)
    cur_ids = {r["article_no"] for r in cur}
    prev_ids = {r["article_no"] for r in prev}
    added_rows = [r for r in cur if r["article_no"] not in prev_ids]
    removed_rows = [r for r in prev if r["article_no"] not in cur_ids]

    # 끌올(재등록) 매칭 — 가격·동·평형·중개사·거래유형이 모두 같으면 같은 물건을 내렸다 다시 올린 것으로 간주.
    # 내림↔올림 1:1 짝지어 bumped로 분류하고 신규/빠짐에서 제외.
    def keyof(r):
        return (r.get("trade_type"), r.get("deal_or_warrant_price"), r.get("rent_price"),
                r.get("building_name"), r.get("area_name"), r.get("realtor_id"))
    pool: dict = defaultdict(list)
    for r in removed_rows:
        pool[keyof(r)].append(r)
    bumped_rows, new_added = [], []
    for a in added_rows:
        lst = pool.get(keyof(a))
        if lst:
            lst.pop(0)
            bumped_rows.append(a)
        else:
            new_added.append(a)
    new_removed = [r for lst in pool.values() for r in lst]

    def fmt(r):
        tt = r.get("trade_type")
        price = r.get("deal_or_warrant_price_text") or ""
        if tt == "B2" and r.get("rent_price_text"):
            price = f"{price}/{r['rent_price_text']}"
        return {"article_no": r.get("article_no"), "complex_no": r.get("complex_no"),
                "trade_type": tt, "area_name": r.get("area_name"), "floor": r.get("floor_info"),
                "price": price, "building": r.get("building_name"), "direction": r.get("direction")}

    def dstr(p):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        return m.group(1) if m else ""
    return {"added": [fmt(r) for r in new_added][:cap],
            "removed": [fmt(r) for r in new_removed][:cap],
            "bumped": [fmt(r) for r in bumped_rows][:cap],
            "dates": {"current": dstr(f0), "prev": dstr(f1)}}


def _attach_complex_names(items: list):
    cnos = {x.get("complex_no") for x in items if x.get("complex_no")}
    if not cnos:
        return
    names = {}
    with _open_db() as d:
        qm = ",".join("?" * len(cnos))
        for cno, nm in d.execute(f"SELECT complex_no, complex_name FROM complexes WHERE complex_no IN ({qm})", list(cnos)):
            names[cno] = nm
    for x in items:
        x["complex_name"] = names.get(x.get("complex_no"))


@app.get("/lounge/complex-changes")
def lounge_complex_changes(complex_no: str, user: dict = Depends(current_user)):
    """관심단지 매물 변화 상세 — 어제 대비 신규/빠진 매물."""
    with _reviews_db() as c:
        _require_member(c, user["id"])
    res = _listing_changes("complex_no", complex_no)
    with _open_db() as d:
        row = d.execute("SELECT complex_name FROM complexes WHERE complex_no=?", (complex_no,)).fetchone()
    return {"complex_no": complex_no, "complex_name": row[0] if row else complex_no, **res}


@app.get("/lounge/office-changes")
def lounge_office_changes(realtor_id: str, user: dict = Depends(current_user)):
    """관심중개사무소 매물 변화 상세 — 어제 대비 신규/빠진 매물(단지명 포함)."""
    with _reviews_db() as c:
        _require_member(c, user["id"])
    res = _listing_changes("realtor_id", realtor_id)
    _attach_complex_names(res["added"] + res["removed"] + res.get("bumped", []))
    office = _office_brief(realtor_id)
    return {"realtor_id": realtor_id, "realtor_name": office.get("realtor_name"), **res}


@app.get("/lounge/complex-search")
def lounge_complex_search(q: str, user: dict = Depends(current_user)):
    """관심단지 추가용 단지명 검색 — '아파트'·공백 제거 후 매칭, 위치(시도·시군구·동)+세대수 포함."""
    kw = (q or "").strip()
    if len(kw) < 2:
        return {"items": []}
    with _reviews_db() as c:
        _require_member(c, user["id"])
    norm = kw.replace("아파트", "").replace(" ", "").strip()
    like = f"%{norm or kw}%"
    with _open_db() as d:
        rows = d.execute(
            "SELECT cx.complex_no, cx.complex_name, cx.total_household_count, "
            "       rsi.cortar_name, rsg.cortar_name, rdo.cortar_name "
            "FROM complexes cx "
            "LEFT JOIN regions rsi ON rsi.cortar_no = substr(cx.cortar_no,1,2)||'00000000' "
            "LEFT JOIN regions rsg ON rsg.cortar_no = substr(cx.cortar_no,1,5)||'00000' "
            "LEFT JOIN regions rdo ON rdo.cortar_no = cx.cortar_no "
            "WHERE REPLACE(cx.complex_name,' ','') LIKE ? "
            "ORDER BY cx.total_household_count DESC LIMIT 15",
            (like,)).fetchall()
    items = []
    for r in rows:
        region = " ".join(x for x in [_SIDO_SHORT.get(r[3], r[3]), r[4], r[5]] if x)
        items.append({"complex_no": r[0], "complex_name": r[1],
                      "households": r[2], "region": region})
    return {"items": items}


@app.get("/complexes/search")
def complexes_search(q: str, limit: int = 20):
    """공개 단지명 검색 — 우리단지찾기용. 위치(시도·시군구·동)·세대수·현재 매물수 포함."""
    kw = (q or "").strip()
    if len(kw) < 2:
        return {"items": []}
    limit = max(1, min(limit, 40))
    norm = kw.replace("아파트", "").replace(" ", "").strip()
    like = f"%{norm or kw}%"
    with _open_db() as d:
        rows = d.execute(
            "SELECT cx.complex_no, cx.complex_name, cx.total_household_count, "
            "       rsi.cortar_name, rsg.cortar_name, rdo.cortar_name "
            "FROM complexes cx "
            "LEFT JOIN regions rsi ON rsi.cortar_no = substr(cx.cortar_no,1,2)||'00000000' "
            "LEFT JOIN regions rsg ON rsg.cortar_no = substr(cx.cortar_no,1,5)||'00000' "
            "LEFT JOIN regions rdo ON rdo.cortar_no = cx.cortar_no "
            "WHERE REPLACE(cx.complex_name,' ','') LIKE ? "
            "ORDER BY cx.total_household_count DESC LIMIT ?",
            (like, limit)).fetchall()
        counts = {}
        cnos = [r[0] for r in rows]
        if cnos:
            qm = ",".join("?" * len(cnos))
            for cno, n in d.execute(
                f"SELECT complex_no, COUNT(*) FROM listings_current WHERE complex_no IN ({qm}) GROUP BY complex_no",
                cnos):
                counts[cno] = n
    items = []
    for r in rows:
        region = " ".join(x for x in [_SIDO_SHORT.get(r[3], r[3]), r[4], r[5]] if x)
        items.append({"complex_no": r[0], "complex_name": r[1], "households": r[2],
                      "region": region, "listings": counts.get(r[0], 0)})
    return {"items": items}


@app.post("/lounge/verify-doc")
async def lounge_verify_doc(realtor_id: str = Form(""), claimed_name: str = Form(""),
                            document: UploadFile = File(...),
                            user: dict = Depends(current_user)):
    """전화매칭이 안 되는 중개사 보조 인증 — 사업자등록증 제출 → 관리자 승인."""
    data = await document.read()
    if len(data) > 8_000_000:
        raise HTTPException(400, "파일이 너무 큽니다(최대 8MB)")
    ext = Path(document.filename or "").suffix.lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".pdf"):
        raise HTTPException(400, "지원 형식: png/jpg/webp/pdf")
    with _reviews_db() as c:
        cur = c.execute(
            "INSERT INTO realtor_verifications(user_id,realtor_id,claimed_name) VALUES(?,?,?)",
            (user["id"], (realtor_id or None), (claimed_name or None)))
        vid = cur.lastrowid
        dest = LOUNGE_DOC_DIR / f"rv_{vid}{ext}"
        dest.write_bytes(data)
        c.execute("UPDATE realtor_verifications SET doc_path=? WHERE id=?", (str(dest), vid))
        c.commit()
    return {"ok": True, "id": vid}


# ── 중개사 홈페이지 빌더 (Phase B) ─────────────────────────────
HOMEPAGE_IMG_DIR: Path = DB_PATH.parent / "homepage_images"
HOMEPAGE_IMG_DIR.mkdir(parents=True, exist_ok=True)
_PHOTO_KINDS = ("apt", "rep", "office")   # 주요단지 / 대표자 / 사무소
_SLUG_RESERVED = {"admin", "api", "lounge", "www", "r", "public", "complex", "realtor"}
# 기본 제공 이미지(사용자가 직접 사진이 없을 때 골라 쓰는 선택지). 프런트 /presets/<name>.webp.
_PRESET_NAMES = {
    "apt": ["apt1", "apt2", "apt3", "apt4"],
    "rep": ["man1", "man2", "man3", "woman1", "woman2", "woman3"],
    "office": ["office1", "office2", "office3", "office4", "office5"],
}
_ALL_PRESETS = {k: set(v) for k, v in _PRESET_NAMES.items()}


def _photo_marker(v):
    """DB 저장값 → 프런트 마커: None / 'preset:<name>' / 'upload'."""
    if not v:
        return None
    return v if v.startswith("preset:") else "upload"


def _norm_slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = _re_lounge.sub(r"[^a-z0-9-]", "", s.replace(" ", "-"))
    s = _re_lounge.sub(r"-+", "-", s).strip("-")
    return s


_KOCZIP_TEST_LISTINGS = [   # 관리자 테스트용 데모 매물(실제 단지 연결)
    {"complex_no": "134062", "complex_name": "디에이치퍼스티어아이파크", "trade_type": "매매", "price": 4200000000, "excl_use_ar": 84, "area_name": "84A", "count": 3},
    {"complex_no": "128527", "complex_name": "개포자이프레지던스", "trade_type": "매매", "price": 3850000000, "excl_use_ar": 84, "area_name": "84B", "count": 2},
    {"complex_no": "11698", "complex_name": "도곡렉슬", "trade_type": "전세", "price": 1500000000, "excl_use_ar": 84, "area_name": "84", "count": 4},
    {"complex_no": "236", "complex_name": "은마", "trade_type": "매매", "price": 2950000000, "excl_use_ar": 84, "area_name": "84", "count": 5},
    {"complex_no": "105", "complex_name": "한보미도맨션1,2차", "trade_type": "전세", "price": 1100000000, "excl_use_ar": 84, "area_name": "84", "count": 2},
]


# 비단지 카테고리 → 별도 DB파일 (홈페이지 6구분 통합 노출용). 아파트/오피는 listings_current.
_REGION_DBS = {
    "상가": "listings_sangga.sqlite",
    "사무실": "listings_office.sqlite",
    "빌라/연립": "listings_villa.sqlite",
    "단독/다가구": "listings_house.sqlite",
}


def _homepage_listings(realtor_id: str, limit: int = 1000) -> list[dict]:
    """홈페이지 매물 — 우리 6구분(아파트·오피스텔·상가·사무실·빌라/연립·단독/다가구) 통합.
    아파트/오피=listings_current(단지기반), 나머지=비단지 4DB(realtor 귀속분만). 각 항목에 category."""
    if realtor_id == "koczip-test":
        return _KOCZIP_TEST_LISTINGS
    tt = {"A1": "매매", "B1": "전세", "B2": "월세"}
    items: list[dict] = []
    # 1) 아파트·오피스텔 (단지기반) — real_estate_type 으로 구분
    with _open_db() as c:
        rows = c.execute(
            "SELECT l.complex_no, cx.complex_name, l.trade_type, "
            "MIN(l.deal_or_warrant_price), l.area2_m2, l.area_name, COUNT(*), l.real_estate_type "
            "FROM listings_current l JOIN complexes cx ON cx.complex_no=l.complex_no "
            "WHERE l.realtor_id=? AND l.deal_or_warrant_price>0 "
            "GROUP BY l.complex_no, l.trade_type, ROUND(l.area2_m2) "
            "ORDER BY l.deal_or_warrant_price DESC LIMIT ?", (realtor_id, limit)).fetchall()
    for r in rows:
        cat = "오피스텔" if r[7] in ("OPST", "OBYG") else "아파트"
        items.append({"category": cat, "complex_no": r[0], "complex_name": r[1],
                      "trade_type": tt.get(r[2], r[2]), "price": r[3],
                      "excl_use_ar": round(r[4]) if r[4] else None,
                      "area_name": r[5], "count": r[6], "article_no": None})
    # 2) 비단지(상가·사무실·빌라/연립·단독/다가구) — realtor 귀속분만, 별도 DB(읽기전용)
    for cat, dbfile in _REGION_DBS.items():
        path = DB_PATH.parent / dbfile
        if not path.exists():
            continue
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as rc:
                rows = rc.execute(
                    "SELECT building_name, trade_type, MIN(deal_or_warrant_price), MIN(rent_price), "
                    "area1_m2, real_estate_type_name, COUNT(*), MIN(article_no) "
                    "FROM listings WHERE realtor_id=? AND deal_or_warrant_price>0 "
                    "GROUP BY COALESCE(building_name,''), trade_type, ROUND(area1_m2) "
                    "ORDER BY deal_or_warrant_price DESC LIMIT ?", (realtor_id, limit)).fetchall()
            for r in rows:
                items.append({"category": cat, "complex_no": None,
                              "complex_name": r[0] or r[5], "trade_type": tt.get(r[1], r[1]),
                              "price": r[2], "rent_price": r[3],
                              "excl_use_ar": round(r[4]) if r[4] else None,
                              "area_name": r[5], "count": r[6],
                              "article_no": r[7]})  # 네이버 딥링크용
        except Exception:
            continue
    return items


def _homepage_row(c, realtor_id):
    return c.execute(
        "SELECT realtor_id,slug,slogan,intro,specialties,biz_hours,kakao_url,consult_tel,"
        "map_memo,photo_apt,photo_rep,photo_office,published FROM realtor_homepages "
        "WHERE realtor_id=?", (realtor_id,)).fetchone()


def _homepage_dict(r) -> dict:
    return {"realtor_id": r[0], "slug": r[1], "slogan": r[2], "intro": r[3],
            "specialties": r[4], "biz_hours": r[5], "kakao_url": r[6], "consult_tel": r[7],
            "map_memo": r[8], "has_photo": {"apt": bool(r[9]), "rep": bool(r[10]),
            "office": bool(r[11])},
            "photos": {"apt": _photo_marker(r[9]), "rep": _photo_marker(r[10]),
                       "office": _photo_marker(r[11])},
            "published": bool(r[12])}


@app.get("/lounge/homepage")
def lounge_homepage_get(user: dict = Depends(current_user)):
    with _reviews_db() as c:
        rid = _require_member(c, user["id"])
        r = _homepage_row(c, rid)
    cfg = _homepage_dict(r) if r else {"realtor_id": rid, "published": False, "has_photo": {}}
    return {"config": cfg, "office": _office_brief(rid)}


@app.post("/lounge/homepage")
def lounge_homepage_save(body: dict, user: dict = Depends(current_user)):
    with _reviews_db() as c:
        rid = _require_member(c, user["id"])
        slug = _norm_slug(body.get("slug") or "")
        if slug:
            if len(slug) < 3 or len(slug) > 30 or slug in _SLUG_RESERVED:
                raise HTTPException(400, "주소는 3~30자 영문/숫자/-, 예약어 불가")
            dup = c.execute("SELECT realtor_id FROM realtor_homepages WHERE slug=? AND realtor_id<>?",
                            (slug, rid)).fetchone()
            if dup:
                raise HTTPException(409, "이미 사용 중인 주소입니다")
        def g(k, n=500):
            v = (body.get(k) or "").strip()
            return v[:n] or None
        c.execute(
            "INSERT INTO realtor_homepages(realtor_id,user_id,slug,slogan,intro,specialties,"
            "biz_hours,kakao_url,consult_tel,map_memo,published,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,datetime('now')) "
            "ON CONFLICT(realtor_id) DO UPDATE SET slug=excluded.slug,slogan=excluded.slogan,"
            "intro=excluded.intro,specialties=excluded.specialties,biz_hours=excluded.biz_hours,"
            "kakao_url=excluded.kakao_url,consult_tel=excluded.consult_tel,map_memo=excluded.map_memo,"
            "published=excluded.published,updated_at=datetime('now')",
            (rid, user["id"], slug or None, g("slogan", 120), g("intro", 2000),
             g("specialties", 200), g("biz_hours", 200), g("kakao_url", 500),
             g("consult_tel", 50), g("map_memo", 500), 1 if body.get("published") else 0))
        c.commit()
        r = _homepage_row(c, rid)
    return {"ok": True, "config": _homepage_dict(r)}


@app.delete("/lounge/homepage")
def lounge_homepage_delete(user: dict = Depends(current_user)):
    """홈페이지 영구 삭제 — 행 + 업로드 사진 파일 모두 제거(복원 불가). 이후 새로 제작 가능."""
    with _reviews_db() as c:
        rid = _require_member(c, user["id"])
        row = c.execute("SELECT photo_apt, photo_rep, photo_office FROM realtor_homepages "
                        "WHERE realtor_id=?", (rid,)).fetchone()
        c.execute("DELETE FROM realtor_homepages WHERE realtor_id=?", (rid,))
        c.commit()
    # 업로드 사진 파일 삭제(프리셋은 공용이라 건드리지 않음)
    for v in (row or []):
        if v and not v.startswith("preset:"):
            try:
                p = Path(v)
                if p.exists():
                    p.unlink()
            except OSError:
                pass
    return {"ok": True}


@app.get("/lounge/homepage/slug-check")
def lounge_slug_check(slug: str, user: dict = Depends(current_user)):
    s = _norm_slug(slug)
    if len(s) < 3 or len(s) > 30 or s in _SLUG_RESERVED:
        return {"slug": s, "available": False, "reason": "형식 오류 또는 예약어"}
    with _reviews_db() as c:
        rid = _require_member(c, user["id"])
        dup = c.execute("SELECT 1 FROM realtor_homepages WHERE slug=? AND realtor_id<>?",
                        (s, rid)).fetchone()
    return {"slug": s, "available": not dup}


@app.post("/lounge/homepage/photo")
async def lounge_homepage_photo(kind: str = Form(...), document: UploadFile = File(...),
                                user: dict = Depends(current_user)):
    if kind not in _PHOTO_KINDS:
        raise HTTPException(400, "kind must be apt|rep|office")
    data = await document.read()
    if len(data) > 8_000_000:
        raise HTTPException(400, "파일이 너무 큽니다(최대 8MB)")
    ext = Path(document.filename or "").suffix.lower() or ".jpg"
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(400, "지원 형식: png/jpg/webp")
    with _reviews_db() as c:
        rid = _require_member(c, user["id"])
        dest = HOMEPAGE_IMG_DIR / f"{rid}_{kind}{ext}"
        # 같은 kind 다른 확장자 잔존 제거
        for e in (".png", ".jpg", ".jpeg", ".webp"):
            p = HOMEPAGE_IMG_DIR / f"{rid}_{kind}{e}"
            if p.exists() and p != dest:
                try: p.unlink()
                except OSError: pass
        dest.write_bytes(data)
        c.execute(f"UPDATE realtor_homepages SET photo_{kind}=?, updated_at=datetime('now') "
                  f"WHERE realtor_id=?", (str(dest), rid))
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            c.execute(f"INSERT INTO realtor_homepages(realtor_id,user_id,photo_{kind}) VALUES(?,?,?)",
                      (rid, user["id"], str(dest)))
        c.commit()
    return {"ok": True, "kind": kind}


@app.get("/lounge/homepage/presets")
def lounge_homepage_presets(user: dict = Depends(current_user)):
    """기본 제공 이미지 목록(마법사에서 썸네일로 보고 고름)."""
    return {"presets": _PRESET_NAMES}


@app.post("/lounge/homepage/preset")
def lounge_homepage_preset(body: dict, user: dict = Depends(current_user)):
    """기본 이미지 선택(또는 해제). preset 비우면 해당 슬롯 비움."""
    kind = (body.get("kind") or "").strip()
    preset = (body.get("preset") or "").strip()
    if kind not in _PHOTO_KINDS:
        raise HTTPException(400, "bad kind")
    if preset and preset not in _ALL_PRESETS.get(kind, set()):
        raise HTTPException(400, "bad preset")
    val = f"preset:{preset}" if preset else None
    with _reviews_db() as c:
        rid = _require_member(c, user["id"])
        cur = c.execute(f"UPDATE realtor_homepages SET photo_{kind}=?, updated_at=datetime('now') "
                        f"WHERE realtor_id=?", (val, rid))
        if cur.rowcount == 0:
            c.execute(f"INSERT INTO realtor_homepages(realtor_id,user_id,photo_{kind}) VALUES(?,?,?)",
                      (rid, user["id"], val))
        c.commit()
    return {"ok": True}


@app.get("/lounge/homepage/preview")
def lounge_homepage_preview(user: dict = Depends(current_user)):
    """본인 홈페이지 미리보기 데이터 — 게시 전(draft)에도 소유자는 볼 수 있다."""
    with _reviews_db() as c:
        rid = _require_member(c, user["id"])
        r = _homepage_row(c, rid)
    cfg = _homepage_dict(r) if r else {"realtor_id": rid, "slug": None, "published": False,
                                       "has_photo": {}, "photos": {}}
    return {"config": cfg, "office": _office_brief(rid), "listings": _homepage_listings(rid),
            "preview": True}


@app.get("/public/homepage/{slug}")
def public_homepage(slug: str):
    """공개 홈페이지 렌더 데이터(사무소 정보 + 매물 + 설정). 인증 불필요."""
    s = _norm_slug(slug)
    with _reviews_db() as c:
        r = c.execute(
            "SELECT realtor_id,slug,slogan,intro,specialties,biz_hours,kakao_url,consult_tel,"
            "map_memo,photo_apt,photo_rep,photo_office,published FROM realtor_homepages "
            "WHERE slug=?", (s,)).fetchone()
    if not r or not r[12]:
        raise HTTPException(404, "홈페이지를 찾을 수 없습니다")
    cfg = _homepage_dict(r)
    return {"config": cfg, "office": _office_brief(r[0]),
            "listings": _homepage_listings(r[0])}


@app.get("/public/homepage/{slug}/photo/{kind}")
def public_homepage_photo(slug: str, kind: str):
    if kind not in _PHOTO_KINDS:
        raise HTTPException(404, "없음")
    s = _norm_slug(slug)
    with _reviews_db() as c:
        # 사진은 비밀이 아니므로 게시 전(draft)도 서브 → 미리보기에서 업로드 사진이 보인다.
        r = c.execute(f"SELECT photo_{kind} FROM realtor_homepages WHERE slug=?", (s,)).fetchone()
    if not r or not r[0] or not Path(r[0]).exists():
        raise HTTPException(404, "사진 없음")
    ext = Path(r[0]).suffix.lower()
    mt = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
          ".webp": "image/webp"}.get(ext, "image/jpeg")
    return Response(content=Path(r[0]).read_bytes(), media_type=mt,
                    headers={"Cache-Control": "public, max-age=300"})


PRESET_DIR: Path = DB_PATH.parent / "presets"
_NANUM_B = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
_NANUM_R = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"


def _og_font(size: int, bold: bool = True):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(_NANUM_B if bold else _NANUM_R, size)
    except Exception:
        return ImageFont.load_default()


def _photo_path(marker: str | None, kind: str) -> str | None:
    if not marker:
        return None
    if marker.startswith("preset:"):
        return str(PRESET_DIR / f"{marker[7:]}.webp")
    return marker  # 업로드 파일 절대경로


def _circle_photo(path: str | None, size: int):
    from PIL import Image, ImageDraw
    if not path or not Path(path).exists():
        return None
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    w, h = im.size
    sq = min(w, h)
    im = im.crop(((w - sq) // 2, (h - sq) // 2, (w - sq) // 2 + sq, (h - sq) // 2 + sq)).resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def _cover_photo(path: str | None, tw: int, th: int):
    """대상 크기(tw×th)를 꽉 채우도록 비율유지 리사이즈 후 중앙 크롭(object-fit:cover)."""
    from PIL import Image
    if not path or not Path(path).exists():
        return None
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    w, h = im.size
    scale = max(tw / w, th / h)
    nw, nh = max(tw, int(w * scale + 0.5)), max(th, int(h * scale + 0.5))
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return im.crop((left, top, left + tw, top + th))


def _fit_og(path: str):
    """올린 명함 이미지를 1200×630 OG 캔버스에 비율유지로 담는다(레터박스, 내용 안 잘림)."""
    from PIL import Image
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    W, H = 1200, 630
    canvas = Image.new("RGB", (W, H), (244, 246, 249))
    im.thumbnail((W, H), Image.LANCZOS)
    canvas.paste(im, ((W - im.size[0]) // 2, (H - im.size[1]) // 2))
    return canvas


def _trunc(draw, text, font, maxw):
    if draw.textlength(text, font=font) <= maxw:
        return text
    while text and draw.textlength(text + "…", font=font) > maxw:
        text = text[:-1]
    return text + "…"


@app.get("/public/homepage/{slug}/og.png")
def public_homepage_og(slug: str):
    """홈페이지 공유용 OG 명함 카드(중개사 인적사항 명함 + 콕집 작게). 개별 생성."""
    from PIL import Image, ImageDraw
    import io
    s = _norm_slug(slug)
    with _reviews_db() as c:
        r = c.execute("SELECT realtor_id,slogan,consult_tel,photo_rep,photo_apt "
                      "FROM realtor_homepages WHERE slug=? AND published=1", (s,)).fetchone()
    if not r:
        raise HTTPException(404, "없음")
    # 명함(apt 슬롯)을 직접 올렸으면 그 명함을 공유 카드(OG)로 사용. 없으면 아래서 생성.
    card_m = r[4]
    if card_m and not card_m.startswith("preset:"):
        cp = _photo_path(card_m, "apt")
        if cp and Path(cp).exists():
            fit = _fit_og(cp)
            if fit:
                buf = io.BytesIO(); fit.save(buf, "PNG")
                return Response(content=buf.getvalue(), media_type="image/png",
                                headers={"Cache-Control": "public, max-age=600"})
    o = _office_brief(r[0])
    name = o.get("realtor_name") or "공인중개사무소"
    rep, slogan, addr = o.get("representative"), r[1], (o.get("address") or "")
    tel = r[2] or o.get("tel") or o.get("cell") or ""

    W, H, PW = 1200, 630, 468
    NAVY, GRAY, BLUE = (19, 41, 75), (96, 106, 122), (18, 104, 211)
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)

    # 좌측 대표 사진(풀블리드) — 동그라미 대신 패널 전체를 채워 에디토리얼/명함 느낌
    photo = _cover_photo(_photo_path(r[3], "rep"), PW, H)
    if photo:
        img.paste(photo, (0, 0))
        grad = Image.new("RGBA", (PW, 150), (0, 0, 0, 0))
        gdr = ImageDraw.Draw(grad)
        for i in range(150):
            gdr.line([(0, i), (PW, i)], fill=(12, 22, 42, int(165 * (i / 150) ** 1.5)))
        img.paste(grad, (0, H - 150), grad)
        d.text((36, H - 50), "powered by 콕집", font=_og_font(25, False), fill=(238, 242, 248))
    else:
        d.rectangle((0, 0, PW, H), fill=NAVY)
        d.text((PW // 2, H // 2 - 16), (name[:1] or "콕"), font=_og_font(150), fill=(255, 255, 255), anchor="mm")
        d.text((PW // 2, H - 50), "powered by 콕집", font=_og_font(25, False), fill=(190, 205, 228), anchor="mm")

    # 우측 텍스트(흰 패널)
    x, rw = PW + 54, W - (PW + 54) - 56
    d.text((x, 120), _trunc(d, name, _og_font(54), rw), font=_og_font(54), fill=NAVY)
    d.rectangle((x, 200, x + 66, 206), fill=BLUE)   # 강조 라인
    y = 240
    if rep:
        d.text((x, y), f"대표  {rep}", font=_og_font(33, False), fill=(55, 65, 82)); y += 62
    if slogan:
        d.text((x, y), _trunc(d, slogan, _og_font(29, False), rw), font=_og_font(29, False), fill=GRAY); y += 64
    y += 6
    d.line((x, y, x + rw, y), fill=(228, 232, 238), width=2); y += 30
    if tel:
        d.text((x, y), f"전화   {tel}", font=_og_font(37), fill=BLUE); y += 58
    if addr:
        d.text((x, y), _trunc(d, addr, _og_font(25, False), rw), font=_og_font(25, False), fill=GRAY)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=600"})


@app.post("/public/homepage/{slug}/lead")
def public_homepage_lead(slug: str, body: dict):
    """홈페이지 상담신청 → consultation_leads(중개사 라운지·관리자에서 확인). 인증 불필요."""
    s = _norm_slug(slug)
    name = (body.get("name") or "").strip()[:50]
    phone = (body.get("phone") or "").strip()[:30]
    message = (body.get("message") or "").strip()[:1000]
    if not (phone or name):
        raise HTTPException(400, "이름 또는 연락처를 입력해주세요")
    with _reviews_db() as c:
        r = c.execute("SELECT realtor_id FROM realtor_homepages WHERE slug=? AND published=1",
                      (s,)).fetchone()
        if not r:
            raise HTTPException(404, "홈페이지 없음")
        c.execute("INSERT INTO consultation_leads(realtor_id,name,phone,message,source) "
                  "VALUES(?,?,?,?,?)", (r[0], name or None, phone or None, message or None, "homepage"))
        c.commit()
        # 상담신청 즉시 알림 — 이 사무소에 연결된 계정(들)에 푸시
        owner_ids = [m[0] for m in c.execute(
            "SELECT user_id FROM realtor_members WHERE realtor_id=?", (r[0],)).fetchall()]
    if owner_ids:
        who = name or phone or "고객"
        try:
            _send_web_push(owner_ids, "새 상담 신청 📩",
                           f"{who}님이 상담을 신청했어요. 라운지에서 확인하세요.",
                           url="/lounge", tag="lead")
        except Exception:
            pass
    return {"ok": True}


# ── 관리자: 정보수정요청 · 중개사 서류인증 ──────────────────────
@app.get("/admin/realtor-edit-requests")
def admin_realtor_edit_requests(status: str = "pending", _admin: dict = Depends(admin_user)):
    with _reviews_db() as c:
        rows = c.execute(
            "SELECT id,user_id,realtor_id,member_no,content,status,admin_note,created_at,resolved_at "
            "FROM realtor_edit_requests WHERE (?='' OR status=?) ORDER BY id DESC LIMIT 300",
            (status, status)).fetchall()
    items = []
    for r in rows:
        items.append({"id": r[0], "user_id": r[1], "realtor_id": r[2], "member_no": r[3],
                      "content": r[4], "status": r[5], "admin_note": r[6],
                      "created_at": r[7], "resolved_at": r[8],
                      "office": _office_brief(r[2])})
    return {"items": items}


@app.post("/admin/realtor-edit-requests/{req_id}")
def admin_resolve_edit_request(req_id: int, body: dict, _admin: dict = Depends(admin_user)):
    st = (body.get("status") or "").strip()
    if st not in ("pending", "done", "rejected"):
        raise HTTPException(400, "bad status")
    with _reviews_db() as c:
        c.execute("UPDATE realtor_edit_requests SET status=?, admin_note=?, "
                  "resolved_at=CASE WHEN ?='pending' THEN NULL ELSE datetime('now') END "
                  "WHERE id=?", (st, (body.get("admin_note") or None), st, req_id))
        c.commit()
    return {"ok": True}


@app.get("/admin/realtor-verifications")
def admin_realtor_verifications(status: str = "pending", _admin: dict = Depends(admin_user)):
    with _reviews_db() as c:
        rows = c.execute(
            "SELECT id,user_id,realtor_id,claimed_name,doc_path,status,admin_note,created_at,reviewed_at "
            "FROM realtor_verifications WHERE (?='' OR status=?) ORDER BY id DESC LIMIT 200",
            (status, status)).fetchall()
    return {"items": [{"id": r[0], "user_id": r[1], "realtor_id": r[2], "claimed_name": r[3],
                       "has_doc": bool(r[4]), "status": r[5], "admin_note": r[6],
                       "created_at": r[7], "reviewed_at": r[8]} for r in rows]}


@app.get("/admin/realtor-verifications/{vid}/document")
def admin_realtor_verification_doc(vid: int, _admin: dict = Depends(admin_user)):
    with _reviews_db() as c:
        r = c.execute("SELECT doc_path FROM realtor_verifications WHERE id=?", (vid,)).fetchone()
    if not r or not r[0] or not Path(r[0]).exists():
        raise HTTPException(404, "문서 없음")
    ext = Path(r[0]).suffix.lower()
    mt = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
          ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "application/octet-stream")
    return Response(content=Path(r[0]).read_bytes(), media_type=mt)


@app.post("/admin/realtor-verifications/{vid}")
def admin_resolve_verification(vid: int, body: dict, _admin: dict = Depends(admin_user)):
    """승인 시 해당 user를 realtor_id에 연동(method='doc')."""
    action = (body.get("action") or "").strip()   # approve | reject
    note = body.get("admin_note") or None
    with _reviews_db() as c:
        r = c.execute("SELECT user_id, realtor_id, status FROM realtor_verifications WHERE id=?",
                      (vid,)).fetchone()
        if not r:
            raise HTTPException(404, "없음")
        uid, rid = r[0], (body.get("realtor_id") or r[1])
        if action == "approve":
            if not rid:
                raise HTTPException(400, "연동할 realtor_id가 필요합니다")
            c.execute(
                "INSERT INTO realtor_members(user_id,realtor_id,method,updated_at) "
                "VALUES(?,?,?,datetime('now')) "
                "ON CONFLICT(user_id) DO UPDATE SET realtor_id=excluded.realtor_id, "
                "method='doc', updated_at=datetime('now')", (uid, rid, "doc"))
            c.execute("UPDATE realtor_verifications SET status='approved', realtor_id=?, "
                      "admin_note=?, reviewed_at=datetime('now') WHERE id=?", (rid, note, vid))
        elif action == "reject":
            c.execute("UPDATE realtor_verifications SET status='rejected', admin_note=?, "
                      "reviewed_at=datetime('now') WHERE id=?", (note, vid))
        else:
            raise HTTPException(400, "action must be approve|reject")
        c.commit()
    return {"ok": True}


@app.get("/me/points")
def my_points(user: dict = Depends(current_user)) -> dict:
    """내 포인트 잔액·계급·최근 내역 + 계급표."""
    with _reviews_db() as c:
        bal, earned = _user_points(c, user["id"])
        led = [{"delta": r[0], "reason": r[1], "reason_kr": REASON_KR.get(r[1], r[1]),
                "ref": r[2], "balance_after": r[3], "created_at": r[4]}
               for r in c.execute(
                   "SELECT delta, reason, ref, balance_after, created_at FROM point_ledger "
                   "WHERE user_id=? ORDER BY id DESC LIMIT 50", (user["id"],)).fetchall()]
    return {"points": bal, "earned": earned, "ai_cost": AI_COST, **_rank_for(earned),
            "ranks": [{"at": th, "name": nm, "emoji": em} for th, nm, em in RANKS], "ledger": led}


def _has_resident(c: sqlite3.Connection, user_id: str, complex_no: str) -> bool:
    return bool(c.execute(
        "SELECT 1 FROM resident_verifications WHERE user_id=? AND complex_no=? "
        "AND status='approved' LIMIT 1", (user_id, complex_no)).fetchone())


@app.get("/complex/{complex_no}/reviews")
def complex_reviews_list(complex_no: str) -> dict:
    """단지 리뷰 목록 + 요약(평점·건수·입주민 인증 수)."""
    with _reviews_db() as c:
        rows = [{"id": r[0], "user_id": r[1], "author_name": r[2], "rating": r[3],
                 "body": r[4], "resident": bool(r[5]), "created_at": r[6]}
                for r in c.execute(
                    "SELECT id, user_id, author_name, rating, body, resident, created_at "
                    "FROM complex_reviews WHERE complex_no=? AND status='published' "
                    "ORDER BY id DESC LIMIT 200", (complex_no,)).fetchall()]
        nmap = _nick_map(c, [r["user_id"] for r in rows])
    for r in rows:
        # 작성자 표기는 항상 현재 별명. 실명·이메일·회원번호 등은 타인에게 노출 안 함.
        r["author_name"] = nmap.get(r["user_id"]) or r["author_name"] or "회원"
        r["is_admin"] = _is_admin_uid(r["user_id"])
        del r["user_id"]
    n = len(rows)
    avg = round(sum(r["rating"] or 0 for r in rows) / n, 1) if n else None
    return {"count": n, "avg_rating": avg,
            "resident_count": sum(1 for r in rows if r["resident"]), "items": rows}


class ComplexReviewBody(BaseModel):
    rating: int
    body: str


@app.post("/complex/{complex_no}/reviews")
def complex_review_create(complex_no: str, body: ComplexReviewBody,
                          user: dict = Depends(current_user)) -> dict:
    """단지 리뷰 작성(로그인 필수, 단지당 1건). 작성 시 포인트 적립. 입주민이면 뱃지."""
    if not (1 <= body.rating <= 5):
        raise HTTPException(400, "별점은 1~5점입니다")
    text = (body.body or "").strip()
    if len(text) < 5 or len(text) > 2000:
        raise HTTPException(400, "리뷰는 5~2000자로 작성해주세요")
    with _reviews_db() as c:
        nick = _require_nickname(c, user["id"])   # 닉네임으로 작성
        _enforce_hourly(c, "complex_reviews", "user_id", user["id"])  # 시간당 30건 한도
        resident = 1 if _has_resident(c, user["id"], complex_no) else 0
        c.execute("INSERT INTO complex_reviews(complex_no,user_id,author_name,rating,body,resident) "
                  "VALUES(?,?,?,?,?,?)",
                  (complex_no, user["id"], nick, body.rating, text, resident))
        new_bal = _award_points(c, user["id"], "review", ref=f"complex:{complex_no}")
        c.commit()
    return {"ok": True, "points": new_bal, "resident": bool(resident),
            "awarded": POINTS["review"]}


@app.post("/complex/{complex_no}/resident-verify")
async def resident_verify_submit(complex_no: str, document: UploadFile = File(...),
                                 user: dict = Depends(current_user)) -> dict:
    """입주민 인증 서류 제출 → 관리자 승인 대기. 관리비/등기/전입 등 거주 증빙."""
    ext = Path(document.filename or "").suffix.lower()
    if ext not in _REVIEW_DOC_EXTS:
        raise HTTPException(400, f"허용 형식: {', '.join(sorted(_REVIEW_DOC_EXTS))}")
    data = await document.read()
    if len(data) > _REVIEW_DOC_MAX_BYTES:
        raise HTTPException(400, "파일이 너무 큽니다 (최대 10MB)")
    if not data:
        raise HTTPException(400, "빈 파일입니다")
    with _reviews_db() as c:
        last = c.execute("SELECT status FROM resident_verifications WHERE user_id=? AND complex_no=? "
                         "ORDER BY id DESC LIMIT 1", (user["id"], complex_no)).fetchone()
        if last and last[0] == "approved":
            raise HTTPException(409, "이미 입주민 인증된 단지예요")
        if last and last[0] == "pending":
            raise HTTPException(409, "이미 심사 중인 인증이 있어요")
        rid = c.execute("INSERT INTO resident_verifications(user_id,complex_no,doc_name) "
                        "VALUES(?,?,?)", (user["id"], complex_no, document.filename)).lastrowid
        p = REVIEW_DOCS_DIR / f"resident_{rid}{ext}"
        p.write_bytes(data)
        c.execute("UPDATE resident_verifications SET doc_path=? WHERE id=?", (str(p), rid))
        c.commit()
    return {"ok": True, "id": rid, "status": "pending"}


@app.get("/me/resident")
def my_resident(user: dict = Depends(current_user)) -> dict:
    """내 입주민 인증 현황(단지별 상태)."""
    with _reviews_db() as c:
        rows = [{"complex_no": r[0], "status": r[1], "created_at": r[2]} for r in c.execute(
            "SELECT complex_no, status, created_at FROM resident_verifications "
            "WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()]
    return {"items": rows}


@app.get("/admin/resident-verifications")
def admin_resident_list(_admin: dict = Depends(admin_user)) -> dict:
    """입주민 인증 검수 대기 목록. 관리자 전용."""
    with _reviews_db() as c:
        rows = [{"id": r[0], "user_id": r[1], "complex_no": r[2], "doc_name": r[3],
                 "created_at": r[4], "member_no": r[5]}
                for r in c.execute(
                    "SELECT rv.id, rv.user_id, rv.complex_no, rv.doc_name, rv.created_at, up.member_no "
                    "FROM resident_verifications rv LEFT JOIN user_profiles up ON up.user_id=rv.user_id "
                    "WHERE rv.status='pending' ORDER BY rv.id").fetchall()]
    # 단지명 매핑(naverreal.sqlite)
    cnos = list({r["complex_no"] for r in rows})
    if cnos:
        with _open_db() as c2:
            ph = ",".join("?" * len(cnos))
            nm = {x[0]: x[1] for x in c2.execute(
                f"SELECT complex_no, complex_name FROM complexes WHERE complex_no IN ({ph})", cnos)}
        for r in rows:
            r["complex_name"] = nm.get(r["complex_no"])
    return {"count": len(rows), "items": rows}


@app.get("/admin/resident-verifications/{rid}/doc")
def admin_resident_doc(rid: int, _admin: dict = Depends(admin_user)):
    """검수용 서류 원본 보기. 관리자 전용."""
    from fastapi.responses import FileResponse
    with _reviews_db() as c:
        row = c.execute("SELECT doc_path FROM resident_verifications WHERE id=?", (rid,)).fetchone()
    if not row or not row[0] or not Path(row[0]).exists():
        raise HTTPException(404, "서류 없음")
    return FileResponse(row[0])


@app.post("/admin/resident-verifications/{rid}/approve")
def admin_resident_approve(rid: int, _admin: dict = Depends(admin_user)) -> dict:
    """입주민 인증 승인 → 사용자 입주민 뱃지 + 포인트. 서류 폐기."""
    with _reviews_db() as c:
        row = c.execute("SELECT user_id, complex_no, doc_path, status FROM resident_verifications "
                        "WHERE id=?", (rid,)).fetchone()
        if not row or row[3] != "pending":
            raise HTTPException(404, "심사 대기중인 인증이 아닙니다")
        if row[2] and Path(row[2]).exists():
            try: Path(row[2]).unlink()
            except OSError: pass
        c.execute("UPDATE resident_verifications SET status='approved', doc_path=NULL, "
                  "decided_at=datetime('now') WHERE id=?", (rid,))
        _award_points(c, row[0], "resident", ref=f"complex:{row[1]}")
        c.commit()
    return {"ok": True, "status": "approved"}


@app.post("/admin/resident-verifications/{rid}/reject")
def admin_resident_reject(rid: int, _admin: dict = Depends(admin_user)) -> dict:
    """입주민 인증 거부. 서류 폐기."""
    with _reviews_db() as c:
        row = c.execute("SELECT doc_path, status FROM resident_verifications WHERE id=?", (rid,)).fetchone()
        if not row or row[1] != "pending":
            raise HTTPException(404, "심사 대기중인 인증이 아닙니다")
        if row[0] and Path(row[0]).exists():
            try: Path(row[0]).unlink()
            except OSError: pass
        c.execute("UPDATE resident_verifications SET status='rejected', doc_path=NULL, "
                  "decided_at=datetime('now') WHERE id=?", (rid,))
        c.commit()
    return {"ok": True, "status": "rejected"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
