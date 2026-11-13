// 콕집매물 — 지도 시험판 노출(목록·상세·문의)과 일반 회원 직거래 등록(내 집 내놓기).
// 중개사 연동분은 서버가 광고 중 매물을 그대로 주고, 직거래분은 등기 소유자 확인을 통과한 것만 올라온다.
import { useEffect, useMemo, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { API, getJson, Dd, Skel } from "./Drawer";
import { Seg } from "./Stats";
import { LoginBox, PhoneBlock, authHeaders } from "./Request";
import { areaLabel } from "../src/lib/area";
import { dirLabel } from "../src/lib/direction";

export type KokItem = { id: string; kind: "owner" | "realtor"; complex_no: string; name: string; lat?: number; lng?: number; trade: string;
  price: number; rent: number; price_text: string; area_name: string; excl_m2: number | null; floor_text: string; direction: string;
  realtor_id?: string; realtor_name?: string; owner_verified: boolean; photos?: string[]; feature?: string; detail?: string; dong?: string;
  move_in?: string; mgmt_fee?: number | null; contact_mode?: string; phone?: string; created_at?: string; expires_at?: string; expired?: boolean; status?: string;
  inquiries?: { id: number; from_phone: string; message: string; created_at: string }[]; keywords?: string[]; description?: string; kok_since?: string };
const photoName = (u: string) => u.replace(/^.*\/kok\/photo\//, "");
const TRADE_L: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세" };
const DIRS = ["남향", "남동향", "남서향", "동향", "서향", "북향", "북동향", "북서향"];

export function useKok(bbox: { swLat: number; swLng: number; neLat: number; neLng: number } | null, trade: string, tick: number) {
  const [items, setItems] = useState<KokItem[]>([]);
  const [byCx, setByCx] = useState<Record<string, number>>({});
  useEffect(() => {
    if (!bbox) return;
    let off = false;
    getJson(`/kok/listings?swlat=${bbox.swLat}&swlng=${bbox.swLng}&nelat=${bbox.neLat}&nelng=${bbox.neLng}&trade=${trade}&limit=300`)
      .then((j) => { if (!off) { setItems(j.items || []); setByCx(j.by_complex || {}); } }).catch(() => { if (!off) { setItems([]); setByCx({}); } });
    return () => { off = true; };
  }, [bbox?.swLat, bbox?.swLng, bbox?.neLat, bbox?.neLng, trade, tick]);   // eslint-disable-line react-hooks/exhaustive-deps
  return { items, byCx };
}

// 한 줄(패널·서랍 공용). 직거래는 '직거래 · 소유자 확인', 중개사 연동은 사무소 이름.
export function KokRow({ it, onOpen }: { it: KokItem; onOpen: (it: KokItem) => void }) {
  return (
    <li className="t2-kok-row">
      <button onClick={() => onOpen(it)}>
        {it.photos && it.photos.length > 0 ? <img src={`${API}${it.photos[0]}`} alt="" /> : <span className="t2-kok-noimg">{it.kind === "owner" ? "직거래" : "중개"}</span>}
        <span className="t">
          <b>{it.name}{it.dong ? ` ${it.dong}동` : ""}</b>
          <em>{[TRADE_L[it.trade], it.excl_m2 ? areaLabel(it.excl_m2) : it.area_name, it.floor_text, it.direction].filter(Boolean).join(" · ")}</em>
          <small>{it.kind === "owner" ? <><i className="t2-kok-badge own">직거래</i>{it.owner_verified && <i className="t2-kok-badge ok">소유자 확인</i>}</> : <i className="t2-kok-badge rt">{it.realtor_name || "중개사무소"}</i>}
            {it.keywords && it.keywords.length > 0 && <span className="t2-kok-kw">{it.keywords.slice(0, 3).map((k) => <i key={k}>{k}</i>)}</span>}</small>
        </span>
        <span className="p"><b>{it.price_text}</b></span>
      </button>
    </li>
  );
}

// 매물찾기 패널 아래 '콕집 매물' 칸
export function KokPanelList({ items, onOpen, onGo }: { items: KokItem[]; onOpen: (it: KokItem) => void; onGo: (no: string, name: string) => void }) {
  if (items.length === 0) return <p className="t2-empty sm">이 범위엔 아직 콕집 매물이 없어요. 로그인하면 내 집을 직거래로 내놓을 수 있어요.</p>;
  return (
    <ul className="t2-kok-list">
      {items.slice(0, 40).map((it) => <KokRow key={it.id} it={it} onOpen={(x) => { if (x.kind === "realtor") onGo(x.complex_no, x.name); onOpen(x); }} />)}
    </ul>
  );
}

// 사진 넘겨 보기 — 콕집에 직접 올린 사진만(우리 저장소)
export function KokPhotos({ photos }: { photos: string[] }) {
  const [pi, setPi] = useState(0);
  if (photos.length === 0) return null;
  const i = Math.min(pi, photos.length - 1);
  return (
    <div className="t2-kok-photos">
      <img src={`${API}${photos[i]}`} alt="" />
      {photos.length > 1 && <div className="thumbs">{photos.map((p, k) => <img key={p} src={`${API}${p}`} alt="" className={k === i ? "on" : ""} onClick={() => setPi(k)} />)}</div>}
    </div>
  );
}

// 사진·설명·키워드 — 등록자가 콕집에 직접 쓰는 부분. 직거래(소유자)와 중개사 연동분이 같은 편집기를 쓴다.
export function KokExtrasEditor({ session, init, uploadPath, savePath, withFeature, onSaved, onCancel }: {
  session: Session; init: { photos?: string[]; feature?: string; detail?: string; keywords?: string[] };
  uploadPath: string; savePath: string; withFeature?: boolean; onSaved: () => void; onCancel: () => void;
}) {
  const [photos, setPhotos] = useState<string[]>((init.photos || []).map(photoName));
  const [feature, setFeature] = useState(init.feature || "");
  const [detail, setDetail] = useState(init.detail || "");
  const [kw, setKw] = useState((init.keywords || []).join(", "));
  const [up, setUp] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const addPhoto = async (f: File) => {
    if (photos.length >= 10) return; setUp(true); setErr("");
    const fd = new FormData(); fd.append("document", f);
    try { const r = await fetch(`${API}${uploadPath}`, { method: "POST", headers: authHeaders(session), body: fd }); const j = await r.json(); if (r.ok && j.photo) setPhotos((p) => [...p, j.photo]); else setErr(typeof j.detail === "string" ? j.detail : "사진을 올리지 못했어요"); }
    catch { setErr("사진을 올리지 못했어요"); } finally { setUp(false); }
  };
  const save = async () => {
    setBusy(true); setErr("");
    try {
      const body: Record<string, unknown> = { photos, keywords: kw.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 8) };
      if (withFeature) { body.feature = feature; body.detail = detail; } else body.description = detail;
      const r = await fetch(`${API}${savePath}`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders(session) }, body: JSON.stringify(body) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "저장하지 못했어요");
      onSaved();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="t2-kok-edit">
      <div className="t2-kok-upl">
        {photos.map((p) => <span key={p} className="ph"><img src={`${API}/kok/photo/${p}`} alt="" /><button onClick={() => setPhotos((x) => x.filter((y) => y !== p))} aria-label="지우기">×</button></span>)}
        {photos.length < 10 && <button className="add" disabled={up} onClick={() => fileRef.current?.click()}>{up ? "올리는 중…" : "+ 사진"}</button>}
        <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) addPhoto(f); e.target.value = ""; }} />
      </div>
      <small className="mut">사진은 얼굴·글자가 자동으로 가려진 뒤 저장돼요 · 최대 10장</small>
      {withFeature && <input value={feature} onChange={(e) => setFeature(e.target.value.slice(0, 40))} placeholder="한 줄 특징 (40자)" />}
      <textarea rows={4} maxLength={1000} value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="콕집에 보일 설명 (1000자) — 집 상태, 수리 내역, 협의 가능한 점" />
      <input value={kw} onChange={(e) => setKw(e.target.value)} placeholder="키워드, 쉼표로 (최대 8개 · 예: 올수리, 남향, 역 3분)" />
      {err && <p className="t2-err">{err}</p>}
      <div className="row">
        <button className="t2-cta1" style={{ marginTop: 0 }} disabled={busy} onClick={save}>{busy ? "저장 중…" : "저장"}</button>
        <button className="t2-cta1 ghost" style={{ marginTop: 0, flex: "0 0 100px" }} onClick={onCancel}>취소</button>
      </div>
    </div>
  );
}

