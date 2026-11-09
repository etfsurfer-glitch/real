// 콕집매물 — 지도 시험판 노출(목록·상세·문의)과 일반 회원 직거래 등록(내 집 내놓기).
// 중개사 연동분은 서버가 광고 중 매물을 그대로 주고, 직거래분은 등기 소유자 확인을 통과한 것만 올라온다.
import { useEffect, useMemo, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { API, getJson, Dd, Skel } from "./Drawer";
import { Seg } from "./Stats";
import { LoginBox, PhoneBlock, authHeaders } from "./Request";
import { areaLabel } from "../src/lib/area";

export type KokItem = { id: string; kind: "owner" | "realtor"; complex_no: string; name: string; lat?: number; lng?: number; trade: string;
  price: number; rent: number; price_text: string; area_name: string; excl_m2: number | null; floor_text: string; direction: string;
  realtor_id?: string; realtor_name?: string; owner_verified: boolean; photos?: string[]; feature?: string; detail?: string; dong?: string;
  move_in?: string; mgmt_fee?: number | null; contact_mode?: string; phone?: string; created_at?: string; expires_at?: string; status?: string;
  inquiries?: { id: number; from_phone: string; message: string; created_at: string }[] };
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
          <small>{it.kind === "owner" ? <><i className="t2-kok-badge own">직거래</i>{it.owner_verified && <i className="t2-kok-badge ok">소유자 확인</i>}</> : <i className="t2-kok-badge rt">{it.realtor_name || "중개사무소"}</i>}</small>
        </span>
        <span className="p"><b>{it.price_text}</b>{it.kind === "realtor" && it.feature ? <em>{it.feature.slice(0, 18)}</em> : null}</span>
      </button>
    </li>
  );
}

// 매물찾기 패널 아래 '콕집 매물' 칸
export function KokPanelList({ items, onOpen, onGo }: { items: KokItem[]; onOpen: (it: KokItem) => void; onGo: (no: string, name: string) => void }) {
  if (items.length === 0) return <p className="t2-empty sm">이 범위엔 아직 콕집 매물이 없어요. 로그인하면 내 집을 직거래로 내놓을 수 있어요.</p>;
  return (
    <ul className="t2-kok-list">
      {items.slice(0, 40).map((it) => <KokRow key={it.id} it={it} onOpen={(x) => (x.kind === "owner" ? onOpen(x) : onGo(x.complex_no, x.name))} />)}
    </ul>
  );
}

// 직거래 매물 상세(지도 안 작은 창) — 사진·조건·소유자 확인·문의
export function KokDetail({ it, session, onClose, onLogin, onGo }: { it: KokItem; session: Session | null; onClose: () => void; onLogin: () => void; onGo: (no: string, name: string) => void }) {
  const [d, setD] = useState<KokItem>(it);
  const [msg, setMsg] = useState(""); const [sent, setSent] = useState(false); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [pi, setPi] = useState(0);
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
        {ph.length > 0 && (
          <div className="t2-kok-photos">
            <img src={`${API}${ph[pi]}`} alt="" />
            {ph.length > 1 && <div className="thumbs">{ph.map((p, i) => <img key={p} src={`${API}${p}`} alt="" className={i === pi ? "on" : ""} onClick={() => setPi(i)} />)}</div>}
          </div>
        )}
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
                <span className={"st " + (it.status === "active" ? "on" : "")}>{it.status === "active" ? `게시 중 · ${(it.expires_at || "").slice(0, 10)}까지` : it.status === "blocked" ? "관리자가 내림" : "내림"}</span>
                <span>문의 {it.inquiries?.length || 0}건</span>
                {it.status === "active" ? <button className="t2-lnk mut" onClick={async () => { if (!window.confirm("이 매물을 내릴까요?")) return; await fetch(`${API}/kok/owner/listings/${it.id.slice(1)}/close`, { method: "POST", headers: authHeaders(session) }); loadMine(); }}>내리기</button>
                  : it.status !== "blocked" && <button className="t2-lnk" onClick={async () => { await fetch(`${API}/kok/owner/listings/${it.id.slice(1)}/extend`, { method: "POST", headers: authHeaders(session) }); loadMine(); }}>다시 올리기(30일)</button>}
              </div>
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
  const [feature, setFeature] = useState(""); const [detail, setDetail] = useState(""); const [contact, setContact] = useState<"kok" | "phone">("kok");
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
          floor: parseInt(floor || "0"), total_floor: parseInt(total || "0"), floor_consent: consent, direction: dir, move_in: moveIn, mgmt_fee: Math.round(parseFloat(mgmt || "0") * 1e4), feature, detail, contact_mode: contact, photos, agree }) });
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
