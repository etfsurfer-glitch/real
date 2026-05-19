"""Local-only admin UI for inspecting transaction matches.

Read-only v1: filter by method, search by 단지/동, click a row to see the
match_details JSON (candidates + reasons). Phase 2 will add manual
override + re-match.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from ..config import settings

app = FastAPI(title="naverreal admin")


def get_db():
    """Read-only connection per request — avoids threadpool contention."""
    c = sqlite3.connect(str(settings.local_db_path), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA query_only=1")
    try:
        yield c
    finally:
        c.close()


def get_write_db():
    """Read-write connection for admin actions (accept/reject suggestions)."""
    c = sqlite3.connect(str(settings.local_db_path), check_same_thread=False,
                        timeout=30)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


@app.get("/api/stats")
def api_stats(c: sqlite3.Connection = Depends(get_db)) -> dict:
    total = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    by_method = [
        {"method": r[0] or "unmatched", "count": r[1]}
        for r in c.execute(
            "SELECT matched_method, COUNT(*) FROM transactions "
            "GROUP BY matched_method ORDER BY COUNT(*) DESC"
        ).fetchall()
    ]
    rng = c.execute("SELECT MIN(deal_ymd), MAX(deal_ymd) FROM transactions").fetchone()
    return {
        "total": total,
        "by_method": by_method,
        "date_min": rng[0],
        "date_max": rng[1],
    }


@app.get("/api/transactions")
def api_transactions(
    method: str | None = Query(None),
    q: str | None = Query(None, description="단지명 또는 동 검색"),
    sgg: str | None = Query(None, description="시군구 5자리"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    order: str = Query("recent", pattern="^(recent|price_desc|price_asc)$"),
    c: sqlite3.Connection = Depends(get_db),
) -> dict:
    where: list[str] = []
    params: list[Any] = []
    if method:
        if method == "unmatched":
            where.append("(matched_method IS NULL OR matched_method = 'unmatched')")
        else:
            where.append("matched_method = ?")
            params.append(method)
    if q:
        where.append("(apt_nm LIKE ? OR umd_nm LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if sgg:
        where.append("sgg_cd = ?")
        params.append(sgg)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    order_sql = {
        "recent": "ORDER BY deal_ymd DESC, deal_id",
        "price_desc": "ORDER BY deal_amount DESC",
        "price_asc": "ORDER BY deal_amount ASC",
    }[order]

    total = c.execute(f"SELECT COUNT(*) FROM transactions{where_sql}", params).fetchone()[0]
    sql = f"""
        SELECT t.deal_id, t.deal_ymd, t.sgg_cd, t.umd_nm, t.apt_nm, t.jibun,
               t.excl_use_ar, t.floor, t.deal_amount, t.dealing_gbn,
               t.matched_complex_no, t.matched_method, t.matched_score,
               x.complex_name AS matched_complex_name,
               r.cortar_name AS matched_dong
        FROM transactions t
        LEFT JOIN complexes x ON x.complex_no = t.matched_complex_no
        LEFT JOIN regions r ON r.cortar_no = x.cortar_no
        {where_sql}
        {order_sql} LIMIT ? OFFSET ?
    """
    rows = [dict(r) for r in c.execute(sql, params + [limit, offset]).fetchall()]
    return {"total": total, "limit": limit, "offset": offset, "rows": rows}


@app.get("/api/suggestions")
def api_suggestions(
    status: str = Query("pending", pattern="^(pending|accepted|rejected|all)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    c: sqlite3.Connection = Depends(get_db),
) -> dict:
    where = ""
    params: list = []
    if status != "all":
        where = "WHERE s.status = ?"
        params.append(status)
    total = c.execute(
        f"SELECT COUNT(*) FROM match_suggestions s {where}", params
    ).fetchone()[0]
    rows = c.execute(
        f"""
        SELECT s.suggestion_id, s.apt_nm, s.sgg_cd, s.umd_nm, s.tx_count,
               s.suggested_complex_no, s.suggested_method, s.suggested_score,
               s.details, s.status, s.reviewed_at, s.created_at,
               x.complex_name AS suggested_complex_name,
               x.detail_address AS suggested_address,
               r.cortar_name AS suggested_dong
        FROM match_suggestions s
        LEFT JOIN complexes x ON x.complex_no = s.suggested_complex_no
        LEFT JOIN regions r ON r.cortar_no = x.cortar_no
        {where}
        ORDER BY s.tx_count DESC, s.suggestion_id
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("details"):
            try:
                d["details"] = json.loads(d["details"])
            except Exception:  # noqa: BLE001
                pass
        out.append(d)
    # status counts (always, for tab badges)
    counts = {
        row[0]: row[1]
        for row in c.execute(
            "SELECT status, COUNT(*) FROM match_suggestions GROUP BY status"
        ).fetchall()
    }
    return {"total": total, "rows": out, "counts": counts}