// 직거래 매물 상세(지도 안 작은 창) — 사진·조건·소유자 확인·문의
// 변경 이력 — 가격 변경·거래완료·다시 게시 등 등록자가 바꾼 기록(콕집이 자동으로 남김). 허위·미끼 매물을 가려 보는 데 쓴다
type KokHist = { at: string; kind: string; text: string };
export function KokHistory({ h, since }: { h?: KokHist[]; since?: string }) {
  if (!h || h.length === 0) return since ? <p className="t2-pf-src">변경 이력 없음 · {since.replace(/-/g, ".")} 등록 뒤 가격을 바꾼 적 없어요</p> : null;
  return (
    <div className="t2-kl-sec"><h3>변경 이력 <small>콕집이 자동으로 남긴 기록</small></h3>
      <table className="t2-tbl t2-kl-mo"><tbody>{h.map((x, i) => <tr key={i}><td style={{ width: 90 }}>{x.at.replace(/-/g, ".")}</td><td>{x.text}</td></tr>)}</tbody></table></div>
  );
}

// 허위매물 신고 — 로그인 없이도 보낼 수 있다(같은 매물 하루 1번). 콕집 운영자에게 바로 알림
const REPORT_REASONS: [string, string][] = [["sold", "이미 거래된 매물"], ["price", "가격이 달라요"], ["fake", "없는 매물(허위)"], ["info", "면적·층 등 정보가 달라요"], ["etc", "기타"]];
export function KokReport({ lid }: { lid: string }) {
  const [open, setOpen] = useState(false); const [reason, setReason] = useState(""); const [detail, setDetail] = useState("");
  const [done, setDone] = useState(false); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  if (done) return <p className="t2-ask-ok">신고를 받았어요. 콕집이 확인해서 조치할게요.</p>;
  if (!open) return <p className="t2-pf-src"><button className="t2-lnk mut" onClick={() => setOpen(true)}>허위매물 신고</button> · 이미 거래됐거나 표시와 다른 매물이면 알려 주세요</p>;
  const send = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API}/kok/listings/${lid}/report`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reason, detail }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "보내지 못했어요");
      setDone(true);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="t2-safe-sec"><h3>허위매물 신고</h3>
      <div className="t2-revform">
        <div className="t2-chips" style={{ marginBottom: 8 }}>{REPORT_REASONS.map(([k, l]) => <button key={k} type="button" className={reason === k ? "on" : ""} onClick={() => setReason(k)}>{l}</button>)}</div>
        <textarea rows={2} maxLength={500} placeholder="(선택) 확인한 내용 — 예: 11월 초 계약됐다고 들었어요" value={detail} onChange={(e) => setDetail(e.target.value)} />
        {err && <p className="t2-err">{err}</p>}
        <div style={{ display: "flex", gap: 10 }}><button className="t2-cta1" disabled={busy || !reason} onClick={send}>{busy ? "보내는 중…" : "신고 보내기"}</button><button className="t2-lnk mut" onClick={() => setOpen(false)}>닫기</button></div>
      </div>
    </div>
  );
}

export function KokDetail({ it, session, onClose, onLogin, onGo }: { it: KokItem; session: Session | null; onClose: () => void; onLogin: () => void; onGo: (no: string, name: string) => void }) {
  const [d, setD] = useState<KokItem>(it);
  const [msg, setMsg] = useState(""); const [sent, setSent] = useState(false); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { getJson(`/kok/listings/${it.id}`).then(setD).catch(() => {}); }, [it.id]);
  const inquire = async () => {
    if (!session) return;
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API}/kok/listings/${it.id}/inquiry`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders(session) }, body: JSON.stringify({ message: msg }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "보내지 못했어요");
      setSent(true);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const ph = d.photos || [];
  return (
    <div className="t2-modal" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="t2-modal-in legal" style={{ width: "min(640px, 100%)" }} onClick={(e) => e.stopPropagation()}>
        <div className="t2-ph"><h2>{d.name}{d.dong ? ` ${d.dong}동` : ""} <small>{TRADE_L[d.trade]}</small></h2><button className="t2-x" onClick={onClose} aria-label="닫기">×</button></div>
        <p className="t2-favmeta"><i className="t2-kok-badge own">직거래</i>{d.owner_verified && <i className="t2-kok-badge ok">등기 소유자 확인</i>} 올린 날 {(d.created_at || "").slice(0, 10)} · {(d.expires_at || "").slice(0, 10)}까지</p>
        {d.keywords && d.keywords.length > 0 && <p className="t2-kok-kw big">{d.keywords.map((k) => <i key={k}>{k}</i>)}</p>}
        <KokPhotos photos={ph} />
        <div className="t2-kpis">
          <div><span>{TRADE_L[d.trade]}</span><b>{d.price_text}</b></div>
          <div><span>면적</span><b>{d.excl_m2 ? areaLabel(d.excl_m2) : d.area_name || "-"}</b>{d.area_name && d.excl_m2 ? <small>{d.area_name}타입</small> : null}</div>
          <div><span>층 · 방향</span><b>{[d.floor_text, d.direction].filter(Boolean).join(" · ") || "-"}</b></div>
          <div><span>입주</span><b>{d.move_in || "협의"}</b>{d.mgmt_fee ? <small>관리비 약 {Math.round(d.mgmt_fee / 1e4)}만원</small> : null}</div>
        </div>
        {d.feature && <p className="t2-kok-feat">{d.feature}</p>}
        {d.detail && <p className="t2-kok-detail">{d.detail}</p>}
        <div className="t2-calc-row" style={{ gap: 12 }}><button className="t2-lnk" onClick={() => { onClose(); onGo(d.complex_no, d.name); }}>이 단지 실거래·시세 보기</button></div>
        <div className="t2-safe-sec">
          <h3>연락 <small>{d.contact_mode === "phone" ? "소유자가 전화번호를 공개했어요" : "콕집 안 문의 — 소유자에게 알림이 가요"}</small></h3>
          {d.contact_mode === "phone" && d.phone ? <a className="t2-cta1" href={`tel:${d.phone.replace(/[^0-9+]/g, "")}`} style={{ textDecoration: "none" }}>전화 {d.phone}</a>
            : !session ? <div style={{ maxWidth: 420 }}><LoginBox why="문의를 남기려면 로그인이 필요해요." /></div>
            : sent ? <p className="t2-ask-ok">문의를 보냈어요. 소유자가 답하면 알림으로 알려 드려요.</p>
            : (
              <div className="t2-revform">
                <textarea rows={3} maxLength={500} placeholder="예: 이번 주말 집 볼 수 있을까요? 잔금 일정은 협의 가능합니다." value={msg} onChange={(e) => setMsg(e.target.value)} />
                {err && <p className="t2-err">{err}{err.includes("휴대폰") && <> <button className="t2-lnk" onClick={onLogin}>내 정보에서 인증</button></>}</p>}
                <button className="t2-cta1" disabled={busy || msg.trim().length < 5} onClick={inquire}>{busy ? "보내는 중…" : "문의 보내기"}</button>
              </div>
            )}
        </div>
        <KokHistory h={(d as KokItem & { history?: KokHist[] }).history} since={(d.created_at || "").slice(0, 10)} />
        <KokReport lid={it.id} />
        <p className="t2-snote">콕집은 중개 계약의 당사자가 아니고 직거래 매물의 표시만 돕습니다. 계약 전 등기부등본·건축물대장을 직접 확인하세요.</p>
      </div>
    </div>
  );
}

