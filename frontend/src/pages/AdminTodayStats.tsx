import { useEffect, useState, useCallback } from "react";
import { Users, UserPlus, Activity, Eye, LogIn, Bot, Building2, RefreshCw } from "lucide-react";
import { ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

type Stats = {
  date_kst: string; visitors: number; logged_users: number; events: number;
  logins: number; pageviews: number; ai_questions: number; complex_views: number;
  peak_concurrent: number; peak_window: string; new_signups: number; total_users: number;
  hourly: { hour: number; visitors: number; events: number }[];
  top_paths: { path: string; label?: string; n: number }[];
};
type Trend = { date: string; visitors: number; pageviews: number; signups: number };
type Page = { label: string; views: number; visitors: number };

export default function AdminTodayStats() {
  const { token } = useAuth();
  const [d, setD] = useState<Stats | null>(null);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [pages, setPages] = useState<Page[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!token || !API) return;
    setLoading(true);
    const h = { headers: { Authorization: `Bearer ${token}` } };
    Promise.all([
      fetch(`${API}/admin/today-stats`, h).then((r) => { if (!r.ok) throw new Error(r.status === 401 || r.status === 403 ? "관리자 권한이 필요해요" : `오류 ${r.status}`); return r.json(); }),
      fetch(`${API}/admin/trends?days=30`, h).then((r) => r.json()).catch(() => ({ days: [] })),
      fetch(`${API}/admin/top-pages?days=7`, h).then((r) => r.json()).catch(() => ({ pages: [] })),
    ]).then(([s, t, p]) => { setD(s); setTrends(t.days || []); setPages(p.pages || []); })
      .catch((e) => setErr(e.message)).finally(() => setLoading(false));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  if (err) return <div className="ats"><h2>오늘의 접속통계</h2><div className="ats-err">{err}</div></div>;
  if (loading || !d) return <div className="ats"><h2>오늘의 접속통계</h2><div className="muted" style={{ padding: 24 }}>불러오는 중…</div></div>;

  const maxH = Math.max(1, ...d.hourly.map((h) => h.visitors));
  const nowHour = new Date().getHours();

  return (
    <div className="ats">
      <div className="ats-head">
        <h2><Activity size={20} strokeWidth={2.3} aria-hidden /> 오늘의 접속통계</h2>
        <span className="ats-date">{d.date_kst} (KST) · <button className="ats-refresh" onClick={load}><RefreshCw size={13} /> 새로고침</button></span>
      </div>

      <div className="ats-cards">
        <div className="ats-card hl"><span className="ats-ic"><Users size={18} /></span><span className="ats-v">{d.visitors.toLocaleString()}</span><span className="ats-l">방문자(고유 IP)</span></div>
        <div className="ats-card"><span className="ats-ic"><Activity size={18} /></span><span className="ats-v">{d.peak_concurrent.toLocaleString()}</span><span className="ats-l">최대 동시작업자</span></div>
        <div className="ats-card"><span className="ats-ic"><LogIn size={18} /></span><span className="ats-v">{d.logged_users.toLocaleString()}</span><span className="ats-l">로그인 사용자</span></div>
        <div className="ats-card hl2"><span className="ats-ic"><UserPlus size={18} /></span><span className="ats-v">{d.new_signups.toLocaleString()}</span><span className="ats-l">신규 가입</span></div>
      </div>

      <div className="ats-sub">
        <div><Eye size={14} /> 페이지뷰 <b>{d.pageviews.toLocaleString()}</b></div>
        <div><LogIn size={14} /> 로그인 <b>{d.logins.toLocaleString()}</b></div>
        <div><Building2 size={14} /> 단지조회 <b>{d.complex_views.toLocaleString()}</b></div>
        <div><Bot size={14} /> AI질문 <b>{d.ai_questions.toLocaleString()}</b></div>
        <div><Users size={14} /> 총회원 <b>{d.total_users.toLocaleString()}</b></div>
      </div>

      <div className="ats-section">시간대별 방문자 (KST)</div>
      <div className="ats-chart">
        {d.hourly.length === 0 ? <div className="muted">아직 데이터가 없어요</div> : (
          Array.from({ length: 24 }, (_, h) => {
            const row = d.hourly.find((x) => x.hour === h);
            const v = row?.visitors ?? 0;
            return (
              <div key={h} className={`ats-bar-wrap${h === nowHour ? " now" : ""}`} title={`${h}시 · 방문자 ${v}`}>
                <div className="ats-bar" style={{ height: `${(v / maxH) * 100}%` }}><span className="ats-bar-n">{v || ""}</span></div>
                <span className="ats-bar-h">{h}</span>
              </div>
            );
          })
        )}
      </div>

      <div className="ats-section">최근 30일 추이 <span style={{ fontWeight: 400, color: "#9aa7b8", fontSize: 11 }}>순방문자(선)·가입자(막대)</span></div>
      <div style={{ width: "100%", height: 230 }}>
        <ResponsiveContainer>
          <ComposedChart data={trends} margin={{ top: 8, right: 6, left: -14, bottom: 0 }}>
            <CartesianGrid stroke="#eef1f5" vertical={false} />
            <XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} tick={{ fontSize: 10, fill: "#9aa7b8" }} interval="preserveStartEnd" minTickGap={20} />
            <YAxis yAxisId="l" tick={{ fontSize: 10, fill: "#9aa7b8" }} width={34} />
            <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 10, fill: "#9aa7b8" }} width={26} />
            <Tooltip labelFormatter={(v) => `${v}`} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Bar yAxisId="r" dataKey="signups" name="가입자" fill="#1f9d63" radius={[3, 3, 0, 0]} barSize={9} />
            <Line yAxisId="l" type="monotone" dataKey="visitors" name="순방문자" stroke="#1268d3" strokeWidth={2} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="ats-section">인기 페이지 <span style={{ fontWeight: 400, color: "#9aa7b8", fontSize: 11 }}>최근 7일</span></div>
      <div className="ats-paths">
        {(pages.length ? pages.map((p) => ({ label: p.label, n: p.views })) : d.top_paths.map((p) => ({ label: p.label || p.path, n: p.n }))).map((p, i) => (
          <div key={i} className="ats-path"><span className="ats-path-r">{i + 1}</span><span className="ats-path-p">{p.label}</span><span className="ats-path-n">{p.n.toLocaleString()}</span></div>
        ))}
      </div>
      <p className="muted" style={{ fontSize: 11.5, marginTop: 12 }}>순방문자=고유 IP · 가입자=약관동의 기준 · 인기 페이지=사용자 화면 조회수(API·봇 제외).</p>
    </div>
  );
}
