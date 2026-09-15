import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileSignature, Plus, Copy, Trash2, ArrowLeft, CalendarCheck, Building2, Users as UsersIcon, X,
  Save, Clock, FileDown, Printer, ClipboardCheck, FileX } from "lucide-react";
import { useAuth } from "../auth";
import { isMobileDevice } from "../lib/appmode";
import { Loading } from "../components/Loading";
import { BizSubNav } from "../lib/bizNav";
import { amountKorean, autoBalance, commission, dealAmountForCommission, propertyGbOf,
         type CostStyle } from "../lib/contractcalc";

const API = import.meta.env.VITE_API_BASE;

// ── 코드값 seed (hanbang DFM 원문) ──────────────────────────────────
const SUB_CATS = ["아파트", "주상복합", "연립주택", "다세대주택", "다가구주택", "다중주택",
  "도시형생활주택", "주택", "오피스텔", "원룸", "상가", "상가주택", "상가건물", "건물",
  "사무실", "토지", "공장", "창고", "지식산업센터", "일반"];
const MTYPES = ["매매", "전세", "월세", "연세"] as const;
// 특약 상용구 — 클릭 시 다음 번호로 추가(관용 문구, 사용자 수정 전제)
const TEUK_PRESETS_SALE = [
  "현 시설물 상태에서의 매매계약이며, 등기부등본 및 건축물대장을 확인하고 계약을 체결함.",
  "잔금일 기준 관리비·공과금은 정산하기로 한다.",
  "매도인은 잔금일까지 근저당권(채권최고액 ______원)을 말소하기로 한다.",
  "본 계약의 계약금은 위약금으로 하며, 매도인이 위약 시 배액을 상환하고 매수인이 위약 시 계약금을 포기한다.",
  "매수인의 대출 미승인 시 계약금을 반환하고 본 계약은 무효로 한다(승인 기한: ______).",
  "현장 확인 후 계약이며, 표시되지 않은 하자는 민법 및 관련 법령에 따른다.",
];
const TEUK_PRESETS_RENT = [
  "현 시설물 상태에서의 임대차계약이며, 기본 시설물 파손 시 임차인이 원상복구한다.",
  "임차인은 임대인의 동의 없이 반려동물을 사육하지 않는다.",
  "관리비는 월 ______원으로 하며 (포함 항목: ______).",
  "임대인은 잔금(입주일)까지 보일러·수도·전기 등 기본 시설의 정상 작동을 보장한다.",
  "임차인은 계약 만료 1개월 전까지 갱신 여부를 통보하기로 한다.",
  "임대인은 잔금일 다음 날까지 임차인의 전세권/확정일자 설정에 협조하며, 근저당 등 신규 담보를 설정하지 않는다.",
  "장기수선충당금은 임대인 부담으로 하며 퇴거 시 정산한다.",
];

const FINE_TAGS = ["현 상태에서 매수인이 승계함.", "매도인이 잔금지급일까지 말소한다.",
  "특약사항에 별도 명시한다.", "매수인이 인수한다.", "매수인이 인수하지 아니한다."];

type Party = { name: string; jumin: string; tel: string; addr: string;
  agent_name?: string; agent_jumin?: string; agent_tel?: string };   // 대리인(한방 *E 세트)
const emptyParty = (): Party => ({ name: "", jumin: "", tel: "", addr: "" });
// 개업공인중개사(한방 §3.2(g): 최대 4개소 — 1=내 사무소, 2~4=공동중개)
type Broker = { company: string; owner: string; reg_no: string; addr: string; tel: string;
  belong?: string };   // 소속공인중개사(한방 belong_realtor — 서명·날인란)
const emptyBroker = (): Broker => ({ company: "", owner: "", reg_no: "", addr: "", tel: "", belong: "" });

type Body = Record<string, any>;
type ListItem = { id: number; mtype1: string; status: string; title: string; haddress: string;
  contract_date: string | null; ecost_date: string | null; edate: string | null;
  cost: number; charge: number; sell_name: string; buy_name: string };

const man = (v: number) => (v ? `${Math.round(v / 1e4).toLocaleString()}만` : "-");

// 기본 계약조항(서식 1) — scripts/contract_domain.py ARTICLES_* 미러(협회 표준 관용문)
const ARTICLES_SALE: [string, string, string][] = [
  ["제1조", "", "위 부동산의 매매에 대하여 매도인과 매수인은 합의에 의하여 매매대금을 아래와 같이 지급하기로 한다."],
  ["제2조", "소유권이전 등", "매도인은 매매대금의 잔금 수령과 동시에 매수인에게 소유권이전등기에 필요한 모든 서류를 교부하고 등기절차에 협력하며, 위 부동산의 인도일은 {인도일}로 한다."],
  ["제3조", "제한물권 등의 소멸", "매도인은 위 부동산에 설정된 저당권, 지상권, 임차권 등 소유권의 행사를 제한하는 사유가 있거나 제세공과금과 기타 부담금의 미납 등이 있을 때에는 잔금 수수일까지 그 권리의 하자 및 부담 등을 제거하여 완전한 소유권을 매수인에게 이전한다. 다만 승계하기로 합의하는 권리 및 금액은 그러하지 아니하다."],
  ["제4조", "지방세 등", "위 부동산에 관하여 발생한 수익의 귀속과 제세공과금 등의 부담은 위 부동산의 인도일을 기준으로 하되, 지방세의 납부의무 및 납부책임은 지방세법의 규정에 의한다."],
  ["제5조", "계약의 해제", "매수인이 매도인에게 중도금(중도금이 없을 때에는 잔금)을 지불하기 전까지 매도인은 계약금의 배액을 상환하고, 매수인은 계약금을 포기하고 본 계약을 해제할 수 있다."],
  ["제6조", "채무불이행과 손해배상", "매도인 또는 매수인이 본 계약상의 내용에 대하여 불이행이 있을 경우 그 상대방은 불이행한 자에 대하여 서면으로 최고하고 계약을 해제할 수 있다. 그리고 계약당사자는 계약해제에 따른 손해배상을 각각 상대방에게 청구할 수 있으며, 손해배상에 대하여 별도의 약정이 없는 한 계약금을 손해배상의 기준으로 본다."],
  ["제7조", "중개보수", "개업공인중개사는 매도인 또는 매수인의 본 계약 불이행에 대하여 책임을 지지 않는다. 또한 중개보수는 본 계약체결과 동시에 계약 당사자 쌍방이 각각 지불하며, 개업공인중개사의 고의나 과실 없이 본 계약이 무효·취소 또는 해제되어도 중개보수는 지급한다."],
  ["제8조", "중개보수 외", "매도인 또는 매수인이 본 계약 이외의 업무를 의뢰한 경우 이에 관한 보수는 중개보수와는 별도로 지급하며 그 금액은 합의에 의한다."],
  ["제9조", "중개대상물확인·설명서 교부 등", "개업공인중개사는 중개대상물 확인·설명서를 작성하고 업무보증관계증서(공제증서 등) 사본을 첨부하여 계약체결과 동시에 거래당사자 쌍방에게 교부한다."],
];
const ARTICLES_RENT: [string, string, string][] = [
  ["제1조", "목적", "위 부동산의 임대차에 한하여 임대인과 임차인은 합의에 의하여 임차보증금 및 차임을 아래와 같이 지불하기로 한다."],
  ["제2조", "존속기간", "임대인은 위 부동산을 임대차 목적대로 사용·수익할 수 있는 상태로 {인도일}까지 임차인에게 인도하며, 임대차 기간은 인도일로부터 {만기일}까지로 한다."],
  ["제3조", "용도변경 및 전대 등", "임차인은 임대인의 동의 없이 위 부동산의 용도나 구조를 변경하거나 전대·임차권 양도 또는 담보제공을 하지 못하며 임대차 목적 이외의 용도로 사용할 수 없다."],
  ["제4조", "계약의 해지", "임차인의 차임연체액이 {연체기수}기의 차임액에 달하거나 제3조를 위반하였을 때 임대인은 즉시 본 계약을 해지할 수 있다."],
  ["제5조", "계약의 종료", "임대차계약이 종료된 경우에 임차인은 위 부동산을 원상으로 회복하여 임대인에게 반환한다. 이러한 경우 임대인은 보증금을 임차인에게 반환하고, 연체 임대료 또는 손해배상금이 있을 때는 이들을 제하고 그 잔액을 반환한다."],
  ["제6조", "계약의 해제", "임차인이 임대인에게 중도금(중도금이 없을 때에는 잔금)을 지불하기 전까지 임대인은 계약금의 배액을 상환하고, 임차인은 계약금을 포기하고 이 계약을 해제할 수 있다."],
  ["제7조", "채무불이행과 손해배상", "임대인 또는 임차인이 본 계약상의 내용에 대하여 불이행이 있을 경우 그 상대방은 불이행한 자에 대하여 서면으로 최고하고 계약을 해제할 수 있다. 그리고 계약당사자는 계약해제에 따른 손해배상을 각각 상대방에게 청구할 수 있다."],
  ["제8조", "중개보수", "개업공인중개사는 임대인과 임차인이 본 계약을 불이행함으로 인한 책임을 지지 않는다. 또한 중개보수는 본 계약체결과 동시에 계약 당사자 쌍방이 각각 지불하며, 개업공인중개사의 고의나 과실 없이 본 계약이 무효·취소 또는 해제되어도 중개보수는 지급한다."],
  ["제9조", "중개대상물확인·설명서 교부 등", "개업공인중개사는 중개대상물 확인·설명서를 작성하고 업무보증관계증서(공제증서 등) 사본을 첨부하여 계약체결과 동시에 거래당사자 쌍방에게 교부한다."],
];

