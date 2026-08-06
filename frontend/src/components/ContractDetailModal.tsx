import { useCallback, useEffect, useState } from "react";
import { FileText, X, User, Download } from "lucide-react";
import { areaLabel } from "../lib/area";

// 계약 상세 모달 — 계약서 원본 사진/PDF + 당사자(임대인·임차인) + 계약조건.
// 계약캘린더(일정 클릭)·계약관리(행 클릭)·고객관리(고객→계약 클릭)에서 공용으로 쓴다.
// 원본은 소유자 인증이 필요해 <img src>로 직접 못 부르고 blob으로 받아 띄운다.
const API_BASE = import.meta.env.VITE_API_BASE;

type Party = { customer_id: number | null; role: string; name: string; phone: string | null; is_company: boolean };
type Detail = {
  id: number; status: string; created_at: string; parsed: any;
  parties: Party[]; events: { id: number; title: string; event_date: string; event_type: string }[];
  doc: { exists: boolean; ext: string | null };
};

const TYPE_COLOR: Record<string, string> = {
  계약: "#1268d3", 중도금: "#b45309", 잔금: "#c0392b", 입주: "#1a7f4b", 만기: "#6b39c9", 기타: "#64748b",
};
const ROLE_COLOR = (r: string) =>
  r === "임대인" || r === "매도인" ? "#1268d3" : r === "중개사" ? "#64748b" : "#1a7f4b";

