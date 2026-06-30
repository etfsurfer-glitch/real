import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle, XCircle, CheckCircle2, Loader2, Building2, Square, CheckSquare, ShieldCheck,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;
const BATCH = 15;

type Finding = { no: number; item: string; status: string; reason: string };
type Ledger = {
  main_purps: string | null; bld_nm: string | null;
  grnd_flr: number[]; use_apr_day: string[]; parking: number | null;
};
export type AuditResult = {
  article_no: string; kind: string; building: string | null; is_saengsuk: boolean;
  ledger_matched?: boolean; ledger?: Ledger | null; findings: Finding[];
  violation_count: number; warning_count: number; pass: boolean;
};
type Group = { kind: string; kind_label: string; trade: string; trade_label: string; count: number; group: string };

const SC: Record<string, { c: string; bg: string; bd: string }> = {
  위반: { c: "#d23b3b", bg: "#fef2f2", bd: "#f6c9c9" },
  주의: { c: "#c4791a", bg: "#fff7ea", bd: "#f5dca8" },
  통과: { c: "#1f9d63", bg: "#eefaf2", bd: "#bfe7cd" },
};
const TRADE_C: Record<string, string> = { A1: "#1268d3", B1: "#7048e8", B2: "#1f9d63" };
const PRIMARY = "#1268d3";
const BORDER = "#e4e9f0";
const SPIN: React.CSSProperties = { animation: "hp-spin .8s linear infinite" };

function SIcon({ s }: { s: string }) {
  if (s === "위반") return <XCircle size={13} style={{ color: "#d23b3b", flexShrink: 0 }} />;
  if (s === "주의") return <AlertTriangle size={13} style={{ color: "#e08a1e", flexShrink: 0 }} />;
  return <CheckCircle2 size={13} style={{ color: "#1f9d63", flexShrink: 0 }} />;
}
function fmtYmd(s: string): string {
  const d = String(s).replace(/\D/g, "");
  if (d.length >= 8) return `${d.slice(0, 4)}.${d.slice(4, 6)}.${d.slice(6, 8)}`;
  if (d.length >= 6) return `${d.slice(0, 4)}.${d.slice(4, 6)}`;
  return s;
}
const pill = (c: string, bg: string, bd: string): React.CSSProperties => ({
  fontSize: 10.5, fontWeight: 700, color: c, background: bg, border: `1px solid ${bd}`,
  borderRadius: 999, padding: "1px 7px", whiteSpace: "nowrap", lineHeight: 1.5,
});

/**
 * 매물 표시·광고 점검 공용 UI(인라인 스타일 — 프로젝트 디자인 토큰). 유형×거래 분할 →
 * 배치 진행률 → 요약표 → 점검필요 우선. 관리자·라운지가 같은 화면 공유.
 */
