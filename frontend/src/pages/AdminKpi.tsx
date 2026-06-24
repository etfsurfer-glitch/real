import { useEffect, useState, useCallback } from "react";
import { Target, Pencil, Check } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;
type Tier = { tier: number; target: number; deadline: string };
type Metric = { key: string; label: string; unit: string; current: number; tiers: Tier[] };
const TIER_LABEL = ["", "1차", "2차", "3차"];
type Draft = Record<string, { target: number; deadline: string }>;

export default function AdminKpi() {
  const { token } = useAuth();
  const [metrics, setMetrics] = useState<Metric[] | null>(null);
  const [edit, setEdit] = useState(false);
  const [draft, setDraft] = useState<Draft>({});

  const load = useCallback(() => {
    if (!token || !API) return;
    fetch(`${API}/admin/kpi`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then((d) => setMetrics(d.metrics || [])).catch(() => setMetrics([]));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const startEdit = () => {
    const d: Draft = {};
    metrics?.forEach((m) => m.tiers.forEach((t) => { d[`${m.key}_${t.tier}`] = { target: t.target, deadline: t.deadline }; }));
    setDraft(d); setEdit(true);
  };
  const save = async () => {
    for (const m of metrics || []) {
      for (const t of m.tiers) {
        const dv = draft[`${m.key}_${t.tier}`];
        if (dv && (dv.target !== t.target || dv.deadline !== t.deadline)) {
          await fetch(`${API}/admin/kpi/target`, {
            method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
            body: JSON.stringify({ metric: m.key, tier: t.tier, target: Number(dv.target), deadline: dv.deadline }),
          });
        }
      }
    }
    setEdit(false); load();
  };

  if (!metrics) return <div className="muted" style={{ padding: 24 }}>불러오는 중…</div>;
  return (
    <div className="kpi">
      <div className="kpi-head">
        <h2><Target size={19} strokeWidth={2.3} aria-hidden /> KPI 목표 추적</h2>
        {edit
          ? <button className="kpi-save" onClick={save}><Check size={15} /> 저장</button>
          : <button className="kpi-edit" onClick={startEdit}><Pencil size={13} /> 목표 수정</button>}
      </div>
      <div className="kpi-grid">
        {metrics.map((m) => (
          <div key={m.key} className="kpi-card">
            <div className="kpi-label">{m.label}</div>
            <div className="kpi-cur">{m.current.toLocaleString()}<span>{m.unit}</span></div>
            {m.tiers.map((t) => {
              const dk = `${m.key}_${t.tier}`;
              const tgt = edit ? (draft[dk]?.target ?? t.target) : t.target;
              const pct = Math.min(100, Math.round((m.current / Math.max(tgt, 1)) * 100));
              const done = m.current >= tgt;
              return (
                <div key={t.tier} className="kpi-tier">
                  <div className="kpi-tier-h">
                    <span className="kpi-tier-n">{TIER_LABEL[t.tier]}</span>
                    {edit ? (
                      <>
                        <input type="number" className="kpi-in-num" value={draft[dk]?.target ?? t.target}
                          onChange={(e) => setDraft((d) => ({ ...d, [dk]: { target: Number(e.target.value), deadline: d[dk]?.deadline ?? t.deadline } }))} />
                        <input type="date" className="kpi-in-date" value={draft[dk]?.deadline ?? t.deadline}
                          onChange={(e) => setDraft((d) => ({ ...d, [dk]: { target: d[dk]?.target ?? t.target, deadline: e.target.value } }))} />
                      </>
                    ) : (
                      <>
                        <span className="kpi-tgt">{tgt.toLocaleString()}{m.unit}</span>
                        <span className="kpi-dl">~{t.deadline}</span>
                        {done && <span className="kpi-done">달성</span>}
                      </>
                    )}
                  </div>
                  {!edit && (
                    <div className="kpi-bar">
                      <div className={`kpi-bar-fill ${done ? "done" : ""}`} style={{ width: `${pct}%` }} />
                      <span className="kpi-pct">{pct}%</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <p className="muted" style={{ fontSize: 11.5, marginTop: 14 }}>
        방문자=이번 달 일평균 순수방문(고유 IP) · 가입자=누적 회원 · 홈페이지=개설된 중개사 홈페이지. 1차=올해말·2차=내년상반기·3차=내년하반기.
      </p>
    </div>
  );
}
