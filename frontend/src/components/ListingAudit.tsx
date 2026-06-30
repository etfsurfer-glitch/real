import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle, XCircle, CheckCircle2, Loader2, Building2, Square, CheckSquare,
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

const STATUS_STYLE: Record<string, string> = {
  위반: "bg-rose-50 text-rose-700 border-rose-200",
  주의: "bg-amber-50 text-amber-700 border-amber-200",
  통과: "bg-emerald-50 text-emerald-700 border-emerald-200",
};
function StatusIcon({ s }: { s: string }) {
  if (s === "위반") return <XCircle size={14} className="text-rose-500 shrink-0" />;
  if (s === "주의") return <AlertTriangle size={14} className="text-amber-500 shrink-0" />;
  return <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />;
}
function fmtYmd(s: string): string {
  const d = String(s).replace(/\D/g, "");
  if (d.length >= 8) return `${d.slice(0, 4)}.${d.slice(4, 6)}.${d.slice(6, 8)}`;
  if (d.length >= 6) return `${d.slice(0, 4)}.${d.slice(4, 6)}`;
  return s;
}

/**
 * 매물 표시·광고 점검 공용 UI — 유형×거래 분할 → 배치 진행률 → 요약표 → 점검필요 우선.
 * breakdownUrl: 그룹 건수 엔드포인트(경로). buildAuditUrl: 배치 점검 URL 생성기.
 * 관리자(임의 중개사)·라운지(본인 사무소) 양쪽이 같은 화면을 공유한다.
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

  return (
    <div>
      <p className="text-[11px] text-slate-400 mb-3">
        ※ '위반/주의'는 <b className="text-slate-500">표시·광고(광고 작성) 점검</b> 결과입니다 — 건물 자체의 '위반건축물' 여부와는 다릅니다.
      </p>

      {/* 유형×거래 그룹 선택 */}
      {loadingBd ? (
        <div className="text-sm text-slate-400 inline-flex items-center gap-2"><Loader2 size={15} className="animate-spin" /> 매물 불러오는 중…</div>
      ) : groups.length === 0 ? (
        <div className="text-sm text-slate-400">점검할 매물이 없습니다.</div>
      ) : (
        <div className="mb-4">
          <div className="text-xs text-slate-500 mb-2">점검할 유형·거래를 고르세요 (건수 많으면 배치로 진행돼요)</div>
          <div className="flex flex-wrap gap-1.5">
            {groups.map((g) => (
              <button key={`${g.kind}-${g.trade}`} onClick={() => runAudit(g)} disabled={running}
                className={`text-xs px-2.5 py-1.5 rounded-lg border transition disabled:opacity-50 ${
                  group && group.kind === g.kind && group.trade === g.trade
                    ? "bg-indigo-600 text-white border-indigo-600"
                    : "bg-white border-slate-300 hover:border-indigo-300"}`}>
                {g.kind_label} <b>{g.trade_label}</b> <span className="opacity-70">{g.count.toLocaleString()}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 진행률 */}
      {progress && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-slate-600 inline-flex items-center gap-1.5">
              {running ? <><Loader2 size={15} className="animate-spin text-indigo-600" /> 점검 중…</> : <><CheckCircle2 size={15} className="text-emerald-600" /> 점검 완료</>}
              <span className="text-slate-400">{group?.kind_label} {group?.trade_label}</span>
            </span>
            <span className="text-slate-500">{progress.done.toLocaleString()} / {progress.total.toLocaleString()}건</span>
          </div>
          <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full bg-indigo-500 transition-all" style={{ width: `${progress.total ? (progress.done / progress.total) * 100 : 0}%` }} />
          </div>
          {running && <button onClick={() => { cancelRef.current = true; }} className="mt-2 text-xs text-rose-500 hover:text-rose-600">■ 중지</button>}
        </div>
      )}

      {/* 요약표 + 결과 */}
      {results.length > 0 && (
        <>
          <table className="w-full text-sm mb-3 border border-slate-200 rounded-lg overflow-hidden">
            <thead className="bg-slate-50 text-slate-500 text-xs">
              <tr><th className="py-1.5 font-medium">전체</th><th className="py-1.5 font-medium">정상</th><th className="py-1.5 font-medium">점검필요</th><th className="py-1.5 font-medium">위반</th><th className="py-1.5 font-medium">주의</th></tr>
            </thead>
            <tbody className="text-center font-semibold">
              <tr>
                <td className="py-2 text-slate-700">{results.length}</td>
                <td className="py-2 text-emerald-600">{okCount}</td>
                <td className="py-2 text-indigo-600">{problem.length}</td>
                <td className="py-2 text-rose-600">{results.reduce((s, r) => s + r.violation_count, 0)}</td>
                <td className="py-2 text-amber-600">{results.reduce((s, r) => s + r.warning_count, 0)}</td>
              </tr>
            </tbody>
          </table>

          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-slate-600">점검필요 <b className="text-indigo-600">{problem.length}</b>건 {!showPass && okCount > 0 && <span className="text-slate-400">· 정상 {okCount}건 숨김</span>}</span>
            <button onClick={() => setShowPass((v) => !v)} className="text-xs text-slate-500 inline-flex items-center gap-1 hover:text-slate-700">
              {showPass ? <CheckSquare size={14} /> : <Square size={14} />} 정상도 보기
            </button>
          </div>

          <div className="space-y-2">
            {sorted.map((r) => {
              const findings = openCard === r.article_no ? r.findings : r.findings.filter((f) => f.status !== "통과");
              const ok = r.pass && r.warning_count === 0;
              return (
                <div key={r.article_no} className="rounded-xl border border-slate-200 overflow-hidden">
                  <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 border-b border-slate-100 cursor-pointer"
                    onClick={() => setOpenCard(openCard === r.article_no ? null : r.article_no)}>
                    <Building2 size={15} className="text-slate-400 shrink-0" />
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-500">{r.kind}</span>
                    <span className="text-sm font-medium text-slate-700 truncate">{r.building || "—"}</span>
                    {r.is_saengsuk && <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-50 text-violet-600 border border-violet-200">생숙</span>}
                    {r.ledger_matched && <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-50 text-sky-600 border border-sky-200">대장확인</span>}
                    <span className="ml-auto text-xs flex items-center gap-2">
                      {r.violation_count > 0 && <span className="text-rose-600 font-medium">위반 {r.violation_count}</span>}
                      {r.warning_count > 0 && <span className="text-amber-600 font-medium">주의 {r.warning_count}</span>}
                      {ok && <span className="text-emerald-600 font-medium inline-flex items-center gap-1"><CheckCircle2 size={13} />정상</span>}
                    </span>
                  </div>
                  {openCard === r.article_no && r.ledger && (
                    <div className="px-3 py-1.5 text-[11px] text-sky-700 bg-sky-50/60 border-b border-sky-100 flex flex-wrap gap-x-3 gap-y-0.5">
                      <span className="font-semibold">건축물대장</span>
                      {r.ledger.main_purps && <span>용도 {r.ledger.main_purps}</span>}
                      {r.ledger.grnd_flr?.length > 0 && <span>지상 {r.ledger.grnd_flr.join("/")}층</span>}
                      {r.ledger.use_apr_day?.length > 0 && <span>사용승인 {r.ledger.use_apr_day.map(fmtYmd).join("/")}</span>}
                      {r.ledger.parking != null && <span>총주차 {r.ledger.parking}대</span>}
                    </div>
                  )}
                  {findings.length > 0 && (
                    <ul className="divide-y divide-slate-50">
                      {findings.map((f, j) => (
                        <li key={j} className="flex items-start gap-2 px-3 py-1.5 text-sm">
                          <span className="mt-0.5"><StatusIcon s={f.status} /></span>
                          <span className={`text-[11px] px-1.5 py-0.5 rounded border shrink-0 ${STATUS_STYLE[f.status] || ""}`}>{f.status}</span>
                          <span className="text-slate-600"><b className="text-slate-700">{f.no}. {f.item}</b>{f.reason && <span className="text-slate-500"> — {f.reason}</span>}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
            {sorted.length === 0 && !running && (
              <div className="text-center text-sm text-emerald-600 py-6">점검필요 매물이 없습니다 — 모두 정상 👍</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