export default function ListingAudit({ authH, breakdownUrl, buildAuditUrl }: {
  authH: Record<string, string>;
  breakdownUrl: string;
  buildAuditUrl: (kind: string, trade: string, offset: number, limit: number) => string;
}) {
  const [groups, setGroups] = useState<Group[]>([]);
  const [loadingBd, setLoadingBd] = useState(true);
  const [group, setGroup] = useState<Group | null>(null);
  const [results, setResults] = useState<AuditResult[]>([]);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [running, setRunning] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [openCard, setOpenCard] = useState<string | null>(null);
  const cancelRef = useRef(false);

  useEffect(() => {
    if (!API_BASE || !breakdownUrl) return;
    let alive = true;
    setLoadingBd(true); setGroups([]); setGroup(null); setResults([]); setProgress(null);
    fetch(`${API_BASE}${breakdownUrl}`, { headers: authH })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) setGroups(j?.groups ?? []); })
      .catch(() => {})
      .finally(() => { if (alive) setLoadingBd(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [breakdownUrl]);

  async function runAudit(g: Group) {
    setGroup(g); setResults([]); setOpenCard(null);
    setRunning(true); cancelRef.current = false;
    setProgress({ done: 0, total: g.count });
    const acc: AuditResult[] = [];
    let offset = 0;
    while (offset < g.count && !cancelRef.current) {
      try {
        const r = await fetch(`${API_BASE}${buildAuditUrl(g.kind, g.trade, offset, BATCH)}`, { headers: authH });
        if (!r.ok) break;
        const j = await r.json();
        acc.push(...(j.results ?? []));
        offset += j.count ?? 0;
        setResults([...acc]);
        setProgress({ done: Math.min(offset, g.count), total: g.count });
        if (!j.count || j.count < BATCH) break;
      } catch { break; }
    }
    setRunning(false);
  }

  const problem = results.filter((r) => !r.pass);
  const okCount = results.length - problem.length;
  const shown = showPass ? results : problem;
  const sorted = [...shown].sort((a, b) => (b.violation_count - a.violation_count) || (b.warning_count - a.warning_count));
  const sumV = results.reduce((s, r) => s + r.violation_count, 0);
  const sumW = results.reduce((s, r) => s + r.warning_count, 0);

  return (
    <div>
      <p className="muted" style={{ fontSize: 11.5, margin: "0 0 12px", lineHeight: 1.5 }}>
        ※ ‘위반/주의’는 <b style={{ color: "#475569" }}>표시·광고(광고 작성) 점검</b> 결과입니다 — 건물 자체의 ‘위반건축물’ 여부와는 다릅니다.
      </p>

      {/* 유형×거래 그룹 선택 */}
      {loadingBd ? (
        <div className="muted" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
          <Loader2 size={15} style={SPIN} /> 매물 불러오는 중…
        </div>
      ) : groups.length === 0 ? (
        <div className="cdash-empty">점검할 매물이 없습니다.</div>
      ) : (
        <div style={{ marginBottom: 16 }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 9 }}>점검할 유형·거래를 고르세요 · 건수 많으면 자동 배치로 진행돼요</div>
          {(["단지형", "비단지"] as const).map((sec) => {
            const gs = groups.filter((g) => g.group === sec);
            if (gs.length === 0) return null;
            return (
              <div key={sec} style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 800, color: "#94a3b8", margin: "0 2px 7px", letterSpacing: ".02em" }}>{sec}</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(118px, 1fr))", gap: 8 }}>
                  {gs.map((g) => {
                    const active = !!group && group.kind === g.kind && group.trade === g.trade;
                    return (
                      <button key={`${g.kind}-${g.trade}`} onClick={() => runAudit(g)} disabled={running}
                        style={{
                          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6,
                          padding: "9px 11px", borderRadius: 12, textAlign: "left", cursor: running ? "default" : "pointer",
                          border: `1px solid ${active ? PRIMARY : BORDER}`,
                          background: active ? "#f3f7fe" : "#fff",
                          boxShadow: active ? `0 0 0 1px ${PRIMARY}` : "none",
                          opacity: running && !active ? 0.55 : 1, transition: "all .12s",
                        }}>
                        <span style={{ minWidth: 0 }}>
                          <span style={{ display: "block", fontSize: 13, fontWeight: 700, color: "#1f2937", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {g.kind === "SAENGSUK" && <ShieldCheck size={11} style={{ verticalAlign: "-1px", marginRight: 2, color: "#7c3aed" }} />}
                            {g.kind_label}
                          </span>
                          <span style={{ ...pill(TRADE_C[g.trade] || "#64748b", "#f1f5fb", "#dde6f3"), marginTop: 4, display: "inline-block" }}>{g.trade_label}</span>
                        </span>
                        <span style={{ fontSize: 17, fontWeight: 800, color: PRIMARY, fontVariantNumeric: "tabular-nums" }}>{g.count.toLocaleString()}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 진행률 */}
      {progress && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13, marginBottom: 6 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "#475569" }}>
              {running
                ? <><Loader2 size={14} style={{ color: PRIMARY, ...SPIN }} /> 점검 중…</>
                : <><CheckCircle2 size={14} style={{ color: "#1f9d63" }} /> 점검 완료</>}
              <span className="muted">{group?.kind_label} {group?.trade_label}</span>
            </span>
            <span className="muted">{progress.done.toLocaleString()} / {progress.total.toLocaleString()}건</span>
          </div>
          <div style={{ height: 8, borderRadius: 99, background: "#eef2f7", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${progress.total ? (progress.done / progress.total) * 100 : 0}%`, background: PRIMARY, borderRadius: 99, transition: "width .2s" }} />
          </div>
          {running && <button onClick={() => { cancelRef.current = true; }} style={{ marginTop: 7, fontSize: 12, color: "#d23b3b", background: "none", border: "none", cursor: "pointer", padding: 0 }}>■ 중지</button>}
        </div>
      )}

      {/* 요약표 + 결과 */}
      {results.length > 0 && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, marginBottom: 14 }}>
            {[
              ["전체", results.length, "#334155"], ["정상", okCount, "#1f9d63"],
              ["점검필요", problem.length, PRIMARY], ["위반", sumV, "#d23b3b"], ["주의", sumW, "#e08a1e"],
            ].map(([label, val, color]) => (
              <div key={label as string} style={{ border: `1px solid ${BORDER}`, borderRadius: 12, padding: "10px 4px", textAlign: "center", background: "#fff" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: color as string, fontVariantNumeric: "tabular-nums" }}>{val as number}</div>
                <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{label as string}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 9 }}>
            <span style={{ fontSize: 13, color: "#475569" }}>점검필요 <b style={{ color: PRIMARY }}>{problem.length}</b>건{!showPass && okCount > 0 && <span className="muted"> · 정상 {okCount}건 숨김</span>}</span>
            <button onClick={() => setShowPass((v) => !v)} style={{ fontSize: 12, color: "#64748b", background: "none", border: "none", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4, padding: 0 }}>
              {showPass ? <CheckSquare size={14} /> : <Square size={14} />} 정상도 보기
            </button>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {sorted.map((r) => {
              const open = openCard === r.article_no;
              const findings = open ? r.findings : r.findings.filter((f) => f.status !== "통과");
              const ok = r.pass && r.warning_count === 0;
              return (
                <div key={r.article_no} style={{ border: `1px solid ${BORDER}`, borderRadius: 13, overflow: "hidden", background: "#fff" }}>
                  <div onClick={() => setOpenCard(open ? null : r.article_no)}
                    style={{ display: "flex", alignItems: "center", gap: 7, padding: "9px 12px", background: "#f8fafc", borderBottom: open ? `1px solid #eef2f7` : "none", cursor: "pointer" }}>
                    <Building2 size={14} style={{ color: "#94a3b8", flexShrink: 0 }} />
                    <span style={pill("#64748b", "#fff", "#e2e8f0")}>{r.kind}</span>
                    <span style={{ fontSize: 13.5, fontWeight: 600, color: "#1f2937", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.building || "—"}</span>
                    {r.is_saengsuk && <span style={pill("#7c3aed", "#f5f1fe", "#e0d4fb")}>생숙</span>}
                    {r.ledger_matched && <span style={pill("#1268d3", "#eef4ff", "#cfe0ff")}>대장확인</span>}
                    <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, fontSize: 12, flexShrink: 0 }}>
                      {r.violation_count > 0 && <span style={{ color: "#d23b3b", fontWeight: 700 }}>위반 {r.violation_count}</span>}
                      {r.warning_count > 0 && <span style={{ color: "#e08a1e", fontWeight: 700 }}>주의 {r.warning_count}</span>}
                      {ok && <span style={{ color: "#1f9d63", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 3 }}><CheckCircle2 size={12} />정상</span>}
                    </span>
                  </div>
                  {open && r.ledger && (
                    <div style={{ padding: "7px 12px", fontSize: 11, color: "#0e6aa8", background: "#f3f9ff", borderBottom: "1px solid #e2effb", display: "flex", flexWrap: "wrap", columnGap: 12, rowGap: 2 }}>
                      <span style={{ fontWeight: 700 }}>건축물대장</span>
                      {r.ledger.main_purps && <span>용도 {r.ledger.main_purps}</span>}
                      {r.ledger.grnd_flr?.length > 0 && <span>지상 {r.ledger.grnd_flr.join("/")}층</span>}
                      {r.ledger.use_apr_day?.length > 0 && <span>사용승인 {r.ledger.use_apr_day.map(fmtYmd).join("/")}</span>}
                      {r.ledger.parking != null && <span>총주차 {r.ledger.parking}대</span>}
                    </div>
                  )}
                  {findings.length > 0 && (
                    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                      {findings.map((f, j) => (
                        <li key={j} style={{ display: "flex", alignItems: "flex-start", gap: 7, padding: "7px 12px", fontSize: 13, borderTop: j ? "1px solid #f4f7fa" : "none" }}>
                          <span style={{ marginTop: 2 }}><SIcon s={f.status} /></span>
                          <span style={{ ...pill(SC[f.status]?.c || "#64748b", SC[f.status]?.bg || "#f1f5f9", SC[f.status]?.bd || "#e2e8f0"), flexShrink: 0 }}>{f.status}</span>
                          <span style={{ color: "#475569" }}><b style={{ color: "#334155" }}>{f.no}. {f.item}</b>{f.reason && <span> — {f.reason}</span>}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
            {sorted.length === 0 && !running && (
              <div style={{ textAlign: "center", fontSize: 13, color: "#1f9d63", padding: "22px 0" }}>점검필요 매물이 없습니다 — 모두 정상 👍</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
