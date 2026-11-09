import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, MapPin } from "lucide-react";
import { KokTermsBody } from "../pages/KokTerms";

const API = import.meta.env.VITE_API_BASE;

// 라운지에 들어온 중개사에게: 지금 광고 중인 매물을 콕집매물로 등록할지 묻는다.
// 동의하면 자동연동(광고가 생기고 빠지는 대로 콕집 지도에 반영). 하루에 한 번만 묻고, 연동 뒤엔 상태 줄만 보인다.
type St = { realtor_id: string; opted: boolean; agreed_at: string | null; terms_version: string; needs_reagree: boolean;
  listings: { total: number; A1: number; B1: number; B2: number } };
type Item = { article_no: string; complex_name: string | null; building_name: string; area_name: string; area2_m2: number; floor_info: string;
  trade_type: string; price_text: string; rent_price_text: string; type: string };

export function useKokStatus(authH: () => Record<string, string>, enabled: boolean) {
  const [st, setSt] = useState<St | null>(null);
  const load = () => { if (!enabled || !API) return; fetch(`${API}/lounge/kok/status`, { headers: authH() }).then((r) => (r.ok ? r.json() : null)).then(setSt).catch(() => {}); };
  useEffect(load, [enabled]);   // eslint-disable-line react-hooks/exhaustive-deps
  return { st, reload: load };
}

