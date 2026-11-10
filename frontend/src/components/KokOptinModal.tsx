import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, MapPin } from "lucide-react";
import { KokTermsBody } from "../pages/KokTerms";

const API = import.meta.env.VITE_API_BASE;

// 라운지에 들어온 중개사에게: 지금 광고 중인 매물을 콕집매물로 등록할지 묻는다.
// 동의하면 자동연동(광고가 생기고 빠지는 대로 콕집 지도에 반영). 하루에 한 번만 묻고, 연동 뒤엔 상태 줄만 보인다.
type St = { realtor_id: string; opted: boolean; agreed_at: string | null; terms_version: string; needs_reagree: boolean; synced_at?: string | null;
  listings: { total: number; A1: number; B1: number; B2: number } };
type MyItem = { id: string; complex_no: string; name: string; dong?: string; trade: string; area_name: string; excl_m2: number | null; floor_text: string; direction: string;
  price_text: string; kok_since?: string; photos: string[]; keywords: string[]; description: string };
const TRADE_L: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세" };
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
          콕집 지도에 <b>콕집매물</b>로 표시돼요. 광고가 올라오고 내려가는 건 매일 새벽 한 번 반영돼요. 사진·설명·키워드는 라운지에서 콕집용으로 따로 쓸 수 있어요(광고 문구는 옮기지 않아요). 무료이고 언제든 해제할 수 있어요.
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
            요지: 광고 중인 매물의 표시 정보(소재지·면적·가격·층·방향 등)와 사무소 명칭·등록번호·연락처를 콕집매물 자료로 보관해 표시하고, 매일 광고 상태를 반영해요. 사진·설명·키워드는 라운지에서 직접 올려요. 거래 완료 매물은 광고를 내려 주세요. 허위 표시는 연동을 중단할 수 있어요. 무료예요.
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
      <span style={{ flex: 1 }}><b>콕집매물 연동 중</b> · {st.listings.total.toLocaleString()}건이 콕집 지도에 표시돼요{st.synced_at ? ` · ${st.synced_at.slice(5, 16)} 반영` : ""}{st.agreed_at ? ` · ${st.agreed_at.slice(0, 10)} 동의` : ""}</span>
      {st.needs_reagree && <button className="auth-btn kakao" style={{ padding: "6px 12px", fontSize: 13 }} onClick={onOpen}>바뀐 약관 동의</button>}
      <button className="auth-btn" style={{ padding: "6px 12px", fontSize: 13 }} disabled={busy} onClick={off}>해제</button>
    </div>
  );
}