export default function BizWContracts() {
  const nav = useNavigate();
  const { token } = useAuth();
  const [items, setItems] = useState<ListItem[] | null>(null);
  const [mode, setMode] = useState<"list" | "edit">("list");
  const [editId, setEditId] = useState<number | null>(null);
  const [errs, setErrs] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  // ── 에디터 상태 ──
  const [mtype1, setMtype1] = useState<string>("매매");
  const [subCat, setSubCat] = useState("아파트");
  const [status, setStatus] = useState("10");
  const [costStyle, setCostStyle] = useState<CostStyle>("한글+숫자");
  const [autoBal, setAutoBal] = useState(true);
  const [autoChg, setAutoChg] = useState(true);
  const [offQ, setOffQ] = useState(false);
  const [b, setB] = useState<Body>({});
  const [sells, setSells] = useState<Party[]>([emptyParty()]);
  const [buys, setBuys] = useState<Party[]>([emptyParty()]);
  const [brokers, setBrokers] = useState<Broker[]>([emptyBroker()]);
  const [myOffice, setMyOffice] = useState<Broker | null>(null);
  // 자동채움 피커 — 매물(내 매물장) / 고객(고객원장)
  const [picker, setPicker] = useState<null | { kind: "listing" } | { kind: "customer"; side: "sell" | "buy" }>(null);
  const [units, setUnits] = useState<{ dong: string; ho: string; flr: string; purps: string; area: number | null }[] | null>(null);
  const [unitOpen, setUnitOpen] = useState(false);
  const [unitDong, setUnitDong] = useState("");
  const [unitSearchMode, setUnitSearchMode] = useState(false);   // 대형(2,000호↑): 호 검색
  const [unitHoQ, setUnitHoQ] = useState("");
  const [unitBusy, setUnitBusy] = useState(false);
  const [unitTried, setUnitTried] = useState("");   // 검색모드: 마지막 검색어(0건 안내용)
  const [pickRows, setPickRows] = useState<any[] | null>(null);
  const [pickQ, setPickQ] = useState("");

  const hdr = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);
  const load = useCallback(() => {
    if (!API || !token) return;
    fetch(`${API}/biz/wcontracts`, { headers: hdr })
      .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(d => setItems(d.items || [])).catch(() => setItems([]));
  }, [token, hdr]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {                              // 내 사무소 정보(중개사 1번 자동채움용)
    if (!API || !token) return;
    fetch(`${API}/biz/wcontracts/tools/myoffice`, { headers: hdr })
      .then(r => r.ok ? r.json() : null).then(d => { if (d?.office) setMyOffice(d.office); })
      .catch(() => {});
  }, [token, hdr]);

  const set = (k: string, v: any) => setB(p => ({ ...p, [k]: v }));
  const num = (k: string) => Number(b[k]) || 0;
  const isRent = mtype1 !== "매매";

  // 자동계산: 잔금 · 중개보수
  const bal = autoBalance(num("cost"), num("bargain_cost"), num("mcost"), num("m1cost"));
  useEffect(() => { if (autoBal) set("ecost", bal); }, [bal, autoBal]);   // eslint-disable-line
  const chgInfo = useMemo(() => {
    const amt = dealAmountForCommission(mtype1, num("cost"), num("fine_cost"));
    return commission(propertyGbOf(subCat, offQ), mtype1 === "매매" ? "SALE" : "RENT",
      amt, b.contract_date || "");
  }, [b.cost, b.fine_cost, b.contract_date, mtype1, subCat, offQ]);   // eslint-disable-line

  const [stdKind, setStdKind] = useState<"" | "9" | "6" | "5">("");   // ""=일반 9=주택표준 6=상가표준 5=권리금(국토부)
  useEffect(() => { if (autoChg && stdKind !== "5") set("charge", chgInfo.fee); }, [chgInfo.fee, autoChg, stdKind]);  // eslint-disable-line
  // 권리금(서식5)은 중개대상물 거래가 아니어서 법정 요율표 미적용 — 자동계산 강제 해제(협의 수동입력)
  useEffect(() => { if (stdKind === "5") setAutoChg(false); }, [stdKind]);
  const openNew = () => {
    setEditId(null); setB({}); setSells([emptyParty()]); setBuys([emptyParty()]);
    setStdKind("");
    setBrokers([myOffice ? { ...myOffice } : emptyBroker()]);   // 1번=내 사무소 자동
    setMtype1("매매"); setSubCat("아파트"); setStatus("10"); setErrs([]); setMode("edit");
  };
  const openEdit = async (id: number) => {
    const r = await fetch(`${API}/biz/wcontracts/${id}`, { headers: hdr });
    if (!r.ok) return;
    const d = await r.json();
    setEditId(id); setB(d.body || {}); setMtype1(d.mtype1); setStatus(d.status);
    setStdKind(d.category === 9 ? "9" : d.category === 6 ? "6" : d.category === 5 ? "5" : "");
    setSubCat(d.sub_category || "아파트");
    setSells(d.body?.sell_parties?.length ? d.body.sell_parties : [emptyParty()]);
    setBuys(d.body?.buy_parties?.length ? d.body.buy_parties : [emptyParty()]);
    setBrokers(d.body?.brokers?.length ? d.body.brokers
      : [myOffice ? { ...myOffice } : emptyBroker()]);
    setErrs([]); setMode("edit");
  };

  const save = async (draft = false) => {
    setSaving(true); setErrs([]);
    const body: Body = { ...b, sell_parties: sells.filter(p => p.name || p.jumin || p.tel),
      buy_parties: buys.filter(p => p.name || p.jumin || p.tel),
      brokers: brokers.filter(k => k.company || k.owner || k.reg_no) };
    try {
      const r = await fetch(`${API}/biz/wcontracts`, {
        method: "POST", headers: { ...hdr, "Content-Type": "application/json" },
        body: JSON.stringify({ id: editId,
          category: stdKind === "5" ? 5 : (stdKind && mtype1 !== "매매") ? Number(stdKind) : 1,
          sub_category: subCat, mtype1, status, draft, body }),
      });
      const d = await r.json();
      if (!d.ok) { setErrs(d.errors || [d.detail || "저장 실패"]); return; }
      if (draft) {
        setEditId(d.id);                     // 이어서 작성 — 화면 유지
        setToast("임시저장 완료 — 이어서 작성하세요 (일정은 정식 저장 시 등록)");
        setTimeout(() => setToast(""), 3500);
      } else {
        setToast(`저장 완료${d.events_synced ? ` · 일정 ${d.events_synced}건 캘린더 등록` : ""}`);
        setTimeout(() => setToast(""), 3000);
        setMode("list"); load();
      }
    } finally { setSaving(false); }
  };
  // ── 자동채움 ──
  const openPicker = async (p: NonNullable<typeof picker>) => {
    setPicker(p); setPickRows(null); setPickQ("");
    try {
      const url = p.kind === "listing"
        ? `${API}/lounge/listings?private=1&limit=400`
        : `${API}/biz/customers?limit=300`;
      const r = await fetch(url, { headers: hdr });
      if (!r.ok) { setPickRows([]); return; }
      const d = await r.json();
      setPickRows(p.kind === "listing" ? (d.listings || []) : (d.items || d.customers || []));
    } catch { setPickRows([]); }
  };
  const applyListing = (it: any) => {
    const addr = [it.address, it.address_detail].filter(Boolean).join(" ")
      || [it.complex_name, it.building_name].filter(Boolean).join(" ");
    // 동/호는 '건물의 동·호'만 — building_name이 법정동(예: 송도동)으로 오는 비단지 케이스는 제외
    const bDong = (it.dong || "").trim();
    const legalDong = bDong && addr.includes(bDong) && /[동리가]$/.test(bDong) && !/^\d/.test(bDong);
    const patch: Body = { ...b, haddress: addr, hdong: legalDong ? "" : bDong,
      hho: it.ho || "", build_py: it.area2_m2 || it.area1_m2 || "", offer_code: it.article_no };
    // 금액: 백엔드 원 단위 통일 필드(price_won·rent_won) 사용 — 경로별(단지=원/비단지·비공개=만원)
    // 단위 혼재를 서버에서 흡수(2026-09-02 3차 수정). 구 응답 폴백: 단지(complex_no 有)=원, 그 외=만원.
    const priceWon = Number(it.price_won ?? (it.complex_no ? it.price : (Number(it.price) || 0) * 10000)) || 0;
    const rentWon = Number(it.rent_won ?? 0) || 0;
    const w = (n: number) => n || "";
    const tt = ({ A1: "매매", B1: "전세", B2: "월세" } as Record<string, string>)[it.trade_type] || it.trade_type;
    if (tt === "매매") { setMtype1("매매"); patch.cost = w(priceWon); }
    else if (tt === "전세") { setMtype1("전세"); patch.cost = w(priceWon); patch.rent_py = it.area2_m2 || ""; }
    else if (tt === "월세" || tt === "연세") { setMtype1(tt === "연세" ? "연세" : "월세"); patch.cost = w(priceWon); patch.fine_cost = w(rentWon); patch.rent_py = it.area2_m2 || ""; }
    // 계약금 = 총액(매매가/보증금)의 10% 관례 프리필(조율 가능 — 사용자 수정 전제)
    if (typeof patch.cost === "number" && patch.cost > 0) {
      patch.bargain_cost = Math.round(patch.cost * 0.1);
    }
    if (it.type && SUB_CATS.includes(it.type)) setSubCat(it.type);
    else if (it.complex_name) setSubCat("아파트");
    setB(patch); setPicker(null);
    setToast(`매물 ${it.article_no} 정보를 채웠습니다 — 계약금은 10% 관례값, 금액·면적 확인하세요`);
    setTimeout(() => setToast(""), 4000);
  };
  const applyCustomer = (cu: any) => {
    if (!picker || picker.kind !== "customer") return;
    const p: Party = { name: cu.name || "", jumin: "", tel: cu.phone || "", addr: cu.address || "" };
    const [list, setList] = picker.side === "sell" ? [sells, setSells] as const : [buys, setBuys] as const;
    const empt = list.findIndex(x => !x.name && !x.tel);
    const next = [...list];
    if (empt >= 0) next[empt] = p; else next.push(p);
    setList(next); setPicker(null);
  };

  // ── P2 인쇄: 새 창에 정적 HTML 주입(SPA CSS 간섭 0 — headless PDF 검증본과 동일 렌더) ──
  const printNow = async () => {
    if (isMobileDevice()) { setErrs(["인쇄는 PC(koczip.com)에서 이용할 수 있어요 — 휴대폰에서는 'PDF 다운로드'를 눌러 파일로 받아주세요"]); return; }
    if (!editId) { setErrs(["인쇄 전에 먼저 저장(또는 임시저장)하세요"]); return; }
    // 팝업차단 회피: 클릭 동기 시점에 창부터 연다(await 뒤 open은 차단됨)
    const w = window.open("", "_blank", "width=920,height=1200");
    if (!w) { setErrs(["팝업이 차단되었습니다 — 이 사이트의 팝업을 허용한 뒤 다시 시도하세요"]); return; }
    w.document.write("<p style='font-family:sans-serif;padding:20px'>계약서 PDF 생성 중…</p>");
    try {
      let jumins: Record<string, string> = {};
      try {
        const r0 = await fetch(`${API}/biz/wcontracts/${editId}/jumin`, { headers: hdr });
        if (r0.ok) jumins = (await r0.json()).jumins || {};
      } catch { /* 마스킹본으로 진행 */ }
      const html = stdKind === "5"
        ? buildKwonriStdHtml({ b, sells, buys, brokers, jumins })
        : (stdKind === "9" && mtype1 !== "매매")
          ? buildJutaekStdHtml({ b, mtype1, sells, buys, brokers, jumins })
          : (stdKind === "6" && mtype1 !== "매매")
            ? buildSanggaStdHtml({ b, mtype1, sells, buys, brokers, jumins })
            : buildContractHtml({ b, mtype1, subCat, sells, buys, brokers, jumins });
      // 서버 확정 PDF를 새 창에 띄워 그 PDF를 인쇄 — HTML 인쇄 경로(용지·배율 왜곡) 제거
      const r = await fetch(`${API}/biz/wcontracts/render-pdf`, {
        method: "POST", headers: { ...hdr, "Content-Type": "application/json" },
        body: JSON.stringify({ html }),
      });
      if (!r.ok) { w.document.body.innerHTML = `<p style='font-family:sans-serif;padding:20px;color:#b00'>PDF 생성 실패 (${r.status}) — 창을 닫고 다시 시도하세요</p>`; return; }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      w.location.href = url;
      setTimeout(() => { try { w.focus(); w.print(); } catch { /* PDF 뷰어 인쇄버튼 사용 */ } }, 1500);
    } catch {
      try { w.document.body.innerHTML = "<p style='font-family:sans-serif;padding:20px;color:#b00'>네트워크 오류 — 창을 닫고 다시 시도하세요</p>"; } catch { /* noop */ }
    }
  };

  // 별지2) 계약갱신 거절통지서 — 주택표준 부속 서식(당사자·목적물 프리필, 사유는 폼의 rf_* 값)
  const printRefusal = async () => {
    if (isMobileDevice()) { setErrs(["인쇄는 PC(koczip.com)에서 이용할 수 있어요 — 휴대폰에서는 'PDF 다운로드'를 눌러 파일로 받아주세요"]); return; }
    const w = window.open("", "_blank", "width=920,height=1200");
    if (!w) { setErrs(["팝업이 차단되었습니다 — 이 사이트의 팝업을 허용한 뒤 다시 시도하세요"]); return; }
    w.document.write("<p style='font-family:sans-serif;padding:20px'>통지서 PDF 생성 중…</p>");
    try {
      const html = buildRefusalHtml({ b, sells, buys });
      const r = await fetch(`${API}/biz/wcontracts/render-pdf`, {
        method: "POST", headers: { ...hdr, "Content-Type": "application/json" },
        body: JSON.stringify({ html }),
      });
      if (!r.ok) { w.document.body.innerHTML = `<p style='font-family:sans-serif;padding:20px;color:#b00'>PDF 생성 실패 (${r.status})</p>`; return; }
      const url = URL.createObjectURL(await r.blob());
      w.location.href = url;
      setTimeout(() => { try { w.focus(); w.print(); } catch { /* PDF 뷰어 인쇄버튼 사용 */ } }, 1500);
    } catch {
      try { w.document.body.innerHTML = "<p style='font-family:sans-serif;padding:20px;color:#b00'>네트워크 오류</p>"; } catch { /* noop */ }
    }
  };

  // 서버 확정 PDF: 박스 headless Chrome 렌더 — 기기·프린터 설정 무관 동일 결과
  const [pdfBusy, setPdfBusy] = useState(false);
  const downloadPdf = async () => {
    if (!editId) { setErrs(["PDF 생성 전에 먼저 저장(또는 임시저장)하세요"]); return; }
    setPdfBusy(true);
    try {
      let jumins: Record<string, string> = {};
      try {
        const r0 = await fetch(`${API}/biz/wcontracts/${editId}/jumin`, { headers: hdr });
        if (r0.ok) jumins = (await r0.json()).jumins || {};
      } catch { /* 마스킹본으로 진행 */ }
      const html = stdKind === "5"
        ? buildKwonriStdHtml({ b, sells, buys, brokers, jumins })
        : (stdKind === "9" && mtype1 !== "매매")
          ? buildJutaekStdHtml({ b, mtype1, sells, buys, brokers, jumins })
          : (stdKind === "6" && mtype1 !== "매매")
            ? buildSanggaStdHtml({ b, mtype1, sells, buys, brokers, jumins })
            : buildContractHtml({ b, mtype1, subCat, sells, buys, brokers, jumins });
      const r = await fetch(`${API}/biz/wcontracts/render-pdf`, {
        method: "POST", headers: { ...hdr, "Content-Type": "application/json" },
        body: JSON.stringify({ html }),
      });
      if (!r.ok) { setErrs([`PDF 생성 실패 (${r.status})`]); return; }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `계약서_${(b.haddress || "").slice(0, 20)}_${b.contract_date || ""}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } finally { setPdfBusy(false); }
  };

  const fillFromLedger = async () => {
    const addr = (b.haddress || "").trim();
    if (addr.length < 5) { setErrs(["소재지를 먼저 입력하세요 (예: 인천 연수구 송도동 22-22)"]); return; }
    setToast("건축물대장 조회 중…");
    try {
      const r = await fetch(`${API}/biz/wcontracts/tools/ledger?address=${encodeURIComponent(addr)}`, { headers: hdr });
      const d = await r.json();
      if (!r.ok || !d.ok) { setToast(""); setErrs([d.detail || "건축물대장 조회 실패"]); return; }
      setErrs([]);
      setB(p => ({ ...p,
        build1: p.build1 || d.build1 || "",
        build2: p.build2 || d.build2 || "",
        land_py: p.land_py || d.land_py || "",
        jimok: p.jimok || "대",
      }));
      setToast(`대장 반영: ${d.bld_nm || ""} 구조 ${d.build1 || "-"} · 용도 ${d.build2 || "-"} · 대지 ${d.land_py || "-"}㎡`
        + (d.use_apr ? ` · 사용승인 ${d.use_apr}` : "") + " (빈 칸만 채움 · 대지권비율은 등기부 확인)");
      setTimeout(() => setToast(""), 6000);
      if (d.units?.length) { setUnits(d.units); setUnitDong(""); setUnitSearchMode(false); setUnitOpen(true); }
      else if (d.unit_search) { setUnits([]); setUnitSearchMode(true); setUnitHoQ(""); setUnitTried(""); setUnitOpen(true); }
      else setUnits(null);
    } catch { setToast(""); setErrs(["건축물대장 조회 실패"]); }
  };

  const doCopy = async (id: number) => {
    await fetch(`${API}/biz/wcontracts/${id}/copy`, { method: "POST", headers: hdr }); load();
  };
  const doDel = async (id: number) => {
    if (!confirm("이 계약서를 삭제할까요? (연동된 일정도 함께 삭제)")) return;
    await fetch(`${API}/biz/wcontracts/${id}`, { method: "DELETE", headers: hdr }); load();
  };

  if (items === null) return <Loading />;

  // ═══════════ 목록 ═══════════
  if (mode === "list") {
    return (
      <div style={{ maxWidth: 980, margin: "0 auto", padding: "18px 16px 96px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, display: "flex", alignItems: "center", gap: 7, margin: 0 }}>
            <FileSignature size={20} /> 계약서 작성
          </h1>
          <div style={{ flex: 1 }} />
          <button onClick={openNew} style={btnPrimary}><Plus size={15} /> 신규 작성</button>
        </div>
        <BizSubNav screen="wcontracts" />
        <p style={{ color: "var(--c-muted)", fontSize: 13.5, margin: "0 0 14px" }}>
          부동산 매매·임대차 계약서(일반) — 저장 시 중도금·잔금·만기 일정이 캘린더에 자동 등록됩니다.
        </p>
        {toast && <div style={toastSt}>{toast}</div>}
        {items.length === 0 ? (
          <div style={{ textAlign: "center", color: "var(--c-muted)", padding: "60px 0" }}>
            작성한 계약서가 없습니다. <b>신규 작성</b>으로 시작하세요.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {items.map(it => (
              <div key={it.id} onClick={() => openEdit(it.id)}
                style={{ display: "flex", alignItems: "center", gap: 10, background: "var(--c-card)",
                  border: "1px solid var(--c-border)", borderRadius: 12, padding: "12px 14px", cursor: "pointer" }}>
                <span style={{ fontSize: 11.5, fontWeight: 800, borderRadius: 6, padding: "3px 8px",
                  background: it.mtype1 === "매매" ? "#fdeaea" : "#e8f0ff",
                  color: it.mtype1 === "매매" ? "var(--c-sale)" : "var(--c-jeonse)" }}>{it.mtype1}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 14.5, overflow: "hidden",
                    textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.title}</div>
                  <div style={{ fontSize: 12.5, color: "var(--c-muted)" }}>
                    계약 {it.contract_date || "-"} · {man(it.cost)}
                    {it.sell_name && ` · ${it.sell_name} → ${it.buy_name || "?"}`}
                  </div>
                </div>
                <span style={{ fontSize: 11.5, fontWeight: 700,
                  color: it.status === "30" ? "var(--c-wolse)" : it.status === "00" ? "var(--c-faint)" : "var(--c-warn)",
                  ...(it.status === "00" ? { background: "var(--c-row-stripe)", borderRadius: 6, padding: "2px 7px" } : {}) }}>
                  {it.status === "30" ? "계약완료" : it.status === "00" ? "임시" : "계약중"}</span>
                <button title="복사" onClick={e => { e.stopPropagation(); doCopy(it.id); }} style={iconBtn}><Copy size={14} /></button>
                <button title="삭제" onClick={e => { e.stopPropagation(); doDel(it.id); }} style={iconBtn}><Trash2 size={14} /></button>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ═══════════ 에디터 (서식 1) ═══════════
  // ⚠ 입력 컴포넌트(FField·MoneyField·PartyRowsField)는 파일 하단 '외부 정의' —
  //   렌더 내부 정의는 매 타이핑마다 리마운트되어 포커스가 빠진다(2026-09-02 치명버그 수정).
  const fp = { b, set } as const;                       // 공통 프롭

  return (
    <div style={{ maxWidth: 880, margin: "0 auto", padding: "18px 16px 96px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <button onClick={() => setMode("list")} style={iconBtn}><ArrowLeft size={16} /></button>
        <h1 style={{ fontSize: 19, fontWeight: 800, margin: 0 }}>
          부동산 {isRent ? "임대차" : "매매"} 계약서 {editId ? `#${editId}` : "(신규)"}</h1>
      </div>

      {errs.length > 0 && (
        <div style={{ background: "#fff0f0", border: "1px solid #f3c2c2", borderRadius: 10,
          padding: "10px 14px", marginBottom: 12 }}>
          {errs.map((e, i) => <div key={i} style={{ color: "crimson", fontSize: 13 }}>· {e}</div>)}
        </div>
      )}

      <Sec title="기본">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <label style={{ flex: 1 }}><span style={lbl}>유형</span>
            <select value={subCat} onChange={e => setSubCat(e.target.value)} style={inp}>
              {SUB_CATS.map(s => <option key={s}>{s}</option>)}</select></label>
          <label style={{ flex: 1 }}><span style={lbl}>거래구분</span>
            <select value={mtype1} onChange={e => setMtype1(e.target.value)} style={inp}>
              {MTYPES.map(m => <option key={m}>{m}</option>)}</select></label>
          <label style={{ flex: 1 }}><span style={lbl}>계약일</span>
            <input type="date" value={b.contract_date ?? ""} onChange={e => set("contract_date", e.target.value)} style={inp} /></label>
          <label style={{ flex: 1 }}><span style={lbl}>상태</span>
            <select value={status} onChange={e => setStatus(e.target.value)} style={inp}>
              <option value="10">계약중</option><option value="30">계약완료</option></select></label>
        </div>
        <div style={{ display: "flex", gap: 6, marginTop: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ ...lbl, marginBottom: 0 }}>서식</span>
          {([...(isRent ? [["", "일반 임대차(협회 서식)"], ["9", "주택임대차표준(법무부)"], ["6", "상가건물임대차표준(법무부)"]] as const
                       : [["", "일반(협회 서식)"]] as const),
             ["5", "상가 권리금(국토부)"]] as ReadonlyArray<readonly [string, string]>).map(([v, t]) => (
            <button key={v} type="button" onClick={() => setStdKind(v as "" | "9" | "6" | "5")}
              style={{ padding: "6px 14px", borderRadius: 8, fontSize: 12.5, cursor: "pointer", fontWeight: 800,
                border: `1.5px solid ${stdKind === v ? "var(--c-primary)" : "var(--c-border)"}`,
                background: stdKind === v ? "var(--c-primary)" : "var(--c-surface)",
                color: stdKind === v ? "#fff" : "var(--c-text)" }}>{t}</button>
          ))}
          {stdKind && <span style={{ fontSize: 11, color: "var(--c-faint, #94a3b8)" }}>
            인쇄={stdKind === "9" ? "주택표준 원본(2023.10.6)+별지1" : stdKind === "6" ? "상가표준 원본(2024.5.8)+별지"
                 : "권리금계약서 원본(국토부 2015.5.27)+별지(상법 조문)"}</span>}
        </div>
      </Sec>

      {toast && <div style={toastSt}>{toast}</div>}

      <Sec title="부동산의 표시" right={<div style={{ display: "flex", gap: 6 }}>
        <button onClick={() => openPicker({ kind: "listing" })} style={{ ...iconBtn, fontSize: 12.5 }}>
          <Building2 size={13} /> 내 매물에서</button>
        <button onClick={fillFromLedger} style={{ ...iconBtn, fontSize: 12.5 }}>
          대장에서 채우기</button>
      </div>}>
        <div style={{ display: "flex", gap: 8 }}>
          <FField {...fp} label="소재지" k="haddress" flex={3} ph="예: 서울특별시 서초구 방배동 860-1" />
          <FField {...fp} label="동" k="hdong" flex={0.7} /><FField {...fp} label="호" k="hho" flex={0.7} />
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <FField {...fp} label="지목" k="jimok" ph="대" /><FField {...fp} label="토지면적(㎡)" k="land_py" />
          <FField {...fp} label="대지권 비율" k="rate" ph="예: 12345분의 40" />
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <FField {...fp} label="구조" k="build1" ph="철근콘크리트" /><FField {...fp} label="용도" k="build2" ph="공동주택" />
          <FField {...fp} label="건물면적(㎡)" k="build_py" />{isRent && <FField {...fp} label="임대면적(㎡)" k="rent_py" />}
        </div>
        {subCat === "오피스텔" && (
          <label style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 8, fontSize: 12.5 }}>
            <input type="checkbox" checked={offQ} onChange={e => setOffQ(e.target.checked)} />
            주거용 요건 충족(전용85㎡↓·전용입식부엌·전용수세식화장실) — 오피스텔 특례 보수 적용
          </label>
        )}
      </Sec>

      <Sec title="계약 내용" right={
        <select value={costStyle} onChange={e => setCostStyle(e.target.value as CostStyle)} style={{ ...inp, width: 110, padding: "4px 6px" }}>
          {["한글+숫자", "한글", "한자+숫자", "한자", "숫자"].map(s => <option key={s}>{s}</option>)}</select>}>
        <MoneyField {...fp} costStyle={costStyle} label={isRent ? "보증금" : "매매대금"} k="cost" />
        <div style={{ height: 8 }} />
        <MoneyField {...fp} costStyle={costStyle} label="계약금" k="bargain_cost" />
        <div style={{ height: 8 }} />
        <MoneyField {...fp} costStyle={costStyle} label="가계약금" k="ga_bargain_cost" dateK="ga_cont_date" toggleK="ga_on" />
        <div style={{ height: 8 }} />
        <MoneyField {...fp} costStyle={costStyle} label="융자금" k="free_cost" toggleK="free_on" />
        <div style={{ height: 8 }} />
        <MoneyField {...fp} costStyle={costStyle} label="중도금 1차" k="mcost" dateK="mcost_date" toggleK="mcost_on" />
        <div style={{ height: 8 }} />
        <MoneyField {...fp} costStyle={costStyle} label="중도금 2차" k="m1cost" dateK="m1cost_date" toggleK="m1cost_on" />
        <div style={{ height: 8 }} />
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <label style={{ flex: 2 }}>
            <span style={lbl}>잔금<em style={{ fontWeight: 400, fontStyle: "normal", fontSize: 10, color: "var(--c-faint, #94a3b8)", marginLeft: 5 }}>· 자동계산(총액−계약금−중도금)</em>
              <label style={{ marginLeft: 10, fontWeight: 400 }}>
                <input type="checkbox" checked={autoBal} onChange={e => setAutoBal(e.target.checked)} /> 자동계산</label>
            </span>
            <input type="text" inputMode="numeric" readOnly={autoBal}
              value={num("ecost") ? num("ecost").toLocaleString() : ""}
              onChange={e => set("ecost", Number(e.target.value.replace(/[^0-9]/g, "")) || "")}
              style={{ ...inp, background: autoBal ? "var(--c-row-stripe)" : undefined }} />
            {num("ecost") > 0 && <div style={{ fontSize: 11.5, color: "var(--c-primary)", marginTop: 2 }}>
              {amountKorean(num("ecost"), costStyle)}</div>}
          </label>
          <label style={{ flex: 1 }}><span style={lbl}>잔금일</span>
            <input type="date" value={b.ecost_date ?? ""} onChange={e => set("ecost_date", e.target.value)} style={inp} /></label>
        </div>
        {(mtype1 === "월세" || mtype1 === "연세") && (<>
          <div style={{ height: 8 }} />
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
            <div style={{ flex: 2 }}><MoneyField {...fp} costStyle={costStyle} label={`차임(${mtype1 === "연세" ? "연" : "월"}, 부가세 제외)`} k="fine_cost" /></div>
            <FField {...fp} label="지급일(매월)" k="rent_day" ph="예: 25" flex={1} />
            <label style={{ flex: 0.8 }}><span style={lbl}>선불/후불</span>
              <select value={b.senbul_gb ?? "후불"} onChange={e => set("senbul_gb", e.target.value)} style={inp}>
                <option>후불</option><option>선불</option></select></label>
          </div>
          <div style={{ height: 8 }} />
          <MoneyField {...fp} costStyle={costStyle} label="관리비(월)" k="manage_cost" toggleK="manage_on" />
        </>)}
        {isRent && (
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <label style={{ flex: 1 }}><span style={lbl}>임대차 시작</span>
              <input type="date" value={b.sdate ?? ""} onChange={e => set("sdate", e.target.value)} style={inp} /></label>
            <label style={{ flex: 1 }}><span style={lbl}>만기</span>
              <input type="date" value={b.edate ?? ""} onChange={e => set("edate", e.target.value)} style={inp} /></label>
          </div>
        )}
        {!isRent && (
          <div style={{ marginTop: 8 }}>
            <span style={lbl}>근저당권 등 처리</span>
            <select value={b.fine_tag ?? ""} onChange={e => set("fine_tag", e.target.value)} style={inp}>
              <option value="">선택</option>{FINE_TAGS.map(t => <option key={t}>{t}</option>)}</select>
          </div>
        )}
        {!isRent && (
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <label style={{ flex: 1 }}><span style={lbl}>매매 부가세</span>
              <select value={b.sale_tax ?? "해당사항 없음"} onChange={e => set("sale_tax", e.target.value)} style={inp}>
                <option>해당사항 없음</option><option>포함</option><option>별도</option></select></label>
            <div style={{ flex: 2 }} />
          </div>
        )}
      </Sec>

      <Sec title="거래 당사자">
        <div style={{ fontSize: 10, color: "var(--c-faint, #94a3b8)", marginBottom: 4 }}>출처: 고객 불러오기·직접 입력 (신분증 대조)</div>
        <PartyRowsField list={sells} setList={setSells}
          title={stdKind === "5" ? "임차인(권리금 받는 자)" : isRent ? "임대인" : "매도인"}
          onPick={() => openPicker({ kind: "customer", side: "sell" })} />
        <div style={{ height: 12 }} />
        <PartyRowsField list={buys} setList={setBuys}
          title={stdKind === "5" ? "신규임차인(권리금 지급자)" : isRent ? "임차인" : "매수인"}
          onPick={() => openPicker({ kind: "customer", side: "buy" })} />
        <div style={{ fontSize: 11.5, color: "var(--c-faint)", marginTop: 8 }}>
          주민번호는 암호화 저장되며 화면·저장본에는 마스킹으로만 표시됩니다.
        </div>
      </Sec>

      <Sec title={stdKind === "5" ? "알선 수수료 (협의)" : "중개보수"}>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
          <label style={{ flex: 1.4 }}>
            <span style={lbl}>보수액{stdKind !== "5" && <em style={{ fontWeight: 400, fontStyle: "normal", fontSize: 10, color: "var(--c-faint, #94a3b8)", marginLeft: 5 }}>· 법정상한(최대요율) 자동 적용 — 바로 수정 가능</em>}
              {stdKind !== "5" && <label style={{ marginLeft: 10, fontWeight: 400 }}>
                <input type="checkbox" checked={autoChg} onChange={e => setAutoChg(e.target.checked)} /> 법정상한 적용</label>}
            </span>
            <input type="text" inputMode="numeric"
              value={num("charge") ? num("charge").toLocaleString() : ""}
              onChange={e => {
                // 직접 수정하면 자동 갱신 중단(입력값 유지) — 체크박스 재선택으로 상한 복귀
                if (autoChg && stdKind !== "5") setAutoChg(false);
                set("charge", Number(e.target.value.replace(/[^0-9]/g, "")) || "");
              }}
              style={{ ...inp, background: (autoChg && stdKind !== "5") ? "var(--c-row-stripe)" : undefined }} />
            <div style={{ fontSize: 11.5, color: "var(--c-muted)", marginTop: 2 }}>
              {stdKind === "5"
                ? "권리금 알선은 중개대상물 중개가 아니어서 법정 요율·상한이 없습니다 — 협의 금액을 직접 입력하세요"
                : <>요율 {(chgInfo.rate * 100).toFixed(2)}%{chgInfo.limit ? ` · 한도 ${man(chgInfo.limit)}` : ""}
                  {chgInfo.negotiable && " · 협의구간(상한 제안)"}
                  {!autoChg && " · 수동 입력 중(법정상한 " + chgInfo.fee.toLocaleString() + "원)"}</>}
            </div>
          </label>
          <FField {...fp} label="지급시기 (의무기재)" k="charge_sigi" ph="예: 잔금일" flex={1} />
          <label style={{ flex: 0.8 }}><span style={lbl}>부가세</span>
            <select value={b.vat_yn ?? "별도"} onChange={e => set("vat_yn", e.target.value)} style={inp}>
              <option>별도</option><option>포함</option></select></label>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", marginTop: 8 }}>
          <label style={{ flex: 1, maxWidth: 220, opacity: b.gyobu_skip ? .45 : 1 }}>
            <span style={lbl}>확인설명서 교부일자</span>
            <input type="date" disabled={!!b.gyobu_skip} value={b.gyobu_date ?? ""}
              onChange={e => set("gyobu_date", e.target.value)} style={inp} /></label>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, paddingBottom: 9 }}>
            <input type="checkbox" checked={!!b.gyobu_skip}
              onChange={e => { set("gyobu_skip", e.target.checked); if (e.target.checked) set("gyobu_date", ""); }} />
            교부일자 미입력
          </label>
        </div>
      </Sec>

      <Sec title="개업공인중개사" right={
        brokers.length < 4
          ? <button onClick={() => setBrokers([...brokers, emptyBroker()])}
              style={{ ...iconBtn, fontSize: 12.5 }}>+ 공동중개 추가</button>
          : <span style={{ fontSize: 11.5, color: "var(--c-faint)" }}>최대 4개소</span>}>
        {brokers.map((k, i) => (
          <BrokerRow key={i} idx={i} broker={k}
            onChange={nb => { const l = [...brokers]; l[i] = nb; setBrokers(l); }}
            onRemove={i > 0 ? () => setBrokers(brokers.filter((_, j) => j !== i)) : undefined} />
        ))}
        <div style={{ fontSize: 11.5, color: "var(--c-faint)", marginTop: 6 }}>
          1번은 내 사무소가 자동 입력됩니다{myOffice ? "" : " (라운지 사무소 연동 시)"} — 공동중개는 추가 버튼으로.
        </div>
      </Sec>

      <Sec title="계약조항 (기본)" right={
        <span style={{ fontSize: 11.5, color: "var(--c-faint)" }}>표준 서식 조문 — 변경사항은 특약에</span>}>
        <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
          <label style={{ flex: 1, minWidth: 150 }}><span style={lbl}>부동산 인도일 (제2조)</span>
            <input type="date" value={b.handover_date ?? ""} onChange={e => set("handover_date", e.target.value)} style={inp} /></label>
          {isRent && <label style={{ flex: 0.7, minWidth: 110 }}><span style={lbl}>차임연체 해지 기수 (제4조)</span>
            <select value={b.chaim ?? "2"} onChange={e => set("chaim", e.target.value)} style={inp}>
              <option value="2">2기 (주택)</option><option value="3">3기 (상가)</option></select></label>}
        </div>
        <div style={{ background: "var(--c-row-stripe)", borderRadius: 10, padding: "12px 14px",
          maxHeight: 260, overflowY: "auto" }}>
          {(isRent ? ARTICLES_RENT : ARTICLES_SALE).map(([no, tt, txt]) => {
            const slot = (s: string, v: string | undefined, fallback: string) =>
              s.split(`{${fallback}}`).flatMap((part, i, arr) => i < arr.length - 1
                ? [part, <b key={i} style={{ color: v ? "var(--c-primary)" : "var(--c-sale)" }}>
                    {v || `[${fallback} 미입력]`}</b>]
                : [part]);
            let node: any = [txt];
            node = node.flatMap((n: any) => typeof n === "string" ? slot(n, b.handover_date || b.ecost_date, "인도일") : [n]);
            node = node.flatMap((n: any) => typeof n === "string" ? slot(n, b.edate, "만기일") : [n]);
            node = node.flatMap((n: any) => typeof n === "string" ? slot(n, b.chaim ?? "2", "연체기수") : [n]);
            return (
              <p key={no} style={{ fontSize: 12.5, lineHeight: 1.65, margin: "0 0 8px", color: "var(--c-text-soft)" }}>
                <b>{no}</b>{tt ? ` [${tt}]` : ""} {node}
              </p>
            );
          })}
        </div>
        <div style={{ fontSize: 11, color: "var(--c-faint)", marginTop: 6 }}>
          인도일 미입력 시 잔금일이 인도일로 표시됩니다. 조문은 인쇄 시 그대로 출력됩니다.
        </div>
      </Sec>

      {stdKind === "9" && isRent && (<>
      <Sec title="표준계약서 — 계약의 종류 · 확인사항">
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {["신규 계약", "합의에 의한 재계약", "계약갱신요구권 행사에 의한 갱신계약"].map((t, i) => {
            const on = String(b.cont_kind ?? "1") === String(i + 1);
            return <button key={t} type="button" onClick={() => set("cont_kind", String(i + 1))}
              style={{ padding: "7px 11px", borderRadius: 8, fontSize: 12.5, cursor: "pointer", fontWeight: on ? 800 : 500,
                border: `1.5px solid ${on ? "var(--c-primary)" : "var(--c-border)"}`,
                background: on ? "var(--c-primary)" : "var(--c-surface)", color: on ? "#fff" : "var(--c-text)" }}>{t}</button>;
          })}
        </div>
        {String(b.cont_kind) === "3" && (
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            <FField {...fp} label="갱신 전 계약기간" k="prev_period" ph="예: 2024.9.1.~2026.8.31." flex={1.4} />
            <FField {...fp} label="갱신 전 보증금(원)" k="prev_cost" />
            <FField {...fp} label="갱신 전 차임(월, 원)" k="prev_fine" />
          </div>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
          <label style={{ flex: 1 }}><span style={lbl}>미납 국세·지방세</span>
            <select value={b.tax_due ?? ""} onChange={e => set("tax_due", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">없음</option><option value="2">있음(확인·설명서 ⑩에 기재)</option></select></label>
          <label style={{ flex: 1 }}><span style={lbl}>선순위 확정일자 현황</span>
            <select value={b.senior_fix ?? ""} onChange={e => set("senior_fix", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">해당 없음</option><option value="2">해당 있음(확인·설명서 ⑩에 기재)</option></select></label>
          <FField {...fp} label="차임 입금계좌" k="rent_account" ph="은행·계좌번호" flex={1.4} />
        </div>
      </Sec>

      <Sec title="표준계약서 — 관리비 (제1조)">
        <div style={{ display: "flex", gap: 6 }}>
          {["정액", "정액이 아닌 경우"].map((t, i) => {
            const on = String(b.manage_mode ?? "1") === String(i + 1);
            return <button key={t} type="button" onClick={() => set("manage_mode", String(i + 1))}
              style={{ padding: "7px 11px", borderRadius: 8, fontSize: 12.5, cursor: "pointer", fontWeight: on ? 800 : 500,
                border: `1.5px solid ${on ? "var(--c-primary)" : "var(--c-border)"}`,
                background: on ? "var(--c-primary)" : "var(--c-surface)", color: on ? "#fff" : "var(--c-text)" }}>{t}</button>;
          })}
        </div>
        {String(b.manage_mode ?? "1") === "1" ? (<>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <MoneyField {...fp} costStyle={costStyle} label="관리비 총액(월, 원)" k="manage_cost" />
          </div>
          <div style={{ fontSize: 11.5, color: "var(--c-muted)", margin: "8px 0 4px" }}>월 10만원 이상 정액인 경우 세부금액 기재</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {["일반관리비", "전기료", "수도료", "가스 사용료", "난방비", "인터넷 사용료", "TV 사용료", "기타관리비"].map((t, i) => (
              <FField key={t} {...fp} label={t + "(원)"} k={`mfee${i + 1}`} flex={0.9} />
            ))}
          </div>
        </>) : (
          <FField {...fp} label="관리비의 항목 및 산정방식" k="manage_method" ph="예: 세대별 사용량 비례" flex={2} />
        )}
      </Sec>

      <Sec title="표준계약서 — 입주 전 수리 (제3조) · 수선 부담 (제4조)">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <label style={{ flex: 0.8 }}><span style={lbl}>수리 필요 시설</span>
            <select value={b.repair_need ?? ""} onChange={e => set("repair_need", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">없음</option><option value="2">있음</option></select></label>
          <FField {...fp} label="수리할 내용" k="repair_content" flex={2} />
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          <label style={{ flex: 0.9 }}><span style={lbl}>수리 완료 시기</span>
            <select value={b.repair_by ?? ""} onChange={e => set("repair_by", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">잔금지급 기일까지</option><option value="2">기타</option></select></label>
          <FField {...fp} label="기타(시기)" k="repair_by_etc" flex={1} />
          <label style={{ flex: 1.1 }}><span style={lbl}>미수리 시</span>
            <select value={b.repair_unfix ?? ""} onChange={e => set("repair_unfix", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">보증금·차임에서 공제</option><option value="2">기타</option></select></label>
          <FField {...fp} label="기타(내용)" k="repair_unfix_etc" flex={1} />
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <FField {...fp} label="임대인 부담 (제4조③)" k="duty_landlord" ph="예: 난방·상하수도·전기시설 등 주요설비 노후·불량 수선" flex={1} />
          <FField {...fp} label="임차인 부담" k="duty_tenant" ph="예: 고의·과실 파손, 전구 등 통상의 간단한 수선·소모품 교체" flex={1} />
        </div>
      </Sec>

      <Sec title="표준계약서 — 특약(서식 고정문 빈칸)">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <FField {...fp} label="주민등록(전입신고)·확정일자 기한" k="sp_move_date" type="date" flex={1} />
          <FField {...fp} label="미납 국세·지방세 확인 금액(원)" k="sp_tax_amt" flex={1} />
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          <label style={{ flex: 1 }}><span style={lbl}>분쟁조정위 선(先)조정 신청</span>
            <select value={b.sp_mediation ?? ""} onChange={e => set("sp_mediation", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">동의</option><option value="2">미동의</option></select></label>
          <label style={{ flex: 1 }}><span style={lbl}>철거·재건축 계획</span>
            <select value={b.sp_demolition ?? ""} onChange={e => set("sp_demolition", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">없음</option><option value="2">있음</option></select></label>
          <FField {...fp} label="공사시기" k="sp_demo_time" flex={0.8} />
          <FField {...fp} label="소요기간(개월)" k="sp_demo_period" flex={0.7} />
          <label style={{ flex: 1 }}><span style={lbl}>상세주소 신청 소유자 동의</span>
            <select value={b.sp_addr_consent ?? ""} onChange={e => set("sp_addr_consent", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">동의</option><option value="2">미동의</option></select></label>
        </div>
      </Sec>
      </>)}

      {stdKind === "6" && isRent && (<>
      <Sec title="상가표준 — 임차목적 · 차임 부가세 · 관리비">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <FField {...fp} label="임차목적 업종 (제3조)" k="purpose_biz" ph="예: 소매점(의류)" flex={1.2} />
          <label style={{ flex: 0.8 }}><span style={lbl}>차임 부가세</span>
            <select value={b.rent_vat ?? ""} onChange={e => set("rent_vat", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">불포함</option><option value="2">포함</option></select></label>
          <FField {...fp} label="차임 입금계좌" k="rent_account" ph="은행·계좌번호" flex={1.2} />
        </div>
        <div style={{ fontSize: 12, color: "var(--c-muted)", marginTop: 6 }}>
          환산보증금(보증금+차임×100)은 인쇄 시 자동 계산·기재됩니다.
        </div>
        <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
          {["정액", "정액이 아닌 경우"].map((t, i) => {
            const on = String(b.manage_mode ?? "1") === String(i + 1);
            return <button key={t} type="button" onClick={() => set("manage_mode", String(i + 1))}
              style={{ padding: "7px 11px", borderRadius: 8, fontSize: 12.5, cursor: "pointer", fontWeight: on ? 800 : 500,
                border: `1.5px solid ${on ? "var(--c-primary)" : "var(--c-border)"}`,
                background: on ? "var(--c-primary)" : "var(--c-surface)", color: on ? "#fff" : "var(--c-text)" }}>{t}</button>;
          })}
        </div>
        {String(b.manage_mode ?? "1") === "1" ? (<>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <MoneyField {...fp} costStyle={costStyle} label="관리비 총액(월, 원)" k="manage_cost" />
          </div>
          <div style={{ fontSize: 11.5, color: "var(--c-muted)", margin: "8px 0 4px" }}>월 10만원 이상 정액인 경우 세부금액 기재</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {["일반관리비", "전기료", "수도료", "가스 사용료", "수선·유지비", "청소비", "충당금", "기타관리비"].map((t, i) => (
              <FField key={t} {...fp} label={t + "(원)"} k={`mfee${i + 1}`} flex={0.9} />
            ))}
          </div>
        </>) : (
          <FField {...fp} label="관리비의 항목 및 산정방식" k="manage_method" ph="예: 점포/호실별 사용량 비례" flex={2} />
        )}
        <FField {...fp} label="임차인이 직접 납부하는 공과금" k="utility_direct" ph="예: 전기료, 수도료는 임차인이 별도로 직접 납부" flex={2} />
      </Sec>

      <Sec title="상가표준 — 특약 동의 (조정·해지권·연체)">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {([["sg_med1", "선(先)조정 신청 (조정특약①)"], ["sg_med2", "조정 절차 성실 응대 (조정특약②)"],
             ["sg_quit1", "감염병 집합제한 3개월 시 해지권 (해지특약①)"], ["sg_quit2", "해지 통고 3개월 후 효력 (해지특약②)"],
             ["sg_delay1", "감염병 조치기간 연체액 제외 (연체특약①)"], ["sg_delay2", "제외 연체액 6개월분 한도 (연체특약②)"]] as const).map(([k, t]) => (
            <label key={k} style={{ flex: "1 1 44%", minWidth: 240 }}><span style={lbl}>{t}</span>
              <select value={b[k] ?? ""} onChange={e => set(k, e.target.value)} style={inp}>
                <option value="">선택 안 함</option><option value="1">동의</option><option value="2">부동의</option></select></label>
          ))}
        </div>
      </Sec>
      </>)}

      {stdKind === "5" && (<>
      <Sec title="권리금 — 상가건물·임대차 현황 (서식 1면)">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <FField {...fp} label="상호" k="shop_name" ph="예: OO분식" flex={1} />
          <FField {...fp} label="업종" k="biz_type" ph="예: 일반음식점" flex={1} />
          <FField {...fp} label="허가(등록)번호" k="license_no" flex={1} />
          <FField {...fp} label="임대면적(㎡)" k="rent_area" flex={0.7} />
          <FField {...fp} label="전용면적(㎡)" k="exclusive_area" flex={0.7} />
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          <MoneyField {...fp} costStyle={costStyle} label="임차보증금(원)" k="lease_cost" />
          <MoneyField {...fp} costStyle={costStyle} label="월차임(원)" k="lease_fine" />
          <MoneyField {...fp} costStyle={costStyle} label="관리비(원)" k="lease_manage" />
          <label style={{ flex: 0.7 }}><span style={lbl}>부가가치세</span>
            <select value={b.lease_vat ?? ""} onChange={e => set("lease_vat", e.target.value)} style={inp}>
              <option value="">선택</option><option value="1">별도</option><option value="2">포함</option></select></label>
          <FField {...fp} label="임대차 계약기간" k="lease_period" ph="예: 2025.3.1.부터 2027.2.28.까지(24월)" flex={1.6} />
        </div>
      </Sec>
      <Sec title="권리금 — 지급 (제1조)">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <MoneyField {...fp} costStyle={costStyle} label="총 권리금(원)" k="kw_total" />
          <MoneyField {...fp} costStyle={costStyle} label="계약금(원)" k="kw_down" />
          <MoneyField {...fp} costStyle={costStyle} label="중도금(원)" k="kw_mid" />
          <FField {...fp} label="중도금 지급일" k="kw_mid_date" type="date" flex={0.8} />
          <MoneyField {...fp} costStyle={costStyle} label="잔금(원)" k="kw_bal" />
          <FField {...fp} label="잔금 지급일" k="kw_bal_date" type="date" flex={0.8} />
        </div>
        <div style={{ fontSize: 11.5, color: "var(--c-muted)", marginTop: 6 }}>
          ※ 잔금지급일까지 임대인과 신규임차인 사이에 임대차계약이 체결되지 않는 경우 임대차계약 체결일을 잔금지급일로 봅니다(서식 고정문).
        </div>
      </Sec>
      <Sec title="권리금 — 이전할 재산적 가치 (제2조③)">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <FField {...fp} label="유형의 재산적 가치" k="kw_tangible" ph="영업시설·비품 등 (비우면 서식 예시문 인쇄)" flex={1} />
          <FField {...fp} label="무형의 재산적 가치" k="kw_intangible" ph="거래처, 신용, 영업상의 노하우 등 (비우면 서식 예시문 인쇄)" flex={1} />
        </div>
        <div style={{ fontSize: 11.5, color: "var(--c-muted)", marginTop: 6 }}>※ 필요한 경우 이전 대상 목록을 별지로 첨부할 수 있습니다.</div>
      </Sec>
      </>)}

      {stdKind === "9" && isRent && (
      <Sec title="갱신거절 통지서 (별지2 — 필요 시)">
        <div style={{ fontSize: 11.5, color: "var(--c-muted)", marginBottom: 6 }}>
          임대인이 임차인의 계약갱신 요구를 거절할 때 쓰는 부속 서식입니다. 사유를 선택하고 하단 ‘갱신거절 통지서’ 버튼으로 인쇄하세요(저장 불필요, 계약서에는 인쇄되지 않음).
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <FField {...fp} label="갱신 요구받은 날" k="rf_req_date" type="date" flex={0.8} />
          <FField {...fp} label="통지서 작성일" k="rf_write_date" type="date" flex={0.8} />
          <label style={{ flex: 1.2 }}><span style={lbl}>거절 사유 (주택임대차보호법 제6조의3 제1항)</span>
            <select value={b.rf_reason ?? ""} onChange={e => set("rf_reason", e.target.value)} style={inp}>
              <option value="">선택</option>
              <option value="1">1호 — 2기 차임액 연체 사실</option>
              <option value="2">2호 — 거짓·부정한 방법의 임차</option>
              <option value="3">3호 — 상당한 보상 제공 합의</option>
              <option value="4">4호 — 무단 전대</option>
              <option value="5">5호 — 고의·중과실 파손</option>
              <option value="6">6호 — 멸실로 목적 달성 불능</option>
              <option value="7-1">7호 가목 — 철거·재건축 계획 고지 후 이행</option>
              <option value="7-2">7호 나목 — 노후·훼손 등 안전사고 우려</option>
              <option value="7-3">7호 다목 — 다른 법령에 따른 철거·재건축</option>
              <option value="8">8호 — 임대인(직계존비속) 실거주</option>
              <option value="9">9호 — 의무 위반 등 중대한 사유</option>
            </select></label>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          {String(b.rf_reason) === "3" && <FField {...fp} label="상당한 보상의 내용 (3호)" k="rf_comp" flex={1.4} />}
          {String(b.rf_reason) === "8" && (<>
            <FField {...fp} label="실거주자 성명 (8호)" k="rf_resident" flex={0.8} />
            <label style={{ flex: 0.8 }}><span style={lbl}>임대인과의 관계 (8호)</span>
              <select value={b.rf_rel ?? ""} onChange={e => set("rf_rel", e.target.value)} style={inp}>
                <option value="">선택</option><option value="1">본인</option>
                <option value="2">직계존속</option><option value="3">직계비속</option></select></label>
          </>)}
          <FField {...fp} label="구체적 사정(보충설명)" k="rf_detail" flex={2} />
        </div>
      </Sec>
      )}

      <Sec title="특약사항">
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 6 }}>
          {(isRent ? TEUK_PRESETS_RENT : TEUK_PRESETS_SALE).map((t, i) => (
            <button key={i} type="button" title={t}
              onClick={() => {
                const cur = (b.teukyak || "").trimEnd();
                const n = cur ? cur.split("\n").filter((x: string) => x.trim()).length + 1 : 1;
                set("teukyak", (cur ? cur + "\n" : "") + `${n}. ${t}`);
              }}
              style={{ padding: "5px 9px", borderRadius: 7, fontSize: 11.5, cursor: "pointer",
                border: "1px dashed var(--c-border)", background: "var(--c-surface)", color: "var(--c-muted)",
                maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              + {t.slice(0, 22)}…</button>
          ))}
        </div>
        <textarea value={b.teukyak ?? ""} onChange={e => set("teukyak", e.target.value)} rows={5}
          placeholder="특약사항을 입력하세요" style={{ ...inp, resize: "vertical", fontFamily: "inherit" }} />
      </Sec>

      <div className="wc-actions">
        <div className="wc-actions-hint">
          <CalendarCheck size={13} /> 저장 시 중도금·잔금{isRent ? "·만기" : ""} 일정이 캘린더에 자동 등록돼요
        </div>
        <div className="wc-actions-row">
          <button className="wc-btn primary" onClick={() => save(false)} disabled={saving}>
            <Save size={16} /> {saving ? "저장 중…" : "저장"}</button>
          <button className="wc-btn" onClick={() => save(true)} disabled={saving}>
            <Clock size={15} /> 임시저장</button>
          <button className="wc-btn accent" onClick={downloadPdf} disabled={saving || pdfBusy}>
            <FileDown size={15} /> {pdfBusy ? "생성 중…" : "PDF 저장"}</button>
          {/* 인쇄는 PC 전용(용지·배율) — 모바일에선 버튼 자체를 숨기고 PDF 저장으로 유도 */}
          {!isMobileDevice() && (
            <button className="wc-btn" onClick={printNow} disabled={saving}>
              <Printer size={15} /> 인쇄</button>
          )}
          <button className={"wc-btn" + (stdKind === "5" ? " muted" : "")}
            onClick={() => {
              if (stdKind === "5") { setErrs(["권리금계약서는 중개대상물 확인·설명서를 사용하지 않습니다"]); return; }
              if (!editId) { setErrs(["확인설명서 작성 전에 먼저 계약서를 저장하세요"]); return; }
              nav(`/biz/wcontracts/${editId}/offerinfo`);
            }}
            title={stdKind === "5" ? "권리금계약서는 확인설명서 사용 대상이 아닙니다" : undefined}>
            <ClipboardCheck size={15} /> 확인설명서</button>
          {stdKind === "9" && isRent && (
            <button className="wc-btn" onClick={printRefusal} disabled={saving}>
              <FileX size={15} /> 갱신거절 통지서</button>
          )}
        </div>
      </div>

      {/* ── 건축물대장 동·호 선택 모달 ── */}
      {unitOpen && units && (
        <div onClick={() => setUnitOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 91,
          background: "rgba(10,18,30,.45)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "var(--c-card)", borderRadius: 16,
            width: "min(520px, 94vw)", maxHeight: "72vh", display: "flex", flexDirection: "column",
            boxShadow: "0 18px 50px rgba(0,0,0,.3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "13px 16px",
              borderBottom: "1px solid var(--c-border-soft)" }}>
              <b style={{ fontSize: 15 }}>
                {unitSearchMode ? "대장 전유부 — 호 검색(대형 건물)" : `대장 전유부 — 동·호 선택 (${units.length}호)`}</b>
              <div style={{ flex: 1 }} />
              <button onClick={() => setUnitOpen(false)} style={iconBtn}><X size={15} /></button>
            </div>
            {unitSearchMode && (
              <div style={{ display: "flex", gap: 6, padding: "10px 16px 0" }}>
                <input placeholder="호수 입력 후 Enter (예: 101)" value={unitHoQ} autoFocus
                  onChange={e => setUnitHoQ(e.target.value)}
                  onKeyDown={async e => {
                    if (e.key !== "Enter" || !unitHoQ.trim() || unitBusy) return;
                    setUnitBusy(true); setUnitTried("");
                    try {
                      const r = await fetch(`${API}/biz/wcontracts/tools/ledger?address=${encodeURIComponent((b.haddress || "").trim())}&ho=${encodeURIComponent(unitHoQ.trim())}`, { headers: hdr });
                      const d = await r.json();
                      setUnits(d.units || []);
                      if (!d.units?.length) setUnitTried(unitHoQ.trim());
                    } finally { setUnitBusy(false); }
                  }} style={inp} />
              </div>
            )}
            {unitSearchMode && units.length === 0 && !unitBusy && (
              <div style={{ padding: "14px 16px", fontSize: 12.5, color: unitTried ? "var(--c-sale)" : "var(--c-muted)" }}>
                {unitTried
                  ? <>‘{unitTried}’ 검색 결과가 없어요 — 이 건물 대장은 <b>구획 접두 표기</b>(예: A-202, B-202)일 수 있습니다. 표기를 바꿔 다시 검색해 보세요.</>
                  : "호수가 2,000개가 넘는 건물이라 목록 대신 검색으로 찾습니다 — 호수 입력 후 Enter."}
              </div>
            )}
            {!unitSearchMode && units.length > 12 && (
              <div style={{ padding: "10px 16px 0" }}>
                <input placeholder="호 검색 (예: 202 — 부분일치)" value={unitHoQ}
                  onChange={e => setUnitHoQ(e.target.value)} style={inp} />
              </div>
            )}
            {unitBusy && <div style={{ padding: "14px 16px", color: "var(--c-muted)" }}>조회 중…</div>}
            {(() => {
              const dongs = Array.from(new Set(units.map(u => u.dong || "(동 없음)")));
              return dongs.length > 1 ? (
                <div style={{ display: "flex", gap: 6, padding: "10px 16px 0", flexWrap: "wrap" }}>
                  {["", ...dongs].map(dn => (
                    <button key={dn || "전체"} onClick={() => setUnitDong(dn)}
                      style={{ ...iconBtn, fontSize: 12,
                        background: unitDong === dn ? "var(--c-primary)" : undefined,
                        color: unitDong === dn ? "#fff" : undefined }}>{dn || "전체"}</button>
                  ))}
                </div>
              ) : null;
            })()}
            <div style={{ overflowY: "auto", padding: "8px 10px 14px" }}>
              {units
                .filter(u => !unitDong || (u.dong || "(동 없음)") === unitDong)
                .filter(u => unitSearchMode || !unitHoQ.trim() || (u.ho || "").includes(unitHoQ.trim()))
                .slice(0, 400)
                .map((u, i) => (
                  <div key={i} onClick={() => {
                    // 대지권비율은 채우지 않는다 — 등기사항이라 근사값은 위험(사용자 결정 2026-09-02)
                    setB(p => ({ ...p, hdong: u.dong || "", hho: u.ho || "",
                      build_py: u.area ?? p.build_py }));
                    setUnitOpen(false);
                    setToast(`${u.dong ? u.dong + " " : ""}${u.ho} 선택 — 전용 ${u.area ?? "-"}㎡ 반영 (대지권비율은 등기부에서 확인해 직접 입력)`);
                    setTimeout(() => setToast(""), 4000);
                  }} style={pickRow}>
                    <div style={{ fontWeight: 700, fontSize: 13.5 }}>
                      {u.dong ? `${u.dong} ` : ""}{u.ho}
                      <span style={{ marginLeft: 8, fontSize: 12, color: "var(--c-muted)", fontWeight: 400 }}>
                        {u.flr}{u.purps ? ` · ${u.purps}` : ""}</span>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--c-primary)" }}>전용 {u.area ?? "-"}㎡</div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 자동채움 피커 모달 ── */}
      {picker && (
        <div onClick={() => setPicker(null)} style={{ position: "fixed", inset: 0, zIndex: 90,
          background: "rgba(10,18,30,.45)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "var(--c-card)", borderRadius: 16,
            width: "min(560px, 94vw)", maxHeight: "76vh", display: "flex", flexDirection: "column",
            boxShadow: "0 18px 50px rgba(0,0,0,.3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "13px 16px",
              borderBottom: "1px solid var(--c-border-soft)" }}>
              <b style={{ fontSize: 15 }}>
                {picker.kind === "listing" ? "내 매물에서 불러오기"
                  : `고객원장에서 ${picker.side === "sell" ? (isRent ? "임대인" : "매도인") : (isRent ? "임차인" : "매수인")} 추가`}
              </b>
              <div style={{ flex: 1 }} />
              <button onClick={() => setPicker(null)} style={iconBtn}><X size={15} /></button>
            </div>
            <div style={{ padding: "10px 16px 0" }}>
              <input placeholder="검색 (이름·주소·단지·전화)" value={pickQ}
                onChange={e => setPickQ(e.target.value)} style={inp} autoFocus />
            </div>
            <div style={{ overflowY: "auto", padding: "8px 10px 14px" }}>
              {pickRows === null && <div style={{ padding: 20, color: "var(--c-muted)" }}>불러오는 중…</div>}
              {pickRows?.length === 0 && <div style={{ padding: 20, color: "var(--c-muted)" }}>
                {picker.kind === "listing" ? "매물이 없어요 — 사무소 연동(라운지)이 필요할 수 있습니다." : "고객이 없어요."}</div>}
              {(pickRows || [])
                .filter((it: any) => {
                  if (!pickQ.trim()) return true;
                  const q = pickQ.trim();
                  const hay = picker.kind === "listing"
                    ? `${it.complex_name || ""}${it.building_name || ""}${it.address || ""}${it.article_no || ""}`
                    : `${it.name || ""}${it.phone || ""}${it.address || ""}`;
                  return hay.includes(q);
                })
                .slice(0, 80)
                .map((it: any, i: number) => picker.kind === "listing" ? (
                  <div key={i} onClick={() => applyListing(it)} style={pickRow}>
                    <div style={{ fontWeight: 700, fontSize: 13.5 }}>
                      {(it.complex_name || it.building_name || it.address || "매물")}
                      {it.dong ? ` ${it.dong}` : ""}{it.ho ? ` ${it.ho}` : ""}
                      <span style={{ marginLeft: 6, fontSize: 11.5, color: "var(--c-primary)" }}>{({ A1: "매매", B1: "전세", B2: "월세" } as Record<string, string>)[it.trade_type] || it.trade_type}</span>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--c-muted)" }}>
                      {it.area2_m2 ? `전용 ${it.area2_m2}㎡ · ` : ""}{man(Number(it.price_won ?? (it.complex_no ? it.price : (Number(it.price) || 0) * 10000)) || 0)}
                      {Number(it.rent_won) ? ` / ${man(Number(it.rent_won))}` : ""} · {it.article_no}
                    </div>
                  </div>
                ) : (
                  <div key={i} onClick={() => applyCustomer(it)} style={pickRow}>
                    <div style={{ fontWeight: 700, fontSize: 13.5 }}>{it.name}
                      {it.roles ? <span style={{ marginLeft: 6, fontSize: 11.5, color: "var(--c-muted)" }}>{it.roles}</span> : null}</div>
                    <div style={{ fontSize: 12, color: "var(--c-muted)" }}>{it.phone || "-"} · {it.address || ""}</div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Sec({ title, right, children }: { title: string; right?: any; children: any }) {
  return (
    <section style={{ background: "var(--c-card)", border: "1px solid var(--c-border)",
      borderRadius: 14, padding: "14px 16px", marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
        <h2 style={{ fontSize: 14.5, fontWeight: 800, margin: 0 }}>{title}</h2>
        <div style={{ flex: 1 }} />{right}
      </div>
      {children}
    </section>
  );
}
const lbl: React.CSSProperties = { display: "block", fontSize: 12, fontWeight: 700,
  color: "var(--c-text-soft)", marginBottom: 3 };
const inp: React.CSSProperties = { width: "100%", boxSizing: "border-box",
  border: "1px solid var(--c-border)", borderRadius: 8, padding: "8px 10px", fontSize: 13.5 };
const btnPrimary: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 6,
  background: "var(--c-primary)", color: "#fff", border: 0, borderRadius: 9,
  padding: "9px 16px", fontWeight: 800, fontSize: 13.5, cursor: "pointer" };
const iconBtn: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 4,
  background: "var(--c-row-stripe)", border: "1px solid var(--c-border-soft)", borderRadius: 8,
  padding: "6px 8px", cursor: "pointer", color: "var(--c-text-soft)" };
// ── 안정 입력 컴포넌트(외부 정의 — 리마운트/포커스 유실 방지) ──────────────
// 항목별 자동채움 출처 — 편집화면 전용 주석(인쇄물에는 미출력)
const WSRC: Record<string, string> = {
  haddress: "매물 불러오기·직접", hdong: "매물·건축물대장(동 선택)", hho: "매물·건축물대장(호 선택)",
  jimok: "직접 입력(토지대장)", land_py: "건축물대장(대지면적)",
  rate: "직접 입력(등기부) — 자동채움 없음",
  build1: "건축물대장(구조)", build2: "건축물대장(용도)", build_py: "매물·건축물대장",
  rent_py: "매물(전용면적)",
  cost: "연동 매물(호가)", bargain_cost: "총액 10% 관례값 — 조율",
  ga_bargain_cost: "직접 입력", free_cost: "직접 입력(등기부 확인)",
  mcost: "직접 입력", m1cost: "직접 입력",
  fine_cost: "연동 매물(월세)", rent_day: "직접 입력", manage_cost: "매물 확인·직접",
  charge_sigi: "직접 입력(의무기재)",
};
const wsrcHint = (k?: string) =>
  k && WSRC[k] ? <em style={{ fontWeight: 400, fontStyle: "normal", fontSize: 10, color: "var(--c-faint, #94a3b8)", marginLeft: 5 }}>· {WSRC[k]}</em> : null;

function FField({ b, set, label, k, type = "text", ph = "", flex = 1 }: {
  b: Body; set: (k: string, v: any) => void; label: string; k: string;
  type?: string; ph?: string; flex?: number;
}) {
  return (
    <label style={{ flex, minWidth: 0 }}>
      <span style={lbl}>{label}{wsrcHint(k)}</span>
      <input type={type} value={b[k] ?? ""} placeholder={ph}
        onChange={e => set(k, type === "number" ? (e.target.value === "" ? "" : Number(e.target.value)) : e.target.value)}
        style={inp} />
    </label>
  );
}

function MoneyField({ b, set, costStyle, label, k, dateK, toggleK }: {
  b: Body; set: (k: string, v: any) => void; costStyle: CostStyle;
  label: string; k: string; dateK?: string;
  toggleK?: string;   // 선택 항목(중도금 등): 체크 해제 시 비활성+값 비움
}) {
  const v = Number(b[k]) || 0;
  const on = toggleK ? (b[toggleK] !== undefined ? !!b[toggleK] : v > 0) : true;
  const toggle = (nv: boolean) => {
    if (!toggleK) return;
    set(toggleK, nv);
    if (!nv) { set(k, ""); if (dateK) set(dateK, ""); }   // 끄면 값·일자 비움(잔금·일정 오염 방지)
  };
  if (toggleK && !on) {
    return (
      <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13,
        color: "var(--c-muted)", padding: "6px 0" }}>
        <input type="checkbox" checked={false} onChange={() => toggle(true)} />
        {label} <span style={{ fontSize: 11.5 }}>(없음 — 체크하면 입력)</span>
      </label>
    );
  }
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
      <label style={{ flex: 2 }}>
        <span style={lbl}>
          {toggleK && <input type="checkbox" checked onChange={() => toggle(false)}
            style={{ marginRight: 6, verticalAlign: "-2px" }} />}
          {label}{wsrcHint(k)}
        </span>
        <input type="text" inputMode="numeric" value={v ? v.toLocaleString() : (b[k] ?? "")}
          onChange={e => set(k, Number(e.target.value.replace(/[^0-9]/g, "")) || "")}
          placeholder="원 단위" style={inp} />
        {v > 0 && <div style={{ fontSize: 11.5, color: "var(--c-primary)", marginTop: 2 }}>
          {amountKorean(v, costStyle)}</div>}
      </label>
      {dateK && <label style={{ flex: 1 }}><span style={lbl}>지급일</span>
        <input type="date" value={b[dateK] ?? ""} onChange={e => set(dateK, e.target.value)} style={inp} /></label>}
    </div>
  );
}

function BrokerRow({ idx, broker, onChange, onRemove }: {
  idx: number; broker: Broker; onChange: (b: Broker) => void; onRemove?: () => void;
}) {
  const up = (k: keyof Broker) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...broker, [k]: e.target.value });
  return (
    <div style={{ border: "1px solid var(--c-border-soft)", borderRadius: 10,
      padding: "9px 11px", marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 800, color: "var(--c-text-soft)" }}>
          {idx === 0 ? "개업공인중개사 (내 사무소)" : `공동중개 ${idx + 1}`}</span>
        <div style={{ flex: 1 }} />
        {onRemove && <button onClick={onRemove} style={{ ...iconBtn, fontSize: 11.5, padding: "3px 8px" }}>삭제</button>}
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <input placeholder="사무소 명칭" value={broker.company} onChange={up("company")} style={{ ...inp, flex: 1.4, minWidth: 140 }} />
        <input placeholder="대표(성명)" value={broker.owner} onChange={up("owner")} style={{ ...inp, flex: 0.8, minWidth: 90 }} />
        <input placeholder="등록번호" value={broker.reg_no} onChange={up("reg_no")} style={{ ...inp, flex: 1.1, minWidth: 130 }} />
      </div>
      <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
        <input placeholder="사무소 소재지" value={broker.addr} onChange={up("addr")} style={{ ...inp, flex: 2 }} />
        <input placeholder="전화" value={broker.tel} onChange={up("tel")} style={{ ...inp, flex: 0.8, minWidth: 110 }} />
        <input placeholder="소속공인중개사(있을 때)" value={broker.belong || ""} onChange={up("belong")} style={{ ...inp, flex: 1, minWidth: 130 }} />
      </div>
    </div>
  );
}

function PartyRowsField({ list, setList, title, onPick }: {
  list: Party[]; setList: (p: Party[]) => void; title: string; onPick: () => void;
}) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ ...lbl, fontSize: 13 }}>{title}</span>
        <button onClick={() => setList([...list, emptyParty()])} style={{ ...iconBtn, fontSize: 12 }}>+ 추가</button>
        <button onClick={onPick} style={{ ...iconBtn, fontSize: 12 }}>
          <UsersIcon size={12} /> 고객에서</button>
      </div>
      {list.map((p, i) => {
        const up = (k: keyof Party, v: string) => { const l = [...list]; l[i] = { ...p, [k]: v }; setList(l); };
        const hasAgent = p.agent_name !== undefined;
        return (
          <div key={i} style={{ marginTop: 6 }}>
            <div style={{ display: "flex", gap: 6 }}>
              <input placeholder="성명" value={p.name} onChange={e => up("name", e.target.value)} style={{ ...inp, flex: 1 }} />
              <input placeholder="주민(사업자)번호" value={p.jumin} onChange={e => up("jumin", e.target.value)} style={{ ...inp, flex: 1.3 }} />
              <input placeholder="전화" value={p.tel} onChange={e => up("tel", e.target.value)} style={{ ...inp, flex: 1 }} />
              <input placeholder="주소" value={p.addr} onChange={e => up("addr", e.target.value)} style={{ ...inp, flex: 2 }} />
            </div>
            {hasAgent ? (
              <div style={{ display: "flex", gap: 6, marginTop: 4, alignItems: "center" }}>
                <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--c-muted)", flex: "none" }}>↳ 대리인</span>
                <input placeholder="대리인 성명" value={p.agent_name || ""} onChange={e => up("agent_name", e.target.value)} style={{ ...inp, flex: 1 }} />
                <input placeholder="대리인 주민번호" value={p.agent_jumin || ""} onChange={e => up("agent_jumin", e.target.value)} style={{ ...inp, flex: 1.3 }} />
                <input placeholder="대리인 전화" value={p.agent_tel || ""} onChange={e => up("agent_tel", e.target.value)} style={{ ...inp, flex: 1 }} />
                <button onClick={() => { const l = [...list]; const { agent_name, agent_jumin, agent_tel, ...rest } = p; l[i] = rest as Party; setList(l); }}
                  style={{ ...iconBtn, fontSize: 11, padding: "4px 8px", flex: "none" }}>대리인 제거</button>
              </div>
            ) : (
              <button onClick={() => up("agent_name", "")}
                style={{ ...iconBtn, fontSize: 11, padding: "3px 8px", marginTop: 4 }}>+ 대리인(위임 계약)</button>
            )}
          </div>
        );
      })}
    </div>
  );
}

const pickRow: React.CSSProperties = { padding: "9px 10px", borderRadius: 9, cursor: "pointer",
  borderBottom: "1px solid var(--c-border-soft)" };
const toastSt: React.CSSProperties = { background: "#e9f8ef", border: "1px solid #bfe8cd",
  color: "#0f7a3d", borderRadius: 10, padding: "9px 13px", fontSize: 13, fontWeight: 700,
  marginBottom: 12 };


// ── P2 인쇄: 정적 HTML 생성(새 창 주입용) — headless Chrome PDF 검증 확정 레이아웃(1페이지) ──
function esc(v: any): string {
  return String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function fmtK(d?: string): string {
  if (!d) return "        년    월    일";
  const [y, m, dd] = d.split("-");
  return `${y}년 ${Number(m)}월 ${Number(dd)}일`;
}
function koAmt(n: number): string {
  if (!n) return "";
  return amountKorean(n, "한글").replace(/^일금\s*/, "").replace(/원정$/, "").trim();
}
function monthsBetween(a?: string, z?: string): number {
  if (!a || !z) return 0;
  const [ay, am] = a.split("-").map(Number); const [zy, zm, zd] = z.split("-").map(Number);
  const [, , ad] = a.split("-").map(Number);
  let m = (zy - ay) * 12 + (zm - am);
  if (zd >= ad - 1) { /* 말일 관례: 하루 전 만기도 정수 개월 */ } else m -= 1;
  return m;
}
function buildContractHtml(x: {
  b: Body; mtype1: string; subCat: string;
  sells: Party[]; buys: Party[]; brokers: Broker[]; jumins: Record<string, string>;
}): string {
  const { b, mtype1, subCat, sells, buys, brokers, jumins } = x;
  const isRent = mtype1 !== "매매";
  const num = (k: string) => Number(b[k]) || 0;
  const jm = (side: string, i: number, field: string, masked?: string) =>
    jumins[`${side}.${i}.${field}`] || masked || "";
  const sp = (t: string) => t.split("").join(" ");
  const title = `부 동 산 (${esc(subCat)})  ${sp(mtype1)}  계 약 서`;
  const roles = isRent ? ["임대인", "임차인"] : ["매도인", "매수인"];
  const intro = isRent
    ? `임대인과 임차인 쌍방은 아래 표시 부동산에 관하여 다음 계약 내용과 같이 임대차계약을 체결한다.`
    : `매도인과 매수인 쌍방은 아래 표시 부동산에 관하여 다음 계약 내용과 같이 매매계약을 체결한다.`;
  const addrFull = [b.haddress, b.hdong ? `${b.hdong}동` : "", b.hho ? `${b.hho}호` : ""].filter(Boolean).join(" ");
  const partLabel = [b.hdong ? `${b.hdong}동` : "", b.hho ? `${b.hho}호` : ""].filter(Boolean).join(" ") || addrFull;

  // 금액표 행: [라벨, 한글, 숫자, 후미문구]
  const rows: [string, number, string][] = [];
  const push = (label: string, k: string, tail: string) => { if (num(k) > 0) rows.push([label, num(k), tail]); };
  const vatSale = b.sale_tax && b.sale_tax !== "해당사항 없음" ? ` (부가세 ${esc(b.sale_tax)})` : "";
  push(isRent ? "보 증 금" : "매매대금", "cost", isRent ? "" : vatSale);
  if (b.ga_on) push("가계약금", "ga_bargain_cost", b.ga_cont_date ? `은 ${fmtK(b.ga_cont_date)}에 지급하고 영수함.` : "은 지급하고 영수함.");
  push("계 약 금", "bargain_cost", "은 계약시에 지급하고 영수함.  ※영수자 (              印)");
  if (b.free_on) push("융 자 금", "free_cost", b.fine_tag ? `— ${esc(b.fine_tag)}` : "");
  if (b.mcost_on) push("중도금 1차", "mcost", b.mcost_date ? `은 ${fmtK(b.mcost_date)}에 지급한다.` : "");
  if (b.m1cost_on) push("중도금 2차", "m1cost", b.m1cost_date ? `은 ${fmtK(b.m1cost_date)}에 지급한다.` : "");
  push("잔    금", "ecost", b.ecost_date ? `은 ${fmtK(b.ecost_date)}에 지급한다.` : "");
  if (isRent && mtype1 !== "전세") {
    const pay = `은 매${mtype1 === "연세" ? "년" : "월"} ${esc(b.rent_day || "  ")}일 ${esc(b.senbul_gb || "후불")}로 지급한다. (부가세 제외)`;
    push("차    임", "fine_cost", pay);
    if (b.manage_on) push("관 리 비", "manage_cost", "(월)");
  }
  const moneyRows = rows.map(([label, v, tail]) =>
    `<tr><th class="grn">${label}</th><td class="gm">金</td><td style="width:30%">${esc(koAmt(v))} 원整</td>` +
    `<td class="num" style="width:16%">(₩${v.toLocaleString()})</td><td>${tail}</td></tr>`).join("\n");

  // 조항(슬롯 치환)
  const arts = isRent ? ARTICLES_RENT : ARTICLES_SALE;
  const handover = b.handover_date || b.ecost_date;
  const months = monthsBetween(b.sdate || handover, b.edate);
  const artHtml = arts.slice(1).map(([no, t, body0]) => {
    let body = esc(body0)
      .replace("{인도일}", `<span class="slot">${fmtK(handover)}</span>`)
      .replace("{만기일}", `<span class="slot">${fmtK(b.edate)}</span>${months > 0 ? `(${months}개월)` : ""}`)
      .replace("{연체기수}", `<span class="slot">${esc(b.chaim ?? "2")}</span>`);
    if (no === "제9조" && !b.gyobu_skip && b.gyobu_date)
      body += ` (교부일자 : <span class="slot">${fmtK(b.gyobu_date)}</span>)`;
    return `<p class="art"><b>${no}</b> ${t ? `[${esc(t)}] ` : ""}${body}</p>`;
  }).join("\n");

  // 당사자 서명 테이블
  const partyTable = (list: Party[], role: string, sideKey: string) => list.map((p, i) => {
    const hasAgent = !!(p.agent_name || p.agent_jumin || p.agent_tel);
    const rowN = hasAgent ? 3 : 2;
    const multi = list.length > 1 ? `<div style="font-size:7pt">${i + 1}</div>` : "";
    return `<table class="sign" style="border-top:0"><tbody>
    <tr><th class="vlab" rowspan="${rowN}">${role.split("").map(c => `<div>${c}</div>`).join("")}${multi}</th>
      <th style="width:13%">주    소</th><td colspan="5">${esc(p.addr)}</td>
      <td rowspan="${rowN}" style="width:7%;text-align:center">(인)</td></tr>
    <tr><th>주민등록번호</th><td class="num" style="width:21%">${esc(jm(sideKey, i, "jumin", p.jumin))}</td>
      <th style="width:8%">전화</th><td class="num" style="width:15%">${esc(p.tel)}</td>
      <th style="width:8%">성명</th><td>${esc(p.name)}</td></tr>
    ${hasAgent ? `<tr><th>대 리 인</th><td class="num">${esc(jm(sideKey, i, "agent_jumin", p.agent_jumin))}</td>
      <th>전화</th><td class="num">${esc(p.agent_tel || "")}</td>
      <th>성명</th><td>${esc(p.agent_name || "")}</td></tr>` : ""}
  </tbody></table>`;
  }).join("\n");

  const brokerTables = brokers.filter(k => k.company || k.owner).map(k =>
    `<table class="sign" style="border-top:0"><tbody>
    <tr><th class="vlab" rowspan="3">${"개업공인중개사".split("").map(c => `<div>${c}</div>`).join("")}</th>
      <th style="width:13%">사무소 소재지</th><td colspan="5">${esc(k.addr)}</td></tr>
    <tr><th>사무소 명칭</th><td colspan="2">${esc(k.company)}</td>
      <th style="width:12%">대 표 자 명</th><td>${esc(k.owner)}</td>
      <td style="width:13%;text-align:center;font-size:7.5pt">서명 및 날인 (인)</td></tr>
    <tr><th>전 화 번 호</th><td class="num" style="width:16%">${esc(k.tel)}</td>
      <th style="width:10%">등록번호</th><td class="num">${esc(k.reg_no)}</td>
      <th style="font-size:8pt">소속공인중개사</th>
      <td style="text-align:center;font-size:7.5pt">${k.belong ? esc(k.belong) + " " : ""}서명 및 날인 (인)</td></tr>
  </tbody></table>`).join("\n");

  const chargeRow = `<table class="sign" style="border-top:0"><tbody>
    <tr><th style="width:19%">중개보수</th>
      <td>₩${num("charge").toLocaleString()} (부가세 ${esc(b.vat_yn || "별도")})</td>
      <th style="width:12%">지급시기</th><td style="width:28%">${esc(b.charge_sigi || "")}</td></tr>
  </tbody></table>`;

  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${title}</title>
<style>
  @page{size:A4;margin:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{margin:0;padding:8mm 9mm;box-sizing:border-box}
  .wc-print{display:flex;flex-direction:column;width:192mm;
    min-height:280mm;font-family:'AppleGothic','Malgun Gothic','NanumGothic','나눔고딕','돋움',sans-serif;color:#000;
    font-size:9pt;line-height:1.32;border:2.2px solid #000;padding:2mm;box-sizing:border-box}
  .wc-print h1{text-align:center;font-size:17.5pt;letter-spacing:2px;margin:0 0 0.8mm;font-weight:900}
  .wc-print .intro{background:#eaf3fb;padding:0.7mm 2mm;font-weight:700;font-size:9pt}
  .wc-print .shead{background:#eaf3fb;font-weight:800;padding:0.5mm 2mm;margin-top:0.8mm;font-size:9.5pt}
  .wc-print table{width:100%;border-collapse:collapse;table-layout:fixed}
  .wc-print th,.wc-print td{border:1px solid #000;padding:0.8mm 1.3mm;font-size:8.6pt;
    word-break:break-all;vertical-align:middle}
  .wc-print th{font-weight:700;text-align:center;background:#efefef}
  .wc-print th.grn{background:#dcead2;width:12%}
  .wc-print td.gm{width:3.5%;text-align:center;font-weight:700}
  .wc-print td.num{white-space:nowrap;word-break:keep-all}
  .wc-print .art{font-size:8.3pt;margin:0.5mm 0;text-align:justify}
  .wc-print .art b{margin-right:1mm}
  .wc-print .slot{font-weight:800;text-decoration:underline;padding:0 0.5mm}
  .wc-print .teukwrap{flex:1;display:flex;flex-direction:column;border:1px solid #000;
    margin-top:0.8mm;min-height:13mm}
  .wc-print .teuk{padding:1mm 2mm;font-size:8.6pt;white-space:pre-wrap;flex:1}
  .wc-print .attest{margin:1mm 0 0.8mm;font-size:8.8pt;display:flex;justify-content:space-between}
  .wc-print th.vlab{background:#dcead2;width:5.5%;font-size:8.6pt;padding:0;line-height:1.15}
  .wc-print .sign td,.wc-print .sign th{height:5.2mm;font-size:8.4pt}
  .wc-print .sign{page-break-inside:avoid}
  @media screen{body{background:#888;padding:8mm 9mm;box-sizing:content-box}
    .wc-print{width:192mm;min-height:280mm;margin:0 auto;background:#fff;box-shadow:0 0 0 9mm #fff,0 2px 18px 10mm rgba(0,0,0,.35)}}
  .pbar{position:sticky;top:0;background:#1e293b;color:#fff;padding:10px 16px;font-family:sans-serif;
    font-size:13px;display:flex;gap:14px;align-items:center;justify-content:center;flex-wrap:wrap}
  .pbar b{color:#fbbf24}
  .pbar button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:7px 22px;
    font-size:14px;font-weight:700;cursor:pointer}
  @media print{.pbar{display:none}}
</style></head><body>
<div class="pbar"><span>인쇄 설정에서 <b>용지 크기: A4</b> · <b>배율: 100%(기본값)</b> · <b>여백: 기본값</b>인지 꼭 확인하세요 — 다르면 글자가 작아지거나 배치가 어긋납니다.</span>
  <button onclick="window.print()">인쇄 / PDF 저장</button></div>
<div class="wc-print">
  <h1>${title}</h1>
  <div class="intro">${intro}</div>
  <div class="shead">1. 부동산의 표시</div>
  <table><tbody>
    <tr><th class="grn">소 재 지</th><td colspan="6">${esc(addrFull)}</td></tr>
    <tr><th class="grn">토 지</th><th style="width:9%">지목</th><td style="width:13%">${esc(b.jimok || "")}</td>
      <th style="width:9%">면적</th><td style="width:15%">${b.land_py ? esc(b.land_py) + " ㎡" : ""}</td>
      <th style="width:10%">대지권비율</th><td class="num">${esc(b.rate || "")}</td></tr>
    <tr><th class="grn">건 물</th><th>구조</th><td style="width:18%;word-break:keep-all">${esc(b.build1 || "")}</td>
      <th>용도</th><td colspan="2">${esc(b.build2 || "")}</td>
      <td>면적  ${b.build_py ? esc(b.build_py) + " ㎡" : ""}</td></tr>
    ${isRent ? `<tr><th class="grn">임대할부분</th><td colspan="4">${esc(partLabel)}</td>
      <th>면적</th><td>${b.rent_py ? esc(b.rent_py) + " ㎡" : ""}</td></tr>` : ""}
  </tbody></table>
  <div class="shead">2. 계약내용</div>
  <p class="art"><b>제1조</b> ${isRent ? "[목적] " : ""}${esc(arts[0][2])}</p>
  <table><tbody>
${moneyRows}
  </tbody></table>
${artHtml}
  <div class="teukwrap">
    <div style="padding:1mm 2mm;font-weight:800;font-size:9.3pt">[ 특약사항 ]</div>
    <div class="teuk">${esc(b.teukyak || "")}</div>
  </div>
  <div class="attest">
    <span>본 계약을 증명하기 위하여 계약 당사자가 이의 없음을 확인하고 각각 서명 또는 기명 날인한다.</span>
    <b>${fmtK(b.contract_date)}</b>
  </div>
  ${partyTable(sells, roles[0], "sell_parties")}
  ${partyTable(buys, roles[1], "buy_parties")}
  ${brokerTables}
  ${chargeRow}
</div>
</body></html>`;
}


// ───────────────────────────────────────────────────────────────────
// 인쇄 — 주택임대차표준계약서(법무부·국토부, 2023.10.6 개정) 원본 복제
// 본문 3쪽 + 별지1 중요확인사항. 표기: 해당 □에 √
// ───────────────────────────────────────────────────────────────────
function jck(on: boolean, label: string): string {
  return `<b>${on ? "☑" : "□"}</b> ${label}`;
}
function jdate(d?: string, blank = "&nbsp;&nbsp;&nbsp;&nbsp;년 &nbsp;&nbsp;월 &nbsp;&nbsp;일"): string {
  if (!d) return blank;
  const [y, m, dd] = d.split("-");
  return `${y}년 ${Number(m)}월 ${Number(dd)}일`;
}
function jwon(v: any): string {
  const n = Number(String(v ?? "").replace(/[^0-9]/g, ""));
  return n ? n.toLocaleString() : "";
}
function buildJutaekStdHtml(x: {
  b: Body; mtype1: string; sells: Party[]; buys: Party[]; brokers: Broker[];
  jumins: Record<string, string>;
}): string {
  const { b, mtype1, sells, buys, brokers, jumins } = x;
  const e = (v: any) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const jm = (side: string, i: number, field: string, masked?: string) =>
    jumins[`${side}.${i}.${field}`] || masked || "";
  const num = (k: string) => Number(b[k]) || 0;
  const kindMonthly = mtype1 === "월세" || mtype1 === "연세";
  const hasDeposit = num("cost") > 0;
  const addrFull = [b.haddress, b.hdong ? `${b.hdong}동` : "", b.hho ? `${b.hho}호` : ""].filter(Boolean).join(" ");
  const partLabel = [b.hdong ? `${b.hdong}동` : "", b.hho ? `${b.hho}호` : ""].filter(Boolean).join(" ") || addrFull;
  const koW = (k: string) => num(k) ? amountKorean(num(k), "한글").replace(/^일금\s*/, "").replace(/원정$/, "") : "";
  const mfees = ["일반관리비", "전기료", "수도료", "가스 사용료", "난방비", "인터넷 사용료", "TV 사용료", "기타관리비"];
  const s0 = sells[0], b0 = buys[0];
  const bk = (i: number): Broker | undefined => (brokers || []).filter(k => k.company || k.owner)[i];
  const bkCell = (i: number) => {
    const k = bk(i);
    return `<th style="width:11%">사무소소재지</th><td style="width:22%">${e(k?.addr || "")}</td>`;
  };

  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>주택임대차표준계약서</title>
<style>
  @page{size:A4;margin:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{margin:0;padding:7mm 9mm;box-sizing:border-box;
    font-family:'AppleGothic','Malgun Gothic','NanumGothic','나눔고딕','돋움',sans-serif;color:#000;font-size:8.6pt;line-height:1.4}
  .pg{width:192mm;min-height:282mm;box-sizing:border-box;display:flex;flex-direction:column}
  .pg + .pg{page-break-before:always}
  .intro{border:1.4px dashed #c33;color:#c33;padding:1.5mm 2mm;font-size:8pt;font-weight:700;margin-bottom:1.5mm}
  h1{text-align:center;font-size:16pt;margin:0;font-weight:900;letter-spacing:1px}
  .kind{position:absolute;right:0;top:0;font-size:8.4pt;text-align:left}
  .tb{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:0.8mm}
  .tb th,.tb td{border:0.6px solid #000;padding:0.9mm 1.3mm;font-size:8.2pt;word-break:break-all;vertical-align:middle}
  .tb th{font-weight:700;text-align:center;background:#f4f4f4}
  .sh{font-weight:900;font-size:9.5pt;margin:1.6mm 0 0.4mm}
  .art{margin:0.8mm 0;font-size:8.4pt;text-align:justify}
  .art b{margin-right:1mm}
  .slot{font-weight:800;text-decoration:underline;padding:0 0.5mm}
  .gray{color:#999}
  b{font-weight:900}
  .teukbox{border:1.4px dotted #46f;background:#f4f7ff;padding:1.5mm 2mm;font-size:8.2pt;line-height:1.5}
  .grow{flex:1}
  .pn{text-align:center;font-size:8pt;margin-top:1mm}
  .b1h{background:#5b4ba0;color:#fff;text-align:center;font-weight:900;font-size:10.5pt;padding:1.4mm 0;margin-bottom:2mm}
  .b1s{border:1.6px solid #000;border-radius:4mm;padding:1.5mm 3mm;font-weight:900;font-size:9.5pt;display:inline-block;margin:2mm 0 1mm}
  .b1t{font-size:8pt;line-height:1.55;text-align:justify}
  .b1t b{font-weight:900}
  .sgn{float:right;font-size:7pt;color:#333}
</style></head><body>

<div class="pg">
  <div class="intro">이 계약서는 법무부가 국토교통부·서울시 및 관련 전문가들과 함께 민법, 주택임대차보호법, 공인중개사법 등 관계법령에 근거하여 만들었습니다. 법의 보호를 받기 위해 【중요확인사항】(별지1)을 꼭 확인하시기 바랍니다.</div>
  <div style="position:relative">
    <h1>주택임대차표준계약서</h1>
    <div class="kind">${jck(kindMonthly && hasDeposit, "보증금 있는 월세")}<br>${jck(mtype1 === "전세", "전세")} &nbsp; ${jck(kindMonthly && !hasDeposit, "월세")}</div>
  </div>
  <table class="tb"><tbody>
    <tr><td style="text-align:center">임대인( <b>${e(s0?.name || "")}</b> )과 임차인( <b>${e(b0?.name || "")}</b> )은 아래와 같이 임대차 계약을 체결한다</td></tr>
  </tbody></table>

  <div class="sh">[임차주택의 표시]</div>
  <table class="tb"><tbody>
    <tr><th style="width:12%">소 재 지</th><td colspan="5">${e(addrFull)}</td></tr>
    <tr><th>토&nbsp;&nbsp;&nbsp;&nbsp;지</th><th style="width:10%">지목</th><td style="width:26%">${e(b.jimok || "")}</td><th style="width:10%">면적</th><td colspan="2">${e(b.land_py || "")} ㎡</td></tr>
    <tr><th>건&nbsp;&nbsp;&nbsp;&nbsp;물</th><th>구조·용도</th><td>${e([b.build1, b.build2].filter(Boolean).join(" · "))}</td><th>면적</th><td colspan="2">${e(b.build_py || "")} ㎡</td></tr>
    <tr><th>임차할부분</th><td colspan="3">${e(partLabel)}</td><th>면적</th><td>${e(b.rent_py || b.build_py || "")} ㎡</td></tr>
    <tr><th rowspan="2">계약의종류</th><td colspan="2">${jck(String(b.cont_kind ?? "1") === "1", "신규 계약")} &nbsp;&nbsp; ${jck(String(b.cont_kind) === "2", "합의에 의한 재계약")}</td>
      <td colspan="3">${jck(String(b.cont_kind) === "3", "「주택임대차보호법」 제6조의3의 계약갱신요구권 행사에 의한 갱신계약")}</td></tr>
    <tr><td colspan="5">* 갱신 전 임대차계약 기간 및 금액 — 계약기간: ${b.prev_period ? e(b.prev_period) : "&nbsp;&nbsp;&nbsp;. &nbsp;&nbsp;. &nbsp;&nbsp;. ~ &nbsp;&nbsp;&nbsp;. &nbsp;&nbsp;. &nbsp;&nbsp;."} &nbsp; 보증금: ${jwon(b.prev_cost) || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"} 원, 차임: 월 ${jwon(b.prev_fine) || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"} 원</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th style="width:34%">미납 국세·지방세</th><th style="width:34%">선순위 확정일자 현황</th><th rowspan="2">확정일자 부여란<br><span style="font-weight:400;font-size:7.2pt">※ 주택임대차계약서를 제출하고 임대차 신고의 접수를 완료한 경우에는 별도로 확정일자 부여를 신청할 필요가 없습니다.</span></th></tr>
    <tr><td style="vertical-align:top">${jck(String(b.tax_due) === "1", "없음")}<span class="gray">(임대인 서명 또는 날인 __________ ㊞)</span><br>${jck(String(b.tax_due) === "2", "있음")}<span style="font-size:7.2pt">(중개대상물 확인·설명서 제2쪽 Ⅱ. 개업공인중개사 세부 확인사항 ‘⑨(⑩) 실제 권리관계 또는 공시되지 않은 물건의 권리사항’에 기재)</span></td>
      <td style="vertical-align:top">${jck(String(b.senior_fix) === "1", "해당 없음")}<span class="gray">(임대인 서명 또는 날인 __________ ㊞)</span><br>${jck(String(b.senior_fix) === "2", "해당 있음")}<span style="font-size:7.2pt">(중개대상물 확인·설명서 제2쪽 Ⅱ. 개업공인중개사 세부 확인사항 ‘⑨(⑩) 실제 권리관계 또는 공시되지 않은 물건의 권리사항’에 기재)</span></td></tr>
  </tbody></table>

  <div class="sh">[계약내용]</div>
  <p class="art"><b>제1조(보증금과 차임 및 관리비)</b> 위 부동산의 임대차에 관하여 임대인과 임차인은 합의에 의하여 보증금과 차임 및 관리비를 아래와 같이 지불하기로 한다.</p>
  <table class="tb"><tbody>
    <tr><th style="width:12%">보 증 금</th><td colspan="3">금 &nbsp;${koW("cost")}&nbsp; 원정(₩ ${jwon(b.cost)} )</td></tr>
    <tr><th>계 약 금</th><td colspan="3">금 ${koW("bargain_cost")} 원정(₩ ${jwon(b.bargain_cost)} )은 계약시에 지불하고 영수함. 영수자 ( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 인 )</td></tr>
    <tr><th>중 도 금</th><td colspan="3">금 ${koW("mcost")} 원정(₩ ${jwon(b.mcost)} )은 ${jdate(b.mcost_date, "&nbsp;&nbsp;&nbsp;&nbsp;년 &nbsp;&nbsp;월 &nbsp;&nbsp;일")}에 지불하며</td></tr>
    <tr><th>잔&nbsp;&nbsp;&nbsp;금</th><td colspan="3">금 ${koW("ecost")} 원정(₩ ${jwon(b.ecost)} )은 ${jdate(b.ecost_date)}에 지불한다</td></tr>
    <tr><th>차임(월세)</th><td colspan="3">금 ${koW("fine_cost")} 원정은 매월 ${e(b.rent_day || "&nbsp;&nbsp;")}일에 지불한다(입금계좌: ${e(b.rent_account || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;")} )</td></tr>
    <tr><th rowspan="3">관 리 비</th><td colspan="3">(정액인 경우) 총액 금 ${String(b.manage_mode ?? "1") === "1" ? koW("manage_cost") : ""} 원정(₩ ${String(b.manage_mode ?? "1") === "1" ? jwon(b.manage_cost) : ""} )<br><span class="gray">월 10만원 이상인 경우 세부금액 기재</span></td></tr>
    <tr><td colspan="3">${mfees.map((t, i) => `${i + 1}. ${t} 금 원정(₩ ${jwon(b["mfee" + (i + 1)]) || "&nbsp;&nbsp;&nbsp;"} )`).join(" &nbsp; ")}</td></tr>
    <tr><td colspan="3">(정액이 아닌 경우) 관리비의 항목 및 산정방식을 기재: ${String(b.manage_mode) === "2" ? e(b.manage_method || "") : '<span class="gray">(예: 세대별 사용량 비례, 세대수 비례)</span>'}</td></tr>
  </tbody></table>
  <p class="art"><b>제2조(임대차기간)</b> 임대인은 임차주택을 임대차 목적대로 사용·수익할 수 있는 상태로 <span class="slot">${jdate(b.handover_date || b.ecost_date)}</span>까지 임차인에게 인도하고, 임대차기간은 인도일로부터 <span class="slot">${jdate(b.edate)}</span>까지로 한다.</p>
  <p class="art"><b>제3조(입주 전 수리)</b> 임대인과 임차인은 임차주택의 수리가 필요한 시설물 및 비용부담에 관하여 다음과 같이 합의한다.</p>
  <table class="tb"><tbody>
    <tr><th style="width:20%">수리 필요 시설</th><td>${jck(String(b.repair_need) === "1", "없음")} &nbsp; ${jck(String(b.repair_need) === "2", `있음(수리할 내용: ${e(b.repair_content || "")})`)}</td></tr>
    <tr><th>수리 완료 시기</th><td>${jck(String(b.repair_by) === "1", "잔금지급 기일인")} ${String(b.repair_by) === "1" ? `<span class="slot">${jdate(b.ecost_date)}</span>까지` : "&nbsp;&nbsp;&nbsp;&nbsp;년 &nbsp;&nbsp;월 &nbsp;&nbsp;일까지"} &nbsp; ${jck(String(b.repair_by) === "2", `기타 (${e(b.repair_by_etc || "")})`)}</td></tr>
    <tr><th>약정한 수리 완료 시기<br>까지 미 수리한 경우</th><td>${jck(String(b.repair_unfix) === "1", "수리비를 임차인이 임대인에게 지급하여야 할 보증금 또는 차임에서 공제")}<br>${jck(String(b.repair_unfix) === "2", `기타(${e(b.repair_unfix_etc || "")})`)}</td></tr>
  </tbody></table>
  <div class="grow"></div>
  <div class="pn">- 1 / 4 -</div>
</div>

<div class="pg">
  <p class="art"><b>제4조(임차주택의 사용·관리·수선)</b> ① 임차인은 임대인의 동의 없이 임차주택의 구조변경 및 전대나 임차권 양도를 할 수 없으며, 임대차 목적인 주거 이외의 용도로 사용할 수 없다.<br>
  ② 임대인은 계약 존속 중 임차주택을 사용·수익에 필요한 상태로 유지하여야 하고, 임차인은 임대인이 임차주택의 보존에 필요한 행위를 하는 때 이를 거절하지 못한다.<br>
  ③ 임대인과 임차인은 계약 존속 중에 발생하는 임차주택의 수리 및 비용부담에 관하여 다음과 같이 합의한다. 다만, 합의되지 아니한 기타 수선비용에 관한 부담은 민법, 판례 기타 관습에 따른다.</p>
  <table class="tb"><tbody>
    <tr><th style="width:15%">임대인부담</th><td>${e(b.duty_landlord || "") || '<span class="gray">(예컨대, 난방, 상·하수도, 전기시설 등 임차주택의 주요설비에 대한 노후·불량으로 인한 수선은 민법 제623조, 판례상 임대인이 부담하는 것으로 해석됨)</span>'}</td></tr>
    <tr><th>임차인부담</th><td>${e(b.duty_tenant || "") || '<span class="gray">(예컨대, 임차인의 고의·과실에 기한 파손, 전구 등 통상의 간단한 수선, 소모품 교체 비용은 민법 제623조, 판례상 임차인이 부담하는 것으로 해석됨)</span>'}</td></tr>
  </tbody></table>
  <p class="art">④ 임차인이 임대인의 부담에 속하는 수선비용을 지출한 때에는 임대인에게 그 상환을 청구할 수 있다.</p>
  <p class="art"><b>제5조(계약의 해제)</b> 임차인이 임대인에게 중도금(중도금이 없을 때는 잔금)을 지급하기 전까지, 임대인은 계약금의 배액을 상환하고, 임차인은 계약금을 포기하고 이 계약을 해제할 수 있다.</p>
  <p class="art"><b>제6조(채무불이행과 손해배상)</b> 당사자 일방이 채무를 이행하지 아니하는 때에는 상대방은 상당한 기간을 정하여 그 이행을 최고하고 계약을 해제할 수 있으며, 그로 인한 손해배상을 청구할 수 있다. 다만, 채무자가 미리 이행하지 아니할 의사를 표시한 경우의 계약해제는 최고를 요하지 아니한다.</p>
  <p class="art"><b>제7조(계약의 해지)</b> ① 임차인은 본인의 과실 없이 임차주택의 일부가 멸실 기타 사유로 인하여 임대차의 목적대로 사용할 수 없는 경우에는 계약을 해지할 수 있다.<br>
  ② 임대인은 임차인이 2기의 차임액에 달하도록 연체하거나, 제4조 제1항을 위반한 경우 계약을 해지할 수 있다.</p>
  <p class="art"><b>제8조(갱신요구와 거절)</b> ① 임차인은 임대차기간이 끝나기 6개월 전부터 2개월 전까지의 기간에 계약갱신을 요구할 수 있다. 다만, 임대인은 자신 또는 그 직계존속·직계비속의 실거주 등 주택임대차보호법 제6조의3 제1항 각 호의 사유가 있는 경우에 한하여 계약갱신의 요구를 거절할 수 있다. <span style="font-size:7.4pt">※ 별지2) 계약갱신 거절통지서 양식 사용 가능</span><br>
  ② 임대인이 주택임대차보호법 제6조의3 제1항 제8호에 따른 실거주를 사유로 갱신을 거절하였음에도 불구하고 갱신요구가 거절되지 아니하였더라면 갱신되었을 기간이 만료되기 전에 정당한 사유 없이 제3자에게 주택을 임대한 경우, 임대인은 갱신거절로 인하여 임차인이 입은 손해를 배상하여야 한다.<br>
  ③ 제2항에 따른 손해배상액은 주택임대차보호법 제6조의3 제6항에 의한다.</p>
  <p class="art"><b>제9조(계약의 종료)</b> 임대차계약이 종료된 경우에 임차인은 임차주택을 원래의 상태로 복구하여 임대인에게 반환하고, 이와 동시에 임대인은 보증금을 임차인에게 반환하여야 한다. 다만, 시설물의 노후화나 통상 생길 수 있는 파손 등은 임차인의 원상복구의무에 포함되지 아니한다.</p>
  <p class="art"><b>제10조(비용의 정산)</b> ① 임차인은 계약종료 시 공과금과 관리비를 정산하여야 한다.<br>
  ② 임차인은 이미 납부한 관리비 중 장기수선충당금을 임대인(소유자인 경우)에게 반환 청구할 수 있다. 다만, 관리사무소 등 관리주체가 장기수선충당금을 정산하는 경우에는 그 관리주체에게 청구할 수 있다.</p>
  <p class="art"><b>제11조(분쟁의 해결)</b> 임대인과 임차인은 본 임대차계약과 관련한 분쟁이 발생하는 경우, 당사자 간의 협의 또는 주택임대차분쟁조정위원회의 조정을 통해 호혜적으로 해결하기 위해 노력한다.</p>
  <p class="art"><b>제12조(중개보수 등)</b> 중개보수는 거래 가액의 <span class="slot">${e(b.charge_rate || "&nbsp;&nbsp;")}</span>%인 <span class="slot">${jwon(b.charge) || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"}</span>원(${jck((b.vat_yn || "별도") === "포함", "부가가치세 포함")} ${jck((b.vat_yn || "별도") !== "포함", "불포함")})으로 임대인과 임차인이 각각 부담한다. 다만, 개업공인중개사의 고의 또는 과실로 인하여 중개의뢰인간의 거래행위가 무효·취소 또는 해제된 경우에는 그러하지 아니하다.</p>
  <p class="art"><b>제13조(중개대상물확인·설명서 교부)</b> 개업공인중개사는 중개대상물 확인·설명서를 작성하고 업무보증관계증서(공제증서등) 사본을 첨부하여 <span class="slot">${jdate(b.gyobu_date)}</span> 임대인과 임차인에게 각각 교부한다.</p>

  <div class="sh">[특약사항]</div>
  <div class="teukbox">
    • 주택을 인도받은 임차인은 <b>${jdate(b.sp_move_date, "____년 ____월 ____일")}</b>까지 주민등록(전입신고)과 주택임대차계약서상 확정일자를 받기로 하고, 임대인은 위 약정일자의 다음날까지 임차주택에 저당권 등 담보권을 설정할 수 없다.<br>
    • 임대인이 위 특약에 위반하여 임차주택에 저당권 등 담보권을 설정한 경우에는 임차인은 임대차계약을 해제 또는 해지할 수 있다. 이 경우 임대인은 임차인에게 위 특약 위반으로 인한 손해를 배상하여야 한다.<br>
    • 임대차계약을 체결한 임차인은 임대차계약 체결 시를 기준으로 임대인이 사전에 고지하지 않은 선순위 임대차 정보(주택임대차보호법 제3조의6 제3항)가 있거나 미납 국세·지방세가 <b>${String(b.sp_tax_amt ?? "").trim() !== "" ? jwon(b.sp_tax_amt) || e(b.sp_tax_amt) : "______"}</b>원을 초과하는 것을 확인한 경우 임대차기간이 시작하는 날까지 제5조에도 불구하고 계약금 등의 명목으로 임대인에게 교부한 금전 기타 물건을 포기하지 않고 임대차계약을 해제할 수 있다.<br>
    • 주택임대차계약과 관련하여 분쟁이 있는 경우 임대인 또는 임차인은 법원에 소를 제기하기 전에 먼저 주택임대차분쟁조정위원회에 조정을 신청한다. ( ${jck(String(b.sp_mediation) === "1", "동의")} &nbsp; ${jck(String(b.sp_mediation) === "2", "미동의")} )<br>
    <span style="font-size:7.6pt">※ 주택임대차분쟁조정위원회 조정을 통할 경우 60일(최대 90일) 이내 신속하게 조정 결과를 받아볼 수 있습니다.</span><br>
    • 주택의 철거 또는 재건축에 관한 구체적 계획 ( ${jck(String(b.sp_demolition) === "1", "없음")} ${jck(String(b.sp_demolition) === "2", "있음")} &nbsp;※공사시기: ${e(b.sp_demo_time || "")} &nbsp;※ 소요기간: ${e(b.sp_demo_period || "")} 개월 )<br>
    • 상세주소가 없는 경우 임차인의 상세주소부여 신청에 대한 소유자 동의여부 ( ${jck(String(b.sp_addr_consent) === "1", "동의")} &nbsp; ${jck(String(b.sp_addr_consent) === "2", "미동의")} )
  </div>
  <div class="teukbox" style="margin-top:1mm;min-height:12mm">※ 기타<br>${e(b.teukyak || "").replace(/\n/g, "<br>")}</div>
  <div class="grow"></div>
  <div class="pn">- 2 / 4 -</div>
</div>

<div class="pg">
  <p class="art" style="font-weight:700">본 계약을 증명하기 위하여 계약 당사자가 이의 없음을 확인하고 각각 서명·날인 후 임대인, 임차인, 개업공인중개사는 매 장마다 간인하여, 각각 1통씩 보관한다.
    <span style="float:right">${jdate(b.contract_date)}</span></p>
  <table class="tb"><tbody>
    <tr><th class="grn" rowspan="3" style="width:6%;background:#f4f4f4">임<br>대<br>인</th>
      <th style="width:13%">주&nbsp;&nbsp;&nbsp;&nbsp;소</th><td colspan="5">${e(s0?.addr || "")}</td>
      <td rowspan="3" style="width:9%;text-align:center;font-size:7.6pt">서명 또는<br>날인 ㊞</td></tr>
    <tr><th>주민등록번호</th><td style="width:20%">${e(jm("sell_parties", 0, "jumin", s0?.jumin))}</td><th style="width:8%">전화</th><td style="width:16%">${e(s0?.tel || "")}</td><th style="width:8%">성명</th><td>${e(s0?.name || "")}</td></tr>
    <tr><th>대&nbsp;리&nbsp;인</th><td>주소: ${e(s0?.agent_name ? "" : "")}${e((s0 as any)?.agent_addr || "")}</td><th>주민번호</th><td>${e(jm("sell_parties", 0, "agent_jumin", s0?.agent_jumin))}</td><th>성명</th><td>${e(s0?.agent_name || "")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th rowspan="3" style="width:6%">임<br>차<br>인</th>
      <th style="width:13%">주&nbsp;&nbsp;&nbsp;&nbsp;소</th><td colspan="5">${e(b0?.addr || "")}</td>
      <td rowspan="3" style="width:9%;text-align:center;font-size:7.6pt">서명 또는<br>날인 ㊞</td></tr>
    <tr><th>주민등록번호</th><td style="width:20%">${e(jm("buy_parties", 0, "jumin", b0?.jumin))}</td><th style="width:8%">전화</th><td style="width:16%">${e(b0?.tel || "")}</td><th style="width:8%">성명</th><td>${e(b0?.name || "")}</td></tr>
    <tr><th>대&nbsp;리&nbsp;인</th><td>주소: ${e((b0 as any)?.agent_addr || "")}</td><th>주민번호</th><td>${e(jm("buy_parties", 0, "agent_jumin", b0?.agent_jumin))}</td><th>성명</th><td>${e(b0?.agent_name || "")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th rowspan="5" style="width:6%">개<br>업<br>공<br>인<br>중<br>개<br>사</th>
      ${bkCell(0)}${bkCell(1)}</tr>
    <tr><th>사무소명칭</th><td>${e(bk(0)?.company || "")}</td><th>사무소명칭</th><td>${e(bk(1)?.company || "")}</td></tr>
    <tr><th>대&nbsp;&nbsp;&nbsp;&nbsp;표</th><td>서명 및 날인 &nbsp;${e(bk(0)?.owner || "")} <span class="sgn">㊞</span></td><th>대&nbsp;&nbsp;&nbsp;&nbsp;표</th><td>서명 및 날인 &nbsp;${e(bk(1)?.owner || "")} <span class="sgn">㊞</span></td></tr>
    <tr><th>등 록 번 호</th><td>${e(bk(0)?.reg_no || "")} &nbsp;<b>전화</b> ${e(bk(0)?.tel || "")}</td><th>등 록 번 호</th><td>${e(bk(1)?.reg_no || "")} &nbsp;<b>전화</b> ${e(bk(1)?.tel || "")}</td></tr>
    <tr><th>소속공인중개사</th><td>서명 및 날인 &nbsp;${e(bk(0)?.belong || "")} <span class="sgn">㊞</span></td><th>소속공인중개사</th><td>서명 및 날인 &nbsp;${e(bk(1)?.belong || "")} <span class="sgn">㊞</span></td></tr>
  </tbody></table>
  <div class="grow"></div>
  <div class="pn">- 3 / 4 -</div>
</div>

<div class="pg">
  <div style="font-size:8pt">별지1)</div>
  <div class="b1h">법의 보호를 받기 위한 중요사항! 반드시 확인하세요</div>

  <div class="b1s">&lt; 계약 체결 시 꼭 확인하세요 &gt;</div>
  <div class="b1t">
  <b>【대항력 및 우선변제권 확보】</b><br>
  ① 임차인이 <b>주택의 인도와 주민등록</b>을 마친 때에는 그 다음날부터 제3자에게 임차권을 주장할 수 있고, 계약서에 <b>확정일자</b>까지 받으면 후순위권리자나 그 밖의 채권자에 우선하여 변제받을 수 있으며, 주택의 점유와 주민등록은 임대차 기간 중 계속 유지하고 있어야 합니다.<br>
  ② <b>등기사항증명서, 미납국세·지방세, 다가구주택 확정일자 현황</b> 등을 반드시 확인하여 선순위 권리자 및 금액을 확인하고 계약 체결여부를 결정하여야 보증금을 지킬 수 있습니다.<br>
  ※ 임차인은 임대인의 동의를 받아 미납국세·지방세는 관할 세무서에서, 확정일자 현황은 관할 주민센터·등기소에서 확인할 수 있습니다.<br>
  <b>【임대차 신고의무 및 확정일자 부여 의제】</b><br>
  ① 수도권 전역, 광역시, 세종시 및 도(道)의 시(市) 지역에서 보증금 6천만원 또는 월차임 30만원을 초과하여 주택임대차계약을 체결(보증금 등의 변동이 있는 재계약·갱신계약 포함)한 경우, 임대인과 임차인은 계약체결일로부터 30일 이내에 시군구청에 해당 계약을 공동(계약서를 제출하는 경우 단독신고 가능)으로 신고하여야 합니다.<br>
  ② 주택임대차계약서를 제출하고 임대차 신고의 접수를 완료한 경우, 임대차 신고필증상 접수완료일에 확정일자가 부여된 것으로 간주되므로, 별도로 확정일자 부여를 신청할 필요가 없습니다.</div>

  <div class="b1s">&lt; 계약기간 중 꼭 확인하세요 &gt;</div>
  <div class="b1t">
  <b>【차임증액청구】</b><br>
  계약기간 중이나 임차인의 계약갱신요구권 행사로 인한 갱신 시 차임·보증금을 증액하는 경우에는 기존 차임·보증금의 5%를 초과하여 증액하지 못하고, 계약체결 또는 약정한 차임 등의 증액이 있은 후 1년 이내에는 하지 못합니다.<br>
  <b>【묵시적 갱신 등】</b><br>
  ① 임대인은 임대차기간이 끝나기 6개월부터 2개월* 전까지, 임차인은 2개월 전까지 각 상대방에게 계약을 종료하겠다거나 조건을 변경하여 재계약을 하겠다는 취지의 통지를 하지 않으면 종전 임대차와 동일한 조건으로 자동 갱신됩니다.<br>
  * 기존 규정은 1개월이고, ’20. 12. 10. 이후 최초로 체결되거나 갱신된 계약의 경우 2개월이 적용됩니다.<br>
  ② 제1항에 따라 갱신된 임대차의 존속기간은 2년입니다. 이 경우, 임차인은 언제든지 계약을 해지할 수 있지만 임대인은 계약서 제7조의 사유 또는 임차인과의 합의가 있어야 계약을 해지할 수 있습니다.<br>
  <b>【계약갱신요구 등】</b><br>
  ① 임차인이 임대차기간이 만료되기 6개월 전부터 2개월* 전까지 사이에 계약갱신을 요구할 경우 임대인은 정당한 사유 없이 거절하지 못하고, 갱신거절 시 별지 2에 게재된 계약갱신 거절통지서 양식을 활용할 수 있습니다.<br>
  * 기존 규정은 1개월이고, ’20. 12. 10. 이후 최초로 체결되거나 갱신된 계약의 경우 2개월이 적용됩니다.<br>
  ② 임차인은 계약갱신요구권을 1회에 한하여 행사할 수 있고, 이 경우 갱신되는 임대차의 존속기간은 2년, 나머지 조건은 전 임대차와 동일한 조건으로 다시 계약된 것으로 봅니다. 다만, 차임과 보증금의 증액은 청구 당시의 차임 또는 보증금 액수의 100분의 5를 초과하지 아니하는 범위에서만 가능합니다.<br>
  ③ 묵시적 갱신이나 합의에 의한 재계약의 경우 임차인이 갱신요구권을 사용한 것으로 볼 수 없으므로, 임차인은 주택임대차보호법에 따라 임대기간 중 1회로 한정되어 인정되는 갱신요구권을 차후에 사용할 수 있습니다.</div>

  <div class="b1s">&lt; 계약종료 시 꼭 확인하세요 &gt;</div>
  <div class="b1t">
  <b>【보증금액 증액시 확정일자 날인】</b><br>
  계약기간 중 보증금을 증액하거나, 재계약 또는 계약갱신 과정에서 보증금을 증액한 경우에는 증액된 보증금액에 대한 우선변제권을 확보하기 위하여 반드시 <b>다시 확정일자</b>를 받아야 합니다.</div>

  <div style="background:#5b4ba0;color:#fff;text-align:center;font-size:8pt;padding:1.4mm 2mm;margin-top:2mm">주택임대차 관련 분쟁은 전문가로 구성된 대한법률구조공단, 한국부동산원, 한국토지주택공사, 지방자치단체에 설치된 주택임대차분쟁조정위원회에서 신속하고 효율적으로 해결할 수 있습니다.</div>
  <div class="grow"></div>
  <div class="pn">- 4 / 4 -</div>
</div>
</body></html>`;
}


// ───────────────────────────────────────────────────────────────────
// 인쇄 — 상가건물 임대차 표준계약서(법무부, 2024.5.8 개정) 원본 복제
// 본문 3쪽 + 별지 중요확인사항
// ───────────────────────────────────────────────────────────────────
function buildSanggaStdHtml(x: {
  b: Body; mtype1: string; sells: Party[]; buys: Party[]; brokers: Broker[];
  jumins: Record<string, string>;
}): string {
  const { b, mtype1, sells, buys, brokers, jumins } = x;
  const e = (v: any) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const jm = (side: string, i: number, field: string, masked?: string) =>
    jumins[`${side}.${i}.${field}`] || masked || "";
  const num = (k: string) => Number(b[k]) || 0;
  const kindMonthly = mtype1 === "월세" || mtype1 === "연세";
  const hasDeposit = num("cost") > 0;
  const addrFull = [b.haddress, b.hdong ? `${b.hdong}동` : "", b.hho ? `${b.hho}호` : ""].filter(Boolean).join(" ");
  const partLabel = [b.hdong ? `${b.hdong}동` : "", b.hho ? `${b.hho}호` : ""].filter(Boolean).join(" ") || addrFull;
  const koW = (k: string) => num(k) ? amountKorean(num(k), "한글").replace(/^일금\s*/, "").replace(/원정$/, "") : "";
  const hwansan = num("cost") + num("fine_cost") * 100;
  const hwansanKo = hwansan ? amountKorean(hwansan, "한글").replace(/^일금\s*/, "").replace(/원정$/, "") : "";
  const mfees = ["일반관리비", "전기료", "수도료", "가스 사용료", "수선·유지비", "청소비", "충당금", "기타관리비"];
  const s0 = sells[0], b0 = buys[0];
  const bk = (i: number): Broker | undefined => (brokers || []).filter(k => k.company || k.owner)[i];
  const dnb = (k: string) => `( ${jck(String(b[k]) === "1", "동의")} / ${jck(String(b[k]) === "2", "부동의")} )`;

  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>상가건물 임대차 표준계약서</title>
<style>
  @page{size:A4;margin:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{margin:0;padding:7mm 9mm;box-sizing:border-box;
    font-family:'AppleGothic','Malgun Gothic','NanumGothic','나눔고딕','돋움',sans-serif;color:#000;font-size:8.6pt;line-height:1.42}
  .pg{width:192mm;min-height:282mm;box-sizing:border-box;display:flex;flex-direction:column}
  .pg + .pg{page-break-before:always}
  .intro{border:1.4px dashed #c33;color:#c33;padding:1.5mm 2mm;font-size:8pt;font-weight:700;margin-bottom:1.5mm}
  h1{text-align:center;font-size:16pt;margin:0;font-weight:900;letter-spacing:1px}
  .kind{position:absolute;right:0;top:0;font-size:8.4pt;text-align:left}
  .tb{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:0.8mm}
  .tb th,.tb td{border:0.6px solid #000;padding:0.9mm 1.3mm;font-size:8.2pt;word-break:break-all;vertical-align:middle}
  .tb th{font-weight:700;text-align:center;background:#f4f4f4}
  .sh{font-weight:900;font-size:9.5pt;margin:1.6mm 0 0.4mm}
  .art{margin:0.8mm 0;font-size:8.4pt;text-align:justify}
  .art b{margin-right:1mm}
  .slot{font-weight:800;text-decoration:underline;padding:0 0.5mm}
  .gray{color:#999}
  b{font-weight:900}
  .note{background:#f2f2f2;border:0.6px solid #000;padding:1mm 2mm;font-size:7.8pt}
  .teukbox{border:1.4px dotted #46f;padding:1.5mm 2mm;font-size:8.1pt;line-height:1.5}
  .grow{flex:1}
  .pn{text-align:center;font-size:8pt;margin-top:1mm}
  .b1h{background:#5b4ba0;color:#fff;text-align:center;font-weight:900;font-size:10.5pt;padding:1.4mm 0;margin-bottom:2mm}
  .b1s{border:1.6px solid #000;border-radius:4mm;padding:1.5mm 3mm;font-weight:900;font-size:9.5pt;display:inline-block;margin:2.5mm 0 1mm}
  .b1t{font-size:8.2pt;line-height:1.6;text-align:justify}
  .sgn{float:right;font-size:7pt;color:#333}
</style></head><body>

<div class="pg">
  <div class="intro">이 계약서는 법무부에서 국토교통부·서울시·중소벤처기업부·소상공인진흥공단 등 유관 기관 및 학계 전문가와 함께 민법, 상가건물 임대차보호법, 공인중개사법 등 관계법령에 근거하여 만들었습니다. 법의 보호를 받기 위해 【중요확인사항】(별지)을 꼭 확인하시기 바랍니다.</div>
  <div style="position:relative">
    <h1>상가건물 임대차 표준계약서</h1>
    <div class="kind">${jck(kindMonthly && hasDeposit, "보증금 있는 월세")}<br>${jck(mtype1 === "전세", "전세")} &nbsp; ${jck(kindMonthly && !hasDeposit, "월세")}</div>
  </div>
  <table class="tb"><tbody>
    <tr><td style="text-align:center">임대인( <b>${e(s0?.name || "")}</b> )과 임차인( <b>${e(b0?.name || "")}</b> )은 아래와 같이 임대차 계약을 체결한다</td></tr>
  </tbody></table>

  <div class="sh">[임차 상가건물의 표시]</div>
  <table class="tb"><tbody>
    <tr><th style="width:12%">소 재 지</th><td colspan="5">${e(addrFull)}</td></tr>
    <tr><th>토&nbsp;&nbsp;&nbsp;&nbsp;지</th><th style="width:10%">지목</th><td style="width:26%">${e(b.jimok || "")}</td><th style="width:10%">면적</th><td colspan="2">${e(b.land_py || "")} ㎡</td></tr>
    <tr><th>건&nbsp;&nbsp;&nbsp;&nbsp;물</th><th>구조·용도</th><td>${e([b.build1, b.build2].filter(Boolean).join(" · "))}</td><th>면적</th><td colspan="2">${e(b.build_py || "")} ㎡</td></tr>
    <tr><th>임차할부분</th><td colspan="3">${e(partLabel)}</td><th>면적</th><td>${e(b.rent_py || b.build_py || "")} ㎡</td></tr>
    <tr><td colspan="6" class="note" style="border:0">유의사항: 임차할 부분을 특정하기 위해서 도면을 첨부하는 것이 좋습니다.</td></tr>
  </tbody></table>

  <div class="sh">[계약내용]</div>
  <p class="art"><b>제1조(보증금과 차임 및 관리비)</b> 위 상가건물의 임대차에 관하여 임대인과 임차인은 합의에 의하여 보증금과 차임 및 관리비를 아래와 같이 지급하기로 한다.</p>
  <table class="tb"><tbody>
    <tr><th style="width:12%">보 증 금</th><td colspan="3">금 &nbsp;${koW("cost")}&nbsp; 원정(₩ ${num("cost") ? num("cost").toLocaleString() : ""} )</td></tr>
    <tr><th>계 약 금</th><td colspan="3">금 ${koW("bargain_cost")} 원정(₩ ${num("bargain_cost") ? num("bargain_cost").toLocaleString() : ""} )은 계약시에 지급하고 수령함. 수령인 ( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 인 )</td></tr>
    <tr><th>중 도 금</th><td colspan="3">금 ${koW("mcost")} 원정(₩ ${num("mcost") ? num("mcost").toLocaleString() : ""} )은 ${jdate(b.mcost_date, "&nbsp;&nbsp;&nbsp;&nbsp;년 &nbsp;&nbsp;월 &nbsp;&nbsp;일")}에 지급하며</td></tr>
    <tr><th>잔&nbsp;&nbsp;&nbsp;금</th><td colspan="3">금 ${koW("ecost")} 원정(₩ ${num("ecost") ? num("ecost").toLocaleString() : ""} )은 ${jdate(b.ecost_date)}에 지급한다</td></tr>
    <tr><th>차임(월세)</th><td colspan="3">금 ${koW("fine_cost")} 원정(₩ ${num("fine_cost") ? num("fine_cost").toLocaleString() : ""} )은 매월 ${e(b.rent_day || "&nbsp;&nbsp;")}일에 지급한다. 부가세 ${jck(String(b.rent_vat) === "1", "불포함")} ${jck(String(b.rent_vat) === "2", "포함")}<br>(입금계좌: ${e(b.rent_account || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;")} )</td></tr>
    <tr><th>환산보증금</th><td colspan="3">금 &nbsp;${hwansanKo}&nbsp; 원정(₩ ${hwansan ? hwansan.toLocaleString() : ""} )</td></tr>
    <tr><th rowspan="4">관 리 비</th><td colspan="3">(정액인 경우) 총액 금 ${String(b.manage_mode ?? "1") === "1" ? koW("manage_cost") : ""} 원정(₩ ${String(b.manage_mode ?? "1") === "1" && num("manage_cost") ? num("manage_cost").toLocaleString() : ""} )<br><span class="gray">월 10만원 이상인 경우 세부금액 기재</span></td></tr>
    <tr><td colspan="3">${mfees.map((t, i) => `${i + 1}. ${t} 금 원정(₩ ${num("mfee" + (i + 1)) ? num("mfee" + (i + 1)).toLocaleString() : "&nbsp;&nbsp;&nbsp;"} )`).join(" &nbsp; ")}</td></tr>
    <tr><td colspan="3">(정액이 아닌 경우) 관리비의 항목 및 산정방식을 기재: ${String(b.manage_mode) === "2" ? e(b.manage_method || "") : '<span class="gray">(예: 점포/호실별 사용량 비례, 점포/호실수 비례)</span>'}</td></tr>
    <tr><td colspan="3">(임차인이 직접 납부하는 공과금이 있는 경우) ${e(b.utility_direct || "") || '<span class="gray">임차인이 직접 납부하는 공과금을 기재(예: 전기료, 수도료는 임차인이 별도로 직접 납부한다)</span>'}</td></tr>
  </tbody></table>
  <div class="note">유의사항: ① 당해 계약이 환산보증금을 초과하는 임대차인 경우 확정일자를 부여받을 수 없고, 전세권 등을 설정할 수 있습니다 ② 보증금 보호를 위해 등기사항증명서, 미납국세, 상가건물 확정일자 현황 등을 확인하는 것이 좋습니다 ※ 미납국세·선순위확정일자 현황 확인방법은 "별지" 참조</div>

  <p class="art"><b>제2조(임대차기간)</b> 임대인은 임차 상가건물을 임대차 목적대로 사용·수익할 수 있는 상태로 <span class="slot">${jdate(b.handover_date || b.ecost_date)}</span>까지 임차인에게 인도하고, 임대차기간은 인도일로부터 <span class="slot">${jdate(b.edate)}</span>까지로 한다.</p>
  <p class="art"><b>제3조(임차목적)</b> 임차인은 임차 상가건물을 <span class="slot">${e(b.purpose_biz || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;")}</span>(업종)을 위한 용도로 사용한다.</p>
  <p class="art"><b>제4조(사용·관리·수선)</b> ① 임차인은 임대인의 동의 없이 임차 상가건물의 구조·용도 변경 및 전대나 임차권 양도를 할 수 없다.<br>
  ② 임대인은 계약 존속 중 임차 상가건물을 사용·수익에 필요한 상태로 유지하여야 하고, 임차인은 임대인이 임차 상가건물의 보존에 필요한 행위를 하는 때 이를 거절하지 못한다.<br>
  ③ 임차인이 임대인의 부담에 속하는 수선비용을 지출한 때에는 임대인에게 그 상환을 청구할 수 있다.</p>
  <p class="art"><b>제5조(계약의 해제)</b> 임차인이 임대인에게 중도금(중도금이 없을 때는 잔금)을 지급하기 전까지, 임대인은 계약금의 배액을 상환하고, 임차인은 계약금을 포기하고 계약을 해제할 수 있다.</p>
  <div class="grow"></div>
  <div class="pn">- 1 / 3 -</div>
</div>

<div class="pg">
  <p class="art"><b>제6조(채무불이행과 손해배상)</b> 당사자 일방이 채무를 이행하지 아니하는 때에는 상대방은 상당한 기간을 정하여 그 이행을 최고하고 계약을 해제할 수 있으며, 그로 인한 손해배상을 청구할 수 있다. 다만, 채무자가 미리 이행하지 아니할 의사를 표시한 경우의 계약해제는 최고를 요하지 아니한다.</p>
  <p class="art"><b>제7조(계약의 해지)</b> ① 임차인은 본인의 과실 없이 임차 상가건물의 일부가 멸실 기타 사유로 인하여 임대차의 목적대로 사용, 수익할 수 없는 때에는 임차인은 그 부분의 비율에 의한 차임의 감액을 청구할 수 있다. 이 경우에 그 잔존부분만으로 임차의 목적을 달성할 수 없는 때에는 임차인은 계약을 해지할 수 있다.<br>
  ② 임대인은 임차인이 3기의 차임액에 달하도록 차임을 연체하거나, 제4조 제1항을 위반한 경우 계약을 해지할 수 있다.</p>
  <p class="art"><b>제8조(계약의 종료와 권리금회수기회 보호)</b> ① 계약이 종료된 경우에 임차인은 임차 상가건물을 원상회복하여 임대인에게 반환하고, 이와 동시에 임대인은 보증금을 임차인에게 반환하여야 한다.<br>
  ② 임대인은 임대차기간이 끝나기 6개월 전부터 임대차 종료 시까지 「상가건물임대차보호법」 제10조의4 제1항 각 호의 어느 하나에 해당하는 행위를 함으로써 권리금 계약에 따라 임차인이 주선한 신규임차인이 되려는 자로부터 권리금을 지급받는 것을 방해하여서는 아니 된다. 다만, 「상가건물임대차보호법」 제10조 제1항 각 호의 어느 하나에 해당하는 사유가 있는 경우에는 그러하지 아니하다.<br>
  ③ 임대인이 제2항을 위반하여 임차인에게 손해를 발생하게 한 때에는 그 손해를 배상할 책임이 있다. 이 경우 그 손해배상액은 신규임차인이 임차인에게 지급하기로 한 권리금과 임대차 종료 당시의 권리금 중 낮은 금액을 넘지 못한다.<br>
  ④ 임차인은 임대인에게 신규임차인이 되려는 자의 보증금 및 차임을 지급할 자력 또는 그 밖에 임차인으로서의 의무를 이행할 의사 및 능력에 관하여 자신이 알고 있는 정보를 제공하여야 한다.</p>
  <p class="art"><b>제9조(재건축 등 계획과 갱신거절)</b> 임대인이 계약 체결 당시 공사시기 및 소요기간 등을 포함한 철거 또는 재건축 계획을 임차인에게 구체적으로 고지하고 그 계획에 따르는 경우, 임대인은 임차인이 상가건물임대차보호법 제10조 제1항 제7호에 따라 계약갱신을 요구하더라도 계약갱신의 요구를 거절할 수 있다.</p>
  <p class="art"><b>제10조(비용의 정산)</b> ① 임차인은 계약이 종료된 경우 공과금과 관리비를 정산하여야 한다.<br>
  ② 임차인은 이미 납부한 관리비 중 장기수선충당금을 소유자에게 반환 청구할 수 있다. 다만, 임차 상가건물에 관한 장기수선충당금을 정산하는 주체가 소유자가 아닌 경우에는 그 자에게 청구할 수 있다.</p>
  <p class="art"><b>제11조(중개보수 등)</b> 중개보수는 거래 가액의 <span class="slot">${e(b.charge_rate || "&nbsp;&nbsp;")}</span> % 인 <span class="slot">${num("charge") ? num("charge").toLocaleString() : "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"}</span>원(부가세 ${jck((b.vat_yn || "별도") !== "포함", "불포함")} ${jck((b.vat_yn || "별도") === "포함", "포함")})으로 임대인과 임차인이 각각 부담한다. 다만, 개업공인중개사의 고의 또는 과실로 인하여 중개의뢰인간의 거래행위가 무효·취소 또는 해제된 경우에는 그러하지 아니하다.</p>
  <p class="art"><b>제12조(중개대상물 확인·설명서 교부)</b> 개업공인중개사는 중개대상물 확인·설명서를 작성하고 업무보증관계증서(공제증서 등) 사본을 첨부하여 임대인과 임차인에게 각각 교부한다.</p>

  <div class="sh">[특약사항]</div>
  <div class="teukbox">
    <b>※ 조정 관련 특약</b><br>
    ① 상가 임대차 계약과 관련하여 분쟁이 있는 경우 임대인 또는 임차인은 법원에 소를 제기하기 전에 먼저 상가건물임대차분쟁조정위원회에 조정을 신청하여야 한다 ${dnb("sg_med1")}.<br>
    ② 임차인이 상가건물임대차분쟁조정위원회에 상가 임대차 계약과 관련한 조정을 신청한 경우, 임대인은 조정 절차에 성실하게 응해야 한다 ${dnb("sg_med2")}.<br>
    ○ 참고) 상가건물임대차분쟁조정위원회 조정을 통할 경우 60일(최대90일) 이내 신속하게 조정 결과를 받아볼 수 있습니다.<br>
    <b>※ 해지권 특약</b><br>
    ① 임차인은 「감염병의 예방 및 관리에 관한 법률」 제49조제1항제2호에 따른 집합 제한 또는 금지 조치를 3개월 이상 받음으로써 발생한 경제사정의 변동으로 인하여 폐업한 경우에는 임대차계약을 해지할 수 있다 ${dnb("sg_quit1")}.<br>
    ② 제1항에 따른 해지는 임대인이 계약해지의 통고를 받은 날부터 3개월이 지나면 효력이 발생한다 ${dnb("sg_quit2")}.<br>
    <b>※ 연체 관련 특약</b><br>
    ① 코로나19 또는 그에 준하는 감염병으로 임차인이 집합금지조치 또는 집합제한조치를 받은 경우 그 기간 동안 연체한 차임액은 제10조제1항제1호, 제10조의4제1항 단서 및 제10조의8의 적용에 있어서는 차임연체액으로 보지 아니한다 ${dnb("sg_delay1")}.<br>
    ② 전항에 따라 연체한 것으로 보지 아니하는 차임액은 6개월분을 초과할 수 없다 ${dnb("sg_delay2")}.
  </div>
  <div class="teukbox" style="margin-top:1mm;min-height:10mm">${e(b.teukyak || "").replace(/\n/g, "<br>")}</div>

  <p class="art" style="font-weight:700;margin-top:2mm">본 계약을 증명하기 위하여 계약 당사자가 이의 없음을 확인하고 각각 서명·날인 후 임대인, 임차인, 개업공인중개사는 매 장마다 간인하여, 각각 1통씩 보관한다.
    <span style="float:right">${jdate(b.contract_date)}</span></p>
  <div class="grow"></div>
  <div class="pn">- 2 / 3 -</div>
</div>

<div class="pg">
  <table class="tb"><tbody>
    <tr><th rowspan="3" style="width:6%">임<br>대<br>인</th>
      <th style="width:16%">주&nbsp;&nbsp;&nbsp;&nbsp;소</th><td colspan="5">${e(s0?.addr || "")}</td>
      <td rowspan="3" style="width:9%;text-align:center;font-size:7.6pt">서명 또는<br>날인 ㊞</td></tr>
    <tr><th>주민등록번호<br>(법인등록번호)</th><td style="width:20%">${e(jm("sell_parties", 0, "jumin", s0?.jumin))}</td><th style="width:8%">전화</th><td style="width:15%">${e(s0?.tel || "")}</td><th style="width:10%">성명<br>(회사명)</th><td>${e(s0?.name || "")}</td></tr>
    <tr><th>대&nbsp;리&nbsp;인</th><td>주소:</td><th>주민등록번호</th><td>${e(jm("sell_parties", 0, "agent_jumin", s0?.agent_jumin))}</td><th>성명</th><td>${e(s0?.agent_name || "")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th rowspan="3" style="width:6%">임<br>차<br>인</th>
      <th style="width:16%">주&nbsp;&nbsp;&nbsp;&nbsp;소</th><td colspan="5">${e(b0?.addr || "")}</td>
      <td rowspan="3" style="width:9%;text-align:center;font-size:7.6pt">서명 또는<br>날인 ㊞</td></tr>
    <tr><th>주민등록번호<br>(법인등록번호)</th><td style="width:20%">${e(jm("buy_parties", 0, "jumin", b0?.jumin))}</td><th style="width:8%">전화</th><td style="width:15%">${e(b0?.tel || "")}</td><th style="width:10%">성명<br>(회사명)</th><td>${e(b0?.name || "")}</td></tr>
    <tr><th>대&nbsp;리&nbsp;인</th><td>주소:</td><th>주민등록번호</th><td>${e(jm("buy_parties", 0, "agent_jumin", b0?.agent_jumin))}</td><th>성명</th><td>${e(b0?.agent_name || "")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th rowspan="5" style="width:6%">개<br>업<br>공<br>인<br>중<br>개<br>사</th>
      <th style="width:14%">사무소소재지</th><td style="width:29%">${e(bk(0)?.addr || "")}</td><th style="width:14%">사무소소재지</th><td>${e(bk(1)?.addr || "")}</td></tr>
    <tr><th>사무소명칭</th><td>${e(bk(0)?.company || "")}</td><th>사무소명칭</th><td>${e(bk(1)?.company || "")}</td></tr>
    <tr><th>대&nbsp;&nbsp;&nbsp;&nbsp;표</th><td>서명 및 날인 &nbsp;${e(bk(0)?.owner || "")} <span class="sgn">㊞</span></td><th>대&nbsp;&nbsp;&nbsp;&nbsp;표</th><td>서명 및 날인 &nbsp;${e(bk(1)?.owner || "")} <span class="sgn">㊞</span></td></tr>
    <tr><th>등 록 번 호</th><td>${e(bk(0)?.reg_no || "")} &nbsp;<b>전화</b> ${e(bk(0)?.tel || "")}</td><th>등 록 번 호</th><td>${e(bk(1)?.reg_no || "")} &nbsp;<b>전화</b> ${e(bk(1)?.tel || "")}</td></tr>
    <tr><th>소속공인중개사</th><td>서명 및 날인 &nbsp;${e(bk(0)?.belong || "")} <span class="sgn">㊞</span></td><th>소속공인중개사</th><td>서명 및 날인 &nbsp;${e(bk(1)?.belong || "")} <span class="sgn">㊞</span></td></tr>
  </tbody></table>
  <div class="grow"></div>
  <div class="pn">- 3 / 3 -</div>
</div>

<div class="pg">
  <div style="font-size:8pt">별지)</div>
  <div class="b1h">법의 보호를 받기 위한 중요사항! 반드시 확인하세요</div>

  <div class="b1s">&lt; 계약 체결 시 꼭 확인하세요 &gt;</div>
  <div class="b1t">
  <b>【대항력 및 우선변제권 확보】</b><br>
  임차인이 <b>상가건물의 인도와 사업자등록</b>을 마친 때에는 그 다음날부터 제3자에게 임차권을 주장할 수 있고, 환산보증금을 초과하지 않는 임대차의 경우 계약서에 <b>확정일자</b>까지 받으면, 후순위권리자나 그 밖의 채권자에 우선하여 변제받을 수 있습니다.<br>
  ※ 임차인은 최대한 신속히 ① 사업자등록과 ② 확정일자를 받아야 하고, 상가건물의 점유와 사업자등록은 임대차 기간 중 계속 유지하고 있어야 합니다.</div>

  <div class="b1s">&lt; 계약기간 중 꼭 확인하세요 &gt;</div>
  <div class="b1t">
  <b>【계약갱신요구】</b><br>
  ① 임차인이 임대차기간이 만료되기 6개월 전부터 1개월 전까지 사이에 계약갱신을 요구할 경우 임대인은 정당한 사유(3기의 차임액 연체 등, 상가건물 임대차보호법 제10조제1항 참조) 없이 거절하지 못합니다.<br>
  ② 임차인의 계약갱신요구권은 최초의 임대차기간을 포함한 전체 임대차기간이 10년을 초과하지 아니하는 범위에서만 행사할 수 있습니다.<br>
  ③ 갱신되는 임대차는 전 임대차와 동일한 조건으로 다시 계약된 것으로 봅니다. 다만, 차임과 보증금은 청구 당시의 차임 또는 보증금의 100분의 5의 금액을 초과하지 아니하는 범위에서 증액할 수 있습니다.<br>
  ※ 환산보증금을 초과하는 임대차의 계약갱신의 경우 상가건물에 관한 조세, 공과금, 주변 상가건물의 차임 및 보증금, 그 밖의 부담이나 경제사정의 변동 등을 고려하여 차임과 보증금의 증감을 청구할 수 있습니다.<br>
  <b>【차임 등의 증감청구권】</b><br>
  차임 또는 보증금이 임차건물에 관한 조세, 공과금, 그 밖의 부담의 증감이나 제1급감염병 등에 의한 경제사정의 변동으로 인하여 상당하지 아니하게 된 경우에는 당사자는 장래의 차임 또는 보증금에 대하여 증감을 청구할 수 있습니다. 그러나 증액의 경우에는 대통령령으로 정하는 기준에 따른 비율(5%)을 초과하지 못합니다.</div>

  <div class="b1s">&lt; 계약종료 시 꼭 확인하세요 &gt;</div>
  <div class="b1t">
  <b>【보증금액 변경시 확정일자 날인】</b><br>
  계약기간 중 보증금을 증액하거나, 재계약을 하면서 보증금을 증액한 경우에는 증액된 보증금액에 대한 우선변제권을 확보하기 위하여 반드시 <b>다시 확정일자</b>를 받아야 합니다.</div>
  <div class="grow"></div>
  <div class="pn">- 별지 -</div>
</div>
</body></html>`;
}

// ══════════════════════════════════════════════════════════════════
// 상가건물 임대차 권리금계약서 — 국토부 표준서식(2015.5.27) 원본 복제 인쇄.
// 정본: 법무부 게시 '상가건물 임대차 권리금거래계약서.hwp' (KSRC: moj.go.kr 119/237967)
// 당사자 매핑: sells=임차인(권리금 받는 자) / buys=신규임차인. 중개사 란은 원본에 없어 미인쇄.
// ══════════════════════════════════════════════════════════════════
function buildKwonriStdHtml(x: {
  b: Body; sells: Party[]; buys: Party[]; brokers: Broker[];
  jumins: Record<string, string>;
}): string {
  const { b, sells, buys, jumins } = x;
  const e = (v: any) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const jm = (side: string, i: number, field: string, masked?: string) =>
    jumins[`${side}.${i}.${field}`] || masked || "";
  const num = (k: string) => Number(b[k]) || 0;
  const koW = (k: string) => num(k) ? amountKorean(num(k), "한글").replace(/^일금\s*/, "").replace(/원정$/, "") : "";
  const s0 = sells[0], n0 = buys[0];
  const addrFull = [b.haddress, b.hdong ? `${b.hdong}동` : "", b.hho ? `${b.hho}호` : ""].filter(Boolean).join(" ");
  const dt = (v: any) => {
    const s = String(v || "");
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return m ? `${m[1]}년 ${m[2]}월 ${m[3]}일` : (s || "&nbsp;&nbsp;&nbsp;&nbsp;년 &nbsp;&nbsp;월 &nbsp;&nbsp;일");
  };
  const cd = String(b.contract_date || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const partyRows = (label: string, p: Party | undefined, side: string) => `
    <tr><th rowspan="2" style="width:10%">${label}</th><th style="width:9%">주 소</th><td colspan="4">${e(p?.addr || "")}</td><td rowspan="2" style="width:8%;text-align:center">(인)</td></tr>
    <tr><th>성 명</th><td style="width:22%">${e(p?.name || "")}</td><th style="width:12%">주민등록번호</th><td style="width:20%">${e(jm(side, 0, "jumin", p?.jumin))}</td><td>전화 ${e(p?.tel || "")}</td></tr>
    <tr><th rowspan="2">대 리 인</th><th>주 소</th><td colspan="4"></td><td rowspan="2"></td></tr>
    <tr><th>성 명</th><td>${e(p?.agent_name || "")}</td><th>주민등록번호</th><td>${e(jm(side, 0, "agent_jumin", p?.agent_jumin))}</td><td>전화 ${e(p?.agent_tel || "")}</td></tr>`;
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>상가건물 임대차 권리금계약서</title>
<style>
  @page{size:A4;margin:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{margin:0;padding:9mm 11mm;box-sizing:border-box;
    font-family:'AppleGothic','Malgun Gothic','NanumGothic','나눔고딕','돋움',sans-serif;color:#000;font-size:9pt;line-height:1.5}
  .pg{width:188mm;min-height:278mm;box-sizing:border-box;display:flex;flex-direction:column}
  .pg + .pg{page-break-before:always}
  h1{text-align:center;font-size:17pt;margin:0 0 2mm;font-weight:900;letter-spacing:2px}
  .tb{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:0.8mm}
  .tb th,.tb td{border:0.6px solid #000;padding:1.1mm 1.5mm;font-size:8.6pt;word-break:break-all;vertical-align:middle}
  .tb th{font-weight:700;text-align:center;background:#f4f4f4}
  .sh{font-weight:900;font-size:10pt;margin:2.2mm 0 0.6mm}
  .art{margin:1mm 0;font-size:8.8pt;text-align:justify}
  .art b{margin-right:1mm}
  .gray{color:#777;font-size:8pt}
  b{font-weight:900}
  .teukbox{border:0.6px solid #000;min-height:26mm;padding:1.5mm 2mm;font-size:8.8pt;line-height:1.6;white-space:pre-wrap}
  .grow{flex:1}
  .pn{text-align:center;font-size:8.6pt;margin-top:1mm}
  .lawbox{border:0.6px solid #000;padding:2mm 2.5mm;font-size:8.8pt;line-height:1.65;margin-top:2mm}
</style></head><body>

<div class="pg">
  <h1>상가건물 임대차 권리금계약서</h1>
  <table class="tb"><tbody>
    <tr><td style="text-align:center">임차인( <b>${e(s0?.name || "")}</b> )과 신규임차인이 되려는 자( <b>${e(n0?.name || "")}</b> )는 아래와 같이 권리금 계약을 체결한다.</td></tr>
  </tbody></table>
  <div style="font-size:8pt;margin:0.8mm 0 0">※ 임차인은 권리금을 지급받는 사람을, 신규임차인이 되려는 자(이하 「신규임차인」이라한다)는 권리금을 지급하는 사람을 의미한다.</div>

  <div class="sh">[임대차목적물인 상가건물의 표시]</div>
  <table class="tb"><tbody>
    <tr><th style="width:13%">소 재 지</th><td colspan="3">${e(addrFull)}</td><th style="width:11%">상 호</th><td style="width:20%">${e(b.shop_name || "")}</td></tr>
    <tr><th>임대면적</th><td>${b.rent_area ? e(b.rent_area) + " ㎡" : ""}</td><th style="width:11%">전용면적</th><td>${b.exclusive_area ? e(b.exclusive_area) + " ㎡" : ""}</td><th>업 종</th><td>${e(b.biz_type || "")}</td></tr>
    <tr><th>허가(등록)번호</th><td colspan="5">${e(b.license_no || "")}</td></tr>
  </tbody></table>

  <div class="sh">[임차인의 임대차계약 현황]</div>
  <table class="tb"><tbody>
    <tr><th rowspan="2" style="width:11%">임 대 차<br>관 계</th><th style="width:12%">임차보증금</th><td style="width:19%">${jwon(b.lease_cost) ? "금 " + jwon(b.lease_cost) + " 원" : ""}</td><th style="width:10%">월 차 임</th><td style="width:16%">${jwon(b.lease_fine) ? "금 " + jwon(b.lease_fine) + " 원" : ""}</td>
      <th style="width:9%">관 리 비</th><td style="word-break:keep-all">${jwon(b.lease_manage) ? "금 " + jwon(b.lease_manage) + " 원" : ""}</td></tr>
    <tr><th>부가가치세</th><td>별도( ${String(b.lease_vat) === "1" ? "✔" : "&nbsp;&nbsp;"} ), 포함( ${String(b.lease_vat) === "2" ? "✔" : "&nbsp;&nbsp;"} )</td>
      <th>계약기간</th><td colspan="3">${e(b.lease_period || "&nbsp;&nbsp;&nbsp;&nbsp;년 &nbsp;&nbsp;월 &nbsp;&nbsp;일부터 &nbsp;&nbsp;&nbsp;&nbsp;년 &nbsp;&nbsp;월 &nbsp;&nbsp;일까지( &nbsp;&nbsp;월)")}</td></tr>
  </tbody></table>

  <div class="sh">[계약내용]</div>
  <p class="art"><b>제1조(권리금의 지급)</b> 신규임차인은 임차인에게 다음과 같이 권리금을 지급한다.</p>
  <table class="tb"><tbody>
    <tr><th style="width:14%">총 권리금</th><td colspan="3">금 ${koW("kw_total")} 원정( ₩ ${jwon(b.kw_total)} )</td></tr>
    <tr><th>계 약 금</th><td colspan="3">금 ${koW("kw_down")} 원정( ₩ ${jwon(b.kw_down)} )은 계약시에 지급하고 영수함. 영수자( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; (인) )</td></tr>
    <tr><th>중 도 금</th><td style="width:48%;word-break:keep-all">금 ${koW("kw_mid")} 원정( ₩ ${jwon(b.kw_mid)} )</td><td colspan="2">${dt(b.kw_mid_date)}에 지급한다.</td></tr>
    <tr><th>잔&nbsp;&nbsp;&nbsp;금</th><td style="word-break:keep-all">금 ${koW("kw_bal")} 원정( ₩ ${jwon(b.kw_bal)} )</td><td colspan="2">${dt(b.kw_bal_date)}에 지급한다.</td></tr>
  </tbody></table>
  <div style="font-size:8pt;margin-top:0.6mm">※ 잔금지급일까지 임대인과 신규임차인 사이에 임대차계약이 체결되지 않는 경우 임대차계약 체결일을 잔금지급일로 본다.</div>

  <p class="art"><b>제2조(임차인의 의무)</b> ① 임차인은 신규임차인을 임대인에게 주선하여야 하며, 임대인과 신규임차인 간에 임대차계약이 체결될 수 있도록 협력하여야 한다.<br>
  ② 임차인은 신규임차인이 정상적인 영업을 개시할 수 있도록 전화가입권의 이전, 사업등록의 폐지 등에 협력하여야 한다.<br>
  ③ 임차인은 신규임차인이 잔금을 지급할 때까지 권리금의 대가로 아래 유형·무형의 재산적 가치를 이전한다.</p>
  <table class="tb"><tbody>
    <tr><th style="width:22%">유형의 재산적 가치</th><td>${e(b.kw_tangible || "영업시설·비품 등")}</td></tr>
    <tr><th>무형의 재산적 가치</th><td>${e(b.kw_intangible || "거래처, 신용, 영업상의 노하우, 상가건물의 위치에 따른 영업상의 이점 등")}</td></tr>
  </tbody></table>
  <div style="font-size:8pt;margin-top:0.6mm">※ 필요한 경우 이전 대상 목록을 별지로 첨부할 수 있다.</div>
  <p class="art">④ 임차인은 신규임차인에게 제3항의 재산적 가치를 이전할 때까지 선량한 관리자로서의 주의의무를 다하여 제3항의 재산적 가치를 유지·관리하여야 한다.<br>
  ⑤ 임차인은 본 계약체결 후 신규임차인이 잔금을 지급할 때까지 임차목적물상 권리관계, 보증금, 월차임 등 임대차계약 내용이 변경된 경우 또는 영업정지 및 취소, 임차목적물에 대한 철거명령 등 영업을 지속할 수 없는 사유가 발생한 경우 이를 즉시 신규임차인에게 고지하여야 한다.</p>
  <div class="grow"></div>
  <div class="pn">- 1 / 3 -</div>
</div>

<div class="pg">
  <p class="art"><b>제3조(임대차계약과의 관계)</b> 임대인의 계약거절, 무리한 임대조건 변경, 목적물의 훼손 등 임차인과 신규임차인의 책임 없는 사유로 임대차계약이 체결되지 못하는 경우 본 계약은 무효로 하며, 임차인은 지급받은 계약금 등을 신규임차인에게 즉시 반환하여야 한다.</p>
  <p class="art"><b>제4조(계약의 해제 및 손해배상)</b> ① 신규임차인이 중도금(중도금 약정이 없을 때는 잔금)을 지급하기 전까지 임차인은 계약금의 2배를 배상하고, 신규임차인은 계약금을 포기하고 본 계약을 해제할 수 있다.<br>
  ② 임차인 또는 신규임차인이 본 계약상의 내용을 이행하지 않는 경우 그 상대방은 계약상의 채무를 이행하지 않은 자에 대해서 서면으로 최고하고 계약을 해제할 수 있다.<br>
  ③ 본 계약체결 이후 임차인의 영업기간 중 발생한 사유로 인한 영업정지 및 취소, 임차목적물에 대한 철거명령 등으로 인하여 신규임차인이 영업을 개시하지 못하거나 영업을 지속할 수 없는 중대한 하자가 발생한 경우에는 신규임차인은 계약을 해제하거나 임차인에게 손해배상을 청구할 수 있다. 계약을 해제하는 경우에도 손해배상을 청구할 수 있다.<br>
  ④ 계약의 해제 및 손해배상에 관하여는 이 계약서에 정함이 없는 경우 「민법」의 규정에 따른다.</p>

  <div class="sh">[특약사항]</div>
  <div class="teukbox">${e(b.teukyak || "")}</div>

  <p class="art" style="margin-top:4mm">본 계약을 증명하기 위하여 계약 당사자가 이의 없음을 확인하고 각각 서명 또는 날인한다.</p>
  <div style="text-align:center;font-size:9.5pt;margin:2mm 0 3mm">
    ${cd ? `${cd[1]}년 &nbsp;&nbsp; ${cd[2]}월 &nbsp;&nbsp; ${cd[3]}일` : "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;년 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;월 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;일"}
  </div>
  <table class="tb"><tbody>
    ${partyRows("임 차 인", s0, "sell")}
    ${partyRows("신규임차인", n0, "buy")}
  </tbody></table>
  <div class="grow"></div>
  <div class="pn">- 2 / 3 -</div>
</div>

<div class="pg">
  <div class="sh">별지)</div>
  <div class="lawbox"><b>상법 제41조(영업양도인의 경업금지)</b><br>
  ① 영업을 양도한 경우에 다른 약정이 없으면 양도인은 10년간 동일한 특별시·광역시·시·군과 인접 특별시·광역시·시·군에서 동종영업을 하지 못한다.<br>
  ② 양도인이 동종영업을 하지 아니할 것을 약정한 때에는 동일한 특별시·광역시·시·군과 인접 특별시·광역시·시·군에 한하여 20년을 초과하지 아니한 범위내에서 그 효력이 있다.</div>
  <div class="lawbox"><b>상법 제42조(상호를 속용하는 양수인의 책임)</b><br>
  ① 영업양수인이 양도인의 상호를 계속 사용하는 경우에는 양도인의 영업으로 인한 제3자의 채권에 대하여 양수인도 변제할 책임이 있다.<br>
  ② 전항의 규정은 양수인이 영업양도를 받은 후 지체없이 양도인의 채무에 대한 책임이 없음을 등기한 때에는 적용하지 아니한다. 양도인과 양수인이 지체없이 제3자에 대하여 그 뜻을 통지한 경우에 그 통지를 받은 제3자에 대하여도 같다.</div>
  <div class="grow"></div>
  <div class="pn">- 3 / 3 -</div>
</div>
</body></html>`;
}

// ══════════════════════════════════════════════════════════════════
// 별지2) 계약갱신 거절통지서 — 주택임대차표준계약서(2023.10.6) 부속 서식 원본 복제.
// 당사자 매핑: sells[0]=임대인, buys[0]=임차인. (WSRC: 폼 rf_* 입력값)
// ══════════════════════════════════════════════════════════════════
function buildRefusalHtml(x: { b: Body; sells: Party[]; buys: Party[] }): string {
  const { b, sells, buys } = x;
  const e = (v: any) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const s0 = sells[0], b0 = buys[0];
  const ck = (v: string) => String(b.rf_reason) === v ? "■" : "□";
  const rq = String(b.rf_req_date || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const wd = String(b.rf_write_date || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const addrFull = [b.haddress, b.hdong ? `${b.hdong}동` : "", b.hho ? `${b.hho}호` : ""].filter(Boolean).join(" ");
  const period = b.edate ? `${jdate(b.handover_date || b.ecost_date)} ~ ${jdate(b.edate)}` : "";
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>계약갱신 거절통지서</title>
<style>
  @page{size:A4;margin:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{margin:0;padding:11mm 13mm;box-sizing:border-box;
    font-family:'AppleGothic','Malgun Gothic','NanumGothic','나눔고딕','돋움',sans-serif;color:#000;font-size:9.4pt;line-height:1.6}
  h1{text-align:center;font-size:17pt;margin:2mm 0 4mm;font-weight:900;letter-spacing:3px}
  .bj{font-size:9pt}
  .tb{width:100%;border-collapse:collapse;table-layout:fixed}
  .tb th,.tb td{border:0.7px solid #000;padding:1.6mm 2mm;font-size:9pt;vertical-align:middle;word-break:break-all}
  .tb th{font-weight:700;text-align:center;background:#f0f0f0}
  .box{border:0.7px solid #000;padding:2.5mm 3mm;margin-top:4mm}
  .rtitle{display:inline-block;border:0.7px solid #000;background:#f0f0f0;font-weight:900;padding:1mm 2.5mm;margin-bottom:1.5mm}
  .r{margin:0.9mm 0}
  .dots{border-bottom:0.5px dotted #666;min-height:6mm}
  .note{font-size:8.4pt;background:#f6f6f6;border:0.5px solid #999;padding:1.6mm 2mm;margin-top:2.5mm}
</style></head><body>
  <div class="bj">별지2)</div>
  <h1>계약갱신 거절통지서</h1>
  <table class="tb"><tbody>
    <tr><th rowspan="3" style="width:6%">임<br>대<br>인</th><th style="width:14%">성　　명</th><td style="width:29%">${e(s0?.name || "")}</td>
      <th rowspan="3" style="width:6%">임<br>차<br>인</th><th style="width:14%">성　　명</th><td>${e(b0?.name || "")}</td></tr>
    <tr><th>주　　소</th><td>${e(s0?.addr || "")}</td><th>주　　소</th><td>${e(b0?.addr || "")}</td></tr>
    <tr><th>연 락 처</th><td>${e(s0?.tel || "")}</td><th>연 락 처</th><td>${e(b0?.tel || "")}</td></tr>
    <tr><th colspan="2">임차목적물 주소</th><td colspan="4">${e(addrFull)}</td></tr>
    <tr><th colspan="2">임대차계약 기간</th><td colspan="4">${e(period)}</td></tr>
  </tbody></table>

  <div class="box" style="border:0.7px solid #000">
    &nbsp;임대인(<u>&nbsp;${e(s0?.name || "＿＿＿＿＿")}&nbsp;</u>)은 임차인(<u>&nbsp;${e(b0?.name || "＿＿＿＿＿")}&nbsp;</u>)로부터
    ${rq ? `<u>${rq[1]}</u>년 <u>${rq[2]}</u>월 <u>${rq[3]}</u>일` : "____년 ____월 ____일"}
    주택임대차계약의 갱신을 요구받았으나, 아래와 같은 법률상 사유로 위 임차인에게 갱신요구를 거절한다는 의사를 통지합니다.
  </div>

  <div style="margin-top:4mm">
    <span class="rtitle">계약갱신거절 사유</span> <span style="font-size:8.6pt">(주택임대차보호법 제6조의3 제1항 각 호)</span>
    <div style="border:0.7px solid #000;padding:2mm 2.5mm">
      <div class="r">1. 임차인이 2기의 차임액에 해당하는 금액에 이르도록 차임을 연체한 사실이 있는 경우 ${ck("1")}</div>
      <div class="r">2. 임차인이 거짓이나 그 밖의 부정한 방법으로 임차한 경우 ${ck("2")}</div>
      <div class="r">3. 서로 합의하여 임대인이 임차인에게 상당한 보상을 제공한 경우 ${ck("3")}<br>
        &nbsp;&nbsp;&nbsp;(상당한 보상의 내용 : ${e(b.rf_comp || "")}&nbsp;)</div>
      <div class="r">4. 임차인이 임대인의 동의 없이 목적 주택의 전부 또는 일부를 전대(轉貸)한 경우 ${ck("4")}</div>
      <div class="r">5. 임차인이 임차한 주택의 전부 또는 일부를 고의나 중대한 과실로 파손한 경우 ${ck("5")}</div>
      <div class="r">6. 임차한 주택의 전부 또는 일부가 멸실되어 임대차의 목적을 달성하지 못할 경우 ${ck("6")}</div>
      <div class="r">7. 주택의 전부 또는 대부분을 철거·재건축하기 위하여 점유를 회복할 필요가 있는 경우</div>
      <div class="r">&nbsp;7-1. 임대차계약 체결 당시 공사시기 및 소요기간 등을 포함한 철거 또는 재건축 계획을 임차인에게 구체적으로 고지하고 그 계획에 따르는 경우 ${ck("7-1")}</div>
      <div class="r">&nbsp;7-2. 건물이 노후·훼손 또는 일부 멸실되는 등 안전사고의 우려가 있는 경우 ${ck("7-2")}</div>
      <div class="r">&nbsp;7-3. 다른 법령에 따라 철거 또는 재건축이 이루어지는 경우 ${ck("7-3")}</div>
      <div class="r">8. 임대인 또는 임대인의 직계존비속이 목적 주택에 실제 거주하려는 경우 ${ck("8")}<br>
        &nbsp;&nbsp;&nbsp;(실거주자 성명: ${e(b.rf_resident || "")}&nbsp;&nbsp;, 임대인과의 관계 :
        ${String(b.rf_rel) === "1" ? "■" : "□"} 본인 &nbsp;${String(b.rf_rel) === "2" ? "■" : "□"} 직계존속 &nbsp;${String(b.rf_rel) === "3" ? "■" : "□"} 직계비속)</div>
      <div class="r">9. 그 밖에 임차인이 임차인으로서의 의무를 현저히 위반하거나 임대차를 계속하기 어려운 중대한 사유가 있는 경우 ${ck("9")}</div>
    </div>
  </div>

  <div style="margin-top:4mm;font-weight:900">* 위 계약갱신거절 사유를 보충설명하기 위한 구체적 사정</div>
  <div class="dots">${e(b.rf_detail || "")}</div>
  <div class="dots"></div>

  <div class="note">※ 선택하신 사유를 소명할 수 있는 문서 등 별도의 자료가 있는 경우, 해당 자료들을 본 통지서에 첨부하여 임차인에게 전달해 주시기 바랍니다.</div>

  <table class="tb" style="margin-top:5mm"><tbody>
    <tr><td style="width:50%;font-weight:900">작성일자 : ${wd ? `&nbsp;&nbsp;${wd[1]}년 &nbsp;&nbsp;${wd[2]}월 &nbsp;&nbsp;${wd[3]}일` : "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;년 &nbsp;&nbsp;&nbsp;&nbsp;월 &nbsp;&nbsp;&nbsp;&nbsp;일"}</td>
      <td><b>임대인 :</b> &nbsp;${e(s0?.name || "")}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(서명 또는 날인)</td></tr>
    <tr><td colspan="2">* 거절통지의 효력은 위 계약갱신 거절통지서를 작성 및 발송한 후, 임차인에게 통지가 도달한 때에 발생합니다.</td></tr>
  </tbody></table>
</body></html>`;
}
