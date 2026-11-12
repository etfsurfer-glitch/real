// 중개사라운지 '콕집매물' 메뉴 — 라운지의 중심 화면.
// ① 전환: 광고 중 매물을 콕집매물로(약관 동의 → 매일 동기화) + 전환분에 사진·설명·키워드 쓰기
// ② 전용 등록: 광고와 무관하게 콕집에만 올리는 매물(아파트부터 상가·토지까지 모든 유형)
// ③ 관리: 전환분·전용분을 한 표에서 — 상태·검색·수정·내리기
// ④ 점검: 표시·광고 필수 항목, 콕집 노출 품질, 실거래 대비 가격, 평형 불일치, 중복, 오래된 등록, 사무소 표시 항목
// 광고 쪽 문구(설명·특징·태그)는 어디에도 옮기지 않는다. 콕집에 보이는 글과 사진은 전부 여기서 중개사가 직접 쓴다.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { KokOptinModal, KokMyListings, MyExtrasEditor, useKokStatus } from "../components/KokOptinModal";
import type { Office } from "./bizTabs";

const API = import.meta.env.VITE_API_BASE;
const TRADE_L: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세" };
const DIRS = ["남향", "남동향", "남서향", "동향", "서향", "북향", "북동향", "북서향"];
const COMPLEX_TYPES = new Set(["APT", "OPST", "ABYG", "OBYG", "JGC"]);
const FLOORED = new Set(["APT", "OPST", "ABYG", "OBYG", "JGC", "VL", "OR", "SG", "SMS", "GM", "GJCG"]);
const HOUSING = new Set(["APT", "OPST", "ABYG", "OBYG", "JGC", "VL", "DDDGG", "OR"]);
type TabKey = "convert" | "direct" | "manage" | "audit";

type Overview = { opted: boolean; agreed_at: string | null; needs_reagree: boolean; converted: { active: number; closed: number; hold: number; with_extras: number };
  direct: { active: number; closed: number; hold: number }; ads_preview: number | null; synced_at: string | null; office_ok: boolean; office_reasons: string[] };
export type DirectItem = { id: string; source: "direct"; ptype: string; ptype_name: string; complex_no: string; name: string; address: string; trade: string; price: number | null; rent: number | null;
  price_text: string; area_name: string; supply_m2: number | null; excl_m2: number | null; land_m2: number | null; floor: number | null; total_floor: number | null; floor_text: string;
  direction: string; direction_base?: string; dong: string; move_in: string; mgmt_fee: number | null; rooms: string | null; baths: string | null; kok_since: string; status: string; photos: string[]; keywords: string[]; description: string;
  approve_ymd?: string; parking?: string; land_use?: string; mgmt_declared?: { fee: number | null; items: { name: string; amount: number | null }[] } | null;
  publish_state?: string; hold_reasons?: string[] };
type ConvItem = { id: string; complex_no: string; name: string; dong?: string; trade: string; area_name: string; excl_m2: number | null; floor_text: string; direction: string; price_text: string;
  kok_since?: string; photos: string[]; keywords: string[]; description: string; status: string; publish_state?: string; hold_reasons?: string[] };
type AuditIssue = { code: string; level: "fail" | "warn" | "info"; msg: string };
type AuditItem = { id: string; source: string; ptype: string; ptype_name: string; name: string; dong: string; trade: string; price_text: string; area_name: string; excl: number | null; floor: number | null; level: "fail" | "warn" | "info" | "ok"; issues: AuditIssue[] };
type Audit = { summary: { total: number; fail: number; warn: number; info: number; ok: number; by_code: Record<string, number> }; office: { name: string | null; regno: string; tel: string | null; cell: string | null; issues: AuditIssue[] }; items: AuditItem[] };

const m2 = (v: number | null | undefined) => (v ? `${Math.round(v * 10) / 10}㎡` : "");
const dt = (s?: string | null) => (s ? s.slice(0, 16).replace("T", " ") : "");

export function KokScreen({ authH, office }: { authH: () => Record<string, string>; office: Office }) {
  const [sp, setSp] = useSearchParams();
  const tab = (sp.get("tab") as TabKey) || "";
  const [ov, setOv] = useState<Overview | null>(null);
  const loadOv = useCallback(() => fetch(`${API}/lounge/kok/overview`, { headers: authH() }).then((r) => (r.ok ? r.json() : null)).then(setOv).catch(() => {}), [authH]);
  useEffect(() => { loadOv(); }, [loadOv]);
  const cur: TabKey = tab || (ov ? (ov.opted || ov.direct.active ? "manage" : "convert") : "manage");
  const go = (t: TabKey, extra?: Record<string, string>) => { const n = new URLSearchParams(); n.set("tab", t); Object.entries(extra || {}).forEach(([k, v]) => n.set(k, v)); setSp(n); };
  const total = ov ? ov.converted.active + ov.direct.active : 0;
  return (
    <div className="kokm">
      <div className="kokm-head">
        <div><h1>콕집매물</h1><p>광고와 별개로 콕집이 직접 보여 주는 우리 사무소 매물. 전환하거나 콕집에만 올리고, 한 표에서 관리하고, 점검까지.</p></div>
        <div className="kokm-kpi">
          <div><b>{ov ? total.toLocaleString() : "-"}</b><span>게시 중<small>전환 {ov?.converted.active ?? 0} · 전용 {ov?.direct.active ?? 0}</small></span></div>
          <div className={ov && ov.converted.hold + ov.direct.hold ? "warn" : ""}><b>{ov ? (ov.converted.hold + ov.direct.hold).toLocaleString() : "-"}</b><span>게시 전<small>필수 항목이 빠진 매물</small></span></div>
          <div><b>{ov ? ov.converted.with_extras.toLocaleString() : "-"}</b><span>사진·설명 채움<small>전환분 기준</small></span></div>
          <div><b>{ov?.synced_at ? ov.synced_at.slice(5, 16) : "-"}</b><span>마지막 반영<small>매일 새벽 + 동의 직후</small></span></div>
          <div><b>{ov ? (ov.converted.closed + ov.direct.closed).toLocaleString() : "-"}</b><span>내려간 매물<small>이력으로 남아요</small></span></div>
        </div>
      </div>
      {ov && !ov.office_ok && <p className="kokm-gate">사무소 표시 항목이 빠져 있어 콕집매물이 공개되지 않고 있어요: {ov.office_reasons.join(" · ")}. <Link to="/biz/office">내 사무소</Link>에서 연결을 확인하거나 <Link to="/biz/edit">정보수정요청</Link>으로 알려 주세요. 채워지면 자동으로 공개돼요.</p>}
      <nav className="biz-navtabs kokm-tabs" aria-label="콕집매물 탭">
        {([["convert", "콕집매물로 전환"], ["direct", "콕집 전용 등록"], ["manage", "전체 관리"], ["audit", "콕집매물 점검"]] as [TabKey, string][]).map(([k, l]) => (
          <button key={k} type="button" className={`biz-navtab${cur === k ? " on" : ""}`} onClick={() => go(k)}>{l}</button>
        ))}
      </nav>
      {cur === "convert" && <ConvertTab authH={authH} ov={ov} onChanged={loadOv} />}
      {cur === "direct" && <DirectTab authH={authH} onChanged={loadOv} openId={sp.get("open")} />}
      {cur === "manage" && <ManageTab authH={authH} onChanged={loadOv} openId={sp.get("open")} onEditDirect={(id) => go("direct", { open: id })} />}
      {cur === "audit" && <AuditTab authH={authH} office={office} onFix={(id) => (id.startsWith("D") ? go("direct", { open: id }) : go("manage", { open: id }))} />}
    </div>
  );
}

