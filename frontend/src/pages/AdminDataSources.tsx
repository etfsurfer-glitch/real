import { useEffect, useState, useCallback } from "react";
import { Database, RefreshCw, CheckCircle2, AlertTriangle, AlertCircle, Clock, Info, HardDrive } from "lucide-react";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

type Source = {
  key: string; name: string; category: string; source: string;
  cycle: string; rows: number; last_collected: string | null;
  days_ago: number | null; latest_data: string | null; status: string;
};
type Resp = { checked_at: string; sources: Source[] };
type Disk = { name: string; role: string; mount: string; total: number; used: number;
              free: number; pct: number; at?: string };
type DiskResp = { checked_at: string; disks: Disk[]; remote: Disk[];
                  top: { path: string; name: string; where: string; size: number }[] };

function gb(n: number): string {
  if (n >= 1024 ** 4) return `${(n / 1024 ** 4).toFixed(1)}TB`;
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(n >= 10 * 1024 ** 3 ? 0 : 1)}GB`;
  return `${Math.max(1, Math.round(n / 1024 ** 2))}MB`;
}
/** 용량은 남은 여유가 중요하다 — 95% 넘으면 수집·백업이 실패할 수 있다. */
function diskLevel(pct: number): { label: string; color: string; bg: string } {
  if (pct >= 95) return { label: "위험", color: "#b91c1c", bg: "#fee2e2" };
  if (pct >= 85) return { label: "주의", color: "#b45309", bg: "#fef3c7" };
  return { label: "여유", color: "#15803d", bg: "#dcfce7" };
}

function DiskSection({ token }: { token: string | null }) {
  const [d, setD] = useState<DiskResp | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!API_BASE || !token) return;
    fetch(`${API_BASE}/admin/server-disk`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`서버 응답 ${r.status}`))))
      .then(setD).catch((e) => setErr(e?.message || "불러오지 못했어요."));
  }, [token]);

  if (err) return <div className="dsrc-msg">저장공간 정보를 불러오지 못했어요. {err}</div>;
  if (!d) return null;
  const all = [...d.disks, ...d.remote];
  const worst = all.reduce((m, x) => Math.max(m, x.pct), 0);

  return (
    <div className="dsrc-cat">
      <h3 className="dsrc-cat-t">서버 저장공간</h3>
      <p className="dsrc-sub" style={{ marginTop: -2 }}>
        디스크가 가득 차면 <b>수집·백업이 통째로 멈춥니다</b>.
        {worst >= 95 ? " 지금 정리가 필요한 디스크가 있어요."
          : worst >= 85 ? " 여유가 넉넉하지는 않아요." : " 현재는 여유가 있습니다."}
      </p>
      <div className="dsrc-grid">
        {all.map((x) => {
          const lv = diskLevel(x.pct);
          return (
            <div key={x.name + x.mount} className="dsrc-card">
              <div className="dsrc-card-top">
                <span className="dsrc-name">
                  <HardDrive size={13} strokeWidth={2.4} aria-hidden /> {x.name}
                </span>
                <span className="dsrc-badge" style={{ color: lv.color, background: lv.bg }}>
                  {lv.label} {x.pct}%
                </span>
              </div>
              <div className="dsrc-bar"><i style={{ width: `${Math.min(100, x.pct)}%`, background: lv.color }} /></div>
              <div className="dsrc-rows">
                남은 용량 {gb(x.free)} <span className="dsrc-rows-exact">/ 전체 {gb(x.total)}</span>
              </div>
              <div className="dsrc-meta">
                <div><span>쓰는 곳</span><b>{x.role || "—"}</b></div>
                <div><span>사용 중</span><b>{gb(x.used)}</b></div>
                <div><span>경로</span><b>{x.mount}</b></div>
                {x.at && <div><span>보고 시각</span><b>{x.at.slice(5, 16)}</b></div>}
              </div>
            </div>
          );
        })}
      </div>
      {d.top.length > 0 && (
        <p className="dsrc-note" style={{ marginTop: 10 }}>
          <Info size={12} strokeWidth={2.4} aria-hidden /> 용량을 많이 쓰는 항목 —{" "}
          {d.top.slice(0, 5).map((t, i) => (
            <span key={t.path}>{i > 0 && " · "}<b>{t.name}</b> {gb(t.size)}<span className="muted"> ({t.where})</span></span>
          ))}
        </p>
      )}
    </div>
  );
}

const STATUS: Record<string, { label: string; color: string; bg: string; Icon: typeof CheckCircle2 }> = {
  ok: { label: "정상", color: "#15803d", bg: "#dcfce7", Icon: CheckCircle2 },
  delay: { label: "지연", color: "#b45309", bg: "#fef3c7", Icon: AlertTriangle },
  stale: { label: "점검 필요", color: "#b91c1c", bg: "#fee2e2", Icon: AlertCircle },
  unknown: { label: "수시 갱신", color: "#64748b", bg: "#f1f5f9", Icon: Clock },
};

function relDay(d: number | null): string {
  if (d == null) return "—";
  if (d <= 0) return "오늘";
  if (d === 1) return "어제";
  return `${d}일 전`;
}
function abbrev(n: number): string {
  if (n >= 1e8) return `약 ${(n / 1e8).toFixed(1)}억`;
  if (n >= 1e4) return `약 ${Math.round(n / 1e4).toLocaleString()}만`;
  return n.toLocaleString();
}

export default function AdminDataSources() {
  const { token } = useAuth();
  const [data, setData] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string>("");

  const load = useCallback(() => {
    if (!API_BASE) { setErr("API 주소가 설정되지 않았습니다."); setLoading(false); return; }
    if (!token) { setErr(""); setLoading(false); return; }   // 토큰 도착 후 재시도
    setLoading(true); setErr("");
    fetch(`${API_BASE}/admin/data-sources`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) throw new Error(`서버 응답 ${r.status}${r.status === 401 ? " — 로그인이 만료됐어요. 다시 로그인해 주세요." : ""}`);
        return r.json();
      })
      .then((d) => { setData(d); setErr(""); })
      .catch((e) => setErr(e?.message || "불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const cats = data ? Array.from(new Set(data.sources.map((s) => s.category))) : [];
  const issues = data ? data.sources.filter((s) => s.status === "delay" || s.status === "stale").length : 0;

  return (
    <div className="dsrc">
      <div className="dsrc-head">
        <h2><Database size={20} strokeWidth={2.3} aria-hidden /> 수집 데이터 현황</h2>
        <button className="dsrc-refresh" onClick={load} disabled={loading}>
          <RefreshCw size={14} strokeWidth={2.4} aria-hidden /> 새로고침
        </button>
      </div>
      <p className="dsrc-sub">
        콕집이 모으는 데이터 소스별 <b>수집 주기·마지막 수집·최신성</b>입니다.
        {data && (issues === 0 ? " 현재 모든 소스가 정상이에요." : ` ${issues}개 소스가 점검이 필요해요.`)}
      </p>

      <DiskSection token={token} />

      {loading && !data ? <div className="dsrc-msg">불러오는 중…</div>
        : err && !data ? <div className="dsrc-msg">{err}<br /><button className="dsrc-refresh" style={{ marginTop: 10 }} onClick={load}><RefreshCw size={14} strokeWidth={2.4} aria-hidden /> 다시 시도</button></div>
        : !data ? <div className="dsrc-msg">표시할 데이터가 없어요.</div>
        : cats.map((cat) => {
          const isTx = cat.includes("실거래");
          return (
            <div key={cat} className="dsrc-cat">
              <h3 className="dsrc-cat-t">{cat}</h3>
              <div className="dsrc-grid">
                {data.sources.filter((s) => s.category === cat).map((s) => {
                  const st = STATUS[s.status] ?? STATUS.unknown;
                  return (
                    <div key={s.key} className="dsrc-card">
                      <div className="dsrc-card-top">
                        <span className="dsrc-name">{s.name}</span>
                        <span className="dsrc-badge" style={{ color: st.color, background: st.bg }}>
                          <st.Icon size={12} strokeWidth={2.6} aria-hidden /> {st.label}
                        </span>
                      </div>
                      <div className="dsrc-rows">{abbrev(s.rows)}건 <span className="dsrc-rows-exact">({s.rows.toLocaleString()})</span></div>
                      <div className="dsrc-meta">
                        <div><span>수집 주기</span><b>{s.cycle}</b></div>
                        <div><span>마지막 수집</span><b className={s.status === "stale" ? "dsrc-bad" : s.status === "delay" ? "dsrc-warn" : ""}>
                          {relDay(s.days_ago)}{s.last_collected ? ` · ${s.last_collected}` : ""}</b></div>
                        {s.latest_data && <div><span>{isTx ? "최근 계약일" : "최신 스냅샷"}</span><b>{s.latest_data}</b></div>}
                        <div><span>출처</span><b>{s.source}</b></div>
                      </div>
                    </div>
                  );
                })}
              </div>
              {isTx && (
                <p className="dsrc-note"><Info size={12} strokeWidth={2.4} aria-hidden /> 국토부 실거래는 <b>계약 후 30일 내 신고제</b>라, 최근 계약일 데이터는 신고가 계속 들어오며 완성되어 갑니다. 그래서 신선도 판단은 <b>‘마지막 수집’ 시각</b> 기준입니다.</p>
              )}
            </div>
          );
        })}
      {data && <p className="dsrc-checked">점검 시각 {new Date(data.checked_at).toLocaleString("ko-KR")}</p>}
    </div>
  );
}
