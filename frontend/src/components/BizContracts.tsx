import { useCallback, useEffect, useState } from "react";
import { FileText, Search, Loader2, CalendarDays, Image as ImageIcon } from "lucide-react";
import ContractDetailModal from "./ContractDetailModal";

// 계약관리 — 등록된 계약서 목록(종류·물건·금액·당사자·일정수). 행 클릭 시 계약캘린더의
// 상세와 같은 정보(사진·당사자·조건)를 보여준다.
const API_BASE = import.meta.env.VITE_API_BASE;

type Row = {
  id: number; status: string; created_at: string;
  contract_type: string | null; doc_kind: string | null; property_kind: string | null;
  title: string; address: string | null;
  price: { sale: number | null; deposit: number | null; monthly_rent: number | null };
  parties: { role: string; name: string }[]; events: number; has_doc: boolean;
};

function won(v: number | null | undefined): string {
  if (!v) return "";
  if (v >= 1e8) { const e = Math.floor(v / 1e8), m = Math.round((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`; }
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}
const TC: Record<string, string> = { 매매: "#c0392b", 전세: "#1268d3", 월세: "#1a7f4b", 기타: "#64748b" };
const ROLE_COLOR: Record<string, string> = {
  임대인: "#1268d3", 매도인: "#1268d3", 임차인: "#1a7f4b", 매수인: "#1a7f4b", 중개사: "#64748b",
};

export default function BizContracts({ authH }: { authH: () => Record<string, string> }) {
  const [items, setItems] = useState<Row[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);   // 행 클릭 → 계약 상세
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    const p = new URLSearchParams();
    if (q.trim()) p.set("q", q.trim());
    fetch(`${API_BASE}/biz/contracts?${p}`, { headers: authH() })
      .then((r) => { if (!r.ok) throw new Error(r.status === 403 ? "관리자 전용(가오픈)입니다" : `오류 ${r.status}`); return r.json(); })
      .then((d) => { setItems(d.items ?? []); setErr(""); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [authH, q]);
  useEffect(() => { const t = setTimeout(load, q ? 300 : 0); return () => clearTimeout(t); }, [load, q]);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="bzc-badge">관리자 가오픈 — 작업 중인 기능입니다</div>
      <div className="bzc-card">
        <div className="bzc-h"><FileText size={15} /> 계약관리
          <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>— 등록한 계약서</span>
        </div>
        <p className="muted" style={{ fontSize: 12.5, margin: "2px 0 10px" }}>
          계약캘린더에서 등록한 계약서 목록입니다. 클릭하면 계약서 원본·당사자·계약조건을 볼 수 있습니다.
        </p>

        <span style={{ position: "relative", display: "block", marginBottom: 10 }}>
          <Search size={13} style={{ position: "absolute", left: 9, top: 9, color: "#9aa4b0" }} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="물건·주소·고객명 검색"
            style={{ width: "100%", padding: "7px 9px 7px 27px", border: "1px solid var(--c-border)", borderRadius: 8, fontSize: 13 }} />
        </span>

        {loading && <div className="muted" style={{ fontSize: 12.5 }}><Loader2 size={13} className="spin" /> 불러오는 중…</div>}
        {err && <div style={{ color: "#c0392b", fontSize: 12.5 }}>{err}</div>}
        {!loading && !err && items.length === 0 && (
          <div className="muted" style={{ fontSize: 12.5 }}>등록된 계약서가 없습니다. 계약캘린더에서 계약서를 올려보세요.</div>
        )}

        {items.map((r) => {
          const money = [r.price.sale ? `매매 ${won(r.price.sale)}` : "",
            r.price.deposit ? `보증 ${won(r.price.deposit)}` : "",
            r.price.monthly_rent ? `월세 ${won(r.price.monthly_rent)}` : ""].filter(Boolean).join(" · ");
          return (
            <div key={r.id} className="bzc-evrow" style={{ cursor: "pointer", alignItems: "flex-start" }}
              onClick={() => setOpenId(r.id)}>
              <span className="bzc-tag" style={{ background: TC[r.contract_type ?? "기타"] ?? "#64748b", marginTop: 2 }}>
                {r.contract_type ?? "기타"}
              </span>
              <span style={{ flex: 1, minWidth: 0 }}>
                <b style={{ fontSize: 13 }}>{r.title}</b>
                {r.property_kind && <span className="muted" style={{ fontSize: 11, marginLeft: 5 }}>{r.property_kind}</span>}
                <div className="muted" style={{ fontSize: 11.5 }}>
                  {[r.address, money].filter(Boolean).join(" · ")}
                </div>
                {r.parties.length > 0 && (
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 3 }}>
                    {r.parties.map((p, i) => (
                      <span key={i} style={{ fontSize: 10.5, fontWeight: 700, color: ROLE_COLOR[p.role] ?? "#64748b" }}>
                        {p.role} {p.name}
                      </span>
                    ))}
                  </div>
                )}
              </span>
              <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
                {r.has_doc && <ImageIcon size={12} style={{ color: "#9aa4b0" }} />}
                <span className="muted" style={{ fontSize: 11.5, display: "inline-flex", gap: 3, alignItems: "center" }}>
                  <CalendarDays size={11} /> {r.events}
                </span>
              </span>
            </div>
          );
        })}
      </div>
      {openId != null && <ContractDetailModal contractId={openId} authH={authH} onClose={() => setOpenId(null)} />}
    </div>
  );
}
