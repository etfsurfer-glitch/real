import { useState } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, ChevronLeft, Loader2, Search } from "lucide-react";
import { useAuth } from "../auth";
import ListingAudit from "../components/ListingAudit";

const API_BASE = import.meta.env.VITE_API_BASE;

type Realtor = { realtor_id: string; realtor_name: string; count: number; address: string | null };

export default function AuditRealtor() {
  const { token } = useAuth();
  const authH = { Authorization: `Bearer ${token}` };
  const [q, setQ] = useState("");
  const [realtors, setRealtors] = useState<Realtor[]>([]);
  const [searching, setSearching] = useState(false);
  const [realtor, setRealtor] = useState<Realtor | null>(null);

  async function searchRealtors() {
    if (!q.trim() || !API_BASE) return;
    setSearching(true);
    try {
      const r = await fetch(`${API_BASE}/stats/realtors/search?q=${encodeURIComponent(q.trim())}&limit=20`);
      const j = await r.json();
      setRealtors(j.items ?? []);
    } catch { setRealtors([]); }
    setSearching(false);
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <Link to="/admin" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-3">
        <ChevronLeft size={16} /> 관리자
      </Link>
      <div className="flex items-center gap-2 mb-1">
        <ShieldCheck size={22} className="text-indigo-600" />
        <h1 className="text-xl font-bold text-slate-800">매물 표시·광고 점검</h1>
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-200">가오픈 · 관리자</span>
      </div>
      <p className="text-sm text-slate-500 mb-4">중개사무소를 검색 → 매물 유형·거래별로 골라 점검합니다.</p>

      <div className="flex gap-2 mb-3">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-2.5 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && searchRealtors()}
            placeholder="중개사무소 이름 (예: 시티오씨엘, 고덕탑)"
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200" />
        </div>
        <button onClick={searchRealtors} disabled={searching || !q.trim()}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
          {searching ? <Loader2 size={16} className="animate-spin" /> : "검색"}
        </button>
      </div>

      {realtors.length > 0 && !realtor && (
        <div className="border border-slate-200 rounded-lg divide-y divide-slate-100 mb-4 max-h-64 overflow-auto">
          {realtors.map((rt) => (
            <button key={rt.realtor_id} onClick={() => { setRealtor(rt); setRealtors([]); }}
              className="w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-slate-700 truncate">{rt.realtor_name}
                {rt.address && <span className="text-slate-400 font-normal text-xs ml-2">{rt.address}</span>}</span>
              <span className="text-xs text-slate-500 shrink-0">매물 {rt.count.toLocaleString()}</span>
            </button>
          ))}
        </div>
      )}

      {realtor && (
        <div className="mb-3 p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
          <span className="text-sm font-semibold text-slate-700">{realtor.realtor_name}</span>
          <button onClick={() => setRealtor(null)} className="text-xs text-slate-400 hover:text-slate-600">다른 사무소</button>
        </div>
      )}

      {realtor && (
        <ListingAudit
          authH={authH}
          breakdownUrl={`/admin/audit/breakdown?realtor_id=${encodeURIComponent(realtor.realtor_id)}`}
          buildAuditUrl={(kind, trade, offset, limit) =>
            `/admin/audit/realtor?realtor_id=${encodeURIComponent(realtor.realtor_id)}&kind=${kind}&trade=${trade}&offset=${offset}&limit=${limit}`}
        />
      )}
    </div>
  );
}
