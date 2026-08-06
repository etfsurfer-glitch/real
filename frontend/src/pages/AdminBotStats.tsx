import { useEffect, useState } from "react";
import { Loading } from "../components/Loading";
import { useAuth } from "../auth";
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE;

type BotStats = {
  days: number; total: number;
  reasons: { reason: string; label: string; count: number; ips: number }[];
  daily: { date: string; blocks: number }[];
  top_ips: { ip: string; count: number; reasons: number }[];
  top_uas: { ua: string; count: number }[];
  recent: { ts: string; reason: string; status: number; ip: string; ua: string; path: string }[];
  goodbots: { bot: string; count: number }[];
};

const REASON_COLOR: Record<string, string> = {
  ai_crawler: "#8250c8", scraper_ua: "#e2574c", empty_ua: "#e2882e",
  velocity: "#d4a017", fake_googlebot: "#c0392b", fake_bingbot: "#c0392b",
};
const colorFor = (r: string) => REASON_COLOR[r] || (r.startsWith("fake_") ? "#c0392b" : "#6b7a90");
const kstTime = (ts: string) => {
  const d = new Date(ts.replace(" ", "T") + "Z");
  return d.toLocaleString("ko-KR", { timeZone: "Asia/Seoul", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
};

export default function AdminBotStats() {
  const { token } = useAuth();
  const [data, setData] = useState<BotStats | null>(null);
  const [days, setDays] = useState(7);
  const [err, setErr] = useState(false);

  useEffect(() => {
    if (!token || !API_BASE) return;
    setData(null); setErr(false);
    fetch(`${API_BASE}/admin/bot-stats?days=${days}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(setData).catch(() => setErr(true));
  }, [days, token]);

  if (err) return <div className="muted">봇 통계를 불러오지 못했습니다.</div>;
  if (!data) return <Loading />;

  return (
    <div>
      <div className="section-title" style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        봇 차단 현황 <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>크롤러·스크레이퍼·AI봇 차단 로그</span>
        <div className="chip-row" style={{ marginBottom: 0 }}>
          {[1, 7, 30].map((d) => (
            <button key={d} type="button" className={`chip ${days === d ? "active" : ""}`} onClick={() => setDays(d)}>
              {d === 1 ? "오늘" : `${d}일`}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "10px 0 16px" }}>
        <div style={{ flex: "1 1 140px", background: "#f2f6fb", borderRadius: 12, padding: "14px 18px" }}>
          <div className="muted" style={{ fontSize: 12.5 }}>총 차단</div>
          <div style={{ fontSize: 30, fontWeight: 900, color: "#24344d" }}>{data.total.toLocaleString()}건</div>
        </div>
        {data.reasons.slice(0, 4).map((r) => (
          <div key={r.reason} style={{ flex: "1 1 140px", background: "#fff", border: "1px solid #e5ebf3",
            borderLeft: `4px solid ${colorFor(r.reason)}`, borderRadius: 12, padding: "14px 18px" }}>
            <div className="muted" style={{ fontSize: 12.5 }}>{r.label}</div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "#1f2c40" }}>{r.count.toLocaleString()}
              <span style={{ fontSize: 12, fontWeight: 500, color: "#8a97a8" }}> · IP {r.ips}</span></div>
          </div>
        ))}
      </div>

      {data.daily.length > 1 && (
        <>
          <div className="section-title">일별 차단 추이</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.daily} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8edf3" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(5)} minTickGap={16} />
              <YAxis tick={{ fontSize: 11 }} width={40} allowDecimals={false} />
              <Tooltip formatter={(v) => [`${Number(v).toLocaleString()}건`, "차단"]} />
              <Bar dataKey="blocks" fill="#e2574c" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </>
      )}

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginTop: 18 }}>
        <div style={{ flex: "1 1 300px" }}>
          <div className="section-title">사유별 차단</div>
          <table style={{ width: "100%" }}>
            <thead><tr><th>사유</th><th className="num">차단</th><th className="num">고유 IP</th></tr></thead>
            <tbody>
              {data.reasons.map((r) => (
                <tr key={r.reason}>
                  <td><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2,
                    background: colorFor(r.reason), marginRight: 6 }} />{r.label}</td>
                  <td className="num">{r.count.toLocaleString()}</td>
                  <td className="num">{r.ips}</td>
                </tr>
              ))}
              {data.reasons.length === 0 && <tr><td colSpan={3} className="muted">차단 없음</td></tr>}
            </tbody>
          </table>
        </div>
        <div style={{ flex: "1 1 300px" }}>
          <div className="section-title">정상 봇 유입 <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>검증 통과(검색·미리보기)</span></div>
          <table style={{ width: "100%" }}>
            <thead><tr><th>봇</th><th className="num">요청</th></tr></thead>
            <tbody>
              {data.goodbots.map((g) => (
                <tr key={g.bot}><td>{g.bot}</td><td className="num">{g.count.toLocaleString()}</td></tr>
              ))}
              {data.goodbots.length === 0 && <tr><td colSpan={2} className="muted">유입 없음</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginTop: 18 }}>
        <div style={{ flex: "1 1 300px" }}>
          <div className="section-title">상위 차단 IP</div>
          <table style={{ width: "100%" }}>
            <thead><tr><th>IP</th><th className="num">차단</th><th className="num">사유수</th></tr></thead>
            <tbody>
              {data.top_ips.map((r) => (
                <tr key={r.ip}><td style={{ fontFamily: "monospace", fontSize: 12.5 }}>{r.ip}</td>
                  <td className="num">{r.count.toLocaleString()}</td><td className="num">{r.reasons}</td></tr>
              ))}
              {data.top_ips.length === 0 && <tr><td colSpan={3} className="muted">없음</td></tr>}
            </tbody>
          </table>
        </div>
        <div style={{ flex: "1 1 300px" }}>
          <div className="section-title">상위 차단 User-Agent</div>
          <table style={{ width: "100%" }}>
            <thead><tr><th>User-Agent</th><th className="num">차단</th></tr></thead>
            <tbody>
              {data.top_uas.map((r, i) => (
                <tr key={i}><td style={{ fontSize: 11.5, wordBreak: "break-all" }}>{r.ua}</td>
                  <td className="num">{r.count.toLocaleString()}</td></tr>
              ))}
              {data.top_uas.length === 0 && <tr><td colSpan={2} className="muted">없음</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div className="section-title" style={{ marginTop: 18 }}>최근 차단 50건</div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", minWidth: 640 }}>
          <thead><tr><th>시각</th><th>사유</th><th className="num">코드</th><th>IP</th><th>경로</th><th>User-Agent</th></tr></thead>
          <tbody>
            {data.recent.map((r, i) => (
              <tr key={i}>
                <td style={{ whiteSpace: "nowrap", fontSize: 12 }}>{kstTime(r.ts)}</td>
                <td><span style={{ color: colorFor(r.reason), fontWeight: 700, fontSize: 12.5 }}>{r.reason}</span></td>
                <td className="num">{r.status}</td>
                <td style={{ fontFamily: "monospace", fontSize: 12 }}>{r.ip}</td>
                <td style={{ fontSize: 12 }}>{r.path}</td>
                <td style={{ fontSize: 11, wordBreak: "break-all" }}>{r.ua}</td>
              </tr>
            ))}
            {data.recent.length === 0 && <tr><td colSpan={6} className="muted">차단 기록 없음</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