@app.post("/api/suggestions/{sid}/accept")
def api_accept(sid: int, c: sqlite3.Connection = Depends(get_write_db)) -> dict:
    from ..realprice.storage import accept_suggestion
    n = accept_suggestion(c, sid)
    return {"updated_tx": n}


@app.post("/api/suggestions/{sid}/reject")
def api_reject(sid: int, c: sqlite3.Connection = Depends(get_write_db)) -> dict:
    from ..realprice.storage import reject_suggestion
    return {"ok": reject_suggestion(c, sid)}


@app.post("/api/suggestions/{sid}/reset")
def api_reset(sid: int, c: sqlite3.Connection = Depends(get_write_db)) -> dict:
    from ..realprice.storage import reset_suggestion
    return {"ok": reset_suggestion(c, sid)}


@app.get("/api/transactions/{deal_id}")
def api_transaction_detail(deal_id: str, c: sqlite3.Connection = Depends(get_db)) -> dict:
    r = c.execute(
        """
        SELECT t.*, x.complex_name AS matched_complex_name,
               r.cortar_name AS matched_dong
        FROM transactions t
        LEFT JOIN complexes x ON x.complex_no = t.matched_complex_no
        LEFT JOIN regions r ON r.cortar_no = x.cortar_no
        WHERE t.deal_id = ?
        """,
        (deal_id,),
    ).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="not found")
    d = dict(r)
    # Parse JSON fields for easier consumption client-side
    for k in ("match_details", "raw"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except Exception:  # noqa: BLE001
                pass
    return d


_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>naverreal admin — matching</title>
<style>
  :root { font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif; }
  body { margin: 0; color: #1a1a1a; background: #fafafa; }
  header { position: sticky; top: 0; background: white; border-bottom: 1px solid #ddd;
    padding: 12px 20px; z-index: 10; }
  h1 { margin: 0; font-size: 16px; }
  .stats { font-size: 12px; color: #777; margin-top: 4px; }
  .layout { display: grid; grid-template-columns: 1fr 480px; min-height: calc(100vh - 60px); }
  .left { overflow-y: auto; padding: 16px; }
  .right { background: #fff; border-left: 1px solid #ddd; overflow-y: auto; padding: 16px; }
  .filters { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
  .chip { padding: 4px 10px; border: 1px solid #ccc; border-radius: 14px; background: white;
    cursor: pointer; font-size: 12px; }
  .chip.active { background: #1268d3; color: white; border-color: #1268d3; }
  input[type="text"] { padding: 5px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
  table { width: 100%; border-collapse: collapse; background: white; font-size: 13px;
    border: 1px solid #e0e0e0; border-radius: 4px; }
  th, td { padding: 6px 10px; border-bottom: 1px solid #f0f0f0; text-align: left; }
  th { background: #f5f5f5; font-weight: 600; font-size: 12px; color: #333; }
  tr { cursor: pointer; }
  tr:hover td { background: #eef5ff; }
  tr.selected td { background: #d5e8ff; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 11px;
    font-weight: 600; }
  .b-jibun { background: #d0eed0; color: #074d07; }
  .b-exact { background: #d8e8ff; color: #0a3a80; }
  .b-substr { background: #fff3b0; color: #6a4d00; }
  .b-fuzzy { background: #ffe0b0; color: #803000; }
  .b-unmatched { background: #ffd0d0; color: #800000; }
  .b-naver { background: #e8d8ff; color: #4a1080; }
  .muted { color: #888; }
  nav.tabs { display: flex; gap: 4px; margin-bottom: 12px; }
  nav.tabs button { padding: 6px 14px; border: 1px solid #ccc; border-radius: 4px 4px 0 0;
    background: #f5f5f5; cursor: pointer; font-size: 13px; }
  nav.tabs button.active { background: white; border-bottom-color: white; font-weight: 600; }
  .btn-accept { padding: 3px 10px; border: 1px solid #2e8b57; border-radius: 3px;
    background: #2e8b57; color: white; cursor: pointer; font-size: 11px; margin-right: 3px; }
  .btn-reject { padding: 3px 10px; border: 1px solid #c0392b; border-radius: 3px;
    background: white; color: #c0392b; cursor: pointer; font-size: 11px; margin-right: 3px; }
  .btn-reset { padding: 3px 10px; border: 1px solid #888; border-radius: 3px;
    background: white; color: #555; cursor: pointer; font-size: 11px; }
  tr.processed td { opacity: 0.5; }
  .pager { margin-top: 12px; display: flex; gap: 8px; align-items: center; font-size: 13px; }
  .pager button { padding: 4px 10px; border: 1px solid #ccc; border-radius: 4px;
    background: white; cursor: pointer; }
  .pager button:disabled { opacity: 0.4; cursor: default; }
  pre { background: #f7f7f7; padding: 8px; border-radius: 4px; overflow-x: auto; font-size: 11px;
    white-space: pre-wrap; word-break: break-all; }
  .candidate { background: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 4px;
    padding: 8px; margin-bottom: 6px; font-size: 12px; }
  .candidate .score { float: right; color: #555; font-variant-numeric: tabular-nums; }
  .candidate.chosen { border-color: #1268d3; background: #f0f8ff; }
  .kv { display: grid; grid-template-columns: 100px 1fr; gap: 4px; font-size: 12px; }
  .kv .k { color: #777; }
</style>
</head>
<body>
<header>
  <h1>naverreal admin · 실거래 매칭 검토</h1>
  <div class="stats" id="stats">loading...</div>
  <nav class="tabs">
    <button id="tab-tx" class="active" onclick="switchTab('tx')">거래</button>
    <button id="tab-sug" onclick="switchTab('sug')">의심 매칭 <span id="sug-badge"></span></button>
  </nav>
</header>

<!-- TAB: TRANSACTIONS -->
<div id="view-tx" class="layout">
  <div class="left">
    <div class="filters" id="method-chips"></div>
    <div class="filters">
      <input type="text" id="search" placeholder="단지명/동 검색" style="flex:1">
      <input type="text" id="sgg" placeholder="시군구 5자리" style="width:120px">
      <button onclick="reload()">검색</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>날짜</th><th>단지명 (거래)</th><th>동</th><th>지번</th>
          <th class="num">전용</th><th class="num">층</th><th class="num">가격</th>
          <th>방법</th><th>매칭 단지</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="pager">
      <button id="prev" onclick="page(-1)">‹</button>
      <span id="page-info"></span>
      <button id="next" onclick="page(1)">›</button>
    </div>
  </div>
  <div class="right" id="detail">
    <div class="muted">왼쪽 표에서 행을 선택하세요.</div>
  </div>
</div>

<!-- TAB: SUGGESTIONS -->
<div id="view-sug" style="display:none; padding: 16px;">
  <div class="filters" id="sug-chips"></div>
  <div class="muted" style="margin-bottom: 10px;">
    낮은 confidence(0.75) 의심 매칭. 확인 후 Accept / Reject. Accept하면 해당 거래 묶음의 매칭이 업데이트됩니다.
  </div>
  <table>
    <thead>
      <tr>
        <th>거래 단지명 (raw)</th>
        <th>시군구</th>
        <th>제안 단지</th>
        <th>지번</th>
        <th>동</th>
        <th>방법</th>
        <th class="num">score</th>
        <th class="num">tx</th>
        <th>액션</th>
      </tr>
    </thead>
    <tbody id="sug-tbody"></tbody>
  </table>
  <div class="pager">
    <button id="sug-prev" onclick="sugPage(-1)">‹</button>
    <span id="sug-page-info"></span>
    <button id="sug-next" onclick="sugPage(1)">›</button>
  </div>
</div>
<script>
let state = { method: null, q: '', sgg: '', offset: 0, limit: 50, total: 0, rows: [], selected: null };

function won(n) {
  if (!n) return '-';
  if (n >= 1e8) {
    const eok = Math.floor(n / 1e8);
    const man = Math.floor((n % 1e8) / 1e4);
    return man > 0 ? `${eok}억${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.floor(n / 1e4).toLocaleString()}만`;
}
function methodBadge(m) {
  if (!m || m === 'unmatched') return '<span class="badge b-unmatched">unmatched</span>';
  if (m.startsWith('jibun')) return `<span class="badge b-jibun">${m}</span>`;
  if (m.startsWith('exact')) return `<span class="badge b-exact">${m}</span>`;
  if (m.startsWith('substr')) return `<span class="badge b-substr">${m}</span>`;
  if (m.startsWith('fuzzy')) return `<span class="badge b-fuzzy">${m}</span>`;
  return `<span class="badge">${m}</span>`;
}

async function loadStats() {
  const r = await fetch('/api/stats').then(r => r.json());
  document.getElementById('stats').textContent =
    `${r.total.toLocaleString()} 건 · ${r.date_min} ~ ${r.date_max}`;
  const chips = document.getElementById('method-chips');
  chips.innerHTML = '';
  const all = document.createElement('span'); all.className = 'chip' + (state.method ? '' : ' active');
  all.textContent = `전체 (${r.total.toLocaleString()})`;
  all.onclick = () => { state.method = null; state.offset = 0; reload(); };
  chips.appendChild(all);
  for (const m of r.by_method) {
    const c = document.createElement('span');
    c.className = 'chip' + (state.method === m.method ? ' active' : '');
    c.textContent = `${m.method} (${m.count.toLocaleString()})`;
    c.onclick = () => { state.method = m.method; state.offset = 0; reload(); };
    chips.appendChild(c);
  }
}

async function reload() {
  state.q = document.getElementById('search').value.trim();
  state.sgg = document.getElementById('sgg').value.trim();
  const params = new URLSearchParams();
  if (state.method) params.set('method', state.method);
  if (state.q) params.set('q', state.q);
  if (state.sgg) params.set('sgg', state.sgg);
  params.set('limit', state.limit);
  params.set('offset', state.offset);
  const r = await fetch('/api/transactions?' + params).then(r => r.json());
  state.total = r.total;
  state.rows = r.rows;
  renderTable();
  await loadStats();  // refresh chip counts
}

function renderTable() {
  const tb = document.getElementById('tbody');
  tb.innerHTML = '';
  for (const r of state.rows) {
    const tr = document.createElement('tr');
    tr.dataset.id = r.deal_id;
    tr.onclick = () => selectRow(r.deal_id);
    if (state.selected === r.deal_id) tr.classList.add('selected');
    tr.innerHTML = `
      <td>${r.deal_ymd ?? '-'}</td>
      <td>${r.apt_nm ?? '-'}</td>
      <td>${r.umd_nm ?? '-'}</td>
      <td>${r.jibun ?? '-'}</td>
      <td class="num">${r.excl_use_ar ?? '-'}</td>
      <td class="num">${r.floor ?? '-'}</td>
      <td class="num">${won(r.deal_amount)}</td>
      <td>${methodBadge(r.matched_method)} ${r.matched_score ? `<span class="muted">${r.matched_score}</span>` : ''}</td>
      <td>${r.matched_complex_name ?? '<span class="muted">—</span>'} ${r.matched_dong ? `<span class="muted">(${r.matched_dong})</span>` : ''}</td>
    `;
    tb.appendChild(tr);
  }
  const start = state.offset + 1;
  const end = state.offset + state.rows.length;
  document.getElementById('page-info').textContent =
    state.total ? `${start.toLocaleString()}–${end.toLocaleString()} / ${state.total.toLocaleString()}` : '0';
  document.getElementById('prev').disabled = state.offset === 0;
  document.getElementById('next').disabled = state.offset + state.rows.length >= state.total;
}

function page(delta) {
  state.offset = Math.max(0, state.offset + delta * state.limit);
  reload();
}

async function selectRow(deal_id) {
  state.selected = deal_id;
  document.querySelectorAll('tbody tr').forEach(tr => {
    tr.classList.toggle('selected', tr.dataset.id === deal_id);
  });
  const d = await fetch('/api/transactions/' + deal_id).then(r => r.json());
  renderDetail(d);
}

function renderDetail(d) {
  const md = d.match_details || {};
  const candidates = (md.candidates || []).map((c, i) => {
    const chosen = md.chosen && md.chosen.complex_no === c.complex_no;
    return `
      <div class="candidate ${chosen ? 'chosen' : ''}">
        <span class="score">score ${c.score} · ${c.method}</span>
        <strong>${c.complex_name}</strong> <span class="muted">(${c.dong_name || '-'})</span>
        <div class="muted">addr ${c.detail_address || '-'} · ${c.complex_no}</div>
        <div class="muted">reason: ${c.reason}</div>
      </div>`;
  }).join('') || '<div class="muted">후보 없음</div>';

  document.getElementById('detail').innerHTML = `
    <div class="kv">
      <div class="k">deal_id</div><div>${d.deal_id}</div>
      <div class="k">날짜</div><div>${d.deal_ymd}</div>
      <div class="k">거래 단지명</div><div><strong>${d.apt_nm}</strong></div>
      <div class="k">법정동</div><div>${d.umd_nm}</div>
      <div class="k">시군구</div><div>${d.sgg_cd}</div>
      <div class="k">지번</div><div>${d.jibun}</div>
      <div class="k">도로명</div><div>${d.road_nm || '-'}</div>
      <div class="k">전용/층</div><div>${d.excl_use_ar} m² / ${d.floor}층</div>
      <div class="k">가격</div><div>${won(d.deal_amount)}</div>
      <div class="k">거래유형</div><div>${d.dealing_gbn || '-'}</div>
      <div class="k">매칭</div><div>${methodBadge(d.matched_method)} score ${d.matched_score ?? '-'}</div>
      <div class="k">매칭 단지</div><div>${d.matched_complex_name ?? '-'} ${d.matched_dong ? `(${d.matched_dong})` : ''}</div>
    </div>
    <h3 style="font-size:13px; margin: 16px 0 6px">tx_variants 사용</h3>
    <pre>${JSON.stringify(md.tx_variants || [], null, 2)}</pre>
    <h3 style="font-size:13px; margin: 16px 0 6px">후보 (${(md.candidates || []).length})</h3>
    ${candidates}
    <h3 style="font-size:13px; margin: 16px 0 6px">raw API 응답</h3>
    <pre>${JSON.stringify(d.raw, null, 2)}</pre>
  `;
}

// -------- TAB SWITCHING --------
function switchTab(t) {
  document.getElementById('view-tx').style.display = (t === 'tx') ? '' : 'none';
  document.getElementById('view-sug').style.display = (t === 'sug') ? '' : 'none';
  document.getElementById('tab-tx').classList.toggle('active', t === 'tx');
  document.getElementById('tab-sug').classList.toggle('active', t === 'sug');
  if (t === 'sug' && sugState.rows.length === 0) sugReload();
}

// -------- SUGGESTIONS TAB --------
let sugState = { status: 'pending', offset: 0, limit: 100, total: 0, rows: [], counts: {} };

async function loadSugStats() {
  // counts come bundled with /api/suggestions response
  const badge = document.getElementById('sug-badge');
  const n = sugState.counts.pending || 0;
  badge.textContent = n > 0 ? `(${n.toLocaleString()})` : '';
  const chips = document.getElementById('sug-chips');
  chips.innerHTML = '';
  for (const s of ['pending', 'accepted', 'rejected', 'all']) {
    const c = document.createElement('span');
    c.className = 'chip' + (sugState.status === s ? ' active' : '');
    const cnt = s === 'all'
      ? Object.values(sugState.counts).reduce((a,b)=>a+b, 0)
      : (sugState.counts[s] || 0);
    c.textContent = `${s} (${cnt.toLocaleString()})`;
    c.onclick = () => { sugState.status = s; sugState.offset = 0; sugReload(); };
    chips.appendChild(c);
  }
}

async function sugReload() {
  const params = new URLSearchParams();
  params.set('status', sugState.status);
  params.set('limit', sugState.limit);
  params.set('offset', sugState.offset);
  const r = await fetch('/api/suggestions?' + params).then(r => r.json());
  sugState.total = r.total;
  sugState.rows = r.rows;
  sugState.counts = r.counts || {};
  await loadSugStats();
  renderSugTable();
}

function renderSugTable() {
  const tb = document.getElementById('sug-tbody');
  tb.innerHTML = '';
  for (const s of sugState.rows) {
    const tr = document.createElement('tr');
    tr.id = `sug-${s.suggestion_id}`;
    const actions = s.status === 'pending'
      ? `<button class="btn-accept" onclick="actSug(${s.suggestion_id}, 'accept')">Accept</button>
         <button class="btn-reject" onclick="actSug(${s.suggestion_id}, 'reject')">Reject</button>`
      : `<button class="btn-reset" onclick="actSug(${s.suggestion_id}, 'reset')">↶ pending</button>
         <span class="muted" style="font-size:11px">${s.status}</span>`;
    tr.innerHTML = `
      <td><strong>${s.apt_nm}</strong> ${s.umd_nm ? `<span class="muted">(${s.umd_nm})</span>` : ''}</td>
      <td>${s.sgg_cd}</td>
      <td>${s.suggested_complex_name ?? '<span class="muted">—</span>'}</td>
      <td>${s.suggested_address ?? '-'}</td>
      <td>${s.suggested_dong ?? '-'}</td>
      <td><span class="badge b-naver">${s.suggested_method}</span></td>
      <td class="num">${s.suggested_score}</td>
      <td class="num">${s.tx_count}</td>
      <td>${actions}</td>
    `;
    tb.appendChild(tr);
  }
  const start = sugState.offset + 1;
  const end = sugState.offset + sugState.rows.length;
  document.getElementById('sug-page-info').textContent =
    sugState.total ? `${start.toLocaleString()}–${end.toLocaleString()} / ${sugState.total.toLocaleString()}` : '0';
  document.getElementById('sug-prev').disabled = sugState.offset === 0;
  document.getElementById('sug-next').disabled = sugState.offset + sugState.rows.length >= sugState.total;
}

function sugPage(delta) {
  sugState.offset = Math.max(0, sugState.offset + delta * sugState.limit);
  sugReload();
}

async function actSug(sid, action) {
  const tr = document.getElementById(`sug-${sid}`);
  if (tr) tr.classList.add('processed');
  const r = await fetch(`/api/suggestions/${sid}/${action}`, { method: 'POST' })
    .then(r => r.json());
  if (action === 'accept') {
    alert(`${r.updated_tx} 건의 거래에 매칭 적용됨`);
  }
  sugReload();
}

loadStats();
reload();
document.getElementById('search').addEventListener('keydown', e => { if (e.key === 'Enter') { state.offset = 0; reload(); } });
document.getElementById('sgg').addEventListener('keydown', e => { if (e.key === 'Enter') { state.offset = 0; reload(); } });

// Pre-load suggestion count for the tab badge
fetch('/api/suggestions?status=pending&limit=1').then(r => r.json()).then(r => {
  sugState.counts = r.counts || {};
  loadSugStats();
});
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _HTML
