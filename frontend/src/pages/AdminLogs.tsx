import { useEffect, useState, useCallback, Fragment } from "react";
import { Link } from "react-router-dom";
import { ScrollText, MessageSquare, LogIn, Users, Eye, BarChart3 } from "lucide-react";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

type PageRow = { key?: string; label: string; views: number; visitors: number; users: number };
type PageAnalytics = {
  days: number; has_data: boolean;
  summary: { views: number; visitors: number; users: number };
  pages: PageRow[];
  trend: { day: string; views: number; visitors: number }[];
  top_complex: { ref: string; visits: number; visitors: number }[];
};

type Ev = {
  id: number; ts: string; kind: string; user_id: string | null;
  member_no: number | null; email: string | null; provider: string | null;
  phone: string | null; path: string | null; method: string | null;
  query: string | null; ref: string | null; status: number | null;
  duration_ms: number | null; ip: string | null; user_agent: string | null;
  detail: Record<string, unknown> | string | null;
};
type Stats = {
  days: number; total: number; ai_total: number; logins: number; active_users: number;
  by_kind: Record<string, number>;
  by_day: { day: string; n: number }[];
  top_complex: { ref: string; n: number }[];
  top_realtor: { ref: string; n: number }[];
};

const KIND_LABEL: Record<string, string> = {
  page: "페이지뷰", login: "로그인", view_complex: "단지 API", view_realtor: "중개사 API",
  view: "API 조회", ai_ask: "AI 질문", admin: "관리자", account: "계정", ai_region: "지역추정", api: "API",
};
const KIND_COLOR: Record<string, string> = {
  page: "#1268d3", login: "#1a7f4b", ai_ask: "#7c3aed", view_complex: "#5b8def", view_realtor: "#0891b2",
  admin: "#c0392b", account: "#8a5a00", view: "#64748b", ai_region: "#64748b", api: "#94a3b8",
};

