import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle, XCircle, CheckCircle2, Loader2, Building2, Square, CheckSquare, ShieldCheck,
  Info, X,
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
  address?: string | null; naver_url?: string | null;
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
const TRADE_ORDER = ["A1", "B1", "B2"];   // 매매 → 전세 → 월세
const helpBtnStyle: React.CSSProperties = {
  display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11.5, fontWeight: 600,
  color: "#5b6b80", background: "#f1f5fb", border: "1px solid #dde6f3", borderRadius: 999,
  padding: "3px 9px", cursor: "pointer", marginLeft: 7,
};

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
export default function ListingAudit({ authH, breakdownUrl, buildAuditUrl, intro, title }: {
  authH: Record<string, string>;
  breakdownUrl: string;
  buildAuditUrl: (kind: string, trade: string, offset: number, limit: number) => string;
  intro?: string;
  title?: string;
}) {
  const [showHelp, setShowHelp] = useState(false);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loadingBd, setLoadingBd] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [results, setResults] = useState<AuditResult[]>([]);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [running, setRunning] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [openCard, setOpenCard] = useState<string | null>(null);
  const cancelRef = useRef(false);

  useEffect(() => {
    if (!API_BASE || !breakdownUrl) return;
    let alive = true;
    setLoadingBd(true); setGroups([]); setSelected(new Set()); setResults([]); setProgress(null);
    fetch(`${API_BASE}${breakdownUrl}`, { headers: authH })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) setGroups(j?.groups ?? []); })
      .catch(() => {})
      .finally(() => { if (alive) setLoadingBd(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [breakdownUrl]);

  const gkey = (g: { kind: string; trade: string }) => `${g.kind}|${g.trade}`;
  function toggle(g: Group) {
    setSelected((prev) => {
      const n = new Set(prev); const k = gkey(g);
      if (n.has(k)) n.delete(k); else n.add(k);
      return n;
    });
  }
  function toggleKind(trades: Group[]) {
    setSelected((prev) => {
      const n = new Set(prev); const keys = trades.map(gkey);
      const allOn = keys.every((k) => n.has(k));
      keys.forEach((k) => (allOn ? n.delete(k) : n.add(k)));
      return n;
    });
  }
  const selGroups = groups.filter((g) => selected.has(gkey(g)));
  const selCount = selGroups.reduce((s, g) => s + g.count, 0);

  async function runBulk() {
    if (!selGroups.length) return;
    setResults([]); setOpenCard(null); setRunning(true); cancelRef.current = false;
    const grand = selCount;
    setProgress({ done: 0, total: grand });
    const acc: AuditResult[] = [];
    let done = 0;
    for (const g of selGroups) {
      if (cancelRef.current) break;
      let offset = 0;
      while (offset < g.count && !cancelRef.current) {
        try {
          const r = await fetch(`${API_BASE}${buildAuditUrl(g.kind, g.trade, offset, BATCH)}`, { headers: authH });
          if (!r.ok) break;
          const j = await r.json();
          acc.push(...(j.results ?? []));
          const got = j.count ?? 0;
          offset += got; done += got;
          setResults([...acc]);
          setProgress({ done: Math.min(done, grand), total: grand });
          if (!got || got < BATCH) break;
        } catch { break; }
      }
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
      {title ? (
        <div className="cdash-h" style={{ margin: "0 2px 12px" }}>
          <h3 style={{ gap: 6 }}><ShieldCheck size={15} strokeWidth={2.3} /> {title}
            <button onClick={() => setShowHelp(true)} style={helpBtnStyle}><Info size={12} /> 설명</button>
          </h3>
        </div>
      ) : (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
          <button onClick={() => setShowHelp(true)} style={{ ...helpBtnStyle, marginLeft: 0 }}><Info size={13} /> 설명</button>
        </div>
      )}

      {/* 유형(아파트·오피스텔·생숙…) 행 + 매매·전세·월세 순서 버튼 */}
      {loadingBd ? (
        <div className="muted" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
          <Loader2 size={15} style={SPIN} /> 매물 불러오는 중…
        </div>
      ) : groups.length === 0 ? (
        <div className="cdash-empty">점검할 매물이 없습니다.</div>
      ) : (
        <div style={{ marginBottom: 14 }}>
          <div className="muted" style={{ fontSize: 11.5, margin: "0 2px 9px" }}>유형 이름을 누르면 그 유형 전체, 매매·전세·월세는 개별 선택 — 선택 후 아래 <b style={{ color: "#475569" }}>일괄조회</b></div>
          {(["단지형", "비단지"] as const).map((sec) => {
            const gs = groups.filter((g) => g.group === sec);
            if (gs.length === 0) return null;
            const byKind = new Map<string, { label: string; trades: Group[] }>();
            for (const g of gs) {
              if (!byKind.has(g.kind)) byKind.set(g.kind, { label: g.kind_label, trades: [] });
              byKind.get(g.kind)!.trades.push(g);
            }
            const kinds = [...byKind.entries()].sort((a, b) =>
              b[1].trades.reduce((s, t) => s + t.count, 0) - a[1].trades.reduce((s, t) => s + t.count, 0));
            return (
              <div key={sec} style={{ marginBottom: 11 }}>
                <div style={{ fontSize: 11, fontWeight: 800, color: "#94a3b8", margin: "0 2px 8px", letterSpacing: ".02em" }}>{sec}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {kinds.map(([kind, info]) => {
                    const allSel = info.trades.every((t) => selected.has(gkey(t)));
                    return (
                      <div key={kind} style={{ display: "flex", alignItems: "center", gap: 9 }}>
                        <button onClick={() => !running && toggleKind(info.trades)} title="유형 전체 선택/해제"
                          style={{ width: 88, flexShrink: 0, fontSize: 13, fontWeight: 700, color: allSel ? PRIMARY : "#1f2937",
                            display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", textAlign: "left", padding: 0, cursor: running ? "default" : "pointer" }}>
                          {allSel ? <CheckSquare size={14} style={{ color: PRIMARY, flexShrink: 0 }} /> : <Square size={14} style={{ color: "#cbd5e1", flexShrink: 0 }} />}
                          {kind === "SAENGSUK" && <ShieldCheck size={11} style={{ color: "#7c3aed", flexShrink: 0 }} />}
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{info.label}</span>
                        </button>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                          {TRADE_ORDER.map((t) => {
                            const g = info.trades.find((x) => x.trade === t);
                            if (!g) return null;
                            const sel = selected.has(gkey(g));
                            const tc = TRADE_C[t] || "#64748b";
                            return (
                              <button key={t} onClick={() => !running && toggle(g)} disabled={running}
                                style={{
                                  display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 11px",
                                  borderRadius: 10, cursor: running ? "default" : "pointer", fontSize: 12.5,
                                  border: `1px solid ${sel ? tc : BORDER}`,
                                  background: sel ? tc : "#fff", color: sel ? "#fff" : "#334155",
                                  opacity: running ? 0.6 : 1, transition: "all .12s",
                                }}>
                                {sel && <CheckSquare size={11} />}
                                <span style={{ fontWeight: 600 }}>{g.trade_label}</span>
                                <span style={{ fontWeight: 800, color: sel ? "#fff" : tc, fontVariantNumeric: "tabular-nums" }}>{g.count.toLocaleString()}</span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}

          <button onClick={runBulk} disabled={running || selGroups.length === 0}
            style={{ marginTop: 8, width: "100%", padding: 12, borderRadius: 11, border: "none",
              background: selGroups.length && !running ? PRIMARY : "#cbd5e1", color: "#fff", fontSize: 14, fontWeight: 800,
              cursor: running || !selGroups.length ? "default" : "pointer",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 7 }}>
            <ShieldCheck size={16} />
            {selGroups.length ? `선택 ${selGroups.length}개 · ${selCount.toLocaleString()}건 일괄조회` : "점검할 유형·거래를 선택하세요"}
          </button>
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
              <span className="muted">선택 {selGroups.length}개 유형·거래</span>
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
                  <div style={{ padding: "5px 12px", fontSize: 11, color: "#94a3b8", borderBottom: "1px solid #f4f7fa", display: "flex", flexWrap: "wrap", alignItems: "center", gap: 5 }}>
                    {r.address && <span>📍 {r.address}</span>}
                    {r.address && <span style={{ color: "#cbd5e1" }}>·</span>}
                    {r.naver_url
                      ? <a href={r.naver_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} style={{ fontSize: 11, color: PRIMARY, fontWeight: 600 }}>네이버 매물 {r.article_no} ↗</a>
                      : <span>매물번호 {r.article_no}</span>}
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

      {showHelp && (
        <div onClick={() => setShowHelp(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 16 }}>
          <div onClick={(e) => e.stopPropagation()}
            style={{ background: "#fff", borderRadius: 16, maxWidth: 420, width: "100%", padding: "20px 20px 18px", boxShadow: "0 14px 44px rgba(0,0,0,.2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 12 }}>
              <ShieldCheck size={18} style={{ color: PRIMARY }} />
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "#13294b", flex: 1 }}>매물 표시·광고 점검 안내</h3>
              <button onClick={() => setShowHelp(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "#94a3b8", padding: 2, display: "flex" }}><X size={18} /></button>
            </div>
            <p style={{ margin: "0 0 12px", fontSize: 13, lineHeight: 1.6, color: "#475569" }}>
              {intro || "매물의 표시·광고 의무사항(층·면적·주차·관리비·방향 등) 누락을 점검하고, 건축물대장 기준값과 자동 대조합니다."}
            </p>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.7, color: "#64748b" }}>
              <li>유형·거래를 골라 점검하세요. 건수가 많으면 자동으로 배치로 나눠 진행됩니다.</li>
              <li><b style={{ color: "#475569" }}>‘위반/주의’는 표시·광고(광고 작성) 점검</b> 결과입니다 — 건물 자체의 ‘위반건축물’ 여부와는 다릅니다.</li>
              <li>비단지(빌라·상가 등)는 건축물대장과 대조하고, 단지형은 CP 자동입력 항목을 확인합니다.</li>
            </ul>
            <button onClick={() => setShowHelp(false)}
              style={{ marginTop: 16, width: "100%", padding: 10, borderRadius: 10, border: "none", background: PRIMARY, color: "#fff", fontSize: 13.5, fontWeight: 700, cursor: "pointer" }}>
              확인
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
