// ══════════════════════════════════════════════════════════════════════════
// SNS 분석 — Threads 소재 레이더
//
//   nfind 박스가 20분마다 Threads 를 키워드로 훑어 반응이 붙는 글을 모으고,
//   1차 숫자 필터를 통과한 것만 AI 로 분석해 점수를 매긴다.
//   여기서는 오늘의 소재를 훑고, 쓸 것은 ⭐ 저장하고, 아닌 것은 🗑 제외한다.
//
//   핵심은 좋아요 순위가 아니라 '반응 속도' 다 — 2일 된 200 좋아요보다
//   30분 만의 100 좋아요가 소재로서 값어치가 크다.
// ══════════════════════════════════════════════════════════════════════════
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle, ExternalLink, Heart, Loader2, MessageCircle, Radar, RefreshCw,
  Repeat2, Star, Trash2, Zap,
} from "lucide-react";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

type Post = {
  id: number;
  post_key: string;
  author: string;
  text: string;
  url: string;
  like_count: number;
  reply_count: number;
  repost_count: number;
  quote_count: number;
  age_min: number | null;
  keyword: string;
  keywords_all: string;
  engagement: number;
  velocity: number;
  analyzed_at: string | null;
  humor: number | null;
  satire: number | null;
  gossip: number | null;
  controversy: number | null;
  surprise: number | null;
  empathy: number | null;
  hook: number | null;
  realestate: number | null;
  ai_score: number | null;
  categories: string | null;
  ai_reason: string | null;
  content_idea: string | null;
  final_score: number;
  saved: number;
  first_seen_at: string;
};
type Stats = {
  stats: { total?: number; day?: number; analyzed?: number; saved?: number };
  last_run: { started_at?: string; ended_at?: string; found?: number; fresh?: number; error?: string } | null;
  categories: [string, number][];
};
type Keyword = {
  id: number; keyword: string; category: string;
  enabled: number; priority: number; every_min: number; last_run_at: string | null;
};

const HOURS = [
  { v: 1, label: "1시간" },
  { v: 6, label: "6시간" },
  { v: 24, label: "오늘" },
  { v: 168, label: "7일" },
];

// 경과 시간 — 반응 속도를 읽는 데 필요해 목록에 항상 붙인다
function ago(min: number | null): string {
  if (min == null) return "-";
  if (min < 60) return `${min}분`;
  if (min < 1440) return `${Math.floor(min / 60)}시간`;
  return `${Math.floor(min / 1440)}일`;
}
const n = (v: number) => (v >= 10000 ? `${(v / 10000).toFixed(1)}만` : v.toLocaleString());