// ── ① 전환 ─────────────────────────────────────────────────────────────
function ConvertTab({ authH, ov, onChanged }: { authH: () => Record<string, string>; ov: Overview | null; onChanged: () => void }) {
  const { st, reload } = useKokStatus(authH, true);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const off = async () => {
    if (!window.confirm("콕집매물 전환을 해제할까요? 콕집 지도에서 우리 사무소 전환분 표시가 바로 멈춰요. 콕집 전용 등록분은 그대로예요.")) return;
    setBusy(true); await fetch(`${API}/lounge/kok/optout`, { method: "POST", headers: authH() }).catch(() => null); setBusy(false); reload(); onChanged();
  };
  if (!st) return <p className="muted kokm-pad">불러오는 중…</p>;
  return (
    <div className="kokm-sec">
      {!st.opted ? (
        <>
          <div className="kokm-lead">
            <b>지금 광고 중인 매물 {st.listings.total.toLocaleString()}건</b>을 콕집매물로 전환할 수 있어요. 매매 {st.listings.A1} · 전세 {st.listings.B1} · 월세 {st.listings.B2}.
            <p>전환하면 광고의 표시 정보(소재지·면적·가격·층·방향·입주·방/욕실)만 콕집매물 자료로 가져와요. 광고 상태는 매일 새벽 한 번 반영되고, 광고가 내려가면 다음 반영 때 콕집에서도 빠져요. 광고 문구·사진은 옮기지 않아요. 콕집에 보일 사진·설명·키워드는 전환 뒤 이 화면에서 직접 써요. 무료이고 언제든 해제할 수 있어요.</p>
          </div>
          <button className="auth-btn kakao kokm-cta" onClick={() => setOpen(true)}>콕집매물로 전환하기 (약관 동의)</button>
        </>
      ) : (
        <>
          <dl className="kokm-dl">
            <div><dt>상태</dt><dd><b>전환 중</b> · 게시 {ov?.converted.active ?? st.listings.total}건{ov?.converted.hold ? <> · <span className="kokm-bad">게시 전 {ov.converted.hold}건</span>(광고에 빠진 필수 항목이 있어요 — 전체 관리에서 확인)</> : null} · 내려간 {ov?.converted.closed ?? 0}건</dd></div>
            <div><dt>반영</dt><dd>{st.synced_at ? `${dt(st.synced_at)} 마지막 반영` : "첫 반영 대기 중(몇 분)"} · 매일 새벽 자동, 광고가 내려가면 다음 반영 때 제외</dd></div>
            <div><dt>동의</dt><dd>{st.agreed_at?.slice(0, 10)} · 약관 {st.terms_version}{st.needs_reagree && <> · <button className="kokm-lnk" onClick={() => setOpen(true)}>바뀐 약관 동의하기</button></>}</dd></div>
            <div><dt>해제</dt><dd><button className="kokm-lnk mut" disabled={busy} onClick={off}>전환 해제</button> · 해제하면 전환분 표시가 바로 멈추고 자료는 표시 중단 상태로 남아요</dd></div>
          </dl>
          <h3 className="kokm-h3">전환된 매물에 콕집용 사진·설명·키워드 쓰기</h3>
          <KokMyListings authH={authH} defaultOpen />
        </>
      )}
      {open && <KokOptinModal authH={authH} realtorId={st.realtor_id} st={st} onClose={() => setOpen(false)} onDone={() => { setOpen(false); reload(); onChanged(); }} />}
    </div>
  );
}

// ── ② 콕집 전용 등록 ────────────────────────────────────────────────────
type MgmtItem = { name: string; amount: string };
type Draft = { ptype: string; trade: string; priceEok: string; rentMan: string; complex_no: string; complex_name: string; address: string; dong: string; ho: string;
  area_name: string; supply_m2: string; excl_m2: string; land_m2: string; floor: string; total_floor: string; direction: string; direction_base: string; move_in: string; mgmt_fee: string;
  rooms: string; baths: string; approve_ymd: string; parking: string; land_use: string; items: MgmtItem[]; photos: string[]; description: string; keywords: string };
const EMPTY: Draft = { ptype: "APT", trade: "A1", priceEok: "", rentMan: "", complex_no: "", complex_name: "", address: "", dong: "", ho: "", area_name: "", supply_m2: "", excl_m2: "", land_m2: "",
  floor: "", total_floor: "", direction: "", direction_base: "", move_in: "협의", mgmt_fee: "", rooms: "", baths: "", approve_ymd: "", parking: "", land_use: "", items: [], photos: [], description: "", keywords: "" };
