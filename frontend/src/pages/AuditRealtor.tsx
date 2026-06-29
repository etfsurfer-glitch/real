import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ShieldCheck, AlertTriangle, XCircle, CheckCircle2, ChevronLeft, Loader2, Building2,
} from "lucide-react";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

type Finding = { no: number; item: string; status: string; reason: string };
type Ledger = {
  main_purps: string | null;
  bld_nm: string | null;
  grnd_flr: number[];
  use_apr_day: string[];
  parking: number | null;
};
type Result = {
  article_no: string;
  kind: string;
  building: string | null;
  is_saengsuk: boolean;
  ledger_matched?: boolean;
  ledger?: Ledger | null;
  findings: Finding[];
  violation_count: number;
  warning_count: number;
  pass: boolean;
};
type Report = {
  realtor_id: string;
  count: number;
  violation_total: number;
  warning_total: number;
  results: Result[];
};

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

export default function AuditRealtor() {
  const { token } = useAuth();
  const [rid, setRid] = useState("");
  const [limit, setLimit] = useState(15);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [showAll, setShowAll] = useState(false);

  async function run() {
    if (!rid.trim() || !token || !API_BASE) return;
    setLoading(true);
    setErr(null);
    setReport(null);
    try {
      const r = await fetch(
        `${API_BASE}/admin/audit/realtor?realtor_id=${encodeURIComponent(rid.trim())}&limit=${limit}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!r.ok) throw new Error(`${r.status}`);
      setReport(await r.json());
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <Link to="/admin" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-3">
        <ChevronLeft size={16} /> 관리자
      </Link>

      <div className="flex items-center gap-2 mb-1">
        <ShieldCheck size={22} className="text-indigo-600" />
        <h1 className="text-xl font-bold text-slate-800">매물 표시·광고 점검</h1>
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-200">
          가오픈 · 관리자 전용
        </span>
      </div>
      <p className="text-sm text-slate-500 mb-4">
        중개대상물 인터넷 표시·광고 체크리스트 자동 점검. 단지형(아파트·오피)은 CP 자동입력 항목 제외,
        비단지(빌라·단독·상가)는 건축물대장 대조.
      </p>

      <div className="flex flex-wrap items-end gap-2 mb-5 p-3 rounded-xl bg-slate-50 border border-slate-200">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-slate-500 mb-1">중개사 ID (realtor_id)</label>
          <input
            value={rid}
            onChange={(e) => setRid(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder="예: midas0032"
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">유형별 최대</label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="px-2 py-2 rounded-lg border border-slate-300 text-sm"
          >
            {[10, 15, 25, 40].map((n) => <option key={n} value={n}>{n}건</option>)}
          </select>
        </div>
        <button
          onClick={run}
          disabled={loading || !rid.trim()}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 inline-flex items-center gap-1.5"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
          점검
        </button>
      </div>

      {loading && (
        <p className="text-sm text-slate-500 flex items-center gap-2">
          <Loader2 size={16} className="animate-spin" /> 매물 상세·건축물대장 조회 중… (수십 건이면 10~30초)
        </p>
      )}
      {err && <p className="text-sm text-rose-600">오류: {err}</p>}

      {report && (
        <>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <Stat label="점검 매물" value={report.count} tone="slate" />
            <Stat label="위반" value={report.violation_total} tone="rose" />
            <Stat label="주의" value={report.warning_total} tone="amber" />
          </div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-slate-500">{report.results.length}건 결과</span>
            <label className="text-xs text-slate-500 inline-flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
              통과 항목도 표시
            </label>
          </div>

          <div className="space-y-2">
            {report.results.map((r, i) => {
              const shown = showAll ? r.findings : r.findings.filter((f) => f.status !== "통과");
              const ok = r.violation_count === 0 && r.warning_count === 0;
              return (
                <div key={i} className="rounded-xl border border-slate-200 overflow-hidden">
                  <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 border-b border-slate-100">
                    <Building2 size={15} className="text-slate-400 shrink-0" />
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-500">
                      {r.kind}
                    </span>
                    <span className="text-sm font-medium text-slate-700 truncate">{r.building || "—"}</span>
                    {r.is_saengsuk && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-50 text-violet-600 border border-violet-200">생숙</span>
                    )}
                    {r.ledger_matched && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-50 text-sky-600 border border-sky-200">대장대조</span>
                    )}
                    <span className="ml-auto text-xs flex items-center gap-2">
                      {r.violation_count > 0 && <span className="text-rose-600 font-medium">위반 {r.violation_count}</span>}
                      {r.warning_count > 0 && <span className="text-amber-600 font-medium">주의 {r.warning_count}</span>}
                      {ok && <span className="text-emerald-600 font-medium inline-flex items-center gap-1"><CheckCircle2 size={13} />통과</span>}
                    </span>
                  </div>
                  {r.ledger && (
                    <div className="px-3 py-1.5 text-[11px] text-sky-700 bg-sky-50/60 border-b border-sky-100 flex flex-wrap gap-x-3 gap-y-0.5">
                      <span className="font-semibold">건축물대장</span>
                      {r.ledger.main_purps && <span>용도 {r.ledger.main_purps}</span>}
                      {r.ledger.grnd_flr?.length > 0 && <span>지상 {r.ledger.grnd_flr.join("/")}층</span>}
                      {r.ledger.use_apr_day?.length > 0 && <span>사용승인 {r.ledger.use_apr_day.join("/")}</span>}
                      {r.ledger.parking != null && <span>총주차 {r.ledger.parking}대</span>}
                    </div>
                  )}
                  {shown.length > 0 && (
                    <ul className="divide-y divide-slate-50">
                      {shown.map((f, j) => (
                        <li key={j} className="flex items-start gap-2 px-3 py-1.5 text-sm">
                          <span className="mt-0.5"><StatusIcon s={f.status} /></span>
                          <span className={`text-[11px] px-1.5 py-0.5 rounded border shrink-0 ${STATUS_STYLE[f.status] || ""}`}>
                            {f.status}
                          </span>
                          <span className="text-slate-600">
                            <b className="text-slate-700">{f.no}. {f.item}</b>
                            {f.reason && <span className="text-slate-500"> — {f.reason}</span>}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  const c: Record<string, string> = {
    slate: "text-slate-700", rose: "text-rose-600", amber: "text-amber-600",
  };
  return (
    <div className="rounded-xl border border-slate-200 p-3 text-center">
      <div className={`text-2xl font-bold ${c[tone]}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}