export default function SnsRadar() {
  const { token } = useAuth();
  const [posts, setPosts] = useState<Post[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [keywords, setKeywords] = useState<Keyword[] | null>(null);
  const [err, setErr] = useState("");

  const [hours, setHours] = useState(24);
  const [cat, setCat] = useState("");
  const [mode, setMode] = useState<"top" | "fresh" | "saved">("top");
  const [open, setOpen] = useState<number | null>(null);
  const [raw, setRaw] = useState(false);          // 임베드 대신 수집한 원문 텍스트 보기
  const [running, setRunning] = useState(false);
  const [showKw, setShowKw] = useState(false);

  const api = useCallback(
    async (path: string, init?: RequestInit) => {
      const r = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: { ...(init?.headers || {}), Authorization: `Bearer ${token}` },
      });
      if (!r.ok) {
        let m = `${r.status}`;
        try {
          const j = JSON.parse(await r.text());
          m = j.detail || j.error || m;
        } catch { /* 상태코드만 */ }
        throw new Error(m);
      }
      return r.json();
    },
    [token],
  );

  const load = useCallback(async () => {
    try {
      const q = `?hours=${hours}&mode=${mode}&limit=60${cat ? `&category=${encodeURIComponent(cat)}` : ""}`;
      const [p, s] = await Promise.all([
        api(`/admin/sns-radar/posts${q}`),
        api("/admin/sns-radar/stats"),
      ]);
      setPosts(p.posts ?? []);
      setStats(s);
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  }, [api, hours, cat, mode]);

  useEffect(() => {
    if (token && API_BASE) load();
  }, [token, load]);

  useEffect(() => {
    if (!showKw || !token) return;
    api("/admin/sns-radar/keywords")
      .then((d) => setKeywords(d.keywords ?? []))
      .catch((e) => setErr(String(e)));
  }, [showKw, token, api]);

  const mark = async (p: Post, action: "save" | "exclude") => {
    const on = action === "save" ? !p.saved : true;
    try {
      await api(`/admin/sns-radar/posts/${p.id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ on }),
      });
      if (action === "exclude") setPosts((cur) => (cur ?? []).filter((x) => x.id !== p.id));
      else setPosts((cur) => (cur ?? []).map((x) => (x.id === p.id ? { ...x, saved: on ? 1 : 0 } : x)));
    } catch (e) {
      setErr(String(e));
    }
  };

  const runNow = async () => {
    setRunning(true);
    try {
      await api("/admin/sns-radar/run", { method: "POST" });
      // 수집은 몇 분 걸린다 — 주기적으로 현황만 다시 읽는다
      setTimeout(load, 60000);
      setTimeout(() => setRunning(false), 60000);
    } catch (e) {
      setErr(String(e));
      setRunning(false);
    }
  };

  const toggleKw = async (k: Keyword) => {
    try {
      await api(`/admin/sns-radar/keywords/${k.id}/toggle`, { method: "POST" });
      setKeywords((cur) =>
        (cur ?? []).map((x) => (x.id === k.id ? { ...x, enabled: x.enabled ? 0 : 1 } : x)));
    } catch (e) {
      setErr(String(e));
    }
  };

  const lastRun = stats?.last_run;
  const topCats = useMemo(() => (stats?.categories ?? []).slice(0, 8), [stats]);

  return (
    <div className="rd">
      <style>{css}</style>

      <div className="section-title" style={{ marginTop: 4 }}>
        <Radar size={16} strokeWidth={2.2} /> SNS 분석{" "}
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>
          Threads 소재 레이더 · 관리자
        </span>
      </div>
      <p className="rd-lead">
        Threads 를 키워드로 훑어 <b>반응이 빠르게 붙는 글</b>을 찾는다. 좋아요 총량이 아니라
        올라온 지 얼마 만에 얼마나 붙었는지로 줄을 세우고, 그중 쓸 만한 것만 AI 가 분석한다.
      </p>

      {err && <div className="rd-err"><AlertCircle size={15} strokeWidth={2.3} /><span>{err}</span></div>}

      {/* ── 현황 ─────────────────────────────────────────────────────── */}
      <div className="rd-stat">
        <div><b>{stats?.stats.day ?? "-"}</b><span>오늘 수집</span></div>
        <div><b>{stats?.stats.analyzed ?? "-"}</b><span>AI 분석</span></div>
        <div><b>{stats?.stats.saved ?? "-"}</b><span>저장한 소재</span></div>
        <div className="rd-stat-run">
          {lastRun?.error
            ? <em className="bad">마지막 수집 실패 — {lastRun.error.slice(0, 60)}</em>
            : <em>마지막 수집 {lastRun?.ended_at?.slice(5, 16) ?? "-"} · 새 글 {lastRun?.fresh ?? 0}건</em>}
          <button onClick={runNow} disabled={running}>
            {running ? <Loader2 size={13} className="rd-spin" /> : <Zap size={13} strokeWidth={2.4} />}
            {running ? "수집 중" : "지금 수집"}
          </button>
          <button onClick={load}><RefreshCw size={13} strokeWidth={2.4} /> 새로고침</button>
        </div>
      </div>

      {/* ── 필터 ─────────────────────────────────────────────────────── */}
      <div className="rd-bar">
        <div className="rd-seg">
          {(["top", "fresh", "saved"] as const).map((m) => (
            <button key={m} className={mode === m ? "on" : ""} onClick={() => setMode(m)}>
              {m === "top" ? "점수순" : m === "fresh" ? "최신순" : "저장함"}
            </button>
          ))}
        </div>
        {mode !== "saved" && (
          <div className="rd-seg">
            {HOURS.map((h) => (
              <button key={h.v} className={hours === h.v ? "on" : ""} onClick={() => setHours(h.v)}>
                {h.label}
              </button>
            ))}
          </div>
        )}
        <div className="rd-chips">
          <button className={cat === "" ? "on" : ""} onClick={() => setCat("")}>전체</button>
          {topCats.map(([c, k]) => (
            <button key={c} className={cat === c ? "on" : ""} onClick={() => setCat(c)}>
              {c}<i>{k}</i>
            </button>
          ))}
        </div>
        <button className="rd-kwbtn" onClick={() => setShowKw((v) => !v)}>
          키워드 {showKw ? "닫기" : "관리"}
        </button>
      </div>

      {/* ── 키워드 관리 ──────────────────────────────────────────────── */}
      {showKw && (
        <div className="rd-kw">
          {keywords === null ? <span className="muted">불러오는 중…</span> : keywords.map((k) => (
            <button
              key={k.id}
              className={`rd-kw-chip${k.enabled ? " on" : ""}`}
              onClick={() => toggleKw(k)}
              title={`${k.category} · 우선순위 ${k.priority} · ${k.every_min}분마다${
                k.last_run_at ? ` · 마지막 ${k.last_run_at.slice(5, 16)}` : ""}`}
            >
              {k.keyword}<i>{k.every_min}m</i>
            </button>
          ))}
          <p className="rd-kw-note">
            눌러서 켜고 끈다. 우선순위가 높고 오래 안 본 키워드부터 수집한다.
          </p>
        </div>
      )}

      {/* ── 목록 ─────────────────────────────────────────────────────── */}
      {posts === null ? (
        <div className="rd-skel-wrap">{Array.from({ length: 5 }, (_, i) => <div key={i} className="rd-skel" />)}</div>
      ) : posts.length === 0 ? (
        <p className="rd-empty">
          {mode === "saved" ? "저장한 소재가 없다." : "이 조건에 맞는 글이 없다. 기간을 넓혀 보라."}
        </p>
      ) : (
        <ol className="rd-list">
          {posts.map((p, i) => {
            const cats = (p.categories || "").split(",").filter(Boolean);
            const isOpen = open === p.id;
            return (
              <li key={p.id} className={`rd-item${isOpen ? " open" : ""}`}>
                <button
                  className="rd-head"
                  onClick={() => { setRaw(false); setOpen(isOpen ? null : p.id); }}
                >
                  <span className="rd-rank">{i + 1}</span>
                  <span className="rd-score" title="반응 + AI 종합">{Math.round(p.final_score)}</span>
                  <span className="rd-main">
                    <span className="rd-text">{p.text || "(본문 없음)"}</span>
                    <span className="rd-meta">
                      <b>@{p.author}</b>
                      <i><Heart size={11} /> {n(p.like_count)}</i>
                      <i><MessageCircle size={11} /> {n(p.reply_count)}</i>
                      <i><Repeat2 size={11} /> {n(p.repost_count)}</i>
                      <em>{ago(p.age_min)} 전</em>
                      {p.velocity > 0 && <em className="hot">시간당 {Math.round(p.velocity)}</em>}
                      {!p.analyzed_at && <em className="pend">분석 대기</em>}
                    </span>
                  </span>
                  <span className="rd-cats">
                    {cats.slice(0, 3).map((c) => <span key={c}>{c}</span>)}
                  </span>
                </button>

                {isOpen && (
                  <div className="rd-body">
                    {/* Threads 공식 임베드. curl 로 받으면 x-frame-options: DENY 지만
                        실제 iframe 요청에는 그 헤더가 붙지 않는다(koczip.com 오리진에서 확인).
                        높이를 알려주는 postMessage 는 오지 않아 넉넉히 잡고 안에서 스크롤한다. */}
                    {raw ? (
                      <p className="rd-full">{p.text}</p>
                    ) : (
                      <iframe
                        className="rd-embed"
                        src={`${p.url}/embed/`}
                        title={`@${p.author} 게시물`}
                        loading="lazy"
                        referrerPolicy="no-referrer-when-downgrade"
                      />
                    )}
                    <button className="rd-rawbtn" onClick={() => setRaw((v) => !v)}>
                      {raw ? "원문 보기" : "수집한 텍스트 보기"}
                    </button>

                    {p.analyzed_at ? (
                      <>
                        <div className="rd-bars">
                          {([["풍자", p.satire], ["가십", p.gossip], ["논쟁", p.controversy],
                             ["반전", p.surprise], ["공감", p.empathy], ["훅", p.hook],
                             ["유머", p.humor], ["부동산", p.realestate]] as [string, number | null][])
                            .map(([label, v]) => (
                              <div key={label} className="rd-bar-row">
                                <span>{label}</span>
                                <div><i style={{ width: `${(v ?? 0) * 10}%` }} /></div>
                                <b>{v ?? "-"}</b>
                              </div>
                            ))}
                        </div>
                        {p.ai_reason && (
                          <div className="rd-why"><b>왜 읽히나</b><p>{p.ai_reason}</p></div>
                        )}
                        {p.content_idea && (
                          <div className="rd-idea"><b>콘텐츠 아이디어</b><p>{p.content_idea}</p></div>
                        )}
                      </>
                    ) : (
                      <p className="rd-pending">아직 AI 분석 전이다(반응이 더 붙으면 분석 대상이 된다).</p>
                    )}

                    <div className="rd-acts">
                      <span className="rd-kwtag">검색어 {p.keywords_all || p.keyword}</span>
                      <a href={p.url} target="_blank" rel="noreferrer">
                        <ExternalLink size={13} strokeWidth={2.3} /> 원문
                      </a>
                      <button className={p.saved ? "on" : ""} onClick={() => mark(p, "save")}>
                        <Star size={13} strokeWidth={2.3} /> {p.saved ? "저장됨" : "저장"}
                      </button>
                      <button className="del" onClick={() => mark(p, "exclude")}>
                        <Trash2 size={13} strokeWidth={2.3} /> 제외
                      </button>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

const css = `
.rd{max-width:1040px}
.rd-lead{margin:6px 0 16px;font-size:13.5px;line-height:1.6;color:var(--c-muted);max-width:66ch}
.rd-err{display:flex;align-items:flex-start;gap:8px;margin:10px 0;padding:10px 13px;
  border:1px solid #f3c9c9;background:#fdf3f3;border-radius:var(--r-md);font-size:13px;color:#a52a2a}
.rd-err svg{flex:none;margin-top:1px}

/* 현황 */
.rd-stat{display:flex;align-items:center;gap:26px;flex-wrap:wrap;margin-bottom:14px;
  padding:13px 17px;border:1px solid var(--c-border);background:var(--c-card);
  border-radius:var(--r-lg);box-shadow:var(--sh-sm)}
.rd-stat>div{display:flex;flex-direction:column;gap:1px}
.rd-stat b{font-size:20px;font-weight:800;color:var(--c-text);font-variant-numeric:tabular-nums}
.rd-stat span{font-size:11.5px;font-weight:600;color:var(--c-muted)}
.rd-stat-run{margin-left:auto;flex-direction:row!important;align-items:center;gap:8px!important}
.rd-stat-run em{font-style:normal;font-size:11.5px;color:var(--c-faint)}
.rd-stat-run em.bad{color:var(--c-sale)}
.rd-stat-run button{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--c-border);
  background:#fff;border-radius:var(--r-pill);padding:5px 12px;font:inherit;font-size:11.5px;
  font-weight:700;color:#42506a;cursor:pointer}
.rd-stat-run button:hover:not(:disabled){border-color:var(--c-primary);color:var(--c-primary)}
.rd-stat-run button:disabled{opacity:.55;cursor:default}
.rd-spin{animation:rdspin .9s linear infinite}
@keyframes rdspin{to{transform:rotate(360deg)}}

/* 필터 */
.rd-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.rd-seg{display:inline-flex;border:1px solid #cdd9ea;border-radius:9px;overflow:hidden}
.rd-seg button{border:none;background:#fff;padding:7px 13px;font:inherit;font-size:12.5px;
  font-weight:700;color:#66748a;cursor:pointer}
.rd-seg button.on{background:var(--c-primary);color:#fff}
.rd-chips{display:flex;flex-wrap:wrap;gap:5px}
.rd-chips button{display:inline-flex;align-items:center;gap:4px;border:1px solid #d9e2ef;
  background:#fff;border-radius:var(--r-pill);padding:5px 11px;font:inherit;font-size:12px;
  font-weight:700;color:#3c4a60;cursor:pointer}
.rd-chips button.on{border-color:var(--c-primary);background:var(--c-primary-soft);color:#0b4ea2}
.rd-chips i{font-style:normal;font-size:10.5px;color:var(--c-faint)}
.rd-kwbtn{margin-left:auto;border:1px solid var(--c-border);background:#fff;border-radius:var(--r-pill);
  padding:6px 13px;font:inherit;font-size:11.5px;font-weight:700;color:#42506a;cursor:pointer}

/* 키워드 */
.rd-kw{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px;padding:13px 15px;
  border:1px solid var(--c-border);background:var(--c-primary-tint);border-radius:var(--r-md)}
.rd-kw-chip{display:inline-flex;align-items:center;gap:5px;border:1px solid #d9e2ef;background:#fff;
  border-radius:var(--r-pill);padding:5px 11px;font:inherit;font-size:12px;font-weight:700;
  color:#9aa4b0;cursor:pointer}
.rd-kw-chip.on{border-color:var(--c-primary);color:#0b4ea2}
.rd-kw-chip i{font-style:normal;font-size:10px;color:var(--c-faint)}
.rd-kw-note{flex:0 0 100%;margin:6px 0 0;font-size:11.5px;color:var(--c-muted)}

/* 목록 */
.rd-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px}
.rd-item{border:1px solid var(--c-border);background:var(--c-card);border-radius:var(--r-md);
  box-shadow:var(--sh-xs);overflow:hidden}
.rd-item.open{border-color:var(--c-primary);box-shadow:var(--sh-md)}
.rd-head{display:flex;align-items:flex-start;gap:11px;width:100%;padding:12px 14px;border:none;
  background:none;text-align:left;cursor:pointer}
.rd-head:hover{background:var(--c-row-hover)}
.rd-rank{flex:none;width:19px;font-size:12px;font-weight:800;color:var(--c-faint);line-height:1.5;
  font-variant-numeric:tabular-nums}
.rd-score{flex:none;min-width:44px;height:26px;display:inline-flex;align-items:center;
  justify-content:center;border-radius:8px;background:var(--c-primary-soft);color:#0b4ea2;
  font-size:13px;font-weight:800;font-variant-numeric:tabular-nums}
.rd-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}
.rd-text{font-size:13.5px;line-height:1.5;color:var(--c-text);overflow:hidden;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;word-break:break-word}
.rd-meta{display:flex;flex-wrap:wrap;align-items:center;gap:9px;font-size:11.5px;color:var(--c-muted)}
.rd-meta b{font-weight:700;color:var(--c-text-soft)}
.rd-meta i{display:inline-flex;align-items:center;gap:3px;font-style:normal;
  font-variant-numeric:tabular-nums}
.rd-meta em{font-style:normal;color:var(--c-faint)}
.rd-meta em.hot{color:var(--c-sale);font-weight:700}
.rd-meta em.pend{color:var(--c-warn)}
.rd-cats{flex:none;display:flex;flex-wrap:wrap;gap:4px;max-width:150px;justify-content:flex-end}
.rd-cats span{font-size:11px;font-weight:700;color:#0b4ea2;background:var(--c-primary-tint);
  border-radius:var(--r-pill);padding:2px 8px}

/* 상세 */
.rd-body{padding:2px 16px 14px 60px;border-top:1px solid var(--c-border-soft)}
.rd-embed{display:block;width:100%;max-width:560px;height:620px;margin:12px 0;border:0;
  border-radius:var(--r-md);background:#fff;box-shadow:var(--sh-sm)}
.rd-rawbtn{border:none;background:none;padding:0;font:inherit;font-size:11.5px;font-weight:700;
  color:var(--c-muted);text-decoration:underline;cursor:pointer}
.rd-rawbtn:hover{color:var(--c-primary)}
.rd-full{margin:12px 0;font-size:13.5px;line-height:1.75;color:var(--c-text-soft);white-space:pre-wrap;
  word-break:break-word}
.rd-bars{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:5px 18px;
  margin:12px 0}
.rd-bar-row{display:flex;align-items:center;gap:8px;font-size:11.5px}
.rd-bar-row>span{flex:none;width:34px;color:var(--c-muted);font-weight:700}
.rd-bar-row>div{flex:1;height:6px;border-radius:3px;background:#eef1f5;overflow:hidden}
.rd-bar-row i{display:block;height:100%;border-radius:3px;background:var(--c-primary)}
.rd-bar-row>b{flex:none;width:14px;text-align:right;font-weight:800;color:var(--c-text-soft);
  font-variant-numeric:tabular-nums}
.rd-why,.rd-idea{margin:8px 0;padding:10px 13px;border-radius:var(--r-md);font-size:12.5px;line-height:1.6}
.rd-why{background:#f6f8fb;color:var(--c-text-soft)}
.rd-idea{background:#fffaf0;border:1px solid #f0dfc0;color:#7a5a1e}
.rd-why b,.rd-idea b{display:block;margin-bottom:3px;font-size:11px;font-weight:800;
  letter-spacing:.02em;opacity:.75}
.rd-why p,.rd-idea p{margin:0}
.rd-pending{margin:12px 0;font-size:12.5px;color:var(--c-faint)}
.rd-acts{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:12px}
.rd-kwtag{margin-right:auto;font-size:11px;color:var(--c-faint)}
.rd-acts a,.rd-acts button{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--c-border);
  background:#fff;border-radius:8px;padding:6px 12px;font:inherit;font-size:11.5px;font-weight:700;
  color:#42506a;cursor:pointer;text-decoration:none}
.rd-acts a:hover,.rd-acts button:hover{border-color:var(--c-primary);color:var(--c-primary)}
.rd-acts button.on{border-color:var(--c-warn);background:#fff8ec;color:#a8720f}
.rd-acts button.del:hover{border-color:var(--c-sale);color:var(--c-sale)}

.rd-empty{font-size:13px;color:var(--c-muted)}
.rd-skel-wrap{display:flex;flex-direction:column;gap:7px}
.rd-skel{height:62px;border-radius:var(--r-md);background:linear-gradient(90deg,#eef1f5,#f7f9fb,#eef1f5);
  background-size:200% 100%;animation:rdsh 1.3s linear infinite}
@keyframes rdsh{0%{background-position:200% 0}100%{background-position:-200% 0}}
`;