// 내 콕집매물 — 동기화된 광고 목록에 사진·설명·키워드를 콕집용으로 직접 쓴다(광고 문구는 안 옮김)
function KokMyListings({ authH }: { authH: () => Record<string, string> }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<MyItem[] | null>(null);
  const [synced, setSynced] = useState<string | null>(null);
  const [edit, setEdit] = useState<string | null>(null);
  const load = () => fetch(`${API}/lounge/kok/listings`, { headers: authH() }).then((r) => (r.ok ? r.json() : { items: [] })).then((j) => { setItems(j.items || []); setSynced(j.synced_at || null); }).catch(() => setItems([]));
  useEffect(() => { if (open && items === null) load(); }, [open]);   // eslint-disable-line react-hooks/exhaustive-deps
  const withExtra = (items || []).filter((i) => i.photos.length || i.keywords.length || i.description).length;
  return (
    <div style={{ border: "1px solid #e3e8ef", borderRadius: 12, margin: "0 0 12px", fontSize: 13.5 }}>
      <button type="button" onClick={() => setOpen(!open)} style={{ width: "100%", border: 0, background: "none", padding: "10px 14px", textAlign: "left", font: "inherit", cursor: "pointer", display: "flex", gap: 10, alignItems: "center" }}>
        <span style={{ flex: 1 }}><b>내 콕집매물</b>{items ? ` ${items.length}건 · 사진·설명·키워드 쓴 매물 ${withExtra}건` : " · 사진·설명·키워드 쓰기"}{synced ? <span className="muted"> · {synced.slice(5, 16)} 반영</span> : null}</span>
        <span className="muted">{open ? "접기" : "열기"}</span>
      </button>
      {open && (
        <div style={{ padding: "0 14px 10px" }}>
          <p className="muted" style={{ margin: "0 0 8px" }}>광고 문구는 콕집에 옮기지 않아요. 여기 쓰는 사진·설명·키워드만 콕집매물 상세에 보여요. 사진은 얼굴·글자가 자동으로 가려진 뒤 저장돼요.</p>
          {items === null ? <div className="muted">불러오는 중…</div> : items.length === 0 ? <div className="muted">아직 반영된 매물이 없어요. 동의 뒤 몇 분, 그 다음부터는 매일 새벽에 반영돼요.</div>
            : items.map((it) => (
              <div key={it.id} style={{ borderTop: "1px solid #eef2f7", padding: "8px 0" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                  <span style={{ fontSize: 11.5, fontWeight: 700, color: "#5a6b80", width: 28 }}>{TRADE_L[it.trade] || it.trade}</span>
                  <b style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.name}{it.dong ? ` ${it.dong}동` : ""}</b>
                  <span className="muted">{it.area_name}{it.floor_text ? ` · ${it.floor_text}` : ""}</span>
                  <b>{it.price_text}</b>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 4 }}>
                  <span className="muted" style={{ flex: 1 }}>사진 {it.photos.length} · 키워드 {it.keywords.length ? it.keywords.join(", ") : 0} · 설명 {it.description ? `${it.description.length}자` : "없음"}</span>
                  <button type="button" onClick={() => setEdit(edit === it.id ? null : it.id)} style={{ border: 0, background: "none", padding: 0, fontSize: 13, fontWeight: 700, color: "#1268d3", cursor: "pointer" }}>{edit === it.id ? "닫기" : "쓰기"}</button>
                </div>
                {edit === it.id && <MyExtrasEditor authH={authH} it={it} onSaved={() => { setEdit(null); load(); }} />}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function MyExtrasEditor({ authH, it, onSaved }: { authH: () => Record<string, string>; it: MyItem; onSaved: () => void }) {
  const [photos, setPhotos] = useState<string[]>(it.photos.map((u) => u.replace(/^.*\/kok\/photo\//, "")));
  const [desc, setDesc] = useState(it.description || "");
  const [kw, setKw] = useState(it.keywords.join(", "));
  const [up, setUp] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const inp = { font: "inherit", fontSize: 13.5, border: "1px solid #d9e0ea", borderRadius: 8, padding: "8px 10px", width: "100%", boxSizing: "border-box" as const };
  const addPhoto = async (f: File) => {
    if (photos.length >= 10) return; setUp(true); setErr("");
    const fd = new FormData(); fd.append("document", f);
    try { const r = await fetch(`${API}/lounge/kok/photo`, { method: "POST", headers: authH(), body: fd }); const j = await r.json(); if (r.ok && j.photo) setPhotos((p) => [...p, j.photo]); else setErr(typeof j.detail === "string" ? j.detail : "사진을 올리지 못했어요"); }
    catch { setErr("사진을 올리지 못했어요"); } finally { setUp(false); }
  };
  const save = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API}/lounge/kok/listings/${it.id.slice(1)}/extras`, { method: "POST", headers: { "Content-Type": "application/json", ...authH() },
        body: JSON.stringify({ photos, description: desc, keywords: kw.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 8) }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "저장하지 못했어요");
      onSaved();
    } catch (e) { setErr(e instanceof Error ? e.message : "저장하지 못했어요"); } finally { setBusy(false); }
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {photos.map((p) => <span key={p} style={{ position: "relative" }}><img src={`${API}/kok/photo/${p}`} alt="" style={{ width: 96, height: 72, objectFit: "cover", borderRadius: 6, display: "block" }} /><button type="button" aria-label="지우기" onClick={() => setPhotos((x) => x.filter((y) => y !== p))} style={{ position: "absolute", top: -6, right: -6, width: 20, height: 20, borderRadius: "50%", border: 0, background: "#1a2738", color: "#fff", cursor: "pointer", lineHeight: "18px" }}>×</button></span>)}
        {photos.length < 10 && <label style={{ width: 96, height: 72, border: "1.5px dashed #c9d2df", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12.5, color: "#5a6b80", cursor: "pointer" }}>{up ? "올리는 중…" : "+ 사진"}<input type="file" accept="image/*" hidden disabled={up} onChange={(e) => { const f = e.target.files?.[0]; if (f) addPhoto(f); e.target.value = ""; }} /></label>}
      </div>
      <textarea rows={4} maxLength={1000} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="콕집에 보일 설명 (1000자) — 집 상태, 수리 내역, 협의 가능한 점" style={{ ...inp, resize: "vertical" }} />
      <input value={kw} onChange={(e) => setKw(e.target.value)} placeholder="키워드, 쉼표로 (최대 8개 · 예: 올수리, 남향, 역 3분)" style={inp} />
      {err && <div className="modal-msg">{err}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button className="auth-btn kakao" style={{ flex: 1 }} disabled={busy} onClick={save}>{busy ? "저장 중…" : "저장"}</button>
      </div>
    </div>
  );
}

// 라운지 홈 맨 위에 두는 묶음 — 상태 줄 + (연동 전이면 하루 한 번) 등록 묻기 + 연동 뒤 내 콕집매물 쓰기
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
      {st.opted && <KokMyListings authH={authH} />}
      {open && <KokOptinModal authH={authH} realtorId={st.realtor_id} st={st} onClose={() => setOpen(false)} onDone={() => { setOpen(false); reload(); }} />}
    </>
  );
}