function fmt(ts: string | null): string {
  if (!ts) return "-";
  // SQLite는 UTC로 저장 → 로컬시간으로 표시
  const d = new Date(ts.replace(" ", "T") + "Z");
  return isNaN(d.getTime()) ? ts : d.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function AdminLogs() {
  const { token } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [pa, setPa] = useState<PageAnalytics | null>(null);
  const [paDays, setPaDays] = useState(7);
  const auth = useCallback(() => ({ Authorization: `Bearer ${token}` }), [token]);

  useEffect(() => {
    if (!token || !API_BASE) return;
    fetch(`${API_BASE}/admin/logs/stats?days=7`, { headers: auth() })
      .then((r) => r.json()).then(setStats).catch(() => {});
  }, [token, auth]);

  useEffect(() => {
    if (!token || !API_BASE) return;
    fetch(`${API_BASE}/admin/page-analytics?days=${paDays}`, { headers: auth() })
      .then((r) => r.json()).then(setPa).catch(() => {});
  }, [token, auth, paDays]);

  const load = useCallback(() => {
    if (!token || !API_BASE) return;
    const p = new URLSearchParams({ limit: "300" });
    if (kind) p.set("kind", kind);
    if (q) p.set("q", q);
    fetch(`${API_BASE}/admin/logs?${p}`, { headers: auth() })
      .then(async (r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then((d) => setEvents(d.events ?? []))
      .catch((e) => setErr(String(e)));
  }, [token, auth, kind, q]);

  useEffect(() => { load(); }, [load]);

  if (!API_BASE) return <div className="muted">로컬 API 미설정 — 이 기능은 로컬에서만 동작합니다.</div>;

  const detailText = (d: Ev["detail"]): string => {
    if (!d) return "";
    if (typeof d === "string") return d;
    if ("question" in d) return `Q: ${String((d as { question: unknown }).question)}`;
    if ("name" in d) return String((d as { name: unknown }).name ?? "");
    return JSON.stringify(d).slice(0, 80);
  };
  // ai_ask 등 질문/답변이 있는 detail 추출
  const aiQA = (d: Ev["detail"]) => {
    if (!d || typeof d === "string") return null;
    const o = d as Record<string, unknown>;
    if (!("question" in o) && !("answer" in o)) return null;
    return {
      q: String(o.question ?? ""),
      a: o.answer != null ? String(o.answer) : "",
      error: o.error != null ? String(o.error) : "",
      tools: Array.isArray(o.tools) ? (o.tools as { tool?: string }[]).map((t) => t.tool).filter(Boolean).join(", ") : "",
    };
  };

  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>
        <BarChart3 size={15} strokeWidth={2.2} aria-hidden /> 페이지별 분석
        <span style={{ marginLeft: "auto", display: "inline-flex", gap: 4 }}>
          {[1, 7, 30].map((d) => (
            <button key={d} onClick={() => setPaDays(d)}
              className="ctx-badge" style={{
                cursor: "pointer", border: "none",
                background: paDays === d ? "#1268d3" : "#e8eef7",
                color: paDays === d ? "#fff" : "#5a6b80", fontSize: 12 }}>
              {d === 1 ? "오늘" : `${d}일`}
            </button>
          ))}
        </span>
      </div>

      {pa && !pa.has_data && (
        <div className="muted" style={{ fontSize: 13, padding: "8px 0 14px" }}>
          페이지뷰 집계는 방금 도입돼 오늘부터 쌓입니다 — 방문이 생기면 여기에 페이지별로 표시됩니다.
        </div>
      )}
      {pa && pa.has_data && (
        <>
          <div className="log-cards">
            <Stat ic={<Eye size={16} />} label="페이지뷰" v={pa.summary.views} c="#1268d3" />
            <Stat ic={<Users size={16} />} label="방문자(IP)" v={pa.summary.visitors} c="#0891b2" />
            <Stat ic={<LogIn size={16} />} label="로그인 사용자" v={pa.summary.users} c="#1a7f4b" />
          </div>
          <div className="log-grid2" style={{ marginTop: 12 }}>
            <div className="log-panel">
              <div className="log-panel-t">페이지별 (조회 · 방문자 · 로그인)</div>
              <table style={{ width: "100%", fontSize: 12.5 }}>
                <thead><tr style={{ color: "#8a99ad", textAlign: "left" }}>
                  <th>페이지</th><th className="num">조회</th><th className="num">방문자</th><th className="num">로그인</th>
                </tr></thead>
                <tbody>
                  {pa.pages.map((p) => (
                    <tr key={p.label}>
                      <td style={{ padding: "3px 0" }}>{p.label}</td>
                      <td className="num"><b>{p.views.toLocaleString()}</b></td>
                      <td className="num">{p.visitors.toLocaleString()}</td>
                      <td className="num" style={{ color: "#1a7f4b" }}>{p.users.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="log-panel">
              <div className="log-panel-t">인기 단지 (실제 방문 수)</div>
              {pa.top_complex.length === 0 && <div className="muted" style={{ fontSize: 13 }}>아직 없음</div>}
              {pa.top_complex.map((t) => (
                <div key={t.ref} className="log-row">
                  <Link to={`/complex/${t.ref}`} style={{ fontSize: 13 }}>단지 {t.ref}</Link>
                  <span><b>{t.visits}</b> <span className="muted" style={{ fontSize: 11 }}>· {t.visitors}명</span></span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="section-title" style={{ marginTop: 22 }}>
        <ScrollText size={15} strokeWidth={2.2} aria-hidden /> 활동 로그 (관리자)
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>최근 7일 기준</span>
      </div>

      {stats && (
        <>
          <div className="log-cards">
            <Stat ic={<Eye size={16} />} label="총 활동" v={stats.total} c="#334155" />
            <Stat ic={<MessageSquare size={16} />} label="AI 질문" v={stats.ai_total} c="#7c3aed" />
            <Stat ic={<LogIn size={16} />} label="로그인" v={stats.logins} c="#1a7f4b" />
            <Stat ic={<Users size={16} />} label="활성 사용자" v={stats.active_users} c="#1268d3" />
          </div>

          <div className="log-grid2">
            <div className="log-panel">
              <div className="log-panel-t">종류별</div>
              {Object.entries(stats.by_kind).sort((a, b) => b[1] - a[1]).map(([k, n]) => (
                <div key={k} className="log-row">
                  <span className="ctx-badge" style={{ background: (KIND_COLOR[k] || "#888") + "22", color: KIND_COLOR[k] || "#888" }}>
                    {KIND_LABEL[k] || k}
                  </span>
                  <b>{n.toLocaleString()}</b>
                </div>
              ))}
            </div>
            <div className="log-panel">
              <div className="log-panel-t">인기 단지 (조회수)</div>
              {stats.top_complex.length === 0 && <div className="muted" style={{ fontSize: 13 }}>아직 없음</div>}
              {stats.top_complex.map((t) => (
                <div key={t.ref} className="log-row">
                  <Link to={`/complex/${t.ref}`} style={{ fontSize: 13 }}>단지 {t.ref}</Link>
                  <b>{t.n}</b>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <div style={{ display: "flex", gap: 6, margin: "16px 0 10px", flexWrap: "wrap", alignItems: "center" }}>
        <select className="ai-input" style={{ padding: "7px 10px", maxWidth: 160 }} value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">전체 종류</option>
          {Object.keys(KIND_LABEL).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
        </select>
        <input className="ai-input" style={{ padding: "7px 10px", maxWidth: 240 }} placeholder="AI 질문/상세 검색"
          value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") load(); }} />
        <button className="ai-send" style={{ padding: "0 14px" }} onClick={load}>검색</button>
      </div>

      {err && <div style={{ color: "crimson", fontSize: 13 }}>{err}</div>}
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>시각</th><th>종류</th><th>회원</th><th>대상/내용</th><th>경로</th><th className="num">ms</th><th>IP</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => {
              const qa = aiQA(e.detail);
              const open = openId === e.id;
              return (
              <Fragment key={e.id}>
              <tr style={qa ? { cursor: "pointer" } : undefined}
                  onClick={qa ? () => setOpenId(open ? null : e.id) : undefined}>
                <td style={{ fontSize: 12, whiteSpace: "nowrap" }}>{fmt(e.ts)}</td>
                <td>
                  <span className="ctx-badge" style={{ background: (KIND_COLOR[e.kind] || "#888") + "22", color: KIND_COLOR[e.kind] || "#888" }}>
                    {KIND_LABEL[e.kind] || e.kind}
                  </span>
                </td>
                <td style={{ fontSize: 12 }}>
                  {e.member_no ? <b style={{ color: "#1268d3" }}>#{e.member_no}</b> : <span className="muted">비회원</span>}
                  {e.email && <div style={{ color: "#888", fontSize: 11 }}>{e.email}</div>}
                </td>
                <td style={{ fontSize: 12, maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {e.kind === "view_complex" && e.ref ? <Link to={`/complex/${e.ref}`}>단지 {e.ref}</Link>
                    : e.kind === "view_realtor" && e.ref ? <Link to={`/realtor/${e.ref}`}>중개사 {e.ref}</Link>
                    : qa ? <span>{open ? "▾ " : "▸ "}Q: {qa.q}</span>
                    : detailText(e.detail) || e.ref || "—"}
                </td>
                <td style={{ fontSize: 11, color: "#888", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {e.method} {e.path}{e.status && e.status >= 400 ? ` · ${e.status}` : ""}
                </td>
                <td className="num" style={{ fontSize: 12, color: (e.duration_ms ?? 0) > 800 ? "#c0392b" : "#888" }}>{e.duration_ms ?? "-"}</td>
                <td style={{ fontSize: 11, color: "#aaa" }}>{e.ip ?? "-"}</td>
              </tr>
              {qa && open && (
                <tr>
                  <td colSpan={7} style={{ background: "#f7f9fc", padding: "10px 14px" }}>
                    <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                      <div style={{ fontWeight: 700, color: "#1268d3" }}>Q. {qa.q}</div>
                      {qa.tools && <div style={{ fontSize: 11, color: "#888", margin: "4px 0" }}>도구: {qa.tools}</div>}
                      <div style={{ marginTop: 6, color: "#2c3a4d" }}>A. {qa.a || (qa.error ? `(오류) ${qa.error}` : "(빈 응답)")}</div>
                    </div>
                  </td>
                </tr>
              )}
              </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>
        모든 로그인·조회·AI 질문이 logs.sqlite에 기록됩니다. 개선 분석 및 보안 점검용 · 관리자 전용.
      </p>
    </>
  );
}

function Stat({ ic, label, v, c }: { ic: React.ReactNode; label: string; v: number; c: string }) {
  return (
    <div className="log-card">
      <span className="log-card-ic" style={{ color: c }}>{ic}</span>
      <div>
        <div className="log-card-v">{v.toLocaleString()}</div>
        <div className="log-card-l">{label}</div>
      </div>
    </div>
  );
}
