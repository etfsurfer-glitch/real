import { useCallback, useEffect, useMemo, useState } from "react";
import { Users, Search, Phone, Building2, Loader2, ChevronDown, ChevronRight, CalendarDays, Image as ImageIcon } from "lucide-react";
import ContractDetailModal from "./ContractDetailModal";

// 고객관리 — 계약서에서 쌓인 임대인·임차인·매도인·매수인(내 사무소 전용).
// 주민등록번호·계좌는 저장하지 않는다(고유식별정보). 이름·연락처·역할·계약수만.
const API_BASE = import.meta.env.VITE_API_BASE;

type Customer = {
  id: number; name: string; phone: string | null; is_company: boolean;
  updated_at: string; address: string | null; roles: string[]; contracts: number;
  last_contract?: {
    contract_type: string | null; property_kind: string | null; title: string | null; address: string | null;
    price: { sale: number | null; deposit: number | null; monthly_rent: number | null };
  } | null;
};

const ROLE_COLOR: Record<string, string> = {
  임대인: "#1268d3", 매도인: "#1268d3", 임차인: "#1a7f4b", 매수인: "#1a7f4b", 중개사: "#64748b",
};
const ROLES = ["임대인", "임차인", "매도인", "매수인"];
type CtRow = {
  id: number; role: string; contract_type: string | null; property_kind: string | null;
  title: string; address: string | null;
  price: { sale: number | null; deposit: number | null; monthly_rent: number | null };
  events: number; has_doc: boolean;
};
const TC: Record<string, string> = { 매매: "#c0392b", 전세: "#1268d3", 월세: "#1a7f4b", 기타: "#64748b" };
const moneyOf = (p?: { sale: number | null; deposit: number | null; monthly_rent: number | null } | null): string =>
  !p ? "" : [p.sale ? `매매 ${won(p.sale)}` : "", p.deposit ? `보증 ${won(p.deposit)}` : "",
    p.monthly_rent ? `월세 ${won(p.monthly_rent)}` : ""].filter(Boolean).join(" · ");