function won(v: number | null | undefined): string {
  if (!v) return "";
  if (v >= 1e8) { const e = Math.floor(v / 1e8), m = Math.round((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`; }
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}

export default function ContractDetailModal(
  { contractId, authH, onClose }: { contractId: number; authH: () => Record<string, string>; onClose: () => void },
) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [docUrl, setDocUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const r = await fetch(`${API_BASE}/biz/contracts/${contractId}`, { headers: authH() });
      if (!r.ok) throw new Error("계약 정보를 불러오지 못했어요");
      const d: Detail = await r.json();
      setDetail(d);
      if (d.doc?.exists) {
        const dr = await fetch(`${API_BASE}/biz/contracts/${contractId}/doc`, { headers: authH() });
        if (dr.ok) setDocUrl(URL.createObjectURL(await dr.blob()));
      }
    } catch (e) { setErr(String((e as Error).message || e)); }
    finally { setLoading(false); }
  }, [contractId, authH]);

  useEffect(() => { load(); }, [load]);
  // blob URL 정리(누수 방지)
  useEffect(() => () => { if (docUrl) URL.revokeObjectURL(docUrl); }, [docUrl]);

  const p = detail?.parsed || {}, pr = p.price || {}, lt = p.lease_term || {}, ar = p.area || {};
  const rows: [string, string][] = [];
  if (detail) {
    if (p.contract_type || p.doc_kind) rows.push(["계약 종류", [p.contract_type, p.doc_kind].filter(Boolean).join(" · ")]);
    if (p.property_name || p.property_address) rows.push(["물건", [p.property_name, p.unit, p.property_address].filter(Boolean).join(" ")]);
    if (pr.sale) rows.push(["매매대금", won(pr.sale)]);
    if (pr.deposit) rows.push(["보증금", won(pr.deposit)]);
    if (pr.monthly_rent) rows.push(["월세", won(pr.monthly_rent)]);
    if (pr.maintenance_fee) rows.push(["관리비", won(pr.maintenance_fee)]);
    if (pr.premium) rows.push(["권리금", won(pr.premium)]);
    if (pr.down_payment) rows.push(["계약금", won(pr.down_payment)]);
    if (Array.isArray(pr.interim) && pr.interim.length)
      rows.push(["중도금", pr.interim.map((x: any) => `${won(x.amount)}${x.date ? ` (${x.date})` : ""}${x.note ? ` ${x.note}` : ""}`).join(" / ")]);
    if (pr.balance) rows.push(["잔금", won(pr.balance)]);
    if (lt.start || lt.end) rows.push(["임대기간", `${lt.start ?? "?"} ~ ${lt.end ?? "?"}${lt.months ? ` (${lt.months}개월)` : ""}`]);
    if (ar.exclusive_m2 || ar.supply_m2)
      rows.push(["면적", [ar.supply_m2 && `공급 ${ar.supply_m2}㎡`, ar.exclusive_m2 && areaLabel(ar.exclusive_m2)].filter(Boolean).join(" · ")]);
  }

  return (
    <div className="bzc-modal" onClick={onClose}>
      <div className="bzc-modal-in" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <div className="bzc-h" style={{ margin: 0 }}><FileText size={15} /> 계약 상세</div>
          <button className="chip" style={{ marginLeft: "auto" }} onClick={onClose}><X size={13} /></button>
        </div>
        {loading && <div className="muted" style={{ fontSize: 12.5 }}>불러오는 중…</div>}
        {err && <div style={{ color: "#c0392b", fontSize: 12.5 }}>{err}</div>}
        {detail && (
          <div className="bzc-detail">
            <div>
              <div className="bzc-h" style={{ fontSize: 13 }}><User size={13} /> 당사자</div>
              {detail.parties.length === 0 && <div className="muted" style={{ fontSize: 12 }}>추출된 당사자가 없습니다</div>}
              {detail.parties.map((pt, i) => (
                <div key={i} className="bzc-party">
                  <span className="bzc-tag" style={{ background: ROLE_COLOR(pt.role) }}>{pt.role}</span>
                  <b style={{ fontSize: 12.5 }}>{pt.name}</b>
                  {pt.is_company && <span className="muted" style={{ fontSize: 11 }}>법인</span>}
                  {pt.phone && <a href={`tel:${pt.phone}`} className="muted" style={{ fontSize: 11.5, marginLeft: "auto" }}>{pt.phone}</a>}
                </div>
              ))}

              <div className="bzc-h" style={{ fontSize: 13, marginTop: 12 }}>계약 조건</div>
              <table className="bzc-kv"><tbody>
                {rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}
              </tbody></table>

              {p.special_terms && (
                <div style={{ marginTop: 8 }}>
                  <div className="bzc-h" style={{ fontSize: 13 }}>특약</div>
                  <div style={{ fontSize: 12, color: "#33425a", lineHeight: 1.5 }}>{p.special_terms}</div>
                </div>
              )}
              {p.caution && <div style={{ color: "#b45309", fontSize: 12, marginTop: 8 }}>⚠ {p.caution}</div>}

              {detail.events.length > 0 && (
                <>
                  <div className="bzc-h" style={{ fontSize: 13, marginTop: 12 }}>관련 일정</div>
                  {detail.events.map((e) => (
                    <div key={e.id} className="bzc-evrow">
                      <span className="bzc-tag" style={{ background: TYPE_COLOR[e.event_type] ?? "#64748b" }}>{e.event_type}</span>
                      <span style={{ flex: 1, fontSize: 12.5 }}>{e.title}</span>
                      <span className="muted" style={{ fontSize: 11.5 }}>{e.event_date}</span>
                    </div>
                  ))}
                </>
              )}
            </div>

            <div>
              <div className="bzc-h" style={{ fontSize: 13 }}>계약서 원본</div>
              {!detail.doc.exists && <div className="muted" style={{ fontSize: 12 }}>원본이 없습니다</div>}
              {docUrl && (detail.doc.ext === ".pdf"
                ? <iframe src={docUrl} className="bzc-doc" title="계약서" />
                : <img src={docUrl} className="bzc-doc" alt="계약서" />)}
              {detail.doc.exists && !docUrl && <div className="muted" style={{ fontSize: 12 }}>불러오는 중…</div>}
              {docUrl && (
                <a href={docUrl} download={`계약서_${detail.id}${detail.doc.ext ?? ""}`} className="chip" style={{ marginTop: 6 }}>
                  <Download size={12} /> 원본 저장
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