export function KokOptinModal({ authH, realtorId, st, onClose, onDone }: { authH: () => Record<string, string>; realtorId: string; st: St; onClose: () => void; onDone: () => void }) {
  const [items, setItems] = useState<Item[] | null>(null);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [showTerms, setShowTerms] = useState(false);
  useEffect(() => {
    fetch(`${API}/realtor/${encodeURIComponent(realtorId)}/listings?cat=단지형&limit=12`).then((r) => r.json()).then((d) => setItems(d.listings || [])).catch(() => setItems([]));
  }, [realtorId]);
  const go = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API}/lounge/kok/optin`, { method: "POST", headers: { "Content-Type": "application/json", ...authH() }, body: JSON.stringify({ agree: true }) });
      if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(typeof j.detail === "string" ? j.detail : "등록하지 못했어요"); }
      onDone();
    } catch (e) { setErr(e instanceof Error ? e.message : "등록하지 못했어요"); } finally { setBusy(false); }
  };
  const L = st.listings;
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" style={{ maxWidth: 560, width: "calc(100vw - 32px)", padding: "20px 22px 18px" }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title"><MapPin size={16} strokeWidth={2.2} aria-hidden /> {st.needs_reagree ? "콕집매물 약관이 바뀌었어요" : "콕집매물로 등록하시겠습니까?"}</span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>
        <p style={{ fontSize: 14, lineHeight: 1.6, margin: "6px 0 10px" }}>
          지금 광고 중인 매물 <b>{L.total.toLocaleString()}건</b>(매매 {L.A1.toLocaleString()} · 전세 {L.B1.toLocaleString()} · 월세 {L.B2.toLocaleString()})이
          콕집 지도에 <b>콕집매물</b>로 표시돼요. 광고가 새로 올라오거나 내려가면 그대로 따라가요(자동연동). 무료이고 언제든 해제할 수 있어요.
        </p>
        <div style={{ border: "1px solid var(--c-border, #e3e8ef)", borderRadius: 10, maxHeight: 180, overflowY: "auto", padding: "4px 10px", marginBottom: 10 }}>
          {items === null ? <div className="muted" style={{ padding: 10, fontSize: 13 }}>매물을 불러오는 중…</div>
            : items.length === 0 ? <div className="muted" style={{ padding: 10, fontSize: 13 }}>지금 광고 중인 단지형 매물이 없어요. 광고를 올리면 자동으로 표시돼요.</div>
            : items.map((l) => (
              <div key={l.article_no} style={{ display: "flex", gap: 8, alignItems: "baseline", padding: "6px 0", borderBottom: "1px solid #eef2f7", fontSize: 13 }}>
                <span style={{ fontSize: 11.5, fontWeight: 700, color: "#5a6b80", width: 28 }}>{l.trade_type}</span>
                <b style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{l.complex_name || l.building_name}</b>
                <span className="muted">{l.area_name}{l.floor_info ? ` · ${l.floor_info}층` : ""}</span>
                <b>{l.trade_type === "월세" && l.rent_price_text ? `${l.price_text}/${l.rent_price_text}` : l.price_text}</b>
              </div>
            ))}
          {items && L.total > items.length && <div className="muted" style={{ padding: "6px 0", fontSize: 12 }}>외 {(L.total - items.length).toLocaleString()}건</div>}
        </div>
        <div style={{ border: "1px solid var(--c-border, #e3e8ef)", borderRadius: 10, padding: "8px 12px", marginBottom: 10 }}>
          <button type="button" onClick={() => setShowTerms(!showTerms)} style={{ border: 0, background: "none", padding: 0, fontSize: 13.5, fontWeight: 700, color: "#1268d3", cursor: "pointer" }}>
            콕집매물 약관 {showTerms ? "접기" : "전문 보기"}
          </button>
          {showTerms && <div className="legal" style={{ maxHeight: 240, overflowY: "auto", fontSize: 12.5, marginTop: 6, padding: 0 }}><KokTermsBody /></div>}
          <p className="muted" style={{ fontSize: 12, margin: "6px 0 0", lineHeight: 1.5 }}>
            요지: 광고 중인 매물의 표시 정보(소재지·면적·가격·층·방향 등)와 사무소 명칭·등록번호·연락처가 콕집에 표시돼요. 거래 완료 매물은 광고를 내려 주세요. 허위 표시는 연동을 중단할 수 있어요. 무료예요.
          </p>
          <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13.5, marginTop: 8 }}>
            <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} style={{ marginTop: 3 }} />
            <span>콕집매물 약관에 동의하고, 광고 중인 매물을 콕집매물로 표시하는 데 동의합니다.</span>
          </label>
        </div>
        {err && <div className="modal-msg">{err}</div>}
        <div style={{ display: "flex", gap: 8 }}>
          <button className="auth-btn kakao" style={{ flex: 1 }} disabled={!agree || busy} onClick={go}>{busy ? "등록 중…" : "콕집매물로 등록"}</button>
          <button className="auth-btn" style={{ flex: 1 }} onClick={onClose}>나중에</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

// 연동 뒤 라운지 홈 위에 보이는 한 줄 — 상태·건수·해제
export function KokStatusBar({ st, authH, onChanged, onOpen }: { st: St; authH: () => Record<string, string>; onChanged: () => void; onOpen: () => void }) {
  const [busy, setBusy] = useState(false);
  const off = async () => {
    if (!window.confirm("콕집매물 연동을 해제할까요? 콕집 지도에서 우리 사무소 매물 표시가 바로 멈춰요.")) return;
    setBusy(true);
    await fetch(`${API}/lounge/kok/optout`, { method: "POST", headers: authH() }).catch(() => null);
    setBusy(false); onChanged();
  };
  if (!st.opted) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", border: "1px solid #e3e8ef", borderRadius: 12, margin: "0 0 12px", fontSize: 13.5 }}>
        <MapPin size={16} style={{ color: "#1268d3", flexShrink: 0 }} />
        <span style={{ flex: 1 }}>광고 중인 매물 <b>{st.listings.total.toLocaleString()}건</b>을 콕집 지도에 콕집매물로 표시할 수 있어요.</span>
        <button className="auth-btn kakao" style={{ padding: "6px 12px", fontSize: 13 }} onClick={onOpen}>콕집매물로 등록</button>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", border: "1px solid #cfe3fb", background: "#f4f9ff", borderRadius: 12, margin: "0 0 12px", fontSize: 13.5 }}>
      <MapPin size={16} style={{ color: "#1268d3", flexShrink: 0 }} />
      <span style={{ flex: 1 }}><b>콕집매물 연동 중</b> · 광고 중인 {st.listings.total.toLocaleString()}건이 콕집 지도에 표시돼요{st.agreed_at ? ` · ${st.agreed_at.slice(0, 10)} 동의` : ""}</span>
      {st.needs_reagree && <button className="auth-btn kakao" style={{ padding: "6px 12px", fontSize: 13 }} onClick={onOpen}>바뀐 약관 동의</button>}
      <button className="auth-btn" style={{ padding: "6px 12px", fontSize: 13 }} disabled={busy} onClick={off}>해제</button>
    </div>
  );
}

// 라운지 홈 맨 위에 두는 묶음 — 상태 줄 + (연동 전이면 하루 한 번) 등록 묻기
export function KokPanel({ authH }: { authH: () => Record<string, string> }) {
  const { st, reload } = useKokStatus(authH, true);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!st || st.opted && !st.needs_reagree) return;
    const k = "kok_optin_asked"; let last = "";
    try { last = localStorage.getItem(k) || ""; } catch { /* */ }
    const today = new Date().toISOString().slice(0, 10);
    if (last !== today) { setOpen(true); try { localStorage.setItem(k, today); } catch { /* */ } }
  }, [st]);
  if (!st) return null;
  return (
    <>
      <KokStatusBar st={st} authH={authH} onChanged={reload} onOpen={() => setOpen(true)} />
      {open && <KokOptinModal authH={authH} realtorId={st.realtor_id} st={st} onClose={() => setOpen(false)} onDone={() => { setOpen(false); reload(); }} />}
    </>
  );
}