function won(v: number | null | undefined): string {
  if (!v) return "";
  if (v >= 1e8) { const e = Math.floor(v / 1e8), m = Math.round((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`; }
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}

export default function BizCustomers({ authH }: { authH: () => Record<string, string> }) {
  const [items, setItems] = useState<Customer[]>([]);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [openCu, setOpenCu] = useState<number | null>(null);          // 펼친 고객
  const [cts, setCts] = useState<Record<number, CtRow[]>>({});        // 고객별 계약
  const [ctLoading, setCtLoading] = useState<number | null>(null);
  const [openCt, setOpenCt] = useState<number | null>(null);          // 계약 상세 모달

  // 고객 클릭 → 그 고객의 계약 목록(캐시)
  const toggleCu = async (id: number) => {
    if (openCu === id) { setOpenCu(null); return; }
    setOpenCu(id);
    if (cts[id]) return;
    setCtLoading(id);
    try {
      const r = await fetch(`${API_BASE}/biz/customers/${id}/contracts`, { headers: authH() });
      if (r.ok) { const d = await r.json(); setCts((s) => ({ ...s, [id]: d.items ?? [] })); }
    } catch { /* 무시 */ }
    finally { setCtLoading(null); }
  };

  const load = useCallback(() => {
    setLoading(true);
    const p = new URLSearchParams();
    if (q.trim()) p.set("q", q.trim());
    if (role) p.set("role", role);
    fetch(`${API_BASE}/biz/customers?${p}`, { headers: authH() })
      .then((r) => { if (!r.ok) throw new Error(r.status === 403 ? "관리자 전용(가오픈)입니다" : `오류 ${r.status}`); return r.json(); })
      .then((d) => { setItems(d.items ?? []); setErr(""); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [authH, q, role]);
  useEffect(() => { const t = setTimeout(load, q ? 300 : 0); return () => clearTimeout(t); }, [load, q]);

  const stat = useMemo(() => {
    const m: Record<string, number> = {};
    for (const c of items) for (const r of c.roles) m[r] = (m[r] || 0) + 1;
    return m;
  }, [items]);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="bzc-badge">관리자 가오픈 — 작업 중인 기능입니다</div>
      <div className="bzc-card">
        <div className="bzc-h"><Users size={15} /> 고객관리
          <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>— 계약서에서 자동으로 쌓인 고객</span>
        </div>
        <p className="muted" style={{ fontSize: 12.5, margin: "2px 0 10px" }}>
          계약캘린더에 계약서를 등록하면 임대인·임차인이 여기에 자동으로 쌓입니다. 같은 사람은 이름+연락처로 한 명으로 묶입니다.
        </p>

        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
          <span style={{ position: "relative", flex: "1 1 200px" }}>
            <Search size={13} style={{ position: "absolute", left: 9, top: 9, color: "#9aa4b0" }} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="이름·연락처 검색"
              style={{ width: "100%", padding: "7px 9px 7px 27px", border: "1px solid var(--c-border)", borderRadius: 8, fontSize: 13 }} />
          </span>
          <span className="bzc-seg">
            <button className={role === "" ? "on" : ""} onClick={() => setRole("")}>전체</button>
            {ROLES.map((r) => <button key={r} className={role === r ? "on" : ""} onClick={() => setRole(r)}>{r}</button>)}
          </span>
        </div>

        {Object.keys(stat).length > 0 && (
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 10 }}>
            {Object.entries(stat).map(([r, n]) => (
              <span key={r} className="bzc-tag" style={{ background: ROLE_COLOR[r] ?? "#64748b" }}>{r} {n}</span>
            ))}
          </div>
        )}

        {loading && <div className="muted" style={{ fontSize: 12.5 }}><Loader2 size={13} className="spin" /> 불러오는 중…</div>}
        {err && <div style={{ color: "#c0392b", fontSize: 12.5 }}>{err}</div>}
        {!loading && !err && items.length === 0 && (
          <div className="muted" style={{ fontSize: 12.5 }}>
            아직 고객이 없습니다. 계약캘린더에서 계약서를 등록해 보세요.
          </div>
        )}

        {items.map((c) => (
          <div key={c.id}>
            <div className="bzc-evrow" style={{ cursor: "pointer" }} onClick={() => toggleCu(c.id)}>
              {openCu === c.id ? <ChevronDown size={13} style={{ color: "#9aa4b0", flexShrink: 0 }} />
                : <ChevronRight size={13} style={{ color: "#9aa4b0", flexShrink: 0 }} />}
              <span style={{ display: "inline-flex", gap: 4, flexShrink: 0 }}>
                {(c.roles.length ? c.roles : ["-"]).map((r) => (
                  <span key={r} className="bzc-tag" style={{ background: ROLE_COLOR[r] ?? "#64748b" }}>{r}</span>
                ))}
              </span>
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap" }}>
                  <b style={{ fontSize: 13 }}>{c.name}</b>
                  {c.is_company && <span className="muted" style={{ fontSize: 11 }}><Building2 size={10} /> 법인</span>}
                  <span className="muted" style={{ fontSize: 11.5 }}>계약 {c.contracts}건</span>
                  {c.last_contract?.contract_type && (
                    <span className="bzc-tag" style={{ background: TC[c.last_contract.contract_type] ?? "#64748b" }}>
                      {c.last_contract.contract_type}
                    </span>
                  )}
                </span>
                {/* 이름만으론 누가 누군지 모른다 → 최근 계약 물건·주소·금액을 함께 */}
                {c.last_contract && (
                  <div className="muted" style={{ fontSize: 11.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {[c.last_contract.title,
                      c.last_contract.property_kind,
                      c.last_contract.address,
                      moneyOf(c.last_contract.price)].filter(Boolean).join(" · ")}
                  </div>
                )}
                {!c.last_contract && c.address && (
                  <div className="muted" style={{ fontSize: 11.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.address}
                  </div>
                )}
              </span>
              {c.phone && (
                <a href={`tel:${c.phone}`} className="chip" title="전화" onClick={(e) => e.stopPropagation()}>
                  <Phone size={11} /> {c.phone}
                </a>
              )}
            </div>

            {/* 이 고객의 계약 — 클릭하면 계약서 원본·조건 상세 */}
            {openCu === c.id && (
              <div style={{ padding: "4px 0 8px 22px", borderBottom: "1px dashed #eef1f5" }}>
                {ctLoading === c.id && <div className="muted" style={{ fontSize: 12 }}><Loader2 size={12} className="spin" /> 계약 불러오는 중…</div>}
                {ctLoading !== c.id && (cts[c.id]?.length ?? 0) === 0 && <div className="muted" style={{ fontSize: 12 }}>연결된 계약이 없습니다</div>}
                {(cts[c.id] ?? []).map((t) => {
                  const money = [t.price.sale ? `매매 ${won(t.price.sale)}` : "",
                    t.price.deposit ? `보증 ${won(t.price.deposit)}` : "",
                    t.price.monthly_rent ? `월세 ${won(t.price.monthly_rent)}` : ""].filter(Boolean).join(" · ");
                  return (
                    <div key={t.id} className="bzc-evrow" style={{ cursor: "pointer" }} onClick={() => setOpenCt(t.id)}>
                      <span className="bzc-tag" style={{ background: TC[t.contract_type ?? "기타"] ?? "#64748b" }}>{t.contract_type ?? "기타"}</span>
                      <span className="bzc-tag" style={{ background: ROLE_COLOR[t.role] ?? "#64748b" }}>{t.role}</span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <b style={{ fontSize: 12.5 }}>{t.title}</b>
                        {t.property_kind && <span className="muted" style={{ fontSize: 10.5, marginLeft: 4 }}>{t.property_kind}</span>}
                        <div className="muted" style={{ fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {[t.address, money].filter(Boolean).join(" · ")}
                        </div>
                      </span>
                      {t.has_doc && <ImageIcon size={11} style={{ color: "#9aa4b0" }} />}
                      <span className="muted" style={{ fontSize: 11, display: "inline-flex", gap: 2, alignItems: "center" }}>
                        <CalendarDays size={10} /> {t.events}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>
      {openCt != null && <ContractDetailModal contractId={openCt} authH={authH} onClose={() => setOpenCt(null)} />}
      <p className="muted" style={{ fontSize: 11.5 }}>
        고객 정보는 내 사무소에서만 보이며 외부에 공개되지 않습니다. 주민등록번호·계좌번호는 수집·저장하지 않습니다.
      </p>
    </div>
  );
}