const ymdDot = (s: string) => (s.length >= 6 ? `${s.slice(0, 4)}.${s.slice(4, 6)}${s.length >= 8 ? `.${s.slice(6, 8)}` : ""}` : s);
const toDraft = (it: DirectItem): Draft => ({ ptype: it.ptype, trade: it.trade, priceEok: it.price ? String(it.price / 1e8) : "", rentMan: it.rent ? String(Math.round(it.rent / 1e4)) : "",
  complex_no: it.complex_no || "", complex_name: it.complex_no ? it.name : "", address: it.address || "", dong: it.dong || "", ho: "", area_name: it.area_name || "",
  supply_m2: it.supply_m2 ? String(it.supply_m2) : "", excl_m2: it.excl_m2 ? String(it.excl_m2) : "", land_m2: it.land_m2 ? String(it.land_m2) : "", floor: it.floor ? String(it.floor) : "",
  total_floor: it.total_floor ? String(it.total_floor) : "", direction: it.direction || "", direction_base: it.direction_base || "", move_in: it.move_in || "협의", mgmt_fee: it.mgmt_fee ? String(Math.round(it.mgmt_fee / 1e4)) : "",
  rooms: it.rooms || "", baths: it.baths || "", approve_ymd: ymdDot(it.approve_ymd || ""), parking: it.parking || "", land_use: it.land_use || "",
  items: (it.mgmt_declared?.items || []).map((x) => ({ name: x.name, amount: x.amount != null ? String(Math.round(x.amount / 1e4)) : "" })),
  photos: it.photos.map((u) => u.replace(/^.*\/kok\/photo\//, "")), description: it.description || "", keywords: it.keywords.join(", ") });

// 종류별 표시·광고 필수 항목 — 서버(_kok_required)와 같은 집합. 단지형의 사용승인·주차는 단지 자료로 채워진다.
const REQ: Record<string, string[]> = {
  APT: ["complex_no", "excl_m2", "floor", "total_floor", "direction", "direction_base", "rooms", "baths", "move_in", "mgmt_fee"],
  OPST: ["complex_no", "excl_m2", "floor", "total_floor", "direction", "direction_base", "rooms", "baths", "move_in", "mgmt_fee"],
  // 분양권은 준공 전 — 관리비 해당 없음(서버 _KOK_PRESALE)
  ABYG: ["complex_no", "excl_m2", "floor", "total_floor", "direction", "direction_base", "rooms", "baths", "move_in"],
  OBYG: ["complex_no", "excl_m2", "floor", "total_floor", "direction", "direction_base", "rooms", "baths", "move_in"],
  JGC: ["complex_no", "excl_m2", "floor", "total_floor", "direction", "direction_base", "rooms", "baths", "move_in", "mgmt_fee"],
  VL: ["address", "excl_m2", "floor", "total_floor", "direction", "direction_base", "rooms", "baths", "move_in", "mgmt_fee", "approve_ymd", "parking"],
  OR: ["address", "excl_m2", "floor", "total_floor", "direction", "direction_base", "rooms", "baths", "move_in", "mgmt_fee", "approve_ymd", "parking"],
  DDDGG: ["address", "excl_m2", "land_m2", "total_floor", "direction", "direction_base", "rooms", "baths", "move_in", "approve_ymd", "parking"],
  SG: ["address", "excl_m2", "floor", "total_floor", "direction", "direction_base", "move_in", "mgmt_fee", "approve_ymd", "parking"],
  SMS: ["address", "excl_m2", "floor", "total_floor", "direction", "direction_base", "move_in", "mgmt_fee", "approve_ymd", "parking"],
  GM: ["address", "excl_m2", "land_m2", "total_floor", "move_in", "approve_ymd", "parking"],
  GJCG: ["address", "excl_m2", "land_m2", "total_floor", "move_in", "approve_ymd", "parking"],
  TJ: ["address", "land_m2", "land_use"],
  ETC: ["address"],
};
const LABEL: Record<string, string> = { complex_no: "단지", address: "소재지", excl_m2: "전용면적", land_m2: "대지(토지) 면적", floor: "해당 층", total_floor: "총 층수", direction: "방향", direction_base: "방향 기준",
  rooms: "방 수", baths: "욕실 수", move_in: "입주 가능일", mgmt_fee: "관리비", approve_ymd: "사용승인일", parking: "주차대수", land_use: "지목", rent: "월세" };
const LAND_USES = ["대", "전", "답", "과수원", "임야", "잡종지", "공장용지", "창고용지", "주차장", "도로", "하천", "기타"];
const MGMT_NAMES = ["일반관리비", "전기료", "수도료", "가스사용료", "난방비", "인터넷", "TV", "기타"];

export function DirectForm({ authH, init, editId, ptypes, onSaved, onCancel }: { authH: () => Record<string, string>; init?: Draft; editId?: string; ptypes: Record<string, string>; onSaved: () => void; onCancel: () => void }) {
  const [d, setD] = useState<Draft>(init || EMPTY);
  const set = (k: keyof Draft, v: string | string[] | MgmtItem[]) => setD((x) => ({ ...x, [k]: v }));
  const [q, setQ] = useState(init?.complex_name || ""); const [hits, setHits] = useState<{ complex_no: string; name: string; region?: string; households?: number }[]>([]);
  const [areas, setAreas] = useState<{ pyeong_name: string; exclusive_area: number | null; supply_area: number | null }[]>([]);
  const [up, setUp] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const [led, setLed] = useState<{ busy: boolean; msg: string }>({ busy: false, msg: "" });
  const fileRef = useRef<HTMLInputElement>(null);
  const isCx = COMPLEX_TYPES.has(d.ptype);
  const req = new Set(REQ[d.ptype] || REQ.ETC);
  const R = (k: string) => (req.has(k) ? <em className="kokm-req">필수</em> : null);
  useEffect(() => {
    const t = q.trim(); if (!isCx || !t || d.complex_no) { setHits([]); return; }
    const id = window.setTimeout(() => fetch(`${API}/complexes/search?q=${encodeURIComponent(t)}&limit=8`).then((r) => r.json()).then((j) => setHits(j.items || [])).catch(() => setHits([])), 250);
    return () => window.clearTimeout(id);
  }, [q, d.complex_no, isCx]);
  useEffect(() => { if (!d.complex_no) { setAreas([]); return; } fetch(`${API}/complex/${d.complex_no}/areas`).then((r) => r.json()).then((j) => setAreas(j.items || [])).catch(() => setAreas([])); }, [d.complex_no]);
  // 종류를 바꾸면 방향 기준 기본값(주거=거실, 비주거=주출입구)
  useEffect(() => { if (!d.direction_base) set("direction_base", HOUSING.has(d.ptype) ? "거실" : "주출입구"); }, [d.ptype]);   // eslint-disable-line react-hooks/exhaustive-deps
  const addPhoto = async (f: File) => {
    if (d.photos.length >= 10) return; setUp(true); setErr("");
    const fd = new FormData(); fd.append("document", f);
    try { const r = await fetch(`${API}/lounge/kok/photo`, { method: "POST", headers: authH(), body: fd }); const j = await r.json(); if (r.ok && j.photo) set("photos", [...d.photos, j.photo]); else setErr(typeof j.detail === "string" ? j.detail : "사진을 올리지 못했어요"); }
    catch { setErr("사진을 올리지 못했어요"); } finally { setUp(false); }
  };
  const fillLedger = async () => {
    if (d.address.trim().length < 6) { setLed({ busy: false, msg: "주소를 먼저 적어 주세요" }); return; }
    setLed({ busy: true, msg: "" });
    try {
      const r = await fetch(`${API}/lounge/kok/ledger?address=${encodeURIComponent(d.address.trim())}`, { headers: authH() });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "대장을 받지 못했어요");
      if (!j.found) { setLed({ busy: false, msg: "좌표는 찾았지만 건축물대장이 없어요. 사용승인일·총층·주차를 직접 적어 주세요" }); return; }
      setD((x) => ({ ...x, approve_ymd: j.approve_ymd ? ymdDot(j.approve_ymd) : x.approve_ymd, total_floor: j.total_floor ? String(j.total_floor) : x.total_floor, parking: j.parking || x.parking,
        land_m2: !x.land_m2 && j.plat_area ? String(j.plat_area) : x.land_m2 }));
      setLed({ busy: false, msg: `건축물대장: ${[j.bld_nm, j.main_purps, j.approve_ymd ? `사용승인 ${ymdDot(j.approve_ymd)}` : "", j.total_floor ? `지상 ${j.total_floor}층` : "", j.parking].filter(Boolean).join(" · ")}` });
    } catch (e) { setLed({ busy: false, msg: e instanceof Error ? e.message : "대장을 받지 못했어요" }); }
  };
  const missing = (REQ[d.ptype] || REQ.ETC).filter((k) => {
    const v = (d as unknown as Record<string, string>)[k]; return !v || (k !== "address" && k !== "complex_no" && !isNaN(Number(v)) && Number(v) <= 0);
  }).concat(d.trade === "B2" && !(parseFloat(d.rentMan || "0") > 0) ? ["rent"] : []).concat(!(parseFloat(d.priceEok || "0") > 0) ? ["price"] : []);
  const needItems = ["VL", "OR", "SG", "SMS"].includes(d.ptype) && parseFloat(d.mgmt_fee || "0") >= 10 && d.items.filter((x) => x.name).length === 0;
  const save = async () => {
    setBusy(true); setErr("");
    try {
      const body = { ptype: d.ptype, trade: d.trade, price: Math.round(parseFloat(d.priceEok || "0") * 1e8), rent: Math.round(parseFloat(d.rentMan || "0") * 1e4),
        complex_no: isCx ? d.complex_no : "", address: d.address, dong: d.dong, ho: d.ho, area_name: d.area_name, supply_m2: parseFloat(d.supply_m2 || "0"), excl_m2: parseFloat(d.excl_m2 || "0"),
        land_m2: parseFloat(d.land_m2 || "0"), floor: parseInt(d.floor || "0"), total_floor: parseInt(d.total_floor || "0"), direction: d.direction, direction_base: d.direction_base, move_in: d.move_in,
        mgmt_fee: Math.round(parseFloat(d.mgmt_fee || "0") * 1e4), rooms: d.rooms, baths: d.baths, approve_ymd: d.approve_ymd, parking: d.parking, land_use: d.land_use,
        mgmt_items: d.items.filter((x) => x.name).map((x) => ({ name: x.name, amount: x.amount ? Math.round(parseFloat(x.amount) * 1e4) : null })),
        photos: d.photos, description: d.description, keywords: d.keywords.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 8) };
      const r = await fetch(`${API}/lounge/kok/direct${editId ? `/${editId.slice(1)}` : ""}`, { method: "POST", headers: { "Content-Type": "application/json", ...authH() }, body: JSON.stringify(body) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "저장하지 못했어요");
      onSaved();
    } catch (e) { setErr(e instanceof Error ? e.message : "저장하지 못했어요"); } finally { setBusy(false); }
  };
  const pick = (a: { pyeong_name: string; exclusive_area: number | null; supply_area: number | null }) => setD((x) => ({ ...x, area_name: a.pyeong_name, excl_m2: a.exclusive_area ? String(a.exclusive_area) : x.excl_m2, supply_m2: a.supply_area ? String(a.supply_area) : x.supply_m2 }));
  const setItem = (i: number, k: keyof MgmtItem, v: string) => set("items", d.items.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  return (
    <div className="kokm-form">
      <div className="kokm-row">
        <label>종류<select value={d.ptype} onChange={(e) => set("ptype", e.target.value)}>{Object.entries(ptypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label>거래<select value={d.trade} onChange={(e) => set("trade", e.target.value)}><option value="A1">매매</option><option value="B1">전세</option><option value="B2">월세</option></select></label>
        <label>{d.trade === "A1" ? "매매가" : "보증금"} <small>억</small><em className="kokm-req">필수</em><input inputMode="decimal" value={d.priceEok} onChange={(e) => set("priceEok", e.target.value)} placeholder="12.5" /></label>
        {d.trade === "B2" && <label>월세 <small>만원</small><em className="kokm-req">필수</em><input inputMode="numeric" value={d.rentMan} onChange={(e) => set("rentMan", e.target.value)} placeholder="150" /></label>}
      </div>
      {isCx ? (
        <div className="kokm-row">
          <label className="wide">단지{R("complex_no")}
            {d.complex_no ? <span className="kokm-picked"><b>{d.complex_name}</b> <button type="button" className="kokm-lnk mut" onClick={() => setD((x) => ({ ...x, complex_no: "", complex_name: "", area_name: "" }))}>바꾸기</button></span>
              : <><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="단지 이름으로 찾기" />
                {hits.length > 0 && <ul className="kokm-hits">{hits.map((h) => <li key={h.complex_no}><button type="button" onClick={() => { setD((x) => ({ ...x, complex_no: h.complex_no, complex_name: h.name })); setQ(h.name); setHits([]); }}><b>{h.name}</b><small>{h.region || ""}{h.households ? ` · ${h.households.toLocaleString()}세대` : ""}</small></button></li>)}</ul>}</>}
          </label>
          <label>동<input value={d.dong} onChange={(e) => set("dong", e.target.value)} placeholder="101" /></label>
          <label>호 <small>비공개</small><input value={d.ho} onChange={(e) => set("ho", e.target.value)} placeholder="1203" /></label>
        </div>
      ) : (
        <>
          <div className="kokm-row">
            <label className="wide">소재지 <small>지번 또는 도로명</small>{R("address")}<input value={d.address} onChange={(e) => set("address", e.target.value)} placeholder="서울 송파구 가락동 123-4 / 송파대로 345" /></label>
            <label>동·호 <small>비공개</small><input value={d.ho} onChange={(e) => set("ho", e.target.value)} placeholder="2층 201호" /></label>
            {d.ptype !== "TJ" && <label className="btn"><span>&nbsp;</span><button type="button" className="auth-btn" disabled={led.busy} onClick={fillLedger}>{led.busy ? "대장 조회 중…" : "건축물대장에서 채우기"}</button></label>}
          </div>
          {led.msg && <p className="muted kokm-ledmsg">{led.msg}</p>}
        </>
      )}
      {isCx && areas.length > 0 && <div className="kokm-chips">{areas.map((a) => <button type="button" key={a.pyeong_name} className={d.area_name === a.pyeong_name ? "on" : ""} onClick={() => pick(a)}>{a.pyeong_name}{a.exclusive_area ? ` · 전용 ${m2(a.exclusive_area)}` : ""}</button>)}</div>}
      <div className="kokm-row">
        {d.ptype !== "TJ" && <label>{d.ptype === "GM" || d.ptype === "GJCG" ? "연면적" : "전용"} <small>㎡</small>{R("excl_m2")}<input inputMode="decimal" value={d.excl_m2} onChange={(e) => set("excl_m2", e.target.value)} /></label>}
        {d.ptype !== "TJ" && !["GM", "GJCG", "DDDGG"].includes(d.ptype) && <label>공급 <small>㎡</small><input inputMode="decimal" value={d.supply_m2} onChange={(e) => set("supply_m2", e.target.value)} /></label>}
        {["TJ", "DDDGG", "GM", "GJCG"].includes(d.ptype) && <label>{d.ptype === "TJ" ? "토지" : "대지"} 면적 <small>㎡</small>{R("land_m2")}<input inputMode="decimal" value={d.land_m2} onChange={(e) => set("land_m2", e.target.value)} /></label>}
        {d.ptype === "TJ" && <label>지목{R("land_use")}<select value={d.land_use} onChange={(e) => set("land_use", e.target.value)}><option value="">-</option>{LAND_USES.map((x) => <option key={x}>{x}</option>)}</select></label>}
        {FLOORED.has(d.ptype) && <label>해당 층 / 총 층수{R("floor")}{!req.has("floor") && R("total_floor")}<span className="kokm-pair"><input inputMode="numeric" value={d.floor} onChange={(e) => set("floor", e.target.value)} placeholder="12" disabled={["GM", "GJCG"].includes(d.ptype)} /><input inputMode="numeric" value={d.total_floor} onChange={(e) => set("total_floor", e.target.value)} placeholder="25" /></span></label>}
        {d.ptype === "DDDGG" && <label>총 층수{R("total_floor")}<input inputMode="numeric" value={d.total_floor} onChange={(e) => set("total_floor", e.target.value)} placeholder="3" /></label>}
        {HOUSING.has(d.ptype) && <label>방 / 욕실{R("rooms")}<span className="kokm-pair"><input inputMode="numeric" value={d.rooms} onChange={(e) => set("rooms", e.target.value)} placeholder="3" /><input inputMode="numeric" value={d.baths} onChange={(e) => set("baths", e.target.value)} placeholder="2" /></span></label>}
      </div>
      <div className="kokm-row">
        {(HOUSING.has(d.ptype) || ["SG", "SMS"].includes(d.ptype)) && <label>방향{R("direction")}<select value={d.direction} onChange={(e) => set("direction", e.target.value)}><option value="">-</option>{DIRS.map((x) => <option key={x}>{x}</option>)}</select></label>}
        {(HOUSING.has(d.ptype) || ["SG", "SMS"].includes(d.ptype)) && <label>방향 기준{R("direction_base")}<select value={d.direction_base} onChange={(e) => set("direction_base", e.target.value)}>{(HOUSING.has(d.ptype) ? ["거실", "안방", "주출입구"] : ["주출입구", "거실", "안방"]).map((x) => <option key={x}>{x}</option>)}</select></label>}
        <label>입주 가능일{R("move_in")}<select value={d.move_in} onChange={(e) => set("move_in", e.target.value)}>{["협의", "즉시 입주", "1개월 내", "3개월 내", "6개월 내"].map((x) => <option key={x}>{x}</option>)}</select></label>
        {!isCx && d.ptype !== "TJ" && <label>사용승인일 <small>2015.08</small>{R("approve_ymd")}<input value={d.approve_ymd} onChange={(e) => set("approve_ymd", e.target.value)} placeholder="2015.08.21" /></label>}
        {!isCx && d.ptype !== "TJ" && <label>주차대수 <small>총 또는 세대당</small>{R("parking")}<input value={d.parking} onChange={(e) => set("parking", e.target.value)} placeholder="총 12대 / 세대당 1대" /></label>}
        {d.ptype !== "TJ" && <label>관리비 <small>월 만원</small>{R("mgmt_fee")}<input inputMode="numeric" value={d.mgmt_fee} onChange={(e) => set("mgmt_fee", e.target.value)} placeholder="25" /></label>}
      </div>
      {["VL", "OR", "SG", "SMS"].includes(d.ptype) && d.ptype !== "TJ" && (
        <div className="kokm-fld"><span>관리비 비목 <small>월 10만원 이상 정액 관리비는 비목별 금액 표시가 의무예요 · 만원</small>{needItems && <em className="kokm-req">필수</em>}</span>
          <div className="kokm-items">
            {d.items.map((x, i) => <span key={i} className="it"><select value={x.name} onChange={(e) => setItem(i, "name", e.target.value)}><option value="">비목</option>{MGMT_NAMES.map((n) => <option key={n}>{n}</option>)}</select><input inputMode="numeric" value={x.amount} onChange={(e) => setItem(i, "amount", e.target.value)} placeholder="금액" /><button type="button" aria-label="지우기" onClick={() => set("items", d.items.filter((_, j) => j !== i))}>×</button></span>)}
            {d.items.length < 10 && <button type="button" className="kokm-lnk" onClick={() => set("items", [...d.items, { name: MGMT_NAMES.find((n) => !d.items.some((x) => x.name === n)) || "기타", amount: "" }])}>+ 비목</button>}
          </div>
        </div>
      )}
      <label className="kokm-fld">콕집 설명 <small>1000자 · 집 상태, 수리 내역, 협의 가능한 점</small><textarea rows={4} maxLength={1000} value={d.description} onChange={(e) => set("description", e.target.value)} /></label>
      <label className="kokm-fld">키워드 <small>쉼표로 최대 8개</small><input value={d.keywords} onChange={(e) => set("keywords", e.target.value)} placeholder="올수리, 남향, 역 3분" /></label>
      <div className="kokm-fld"><span>사진 <small>최대 10장 · 얼굴·글자는 자동으로 가려져요</small></span>
        <div className="kokm-photos">
          {d.photos.map((p) => <span key={p} className="ph"><img src={`${API}/kok/photo/${p}`} alt="" /><button type="button" aria-label="지우기" onClick={() => set("photos", d.photos.filter((y) => y !== p))}>×</button></span>)}
          {d.photos.length < 10 && <button type="button" className="add" disabled={up} onClick={() => fileRef.current?.click()}>{up ? "올리는 중…" : "+ 사진"}</button>}
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) addPhoto(f); e.target.value = ""; }} />
        </div>
      </div>
      {(missing.length > 0 || needItems) && <p className="kokm-missing">표시·광고 필수 항목이 비어 있어요: {missing.map((k) => LABEL[k] || (k === "price" ? "가격" : k)).concat(needItems ? ["관리비 비목"] : []).join(" · ")}</p>}
      {err && <p className="kokm-err">{err}</p>}
      <div className="kokm-actions">
        <button className="auth-btn kakao" disabled={busy || missing.length > 0 || needItems} onClick={save}>{busy ? "저장 중…" : editId ? "수정 저장" : "콕집에 올리기"}</button>
        <button className="auth-btn" onClick={onCancel}>취소</button>
      </div>
    </div>
  );
}

function DirectTab({ authH, onChanged, openId }: { authH: () => Record<string, string>; onChanged: () => void; openId: string | null }) {
  const [items, setItems] = useState<DirectItem[] | null>(null);
  const [ptypes, setPtypes] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"list" | "new" | string>(openId ? openId : "list");
  const load = useCallback(() => fetch(`${API}/lounge/kok/direct`, { headers: authH() }).then((r) => (r.ok ? r.json() : { items: [] })).then((j) => { setItems(j.items || []); if (j.ptypes) setPtypes(j.ptypes); }).catch(() => setItems([])), [authH]);
  useEffect(() => { load(); }, [load]);
  const setStatus = async (id: string, status: string) => {
    if (status === "deleted" && !window.confirm("이 매물을 지울까요? 되돌릴 수 없어요.")) return;
    await fetch(`${API}/lounge/kok/direct/${id.slice(1)}/status`, { method: "POST", headers: { "Content-Type": "application/json", ...authH() }, body: JSON.stringify({ status }) });
    load(); onChanged();
  };
  const editing = items?.find((i) => i.id === mode);
  if (mode === "new" || editing) {
    return (
      <div className="kokm-sec">
        <h3 className="kokm-h3">{editing ? `수정 — ${editing.name}` : "콕집에만 올리는 매물"}</h3>
        <p className="muted">광고와 무관하게 콕집 지도에만 보여요. 아파트·오피스텔은 단지를 고르면 좌표·평형이 붙고, 그 밖의 유형은 주소로 좌표를 찾아요. 표시·광고 의무 항목(가격·면적·층·방향·입주·관리비)을 채우면 점검에서 걸리지 않아요.</p>
        <DirectForm authH={authH} init={editing ? toDraft(editing) : undefined} editId={editing?.id} ptypes={ptypes} onSaved={() => { setMode("list"); load(); onChanged(); }} onCancel={() => setMode("list")} />
      </div>
    );
  }
  return (
    <div className="kokm-sec">
      <div className="kokm-bar"><p className="muted">광고에 올리지 않은 물건도 콕집에는 올릴 수 있어요. 모든 유형 · 사무소당 300건.</p><button className="auth-btn kakao" onClick={() => setMode("new")}>+ 콕집 전용 매물 올리기</button></div>
      {items === null ? <p className="muted">불러오는 중…</p> : items.length === 0 ? <p className="kokm-empty">아직 콕집 전용 매물이 없어요.</p> : (
        <table className="kokm-tbl"><thead><tr><th>종류</th><th>물건</th><th>거래</th><th className="num">가격</th><th>면적·층</th><th>상태</th><th>올린 날</th><th></th></tr></thead>
          <tbody>{items.map((it) => (
            <tr key={it.id} className={it.status !== "active" ? "off" : ""}>
              <td><i className="kokm-pt">{it.ptype_name}</i></td>
              <td><b>{it.name}</b>{it.dong ? ` ${it.dong}동` : ""}{it.complex_no ? "" : <small className="blk">{it.address}</small>}<small className="blk">{[it.photos.length ? `사진 ${it.photos.length}` : "", it.keywords.length ? it.keywords.slice(0, 3).join(" · ") : ""].filter(Boolean).join(" · ") || "사진·키워드 없음"}</small></td>
              <td>{TRADE_L[it.trade]}</td><td className="num"><b>{it.price_text}</b></td>
              <td>{[it.excl_m2 ? `전용 ${m2(it.excl_m2)}` : it.land_m2 ? `대지 ${m2(it.land_m2)}` : "", it.floor_text].filter(Boolean).join(" · ") || "-"}</td>
              <td>{it.status === "active" ? <span className="kokm-on">게시 중</span> : "내림"}</td><td>{it.kok_since}</td>
              <td className="act"><button className="kokm-lnk" onClick={() => setMode(it.id)}>수정</button>
                {it.status === "active" ? <button className="kokm-lnk mut" onClick={() => setStatus(it.id, "closed")}>내리기</button> : <button className="kokm-lnk" onClick={() => setStatus(it.id, "active")}>다시 올리기</button>}
                <button className="kokm-lnk mut" onClick={() => setStatus(it.id, "deleted")}>삭제</button></td>
            </tr>))}</tbody></table>
      )}
    </div>
  );
}

// ── ③ 전체 관리 ────────────────────────────────────────────────────────
type Row = { id: string; source: "converted" | "direct"; ptype_name: string; name: string; dong: string; trade: string; price_text: string; area: string; floor_text: string; status: string; since: string; photos: number; kw: string[]; desc: boolean; hold: string[]; raw: ConvItem | DirectItem };
function ManageTab({ authH, onChanged, openId, onEditDirect }: { authH: () => Record<string, string>; onChanged: () => void; openId: string | null; onEditDirect: (id: string) => void }) {
  const [conv, setConv] = useState<ConvItem[] | null>(null);
  const [direct, setDirect] = useState<DirectItem[] | null>(null);
  const [src, setSrc] = useState<"all" | "converted" | "direct">("all");
  const [trade, setTrade] = useState(""); const [stt, setStt] = useState<"active" | "hold" | "closed" | "all">("active"); const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(openId);
  const load = useCallback(() => {
    fetch(`${API}/lounge/kok/listings`, { headers: authH() }).then((r) => (r.ok ? r.json() : { items: [] })).then((j) => setConv(j.items || [])).catch(() => setConv([]));
    fetch(`${API}/lounge/kok/direct`, { headers: authH() }).then((r) => (r.ok ? r.json() : { items: [] })).then((j) => setDirect(j.items || [])).catch(() => setDirect([]));
  }, [authH]);
  useEffect(() => { load(); }, [load]);
  const rows: Row[] = useMemo(() => {
    const a: Row[] = (conv || []).map((c) => ({ id: c.id, source: "converted", ptype_name: "전환", name: c.name, dong: c.dong || "", trade: c.trade, price_text: c.price_text, area: c.excl_m2 ? `전용 ${m2(c.excl_m2)}` : c.area_name, floor_text: c.floor_text, status: c.status || "active", since: c.kok_since || "", photos: c.photos.length, kw: c.keywords, desc: !!c.description, hold: c.publish_state === "hold" ? c.hold_reasons || [] : [], raw: c }));
    const b: Row[] = (direct || []).map((d) => ({ id: d.id, source: "direct", ptype_name: d.ptype_name, name: d.name, dong: d.dong, trade: d.trade, price_text: d.price_text, area: d.excl_m2 ? `전용 ${m2(d.excl_m2)}` : d.land_m2 ? `대지 ${m2(d.land_m2)}` : d.area_name, floor_text: d.floor_text, status: d.status, since: d.kok_since, photos: d.photos.length, kw: d.keywords, desc: !!d.description, hold: d.publish_state === "hold" ? d.hold_reasons || [] : [], raw: d }));
    const stOk = (r: Row) => stt === "all" ? true : stt === "hold" ? r.status === "active" && r.hold.length > 0 : stt === "active" ? r.status === "active" && r.hold.length === 0 : r.status === stt;
    return [...a, ...b].filter((r) => (src === "all" || r.source === src) && (!trade || r.trade === trade) && stOk(r) && (!q || (r.name + r.dong + r.kw.join(" ")).includes(q)))
      .sort((x, y) => (y.since || "").localeCompare(x.since || ""));
  }, [conv, direct, src, trade, stt, q]);
  const setDirectStatus = async (id: string, status: string) => {
    await fetch(`${API}/lounge/kok/direct/${id.slice(1)}/status`, { method: "POST", headers: { "Content-Type": "application/json", ...authH() }, body: JSON.stringify({ status }) }); load(); onChanged();
  };
  const loading = conv === null || direct === null;
  return (
    <div className="kokm-sec">
      <div className="kokm-filters">
        <Seg value={src} onChange={(v) => setSrc(v as typeof src)} opts={[["all", `전체 ${(conv?.length || 0) + (direct?.length || 0)}`], ["converted", `전환 ${conv?.length || 0}`], ["direct", `전용 ${direct?.length || 0}`]]} />
        <Seg value={trade} onChange={setTrade} opts={[["", "거래 전체"], ["A1", "매매"], ["B1", "전세"], ["B2", "월세"]]} />
        <Seg value={stt} onChange={(v) => setStt(v as typeof stt)} opts={[["active", "게시 중"], ["hold", "게시 전"], ["closed", "내림"], ["all", "모두"]]} />
        <input className="kokm-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="단지·주소·키워드 찾기" />
      </div>
      {loading ? <p className="muted">불러오는 중…</p> : rows.length === 0 ? <p className="kokm-empty">조건에 맞는 콕집매물이 없어요.</p> : (
        <table className="kokm-tbl"><thead><tr><th>출처</th><th>물건</th><th>거래</th><th className="num">가격</th><th>면적·층</th><th>콕집 정보</th><th>등록</th><th></th></tr></thead>
          <tbody>{rows.map((r) => (
            <RowView key={r.id} r={r} open={open === r.id} onToggle={() => setOpen(open === r.id ? null : r.id)} authH={authH} onSaved={() => { setOpen(null); load(); onChanged(); }} onEditDirect={onEditDirect} onStatus={setDirectStatus} />
          ))}</tbody></table>
      )}
      <p className="muted kokm-note">전환분은 광고 상태를 매일 반영하고, 광고가 내려가면 다음 반영 때 '내림'으로 바뀌어요(지우지 않고 이력으로 남아요). 전용분은 여기서 바로 내리거나 다시 올릴 수 있어요. <b>게시 전</b>은 표시·광고 필수 항목(관리비·층·방향 등)이 빠져 콕집에 공개하지 않는 매물이에요 — 전환분은 광고에 채우면 다음 반영 때, 전용분은 수정하면 바로 공개돼요.</p>
    </div>
  );
}

function RowView({ r, open, onToggle, authH, onSaved, onEditDirect, onStatus }: { r: Row; open: boolean; onToggle: () => void; authH: () => Record<string, string>; onSaved: () => void; onEditDirect: (id: string) => void; onStatus: (id: string, s: string) => void }) {
  return (
    <>
      <tr className={r.status !== "active" ? "off" : ""}>
        <td><i className={`kokm-pt${r.source === "converted" ? " cv" : ""}`}>{r.ptype_name}</i></td>
        <td><b>{r.name}</b>{r.dong ? ` ${r.dong}동` : ""}{r.source === "direct" && !(r.raw as DirectItem).complex_no && <small className="blk">{(r.raw as DirectItem).address}</small>}</td>
        <td>{TRADE_L[r.trade]}</td><td className="num"><b>{r.price_text}</b></td>
        <td>{[r.area, r.floor_text].filter(Boolean).join(" · ") || "-"}</td>
        <td className="kokm-ex">{r.photos ? <span>사진 {r.photos}</span> : <span className="mut">사진 0</span>}{r.desc ? <span>설명</span> : <span className="mut">설명 없음</span>}{r.kw.length ? <span>{r.kw.slice(0, 3).join(" · ")}</span> : <span className="mut">키워드 없음</span>}</td>
        <td>{r.since}{r.status !== "active" ? <small className="blk">내림</small> : r.hold.length > 0 ? <small className="blk kokm-bad" title={r.hold.join(" · ")}>게시 전 · {r.hold.join(" · ")}</small> : null}</td>
        <td className="act">
          {r.source === "converted" ? <button className="kokm-lnk" onClick={onToggle}>{open ? "닫기" : "사진·설명·키워드"}</button>
            : <><button className="kokm-lnk" onClick={() => onEditDirect(r.id)}>수정</button>{r.status === "active" ? <button className="kokm-lnk mut" onClick={() => onStatus(r.id, "closed")}>내리기</button> : <button className="kokm-lnk" onClick={() => onStatus(r.id, "active")}>다시 올리기</button>}</>}
        </td>
      </tr>
      {open && r.source === "converted" && <tr className="kokm-edit"><td colSpan={8}><MyExtrasEditor authH={authH} it={r.raw as ConvItem} onSaved={onSaved} /></td></tr>}
    </>
  );
}

function Seg({ value, onChange, opts }: { value: string; onChange: (v: string) => void; opts: [string, string][] }) {
  return <div className="kokm-seg">{opts.map(([k, l]) => <button key={k} type="button" className={value === k ? "on" : ""} onClick={() => onChange(k)}>{l}</button>)}</div>;
}

// ── ④ 점검 ─────────────────────────────────────────────────────────────
const LEVEL_L: Record<string, string> = { fail: "위반 가능", warn: "확인 필요", info: "권장", ok: "이상 없음" };
const CODE_L: Record<string, string> = { price: "가격 없음", rent: "월세 없음", area: "면적 없음", floor: "층 없음", floor_vague: "층 고·중·저만", direction: "방향 없음", move_in: "입주일 없음", mgmt: "관리비 없음", area_mismatch: "평형 불일치",
  price_outlier: "실거래 대비 이상", dup: "같은 집 중복", stale: "오래된 등록", photo: "사진 없음", desc: "설명 없음", kw: "키워드 없음", office_regno: "사무소 등록번호", office_tel: "사무소 연락처",
  publish_hold: "게시 보류", mgmt_soft: "중개사 표시 관리비 없음", approve: "사용승인일 없음", parking: "주차대수 없음", land_use: "지목 없음", mgmt_items: "관리비 비목 없음", direction_base: "방향 기준 없음" };
function AuditTab({ authH, office, onFix }: { authH: () => Record<string, string>; office: Office; onFix: (id: string) => void }) {
  const [a, setA] = useState<Audit | null>(null); const [busy, setBusy] = useState(false); const [lv, setLv] = useState<"all" | "fail" | "warn" | "info">("all");
  const run = useCallback(() => { setBusy(true); fetch(`${API}/lounge/kok/audit`, { headers: authH() }).then((r) => (r.ok ? r.json() : null)).then(setA).catch(() => setA(null)).finally(() => setBusy(false)); }, [authH]);
  useEffect(() => { run(); }, [run]);
  const items = (a?.items || []).filter((it) => lv === "all" ? it.level !== "ok" : it.level === lv);
  return (
    <div className="kokm-sec">
      <div className="kokm-bar"><p className="muted">게시 중인 콕집매물 전부를 표시·광고 의무 항목(가격·면적·층·방향·입주·관리비)과 콕집 노출 품질(사진·설명·키워드), 실거래 대비 가격, 단지 평형 불일치, 같은 집 중복, 오래된 등록, 사무소 표시 항목(등록번호·연락처) 기준으로 봐요.</p><button className="auth-btn" disabled={busy} onClick={run}>{busy ? "점검 중…" : "다시 점검"}</button></div>
      {a && (
        <>
          <div className="kokm-kpi audit">
            <div><b>{a.summary.total}</b><span>점검 매물</span></div>
            <div className={a.summary.fail ? "bad" : ""}><b>{a.summary.fail}</b><span>위반 가능<small>가격·면적 없음 등</small></span></div>
            <div className={a.summary.warn ? "warn" : ""}><b>{a.summary.warn}</b><span>확인 필요<small>층·방향·입주·가격 이상</small></span></div>
            <div><b>{a.summary.info}</b><span>권장<small>사진·설명·키워드</small></span></div>
            <div className="good"><b>{a.summary.ok}</b><span>이상 없음</span></div>
          </div>
          <dl className="kokm-dl">
            <div><dt>사무소</dt><dd>{a.office.name || office.realtor_name} · 등록번호 {a.office.regno || <span className="kokm-bad">없음</span>} · 연락처 {a.office.tel || a.office.cell || <span className="kokm-bad">없음</span>}
              {a.office.issues.map((i) => <small key={i.code} className="blk kokm-bad">{i.msg}</small>)}</dd></div>
            {Object.keys(a.summary.by_code).length > 0 && <div><dt>항목별</dt><dd className="kokm-codes">{Object.entries(a.summary.by_code).sort((x, y) => y[1] - x[1]).map(([c, n]) => <span key={c}>{CODE_L[c] || c} <b>{n}</b></span>)}</dd></div>}
          </dl>
          <div className="kokm-filters"><Seg value={lv} onChange={(v) => setLv(v as typeof lv)} opts={[["all", `문제 있음 ${a.summary.total - a.summary.ok}`], ["fail", `위반 가능 ${a.summary.fail}`], ["warn", `확인 ${a.summary.warn}`], ["info", `권장 ${a.summary.info}`]]} /></div>
          {items.length === 0 ? <p className="kokm-empty">{a.summary.total === 0 ? "점검할 콕집매물이 없어요." : "이 단계에 해당하는 매물이 없어요."}</p> : (
            <ul className="kokm-audit">{items.map((it) => (
              <li key={it.id} className={it.level}>
                <div className="hd"><i className={`kokm-pt${it.source === "converted" ? " cv" : ""}`}>{it.source === "converted" ? "전환" : it.ptype_name}</i><b>{it.name}{it.dong ? ` ${it.dong}동` : ""}</b><span>{TRADE_L[it.trade]} · {it.price_text}{it.excl ? ` · 전용 ${m2(it.excl)}` : ""}{it.floor ? ` · ${it.floor}층` : ""}</span><em>{LEVEL_L[it.level]}</em><button className="kokm-lnk" onClick={() => onFix(it.id)}>{it.source === "converted" ? "사진·설명 쓰기" : "수정"}</button></div>
                <ul>{it.issues.map((i, k) => <li key={k} className={i.level}>{i.msg}</li>)}</ul>
              </li>))}</ul>
          )}
          <p className="muted kokm-note">전환분의 층·방향·입주일은 광고의 표시 정보에서 오므로 광고를 고치면 다음 반영 때 바뀌어요. 광고 자체의 표시·광고 점검은 <Link to="/biz/audit">매물점검</Link>에서 해요.</p>
        </>
      )}
    </div>
  );
}

export default KokScreen;