// ── 일반 회원: 내 집 내놓기 ─────────────────────────────────────
type CxHit = { complex_no: string; name: string; region?: string; households?: number };
type Area = { pyeong_name: string; exclusive_area: number | null; household_count: number | null };

export function OwnerTab({ session, onGo }: { session: Session | null; onLogin?: () => void; onGo: (no: string, name: string) => void }) {
  const [me, setMe] = useState<{ phone_verified?: boolean; phone?: string } | null>(null);
  const [mine, setMine] = useState<KokItem[] | null>(null);
  const [mode, setMode] = useState<"list" | "new">("list");
  const [editId, setEditId] = useState<string | null>(null);
  const loadMine = () => { if (!session) return; fetch(`${API}/kok/owner/listings`, { headers: authHeaders(session) }).then((r) => (r.ok ? r.json() : { items: [] })).then((j) => setMine(j.items || [])).catch(() => setMine([])); };
  useEffect(() => {
    if (!session) { setMe(null); setMine(null); return; }
    fetch(`${API}/me`, { headers: authHeaders(session) }).then((r) => (r.ok ? r.json() : null)).then(setMe).catch(() => setMe(null));
    loadMine();
  }, [session]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (!session) return <div className="t2-ask"><p className="t2-safe-lead">내 집을 <b>직거래</b>로 내놓을 수 있어요. 등기부의 소유자 확인을 거쳐야 올라가고, 연락은 콕집 안 문의나 인증한 번호로 받아요. 중개보수 없이 바로 올려요.</p><div style={{ maxWidth: 420 }}><LoginBox why="내 집을 내놓으려면 로그인이 필요해요." /></div></div>;
  if (me && !me.phone_verified) return <div className="t2-ask"><p className="t2-safe-lead">내 집을 내놓으려면 휴대폰 인증이 한 번 필요해요. 인증한 번호가 등록자 연락처로 쓰여요.</p><PhoneBlock session={session} onDone={() => setMe({ ...me, phone_verified: true })} /></div>;
  if (mode === "new") return <OwnerForm session={session} onDone={() => { setMode("list"); loadMine(); }} onCancel={() => setMode("list")} />;
  return (
    <div className="t2-ask">
      <p className="t2-safe-lead">내 집을 <b>직거래</b>로 내놓아요. 단지·동·호와 이름이 등기부의 소유자와 맞아야 올라가고, 30일 뒤 자동으로 내려가요(연장 가능). 한 번에 2건까지.</p>
      <button className="t2-cta1" style={{ maxWidth: 320 }} onClick={() => setMode("new")} disabled={!!mine && mine.filter((m) => m.status === "active").length >= 2}>내 집 내놓기</button>
      <div className="t2-sh"><h3>내가 올린 매물 <small>{mine ? `${mine.length}건` : ""}</small></h3></div>
      {!mine ? <Skel /> : mine.length === 0 ? <p className="t2-sempty">아직 올린 매물이 없어요.</p> : (
        <ul className="t2-kok-list">
          {mine.map((it) => (
            <li key={it.id} className="t2-kok-row mine">
              <KokRow it={it} onOpen={() => onGo(it.complex_no, it.name)} />
              <div className="t2-kok-mine">
                <span className={"st " + (it.status === "active" && !it.expired ? "on" : "")}>{it.status === "active" ? (it.expired ? `기간 끝남(${(it.expires_at || "").slice(0, 10)}) · 자료는 남아 있어요` : `게시 중 · ${(it.expires_at || "").slice(0, 10)}까지`) : it.status === "blocked" ? "관리자가 내림" : "내림"}</span>
                <span>문의 {it.inquiries?.length || 0}건</span>
                {it.status === "active" && !it.expired ? <button className="t2-lnk mut" onClick={async () => { if (!window.confirm("이 매물을 내릴까요?")) return; await fetch(`${API}/kok/owner/listings/${it.id.slice(1)}/close`, { method: "POST", headers: authHeaders(session) }); loadMine(); }}>내리기</button>
                  : it.status !== "blocked" && <button className="t2-lnk" onClick={async () => { await fetch(`${API}/kok/owner/listings/${it.id.slice(1)}/extend`, { method: "POST", headers: authHeaders(session) }); loadMine(); }}>다시 올리기(30일)</button>}
              </div>
              {it.status !== "blocked" && (editId === it.id
                ? <KokExtrasEditor session={session} init={{ photos: it.photos, feature: it.feature, detail: it.detail, keywords: it.keywords }} uploadPath="/kok/owner/photo" savePath={`/kok/owner/listings/${it.id.slice(1)}/extras`} withFeature onSaved={() => { setEditId(null); loadMine(); }} onCancel={() => setEditId(null)} />
                : <div className="t2-kok-mine"><button className="t2-lnk" onClick={() => setEditId(it.id)}>사진·설명·키워드 고치기</button></div>)}
              {it.inquiries && it.inquiries.length > 0 && (
                <table className="t2-tbl"><tbody>{it.inquiries.map((q) => <tr key={q.id}><td className="mut">{q.created_at.slice(5, 16)}</td><td><a className="t2-lnk" href={`tel:${q.from_phone}`}>{q.from_phone}</a></td><td style={{ whiteSpace: "normal" }}>{q.message}</td></tr>)}</tbody></table>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="t2-snote">직거래 안내: 본인 소유 집만 올릴 수 있어요. 가격·면적·층을 사실대로 적어 주세요. 거래가 끝나면 바로 내려 주세요. 콕집은 중개 계약의 당사자가 아니에요.</p>
    </div>
  );
}

function OwnerForm({ session, onDone, onCancel }: { session: Session; onDone: () => void; onCancel: () => void }) {
  const [q, setQ] = useState(""); const [hits, setHits] = useState<CxHit[]>([]); const [cx, setCx] = useState<CxHit | null>(null);
  const [dong, setDong] = useState(""); const [ho, setHo] = useState(""); const [name, setName] = useState("");
  const [vf, setVf] = useState<{ verified: boolean; message?: string; check_id?: number; phone?: string; property?: any } | null>(null);
  const [vbusy, setVbusy] = useState(false);
  const [areas, setAreas] = useState<Area[]>([]); const [area, setArea] = useState<Area | null>(null);
  const [trade, setTrade] = useState("A1"); const [priceEok, setPriceEok] = useState(""); const [rentMan, setRentMan] = useState("");
  const [floor, setFloor] = useState(""); const [total, setTotal] = useState(""); const [consent, setConsent] = useState(true);
  const [dir, setDir] = useState(""); const [moveIn, setMoveIn] = useState("협의"); const [mgmt, setMgmt] = useState("");
  const [feature, setFeature] = useState(""); const [detail, setDetail] = useState(""); const [kw, setKw] = useState(""); const [contact, setContact] = useState<"kok" | "phone">("kok");
  const [photos, setPhotos] = useState<string[]>([]); const [up, setUp] = useState(false);
  const [agree, setAgree] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const [dd, setDd] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const t = q.trim(); if (!t || cx) { setHits([]); return; }
    const id = window.setTimeout(() => getJson(`/complexes/search?q=${encodeURIComponent(t)}&limit=8`).then((j) => setHits(j.items || [])).catch(() => setHits([])), 250);
    return () => window.clearTimeout(id);
  }, [q, cx]);
  useEffect(() => { if (!cx) { setAreas([]); setArea(null); return; } getJson(`/complex/${cx.complex_no}/areas`).then((j) => setAreas(j.items || [])).catch(() => setAreas([])); }, [cx]);
  const verify = async () => {
    if (!cx) return; setVbusy(true); setVf(null);
    try {
      const r = await fetch(`${API}/kok/owner/verify`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders(session) }, body: JSON.stringify({ complex_no: cx.complex_no, dong, ho, name }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : (j.detail?.message || "확인하지 못했어요"));
      setVf(j);
    } catch (e: any) { setVf({ verified: false, message: e.message }); } finally { setVbusy(false); }
  };
  const addPhoto = async (f: File) => {
    if (photos.length >= 10) return; setUp(true);
    const fd = new FormData(); fd.append("document", f);
    try { const r = await fetch(`${API}/kok/owner/photo`, { method: "POST", headers: authHeaders(session), body: fd }); const j = await r.json(); if (r.ok && j.photo) setPhotos((p) => [...p, j.photo]); else setErr(typeof j.detail === "string" ? j.detail : "사진을 올리지 못했어요"); }
    catch { setErr("사진을 올리지 못했어요"); } finally { setUp(false); }
  };
  const eok = parseFloat(priceEok || "0");
  const price = Math.round(eok * 1e8);
  const submit = async () => {
    if (!vf?.verified || !cx) return; setBusy(true); setErr("");
    try {
      const r = await fetch(`${API}/kok/owner/listings`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders(session) },
        body: JSON.stringify({ check_id: vf.check_id, complex_no: cx.complex_no, trade, price, rent: Math.round(parseFloat(rentMan || "0") * 1e4), area_name: area?.pyeong_name || "", excl_m2: area?.exclusive_area || null,
          floor: parseInt(floor || "0"), total_floor: parseInt(total || "0"), floor_consent: consent, direction: dir, move_in: moveIn, mgmt_fee: Math.round(parseFloat(mgmt || "0") * 1e4), feature, detail, keywords: kw.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 8), contact_mode: contact, photos, agree }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "올리지 못했어요");
      onDone();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const step2 = !!vf?.verified;
  return (
    <div className="t2-ask">
      <div className="t2-ask-sec" style={{ borderTop: 0, paddingTop: 0, marginTop: 0 }}>
        <h3><i>1</i>어느 집인가요? <small>단지·동·호와 소유자 이름이 등기부와 맞아야 해요</small></h3>
        {!cx ? (
          <>
            <div className="t2-safe-search"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="단지 이름 (예: 파크리오)" autoFocus /></div>
            {hits.length > 0 && <ul className="t2-kok-hits">{hits.map((h) => <li key={h.complex_no}><button onClick={() => { setCx(h); setQ(h.name); }}><b>{h.name}</b><small>{h.region || ""}{h.households ? ` · ${h.households.toLocaleString()}세대` : ""}</small></button></li>)}</ul>}
          </>
        ) : (
          <p className="t2-safe-target"><b>{cx.name}</b> <small>{cx.region || ""}</small> <button className="t2-lnk mut" onClick={() => { setCx(null); setVf(null); setQ(""); }}>바꾸기</button></p>
        )}
        {cx && !step2 && (
          <>
            <div className="t2-safe-inputs">
              <label>동 <small>숫자만 (예: 101)</small><input value={dong} onChange={(e) => setDong(e.target.value)} inputMode="numeric" /></label>
              <label>호 <small>숫자만 (예: 1203)</small><input value={ho} onChange={(e) => setHo(e.target.value)} inputMode="numeric" /></label>
              <label>소유자 이름 <small>등기부에 있는 이름 그대로</small><input value={name} onChange={(e) => setName(e.target.value)} /></label>
            </div>
            <button className="t2-cta1" style={{ maxWidth: 320 }} disabled={vbusy || !ho || !name} onClick={verify}>{vbusy ? "등기 확인 중… (10초쯤)" : "등기로 소유자 확인"}</button>
            {vf && !vf.verified && <p className="t2-err" style={{ marginTop: 8 }}>{vf.message}</p>}
            <p className="t2-snote">인터넷등기소 자료와 대조해요. 이름이 소유자·등기신청인과 다르면 올릴 수 없어요. 하루 3번까지 확인할 수 있어요.</p>
          </>
        )}
        {step2 && <p className="t2-ask-ok">소유자 확인 완료 · {vf?.property?.address || cx?.name} {dong && `${dong}동`} {ho}호 · 연락처 {vf?.phone}</p>}
      </div>
      {step2 && cx && (
        <>
          <div className="t2-ask-sec">
            <h3><i>2</i>조건</h3>
            <div className="t2-calc-row"><span>거래</span><Seg opts={[{ k: "A1", l: "매매" }, { k: "B1", l: "전세" }, { k: "B2", l: "월세" }]} value={trade} onChange={setTrade} /></div>
            <div className="t2-safe-inputs">
              <label>{trade === "A1" ? "매매가" : "보증금"} <small>억 단위 (예: 12.5)</small><input value={priceEok} onChange={(e) => setPriceEok(e.target.value)} inputMode="decimal" placeholder="12.5" /></label>
              {trade === "B2" && <label>월세 <small>만원</small><input value={rentMan} onChange={(e) => setRentMan(e.target.value)} inputMode="numeric" placeholder="150" /></label>}
              <label>평형 <small>단지 평형에서 고르기</small>
                <Dd id="area" open={dd} setOpen={setDd} label={area ? `${area.pyeong_name}${area.exclusive_area ? ` · ${areaLabel(area.exclusive_area)}` : ""}` : "평형 고르기"} active={!!area}>
                  {areas.map((a) => <button key={a.pyeong_name} className={area?.pyeong_name === a.pyeong_name ? "on" : ""} onClick={() => setArea(a)}>{a.pyeong_name}{a.exclusive_area ? ` · ${areaLabel(a.exclusive_area)}` : ""}{a.household_count ? ` · ${a.household_count}세대` : ""}</button>)}
                </Dd></label>
              <label>층 / 총층 <small>예: 12 / 25</small><span style={{ display: "flex", gap: 6 }}><input value={floor} onChange={(e) => setFloor(e.target.value)} inputMode="numeric" placeholder="12" /><input value={total} onChange={(e) => setTotal(e.target.value)} inputMode="numeric" placeholder="25" /></span></label>
            </div>
            <div className="t2-calc-row"><span>층 표시</span><Seg opts={[{ k: "y", l: "층 그대로" }, { k: "n", l: "고/중/저로" }]} value={consent ? "y" : "n"} onChange={(v) => setConsent(v === "y")} /></div>
            <div className="t2-calc-row"><span>방향</span><Seg opts={DIRS.map((d) => ({ k: d, l: d }))} value={dir} onChange={setDir} /></div>
            <div className="t2-calc-row"><span>입주</span><Seg opts={[{ k: "협의", l: "협의" }, { k: "즉시", l: "즉시 입주" }, { k: "1개월 내", l: "1개월 내" }, { k: "3개월 내", l: "3개월 내" }]} value={moveIn} onChange={setMoveIn} /></div>
            <div className="t2-safe-inputs">
              <label>관리비 <small>월 평균, 만원 (선택)</small><input value={mgmt} onChange={(e) => setMgmt(e.target.value)} inputMode="numeric" placeholder="25" /></label>
              <label>한 줄 특징 <small>40자</small><input value={feature} onChange={(e) => setFeature(e.target.value.slice(0, 40))} placeholder="예: 올수리 · 남향 · 초등학교 3분" /></label>
            </div>
            <label className="t2-fld">상세 설명 <small>1000자 · 평 대신 ㎡를 써 주세요</small><textarea rows={4} maxLength={1000} value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="집 상태, 수리 내역, 입주 가능 시기, 협의 가능한 점 등" /></label>
            <label className="t2-fld" style={{ marginTop: 8 }}>키워드 <small>쉼표로 최대 8개 · 목록에 작은 표로 보여요</small><input className="t2-kok-kwin" value={kw} onChange={(e) => setKw(e.target.value)} placeholder="올수리, 남향, 역 3분" /></label>
          </div>
          <div className="t2-ask-sec">
            <h3><i>3</i>사진 <small>최대 10장 · 얼굴·글자는 자동으로 가려져요</small></h3>
            <div className="t2-kok-upl">
              {photos.map((p) => <span key={p} className="ph"><img src={`${API}/kok/photo/${p}`} alt="" /><button onClick={() => setPhotos((x) => x.filter((y) => y !== p))} aria-label="지우기">×</button></span>)}
              {photos.length < 10 && <button className="add" disabled={up} onClick={() => fileRef.current?.click()}>{up ? "올리는 중…" : "+ 사진"}</button>}
              <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) addPhoto(f); e.target.value = ""; }} />
            </div>
          </div>
          <div className="t2-ask-sec">
            <h3><i>4</i>연락 방법</h3>
            <Seg opts={[{ k: "kok", l: "콕집 안 문의로 받기(번호 비공개)" }, { k: "phone", l: `전화번호 공개 (${vf?.phone || "인증 번호"})` }]} value={contact} onChange={(v) => setContact(v as "kok" | "phone")} />
            <label className="t2-agree" style={{ marginTop: 12 }}>
              <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
              <span><b>직거래 안내</b>에 동의해요 — 본인 소유 집만 올리고, 가격·면적·층을 사실대로 적으며, 거래가 끝나면 바로 내려요. 콕집은 중개 계약의 당사자가 아니고 표시만 도와요. 허위 매물로 신고되면 내려가고 다시 올릴 수 없어요. 30일 뒤 자동으로 내려가요.</span>
            </label>
            {err && <p className="t2-err">{err}</p>}
            <div style={{ display: "flex", gap: 8 }}>
              <button className="t2-cta1" disabled={busy || !agree || price <= 0 || !area} onClick={submit}>{busy ? "올리는 중…" : !area ? "평형을 골라 주세요" : price <= 0 ? "가격을 넣어 주세요" : "콕집에 내놓기"}</button>
              <button className="t2-cta1 ghost" style={{ marginTop: 0, flex: "0 0 120px" }} onClick={onCancel}>취소</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export const useKokTick = () => useMemo(() => Date.now(), []);

// ── 중개사 연동 매물 상세 — 단지 서랍 옆 패널(PC) / 창(휴대폰) ──
type RDetail = KokItem & { history?: KokHist[]; region?: string; confirm_ymd?: string; supply_m2?: number | null; tags?: string[]; rooms?: string | number | null; baths?: string | number | null;
  direction_base?: string; address?: string; ptype_name?: string; total_floor?: number | null; parking?: string; land_use?: string; land_m2?: number | null;
  mgmt_declared?: { fee: number | null; type: string; type_label: string; items: { name: string; amount: number | null }[] } | null;
  finance_price?: number | null; violation?: string; exclusive_rate?: string; approve_ymd?: string; parking_per_household?: number | string | null; verification?: string;
  parking_total?: number | null; presale?: boolean;
  realtor?: { realtor_id: string; name?: string; regno?: string; address?: string; representative?: string; tel?: string; cell?: string };
  complex_facts?: { heat?: string; builder?: string; households?: number | null; households_type?: number | null; parking_total?: number | null; parking_per?: number | null; dongs?: number; subway?: string; entrance?: string; highest_floor?: number | string; lowest_floor?: number | string; approve_ymd?: string };
  py_price?: { supply: number | null; excl: number | null } | null;
  property_tax?: { one_house: { ratio: number; property: number; city: number; edu: number; total: number }; general: { ratio: number; property: number; city: number; edu: number; total: number }; basis: number } | null;
  same_addr?: { count?: number; direct?: number; min?: string; max?: string }; price_change?: string; expose_end?: string;
  public_price?: { year: number; n: number; min?: number; max?: number; median?: number; scope?: string; source?: string } | null;
  acquire?: { rate: number; acq: number; edu: number; rural: number; broker: number; broker_rate: number; total: number; basis: string } | null };
// 이 평형 실제 관리비 — /kok/mgmt: 국토교통부 공동주택관리비 공개(K-apt) 단지 총액을 부과면적으로 나눠 콕집이 환산한 값
type Mgmt = { status: "ready" | "partial" | "pending" | "none"; reason?: string; kapt_name?: string; area?: number; area_basis?: string; households?: number; n?: number;
  avg?: number; avg_common?: number; avg_indiv?: number; avg_ltf?: number; months?: { ym: string; total: number; common: number; indiv: number; ltf: number }[];
  items?: { name: string; avg: number }[]; source?: string;
  facility?: { mgr?: string; guard?: string; clean?: string; cctv?: number; ev?: number; parking?: number; parking_ug?: number; elev?: number; welfare?: string; education?: string; convenient?: string } };
const man = (v?: number | null) => (v == null ? "-" : `${Math.round(v / 1e4).toLocaleString()}만`);
const won = (v?: number | null) => (v == null ? "-" : `${Math.round(v).toLocaleString()}원`);
// 계절 평균 — 월별 공시 합계로 봄(3~5)·여름(6~8)·가을(9~11)·겨울(12~2)을 직접 낸다. 자료가 없는 계절은 비운다.
const SEASONS: { k: string; l: string; m: number[] }[] = [{ k: "spring", l: "봄", m: [3, 4, 5] }, { k: "summer", l: "여름", m: [6, 7, 8] }, { k: "autumn", l: "가을", m: [9, 10, 11] }, { k: "winter", l: "겨울", m: [12, 1, 2] }];
const seasonAvg = (months: { ym: string; total: number | null }[]) => SEASONS.map((sn) => {
  const xs = months.filter((x) => x.total != null && sn.m.includes(parseInt(x.ym.slice(4, 6), 10))).map((x) => x.total as number);
  return { ...sn, avg: xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null, n: xs.length };
});
const eokS = (v?: number | null) => (v == null ? "-" : v >= 1e8 ? `${(v / 1e8).toFixed(v % 1e8 ? 1 : 0)}억` : `${Math.round(v / 1e4).toLocaleString()}만`);
const tel = (s?: string | null) => { const f = (s || "").split(/\s+/)[0].replace(/[^\d]/g, ""); return f.length >= 7 ? f : null; };

export function KokListingPane({ it, onClose, onRealtor, asModal }: { it: KokItem; onClose: () => void; onRealtor: (id: string) => void; asModal: boolean }) {
  const [d, setD] = useState<RDetail | null>(null);
  const [err, setErr] = useState("");
  const [mg, setMg] = useState<Mgmt | null>(null);
  const [mgItems, setMgItems] = useState(false);
  useEffect(() => { setD(null); setErr(""); setMg(null); setMgItems(false); getJson(`/kok/listings/${it.id}`).then(setD).catch((e) => setErr(typeof e === "number" && e === 404 ? "내려갔거나 거래가 끝난 매물이에요." : "불러오지 못했어요.")); }, [it.id]);
  // 관리비는 따로 받는다(첫 단지는 몇 초 걸림). 아직 채워지는 중이면 몇 번 다시 본다.
  useEffect(() => {
    if (!d) return;
    let alive = true; let tries = 0; let timer = 0;
    const q = new URLSearchParams(); if (d.supply_m2) q.set("supply", String(d.supply_m2)); if (d.excl_m2) q.set("excl", String(d.excl_m2)); if (d.area_name) q.set("pyeong", d.area_name);
    const load = () => getJson(`/kok/mgmt/${d.complex_no}?${q.toString()}`).then((j: Mgmt) => {
      if (!alive) return; setMg(j);
      if ((j.status === "pending" || j.status === "partial") && tries++ < 6) timer = window.setTimeout(load, 4000);
    }).catch(() => { if (alive) setMg({ status: "none", reason: "관리비 공개자료를 지금 받지 못했어요" }); });
    load();
    return () => { alive = false; window.clearTimeout(timer); };
  }, [d]);
  const body = (
    <div className="t2-kl">
      <div className="t2-ph"><h2>{d?.name || it.name}{(d?.dong || it.dong) ? ` ${d?.dong || it.dong}동` : ""} <small>{TRADE_L[it.trade]}</small></h2><button className="t2-x" onClick={onClose} aria-label="닫기">×</button></div>
      <p className="t2-favmeta"><i className="t2-kok-badge rt">{d?.realtor?.name || it.realtor_name || "중개사무소"}</i>{d?.kok_since && <> 콕집 등록 {d.kok_since.replace(/-/g, ".")}</>}</p>
      {d && (d.ptype_name || d.address) && <p className="t2-kl-addr">{[d.ptype_name, d.address].filter(Boolean).join(" · ")}</p>}
      {err && <p className="t2-sempty">{err}</p>}
      {!d && !err && <Skel />}
      {d && (
        <>
          {d.keywords && d.keywords.length > 0 && <p className="t2-kok-kw big">{d.keywords.map((k) => <i key={k}>{k}</i>)}</p>}
          {d.photos && d.photos.length > 0 && <KokPhotos photos={d.photos} />}
          <div className="t2-kl-price"><b>{d.price_text}</b></div>
          <table className="t2-tbl t2-kl-tbl"><tbody>
            <tr><th>면적</th><td>{d.excl_m2 ? areaLabel(d.excl_m2) : d.area_name}{d.supply_m2 ? ` · 공급 ${Math.round(d.supply_m2)}㎡` : ""}{d.area_name ? ` · ${d.area_name}타입` : ""}{d.exclusive_rate ? ` · 전용률 ${d.exclusive_rate}%` : ""}</td></tr>
            <tr><th>층 · 방향</th><td>{[d.floor_text ? `${d.floor_text}${d.total_floor ? ` / 총 ${d.total_floor}층` : ""}` : (d.total_floor ? `총 ${d.total_floor}층` : ""),
              d.direction ? (d.direction_base ? `${d.direction} · ${d.direction_base}${/기준$/.test(d.direction_base) ? "" : " 기준"}` : dirLabel(d.direction, d.ptype_name)) : ""].filter(Boolean).join(" · ") || "-"}</td></tr>
            <tr><th>방 · 욕실</th><td>{d.rooms || d.baths ? `방 ${d.rooms ?? "-"} · 욕실 ${d.baths ?? "-"}` : "-"}</td></tr>
            <tr><th>입주</th><td>{d.move_in || "-"}</td></tr>
            {/* 관리비 — 표시 의무 항목이라 줄은 항상 둔다. 분양권은 준공 전이라 해당 없음 */}
            {(() => {
              if (d.presale) return <tr><th>관리비</th><td>준공 전 · 해당 없음</td></tr>;
              const g = d.mgmt_declared; const man = (v: number | null) => (v == null ? "확인 불가" : `${Math.round(v / 1e4).toLocaleString()}만`);
              if (!g || (!g.fee && !g.type_label && g.items.length === 0)) return <tr><th>관리비</th><td>중개사 표시 없음<small className="blk">실제 부과 내역은 아래 공개자료(K-apt)</small></td></tr>;
              const head = g.fee ? `월 ${Math.round(g.fee / 1e4).toLocaleString()}만원` : g.type_label || "-";
              return <tr><th>관리비</th><td>{head}{g.type_label && g.fee ? ` · ${g.type_label}` : ""}{g.items.length > 0 && <small className="blk">{g.items.map((x) => `${x.name} ${man(x.amount)}`).join(" · ")}</small>}<small className="blk">중개사 표시 금액 · 실제 부과 내역은 아래 공개자료</small></td></tr>;
            })()}
            {(d.land_use || d.land_m2) && <tr><th>토지</th><td>{[d.land_use ? `지목 ${d.land_use}` : "", d.land_m2 ? `${Math.round(d.land_m2 * 10) / 10}㎡` : ""].filter(Boolean).join(" · ")}</td></tr>}
            {/* 분양권은 아직 사용승인 전 — 단지 자료의 날짜는 입주(준공) 예정 */}
            <tr><th>{d.presale ? "입주 예정" : "사용승인"}</th><td>{d.approve_ymd ? `${d.approve_ymd.slice(0, 4)}.${d.approve_ymd.slice(4, 6)}` : "-"}{d.violation === "Y" ? " · 위반건축물" : ""}</td></tr>
            <tr><th>주차</th><td>{[d.parking_total ? `총 ${d.parking_total.toLocaleString()}대` : "", d.parking_per_household ? `세대당 ${d.parking_per_household}대` : "", !d.parking_total && !d.parking_per_household && d.parking ? `${d.parking}` : ""].filter(Boolean).join(" · ") || "-"}</td></tr>
          </tbody></table>
          {d.description && <div className="t2-kok-desc"><div className="t2-pf-h"><h3>중개사가 콕집에 쓴 설명</h3></div><p>{d.description}</p></div>}
          {/* 단지 — 콕집 단지 자료 + K-apt 관리 현황을 한 묶음으로. 큰 숫자 넷 뒤에 짧은 정의 목록 */}
          {d.complex_facts && d.complex_facts.households && (() => {
            const f = d.complex_facts!, fa = mg?.facility; const hh = f.households || 0;
            const kpi = [
              f.parking_per ? { b: `${f.parking_per}대`, s: "세대당 주차", t: f.parking_total ? `총 ${f.parking_total.toLocaleString()}대` : "" } : null,
              fa?.elev && hh ? { b: `${Math.round(hh / fa.elev)}세대`, s: "승강기 1대당", t: `${fa.elev}대` } : null,
              fa?.cctv && hh ? { b: `${fa.cctv.toLocaleString()}대`, s: "CCTV", t: `100세대당 ${Math.round((fa.cctv / hh) * 100)}대` } : null,
              fa?.ev ? { b: `${fa.ev}기`, s: "전기차 충전기", t: fa.parking_ug ? `지하 주차 ${fa.parking_ug.toLocaleString()}대` : "" } : null,
            ].filter(Boolean) as { b: string; s: string; t: string }[];
            return (
              <>
                <div className="t2-pf-h"><h3>단지</h3><small>{[f.builder, f.heat, f.approve_ymd ? `${f.approve_ymd.slice(0, 4)}.${f.approve_ymd.slice(4, 6)} 사용승인` : ""].filter(Boolean).join(" · ")}</small></div>
                {kpi.length > 0 && <div className="t2-pf-kpi">{kpi.map((k) => <div key={k.s}><b>{k.b}</b><span>{k.s}{k.t ? <small> · {k.t}</small> : null}</span></div>)}</div>}
                <dl className="t2-pf-dl">
                  <div><dt>규모</dt><dd>{hh.toLocaleString()}세대{f.dongs ? ` · ${f.dongs}개 동` : ""}{f.highest_floor ? ` · ${f.lowest_floor && f.lowest_floor !== f.highest_floor ? `${f.lowest_floor}~` : ""}${f.highest_floor}층` : ""}{f.households_type ? ` · 이 평형 ${f.households_type}세대` : ""}{f.entrance ? ` · ${f.entrance}` : ""}</dd></div>
                  {f.subway && <div><dt>역</dt><dd>{f.subway}</dd></div>}
                  {fa && (fa.mgr || fa.guard || fa.clean) && <div><dt>관리</dt><dd>{[fa.mgr && `관리 ${fa.mgr}`, fa.guard && `경비 ${fa.guard}`, fa.clean && `청소 ${fa.clean}`].filter(Boolean).join(" · ")}</dd></div>}
                  {fa?.welfare && <div><dt>부대시설</dt><dd>{fa.welfare}</dd></div>}
                  {fa && (fa.education || fa.convenient) && <div><dt>주변</dt><dd>{[fa.education, fa.convenient].filter(Boolean).join(" · ")}</dd></div>}
                </dl>
                {fa && (fa.mgr || fa.cctv || fa.elev) && <p className="t2-pf-src">관리 인원·설비는 국토교통부 공동주택관리정보(K-apt) 공개 자료</p>}
              </>
            );
          })()}
          {(!mg || mg.status === "pending") && (
            <div className="t2-kl-sec"><h3>이 평형 실제 관리비 <small>국토교통부 공동주택관리비 공개(K-apt)</small></h3>
              <p className="mut">관리비 공개자료를 받아오는 중이에요…</p></div>
          )}
          {mg && mg.status === "none" && (
            <div className="t2-kl-sec"><h3>이 평형 실제 관리비 <small>국토교통부 공동주택관리비 공개(K-apt)</small></h3>
              <p className="mut">{mg.reason || "이 단지의 관리비 공개자료가 없어요"}</p></div>
          )}
          {mg && mg.months && mg.months.length > 0 && (
            <div className="t2-kl-sec"><h3>이 평형 실제 관리비 <small>국토교통부 공동주택관리비 공개(K-apt) · {mg.area_basis} {mg.area ? Math.round(mg.area) : ""}㎡ 기준 · {mg.n}개월{mg.status === "partial" ? " · 더 받는 중" : ""}</small></h3>
              <div className="t2-kpis small four">
                {seasonAvg(mg.months).map((sn) => <div key={sn.k}><span>{sn.l}{sn.n ? ` ${sn.n}개월` : ""}</span><b>{man(sn.avg)}</b></div>)}
              </div>
              <p className="t2-snote" style={{ margin: "0 0 6px" }}>월평균 {man(mg.avg)} = 공용관리비 {man(mg.avg_common)} + 개별사용료 {man(mg.avg_indiv)} + 장기수선충당금 {man(mg.avg_ltf)}</p>
              <table className="t2-tbl t2-kl-mo"><thead><tr><th>월</th><th className="num">합계</th><th className="num">공용관리비</th><th className="num">개별사용료</th><th className="num">장충금</th></tr></thead>
                <tbody>{mg.months.map((m) => <tr key={m.ym}><td>{m.ym.slice(2, 4)}.{m.ym.slice(4, 6)}</td><td className="num"><b>{man(m.total)}</b></td><td className="num">{man(m.common)}</td><td className="num">{man(m.indiv)}</td><td className="num">{man(m.ltf)}</td></tr>)}</tbody></table>
              {mg.items && mg.items.length > 0 && (
                <>
                  <button className="t2-lnk" onClick={() => setMgItems(!mgItems)}>{mgItems ? "항목별 접기" : `항목별 월평균 보기 (${mg.items.length}항목)`}</button>
                  {mgItems && <table className="t2-tbl t2-kl-mo"><tbody>{mg.items.map((x) => <tr key={x.name}><td>{x.name}</td><td className="num">{won(x.avg)}</td></tr>)}</tbody></table>}
                </>
              )}
            </div>
          )}
          {/* 거래 비용 — 묶음(살 때·해마다) 머리줄에 합계, 그 아래 세목(취득세·재산세…)을 한 줄씩. 숫자는 오른쪽 정렬 */}
          {(d.public_price || d.acquire || d.py_price) && (() => {
            const pct = (r: number) => `${(r * 100).toFixed(2).replace(/\.?0+$/, "")}%`;
            const pp = d.public_price; const pt = d.property_tax; const aq = d.acquire;
            const won = (v?: number | null) => (v == null ? "-" : v >= 1e8 ? eokS(v) : `${Math.round(v / 1e4).toLocaleString()}만`);
            return (
              <section className="t2-cost">
                <div className="t2-pf-h"><h3>거래 비용</h3><small>콕집 산식 · 참고용</small></div>
                {aq && (
                  <div className="grp">
                    <div className="hd"><span>살 때 한 번</span><b>{won(aq.total)}</b></div>
                    <div className="it"><span>취득세 <small>{pct(aq.rate)}</small></span><b>{won(aq.acq)}</b></div>
                    <div className="it"><span>지방교육세</span><b>{won(aq.edu)}</b></div>
                    {aq.rural ? <div className="it"><span>농어촌특별세</span><b>{won(aq.rural)}</b></div> : null}
                    <div className="it"><span>중개보수 <small>상한 {aq.broker_rate}%</small></span><b>{won(aq.broker)}</b></div>
                    <p className="nt">{aq.basis}</p>
                  </div>
                )}
                {pt && (
                  <div className="grp">
                    <div className="hd"><span>해마다 <small>1주택 보유세</small></span><b>{won(pt.one_house.total)}원</b></div>
                    <div className="it"><span>재산세</span><b>{won(pt.one_house.property)}</b></div>
                    <div className="it"><span>도시지역분</span><b>{won(pt.one_house.city)}</b></div>
                    <div className="it"><span>지방교육세</span><b>{won(pt.one_house.edu)}</b></div>
                    <p className="nt">1주택 외 연 {won(pt.general.total)}원 · 공시 중앙값 {eokS(pt.basis)} 기준 · 종합부동산세 별도</p>
                  </div>
                )}
                {(d.py_price?.supply || (pp && pp.n > 0)) && (
                  <div className="grp">
                    {d.py_price?.supply ? <div className="it top"><span>평당가 <small>공급면적</small></span><b>{won(d.py_price.supply)}원</b></div> : null}
                    {d.py_price?.excl ? <div className="it"><span>평당가 <small>전용면적</small></span><b>{won(d.py_price.excl)}원</b></div> : null}
                    {pp && pp.n > 0 && <div className="it"><span>공시가격 <small>{pp.year} · {pp.scope} {pp.n}호</small></span><b>{pp.min === pp.max ? eokS(pp.median) : `${eokS(pp.min)}~${eokS(pp.max)}`}</b></div>}
                    {pp && pp.n === 0 && <div className="it"><span>공시가격 <small>{pp.year}</small></span><b className="mut">못 찾음</b></div>}
                  </div>
                )}
                {pp?.source && <p className="t2-pf-src">{pp.source}</p>}
              </section>
            );
          })()}
          {/* 광고 설명문은 보여 주지 않는다(광고 쪽 문구를 그대로 옮기면 콕집 표시의 신뢰가 깎임) */}
          {d.realtor && (
            <section className="t2-office">
              <h3>{d.realtor.name || "중개사무소"}</h3>
              <p className="meta">{[d.realtor.representative ? `대표 ${d.realtor.representative}` : "", d.realtor.regno ? `등록번호 ${d.realtor.regno}` : "", d.realtor.address || ""].filter(Boolean).join(" · ")}</p>
              <p className="acts">
                {tel(d.realtor.tel) && <a href={`tel:${tel(d.realtor.tel)}`}>전화 {d.realtor.tel!.split(/\s+/)[0]}</a>}
                {tel(d.realtor.cell) && tel(d.realtor.cell) !== tel(d.realtor.tel) && <a href={`tel:${tel(d.realtor.cell)}`}>휴대폰 {d.realtor.cell}</a>}
                <button type="button" onClick={() => onRealtor(d.realtor!.realtor_id)}>사무소 상세</button>
              </p>
            </section>
          )}
          <KokHistory h={d.history} since={d.kok_since} />
          <KokReport lid={it.id} />
          <p className="t2-pf-src" style={{ marginTop: 12 }}>표시 내용의 책임은 광고한 중개사무소에 있어요. 계약 전 현장과 등기부를 확인하세요.</p>
        </>
      )}
    </div>
  );
  if (asModal) return <div className="t2-modal" role="dialog" aria-modal="true" onClick={onClose}><div className="t2-modal-in legal" style={{ width: "min(640px, 100%)" }} onClick={(e) => e.stopPropagation()}>{body}</div></div>;
  return <aside className="t2-drawer t2-drawer2">{body}</aside>;
}
