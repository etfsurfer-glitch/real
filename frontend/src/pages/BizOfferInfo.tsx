import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, FileCheck2, Wand2 } from "lucide-react";
import { useAuth } from "../auth";
import { isMobileDevice } from "../lib/appmode";
import { acquisitionTax, localEducationTax, ruralSpecialTax, DEFAULT_INPUT } from "../lib/buycalc";
import { commission, dealAmountForCommission, propertyGbOf } from "../lib/contractcalc";
import { Loading } from "../components/Loading";

const API = import.meta.env.VITE_API_BASE;

// ───────────────────────────────────────────────────────────────────
// 중개대상물 확인·설명서 [Ⅰ] 주거용 건축물
// 인쇄 = 별지 제20호서식 <개정 2026.8.11> 법정 양식 그대로 복제(편집 금지)
// 입력폼 = 서식 항목 ①~⑮ 순서·문구 준수(레이아웃만 앱 스타일)
// ───────────────────────────────────────────────────────────────────
type Body = Record<string, any>;
type Party = { name: string; jumin: string; tel: string; addr: string };
type Broker = { company: string; owner: string; reg_no: string; addr: string; tel: string; belong?: string };

// 서식 원문 선택지(별지 제20호 2026.8.11)
export const R = {
  pyo_si: ["단독주택", "공동주택", "주거용 오피스텔"],
  offer_section: ["매매·교환", "임대"],
  wiban: ["위반", "적법"],
  trust: ["확인", "유효한 임대차계약 여부 등 주요내용 설명", "해당 없음"],
  joint: ["확인", "공동담보 목록 등 선순위권리관계 설명", "해당 없음"],
  renewal: ["서류 확인(첨부)", "서류 미확인", "해당 없음"],
  renewal_r02: ["확인(확인서류 첨부)", "미확인", "해당 없음"],   // 비주거 서식 원문
  boil_r02: ["중앙공급", "개별공급"],                             // 비주거 서식은 지역난방 없음
  decide: ["임대인 자료 제출", "열람 동의"],
  move: ["확인(확인서류 첨부)", "미확인(열람·교부 신청방법 설명)", "해당 없음"],
  prv_rent: ["장기일반민간임대주택", "공공지원민간임대주택", "그 밖의 유형", "미등록"],
  pojang: ["포장", "비포장"],
  access: ["용이함", "불편함"],
  dobo: ["도보", "차량"],
  carzone: ["없음", "전용주차시설", "공동주차시설", "그 밖의 주차시설"],
  safer: ["있음", "없음"],
  safer2: ["위탁관리", "자체관리", "그 밖의 유형"],
  noview: ["없음", "있음"],
  levy: ["임대인이 직접 부과", "관리규약에 따라 부과", "그 밖의 부과 방식"],
  water_p: ["없음", "있음"],
  water_su: ["정상", "부족함"],
  elect: ["정상", "교체 필요"],
  gas: ["도시가스", "그 밖의 방식"],
  firealarm: ["없음", "있음"],
  boil: ["중앙공급", "개별공급", "지역난방"],
  boil_fuel: ["도시가스", "기름", "프로판가스", "연탄", "그 밖의 종류"],
  state2: ["정상", "수선 필요"],
  eleb: ["있음", "없음"],
  eleb_state: ["양호", "불량"],
  paper: ["깨끗함", "보통임", "도배 필요"],
  bottom: ["깨끗함", "보통임", "수리 필요"],
  ilzo: ["풍부함", "보통임", "불충분"],
  soum: ["아주 작음", "보통임", "심한 편임"],
  guide: ["개업공인중개사", "소속공인중개사", "중개보조원", "해당 없음"],
  yesno: ["예", "아니오"],
} as const;

export const DOCS = ["등기권리증", "등기사항증명서", "신탁원부", "토지대장", "건축물대장",
  "지적도", "임야도", "토지이용계획확인서", "확정일자 부여현황", "전입세대확인서",
  "국세납세증명서", "지방세납세증명서", "그 밖의 자료"];

export const DOCS_R02 = ["등기권리증", "등기사항증명서", "토지대장", "건축물대장", "지적도",
  "임야도", "토지이용계획확인서", "그 밖의 자료"];
export const DOCS_R34 = ["등기권리증", "등기사항증명서", "토지대장", "건축물대장", "지적도",
  "임야도", "토지이용계획확인서"];
export const R02_GUBUN = ["업무용", "상업용", "공업용", "그 밖의 경우"];

export const MANAGE_ITEMS = ["전기료", "수도료", "가스사용료", "난방비", "인터넷 사용료", "TV 수신료", "그 밖의 비목"];

// 항목별 자동채움 출처 — 편집화면 전용 주석(법정 인쇄물에는 미출력)
const SRC: Record<string, string> = {
  address: "계약서", land_py: "계약서·건축물대장", jimok: "계약서", r_jimok: "계약서",
  build_py: "계약서", land_py2: "계약서 대지권비율로 계산(등기부 확인)",
  build_date: "건축물대장", build1: "건축물대장", build2: "계약서", build3: "건축물대장",
  build_eye: "연동 매물", build_eye_std: "연동 매물",
  seidesign: "건축물대장", seicapacity: "건축물대장", wiban: "연동 매물(대장 재확인)",
  yongdo_jiyok: "토지이음(토지이용계획)", yongdo_jigu: "토지이음", yongdo_guyok: "토지이음",
  city_build: "토지이음(계획도로)", biz_safe: "토지이음", infor: "토지이음(기타 규제)",
  land_build_per: "직접 입력(시·군 조례)", info_per: "직접 입력(시·군 조례)",
  small_sum: "주임법 시행령 표 — 현행 참고값", repayment: "주임법 시행령 표 — 현행 참고값",
  carzone: "건축물대장(주차 대수)", manage_total: "연동 매물(월관리비)",
  cost: "계약서", person_gongsi_jiga: "VWorld 개별공시지가",
  build_gongsi_price: "공동주택가격(면적 매칭)·개별주택가격",
  real_property_tax: "자동계산 — 1주택 기준", farm_tax: "자동계산 — 85㎡ 기준", education_tax: "자동계산(취득세×10%)",
  land_in: "직접 입력(등기사항증명서)", land_out: "직접 입력(등기사항증명서)",
  build_in: "직접 입력(등기사항증명서)", build_out: "직접 입력(등기사항증명서)",
  trust_reg_yn: "직접 확인(등기부·신탁원부)", joint_collateral_yn: "직접 확인(등기부)",
  eleb: "건축물대장(승강기 대수)",
  charge: "계약서", charge_sigi: "계약서", t_cost: "자동합계(보수+실비)", susuryo: "요율 자동(계약서)",
  wdate: "계약서(계약일)",
};
const srcHint = (k: string) =>
  SRC[k] ? <em style={{ fontWeight: 400, fontStyle: "normal", fontSize: 10, color: "var(--c-faint, #94a3b8)", marginLeft: 5 }}>· {SRC[k]}</em> : null;

// ── 안정 입력 컴포넌트(렌더 내부 정의 금지 — 포커스 유실 방지) ──
const lbl: React.CSSProperties = { display: "block", fontSize: 12, fontWeight: 700, color: "var(--c-muted)", marginBottom: 3 };
const inp: React.CSSProperties = { width: "100%", boxSizing: "border-box", padding: "8px 10px", border: "1px solid var(--c-border)", borderRadius: 8, fontSize: 13.5, background: "var(--c-surface)", color: "var(--c-text)" };

function TF({ b, set, k, label, ph = "", flex = 1, type = "text" }: {
  b: Body; set: (k: string, v: any) => void; k: string; label: string; ph?: string; flex?: number; type?: string;
}) {
  return (
    <label style={{ flex }}><span style={lbl}>{label}{srcHint(k)}</span>
      <input type={type} value={b[k] ?? ""} placeholder={ph}
        onChange={e => set(k, e.target.value)} style={inp} /></label>
  );
}

function TA({ b, set, k, label, rows = 2, ph = "" }: {
  b: Body; set: (k: string, v: any) => void; k: string; label: string; rows?: number; ph?: string;
}) {
  return (
    <label style={{ display: "block", marginTop: 8 }}><span style={lbl}>{label}{srcHint(k)}</span>
      <textarea value={b[k] ?? ""} rows={rows} placeholder={ph}
        onChange={e => set(k, e.target.value)} style={{ ...inp, resize: "vertical" }} /></label>
  );
}

function RF({ b, set, k, label, opts, flex = 1 }: {
  b: Body; set: (k: string, v: any) => void; k: string; label: string; opts: readonly string[]; flex?: number;
}) {
  return (
    <div style={{ flex }}>
      <span style={lbl}>{label}{srcHint(k)}</span>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {opts.map((o, i) => {
          const code = String(i + 1);
          const on = String(b[k] ?? "") === code;
          return (
            <button key={o} type="button" onClick={() => set(k, on ? "" : code)}
              style={{
                padding: "7px 10px", borderRadius: 8, fontSize: 12.5, cursor: "pointer",
                border: `1.5px solid ${on ? "var(--c-primary)" : "var(--c-border)"}`,
                background: on ? "var(--c-primary)" : "var(--c-surface)",
                color: on ? "#fff" : "var(--c-text)", fontWeight: on ? 800 : 500,
              }}>{o}</button>
          );
        })}
      </div>
    </div>
  );
}

function CKS({ b, set, k, label, opts }: {
  b: Body; set: (k: string, v: any) => void; k: string; label: string; opts: readonly string[];
}) {
  const cur: string[] = b[k] || [];
  return (
    <div style={{ marginTop: 8 }}>
      <span style={lbl}>{label}</span>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {opts.map(o => {
          const on = cur.includes(o);
          return (
            <button key={o} type="button"
              onClick={() => set(k, on ? cur.filter(x => x !== o) : [...cur, o])}
              style={{
                padding: "7px 10px", borderRadius: 8, fontSize: 12.5, cursor: "pointer",
                border: `1.5px solid ${on ? "var(--c-primary)" : "var(--c-border)"}`,
                background: on ? "var(--c-primary)" : "var(--c-surface)",
                color: on ? "#fff" : "var(--c-text)", fontWeight: on ? 800 : 500,
              }}>{o}</button>
          );
        })}
      </div>
    </div>
  );
}

type BjRow = { ho: string; deposit: string; rent: string; period: string; fix: string; note: string };
const emptyBj = (): BjRow => ({ ho: "", deposit: "", rent: "", period: "", fix: "", note: "" });
function ByuljiRows({ rows, onChange }: { rows: BjRow[]; onChange: (r: BjRow[]) => void }) {
  const upd = (i: number, k: keyof BjRow, v: string) => {
    const nx = rows.map((r, j) => j === i ? { ...r, [k]: v } : r); onChange(nx);
  };
  const cells: [keyof BjRow, string, number][] = [["ho", "호수", 0.7], ["deposit", "보증금(만원)", 1],
    ["rent", "차임(만원)", 0.9], ["period", "임대차기간", 1.4], ["fix", "확정일자", 1], ["note", "비고", 1]];
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: "flex", gap: 4, fontSize: 11, fontWeight: 700, color: "var(--c-muted)" }}>
        {cells.map(([, t, f]) => <div key={t} style={{ flex: f }}>{t}</div>)}<div style={{ width: 26 }} /></div>
      {rows.map((r, i) => (
        <div key={i} style={{ display: "flex", gap: 4, marginTop: 4 }}>
          {cells.map(([k, , f]) => (
            <input key={k} value={r[k]} onChange={e => upd(i, k, e.target.value)}
              style={{ ...inp, flex: f, padding: "6px 8px", fontSize: 12.5 }} />
          ))}
          <button type="button" onClick={() => onChange(rows.filter((_, j) => j !== i))}
            style={{ width: 26, border: 0, background: "none", cursor: "pointer", color: "var(--c-muted)" }}>✕</button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...rows, emptyBj()])}
        style={{ marginTop: 6, padding: "6px 14px", borderRadius: 8, border: "1.5px dashed var(--c-border)", background: "none", cursor: "pointer", fontSize: 12.5, color: "var(--c-primary)", fontWeight: 700 }}>
        + 호 추가</button>
    </div>
  );
}

function Grp({ title, children }: { title: string; children: React.ReactNode }) {
  // 항목 그룹 박스 — 하위 필드(위치·내용 등)가 어느 항목 세트인지 시각적으로 묶는다(2026-09-04)
  return (
    <div style={{ border: "1px solid var(--c-border)", borderRadius: 10,
      padding: "10px 12px 4px", marginBottom: 10, background: "var(--c-row-stripe, #f8fafc)" }}>
      <div style={{ fontSize: 12.5, fontWeight: 800, color: "var(--c-primary)", marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}

function Sec({ no, title, children }: { no: string; title: string; children: React.ReactNode }) {
  return (
    <section style={{ background: "var(--c-card)", border: "1px solid var(--c-border)", borderRadius: 14, padding: 16, marginTop: 14 }}>
      <h3 style={{ margin: "0 0 10px", fontSize: 15 }}>
        <span style={{ color: "var(--c-primary)", marginRight: 6 }}>{no}</span>{title}</h3>
      {children}
    </section>
  );
}

const Row = ({ children }: { children: React.ReactNode }) => (
  <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap", marginTop: 8 }}>{children}</div>
);

// ───────────────────────────────────────────────────────────────────
export default function BizOfferInfo() {
  const { wid } = useParams<{ wid: string }>();
  const nav = useNavigate();
  const { token } = useAuth();
  const hdr = { Authorization: `Bearer ${token}` };
  const [b, setB] = useState<Body>({});
  const [wc, setWc] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errs, setErrs] = useState<string[]>([]);
  const [toast, setToast] = useState("");
  const [pdfBusy, setPdfBusy] = useState(false);
  const [form, setForm] = useState<"R01" | "R02" | "R03" | "R04">("R01");
  const [showR3Land, setShowR3Land] = useState(false);   // R03 ③ — 임대차 생략 가능 접힘
  const set = useCallback((k: string, v: any) => setB(p => ({ ...p, [k]: v })), []);
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 4000); };

  useEffect(() => {
    if (!wid || !token) return;
    (async () => {
      try {
        const [rw, ro] = await Promise.all([
          fetch(`${API}/biz/wcontracts/${wid}`, { headers: hdr }),
          fetch(`${API}/biz/wcontracts/${wid}/offerinfo`, { headers: hdr }),
        ]);
        if (!rw.ok) { setErrs(["계약서를 찾을 수 없습니다 — 먼저 계약서를 저장해 주세요"]); setLoading(false); return; }
        const w = await rw.json();
        setWc(w);
        const o = ro.ok ? await ro.json() : { exists: false };
        if (o.exists) { setB(o.body || {}); setForm((["R01","R02","R03","R04"] as const).includes(o.form) ? o.form : "R01"); }
        else {
          // 서식 추천: 비주거 세분류 → R02, 토지 → R03
          if (/토지/.test(w.sub_category || "")) setForm("R03");
          else if (/상가|사무실|건물|공장|창고|지식산업|일반/.test(w.sub_category || "")) setForm("R02");
          const wb = w.body || {};
          setB({
            offer_section: w.mtype1 === "매매" ? "1" : "2",
            address: [wb.haddress, wb.hdong ? `${wb.hdong}동` : "", wb.hho ? `${wb.hho}호` : ""].filter(Boolean).join(" "),
            land_py: wb.land_py || "", jimok: wb.jimok || "", r_jimok: wb.jimok || "",
            build_py: wb.build_py || "", build3: wb.build1 || "", build2: wb.build2 || "",
            build1: wb.build2 || "",
            cost: wb.cost || "", charge: wb.charge || "", charge_sigi: wb.charge_sigi || "",
            t_cost: wb.charge || "",
            // 대지지분 = 계약서 대지권비율("X분의 Y") 분자 — 참고값
            land_py2: (String(wb.rate || "").match(/분의\s*([0-9.]+)/) || [])[1] || "",
            __offer_code: wb.offer_code || "",
            wdate: wb.contract_date || "",
            sell_parties: wb.sell_parties || [], buy_parties: wb.buy_parties || [],
            brokers: wb.brokers || [],
          });
        }
      } catch { setErrs(["불러오기 실패 — 네트워크를 확인하세요"]); }
      setLoading(false);
    })();
  }, [wid, token]);   // eslint-disable-line

  // ⑤입지조건 자동채움 — 주소 좌표 주변 버스·지하철·학교 최근접(도보 분). 빈 필드만 채움.
  const prefillLocation = async () => {
    const addr = (b.address || "").trim();
    if (addr.length < 5) return;
    try {
      const r = await fetch(`${API}/biz/wcontracts/tools/location?address=${encodeURIComponent(addr)}`, { headers: hdr });
      if (!r.ok) return;
      const d = await r.json();
      setB(p => ({
        ...p,
        bus: p.bus || d.bus?.name || "", bus_t: p.bus_t || (d.bus ? String(d.bus.walk_min) : ""),
        inwater1: p.inwater1 || (d.bus ? "1" : ""),
        subway: p.subway || d.subway?.name || "", subway_t: p.subway_t || (d.subway ? String(d.subway.walk_min) : ""),
        inwater2: p.inwater2 || (d.subway ? "1" : ""),
        edu1: p.edu1 || d.edu1?.name || "", edu1_t: p.edu1_t || (d.edu1 ? String(d.edu1.walk_min) : ""),
        edu1_dobo: p.edu1_dobo || (d.edu1 ? "1" : ""),
        edu2: p.edu2 || d.edu2?.name || "", edu2_t: p.edu2_t || (d.edu2 ? String(d.edu2.walk_min) : ""),
        edu2_dobo: p.edu2_dobo || (d.edu2 ? "1" : ""),
        edu3: p.edu3 || d.edu3?.name || "", edu3_t: p.edu3_t || (d.edu3 ? String(d.edu3.walk_min) : ""),
        edu3_dobo: p.edu3_dobo || (d.edu3 ? "1" : ""),
      }));
      return true;
    } catch { return false; }
  };

  const prefill = async () => {
    const addr = (b.address || "").trim();
    if (addr.length < 5) { setErrs(["소재지를 먼저 입력하세요"]); return; }
    flash("건축물대장·공시가격·입지 조회 중…");
    prefillLocation();   // 입지(버스·지하철·학교)는 병렬로 — 실패해도 본 프리필과 무관
    try {
      const q = new URLSearchParams({ address: addr, area: String(Number(b.build_py) || 0),
        offer_code: b.__offer_code || "" });
      const r = await fetch(`${API}/biz/wcontracts/tools/offerinfo-prefill?${q}`, { headers: hdr });
      const d = await r.json();
      if (!r.ok || !d.ok) { setErrs([d.detail || "프리필 조회 실패"]); setToast(""); return; }
      setB(p => ({
        ...p,
        build_date: d.build_date ? `${d.build_date.slice(0, 4)}-${d.build_date.slice(4, 6)}-${d.build_date.slice(6, 8)}` : p.build_date,
        build1: d.build1_ledger || p.build1,
        build3: d.build3 || p.build3,
        land_py: p.land_py || (d.plat_area ?? ""),
        eleb: d.elvt != null ? (d.elvt > 0 ? "1" : "2") : p.eleb,
        carzone: p.carzone || (d.parking != null ? (d.parking > 0 ? "3" : "1") : ""),
        person_gongsi_jiga: d.person_gongsi_jiga ?? p.person_gongsi_jiga,
        build_gongsi_price: d.build_gongsi_price ?? p.build_gongsi_price,
        // ① 내진설계(대장) — 값 형식: Y/1=적용
        seidesign: p.seidesign || (d.seismic_apply ? (["Y", "1", "적용"].includes(String(d.seismic_apply)) ? "1" : "2") : ""),
        seicapacity: p.seicapacity || d.seismic_ablty || "",
        // ① 방향·위반건축물, ⑥ 관리비 — 연동 매물 상세
        build_eye: p.build_eye || d.direction || "",
        build_eye_std: p.build_eye_std || d.direction_base || "",
        wiban: p.wiban || (d.violation === "Y" ? "1" : d.violation === "N" ? "2" : ""),
        manage_total: p.manage_total || d.manage_total || "",
        // ③ 토지이용계획(토지이음)
        yongdo_jiyok: p.yongdo_jiyok || d.yongdo_jiyok || "",
        yongdo_jigu: p.yongdo_jigu || d.yongdo_jigu || "",
        yongdo_guyok: p.yongdo_guyok || d.yongdo_guyok || "",
        // 건폐·용적 상한 제안(서울=조례값, 그 외=시행령 상한) — 빈 칸만, 출처는 플래시로 안내
        land_build_per: p.land_build_per || (d.zone_limit?.build_per != null ? String(d.zone_limit.build_per) : ""),
        info_per: p.info_per || (d.zone_limit?.floor_per != null ? String(d.zone_limit.floor_per) : ""),
        biz_safe: p.biz_safe || (d.landuse_danwi ? "지구단위계획구역" : ""),
        city_build: p.city_build || d.landuse_roads || "",
        toji_heoga: p.toji_heoga || !!d.landuse_heoga,
        infor: p.infor || d.landuse_etc || "",
        // ④ 최우선변제금(현행 표 참고값)
        small_sum: p.small_sum || (d.small_sum ?? ""),
        repayment: p.repayment || (d.repayment ?? ""),
      }));
      // ⑨ 취득세율(매매·1주택 가정) + ⑮ 산출내역 자동
      setB(p => {
        const isSale = String(p.offer_section) === "1";
        const cost = Number(p.cost) || 0;
        const nx: Body = { ...p };
        if (isSale && cost > 0 && !p.real_property_tax) {
          const ci = { ...DEFAULT_INPUT, salePrice: cost, houseCount: 0,
            isOver85m2: (Number(p.build_py) || 0) > 85, isFirstTime: false };
          const acq = acquisitionTax(ci);
          nx.real_property_tax = (acq / cost * 100).toFixed(2);
          nx.education_tax = (localEducationTax(acq) / cost * 100).toFixed(2);
          nx.farm_tax = (ruralSpecialTax(ci) / cost * 100).toFixed(2);
        }
        if (cost > 0 && !p.susuryo) {
          const deal = dealAmountForCommission(isSale ? "매매" : "월세", cost, 0);
          const cm = commission(propertyGbOf("아파트", false), isSale ? "SALE" : "RENT", deal);
          nx.susuryo = `거래예정금액 × ${(cm.rate * 100).toFixed(cm.rate * 100 % 1 ? 1 : 0)}%`;
        }
        if (!p.t_cost && (Number(p.charge) || Number(p.expense))) {
          nx.t_cost = (Number(p.charge) || 0) + (Number(p.expense) || 0);
        }
        return nx;
      });
      flash(`대장·공시가·토지이용·최우선변제 반영${d.repayment_zone ? ` (${d.repayment_zone} 기준)` : ""}${d.gongsi_whole ? " — 주택공시가는 건물 전체값, 확인 필요" : ""}${d.zone_limit ? ` — 건폐·용적 상한은 ${d.zone_limit.src}` : ""} — 취득세율은 1주택 기준, 최우선변제금은 현행 표 참고값(선순위 담보 설정일 기준 확인)`);
    } catch { setErrs(["프리필 조회 실패"]); setToast(""); }
  };

  const save = async () => {
    setSaving(true); setErrs([]);
    try {
      const r = await fetch(`${API}/biz/wcontracts/${wid}/offerinfo`, {
        method: "POST", headers: { ...hdr, "Content-Type": "application/json" },
        body: JSON.stringify({ form, body: b }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { setErrs([d.detail || `저장 실패 (${r.status})`]); return; }
      flash("확인설명서 저장 완료");
    } catch { setErrs(["저장 실패 — 네트워크를 확인하세요"]); }
    finally { setSaving(false); }
  };

  const printPdf = async (download: boolean) => {
    if (!download && isMobileDevice()) { setErrs(["인쇄는 PC(koczip.com)에서 이용할 수 있어요 — 휴대폰에서는 'PDF 다운로드'를 눌러 파일로 받아주세요"]); return; }
    setPdfBusy(true); setErrs([]);
    const w = download ? null : window.open("", "_blank", "width=920,height=1200");
    if (!download && !w) { setErrs(["팝업이 차단되었습니다 — 허용 후 다시 시도하세요"]); setPdfBusy(false); return; }
    if (w) w.document.write("<p style='font-family:sans-serif;padding:20px'>확인설명서 PDF 생성 중…</p>");
    try {
      const html = buildOfferHtml(b, form);
      const r = await fetch(`${API}/biz/wcontracts/render-pdf`, {
        method: "POST", headers: { ...hdr, "Content-Type": "application/json" },
        body: JSON.stringify({ html }),
      });
      if (!r.ok) { setErrs([`PDF 생성 실패 (${r.status})`]); w?.close(); return; }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      if (w) {
        w.location.href = url;
        setTimeout(() => { try { w.focus(); w.print(); } catch { /* 뷰어 버튼 */ } }, 1500);
      } else {
        const a = document.createElement("a");
        a.href = url; a.download = `확인설명서_${(b.address || "").slice(0, 20)}.pdf`; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
      }
    } catch { setErrs(["PDF 생성 실패 — 네트워크를 확인하세요"]); w?.close(); }
    finally { setPdfBusy(false); }
  };

  if (loading) return <Loading />;
  const fp = { b, set };
  const isRent = String(b.offer_section) === "2";
  const isR02 = form === "R02";
  const isR34 = form === "R03" || form === "R04";

  // ⑨/⑮ 중개보수 산정 안내 — 계약서 금액 대입 산식(화면 참고용, 인쇄물 미포함. 2026-09-04 요청)
  const feeGuide = (() => {
    if (!wc) return null;
    const wb = wc.body || {};
    const isSale = wc.mtype1 === "매매";
    const cost = Number(wb.cost) || 0;
    const fine = Number(wb.fine_cost) || 0;
    const amt = dealAmountForCommission(wc.mtype1, cost, fine);
    if (!amt) return null;
    const gb = propertyGbOf(wc.sub_category || "", false);
    const info = commission(gb, isSale ? "SALE" : "RENT", amt, wb.contract_date || "");
    if (!info.rate) return null;
    const f = (n: number) => n.toLocaleString();
    const amtFormula = isSale
      ? `매매금액 ${f(cost)}원`
      : wc.mtype1 === "연세"
        ? `연세 환산 거래금액`
        : fine > 0
          ? (amt === cost + fine * 70
            ? `보증금 ${f(cost)} + 월차임 ${f(fine)} × 70 (환산액 5천만원 미만 특례)`
            : `보증금 ${f(cost)} + 월차임 ${f(fine)} × 100`)
          : `보증금 ${f(cost)}원`;
    return (
      <div style={{ background: "var(--c-primary-tint, #eef4fd)", border: "1px solid var(--c-border)",
        borderRadius: 10, padding: "10px 14px", fontSize: 12.5, lineHeight: 1.7, marginBottom: 10 }}>
        <b>중개보수 산정 기준</b> — 적용 상한요율 <b>{(info.rate * 100).toFixed(2)}%</b>
        {info.limit ? ` (한도 ${f(info.limit)}원)` : ""}{info.negotiable ? " · 협의구간(상한 이내 협의)" : ""}
        <br />거래금액: {amtFormula} = <b>{f(amt)}원</b>
        <br />상한 보수: {f(amt)}원 × {(info.rate * 100).toFixed(2)}% = <b>{f(info.fee)}원</b>
        {/오피스텔/.test(wc.sub_category || "") &&
          <><br /><span style={{ color: "var(--c-muted)" }}>※ 주거용 오피스텔 특례(전용 85㎡ 이하·부엌·욕실) 해당 시 매매 0.5% / 임대 0.4% 적용</span></>}
        <br /><span style={{ color: "var(--c-muted)" }}>※ 화면 참고용 안내입니다 — 인쇄물에는 표시되지 않습니다.</span>
      </div>
    );
  })();

  // 저장·자동채움·PDF·인쇄 — 상단·하단 양쪽에 배치(2026-09-04 요청)
  const actionBar = (
    <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 14, flexWrap: "wrap" }}>
      <button onClick={save} disabled={saving}
        style={{ background: "var(--c-primary)", color: "#fff", border: 0, borderRadius: 10, padding: "12px 26px", fontSize: 15, fontWeight: 800, cursor: "pointer" }}>
        {saving ? "저장 중…" : "저장"}</button>
      <button onClick={prefill}
        style={{ display: "flex", gap: 6, alignItems: "center", background: "var(--c-surface)", border: "1.5px solid var(--c-primary)", color: "var(--c-primary)", borderRadius: 10, padding: "11px 18px", fontSize: 13.5, fontWeight: 800, cursor: "pointer" }}>
        <Wand2 size={15} /> 대장·공시가 자동채움</button>
      <button onClick={() => printPdf(true)} disabled={pdfBusy}
        style={{ background: "#1d4ed8", color: "#fff", border: 0, borderRadius: 10, padding: "11px 18px", fontSize: 13.5, fontWeight: 800, cursor: "pointer" }}>
        {pdfBusy ? "PDF 생성 중…" : "PDF 다운로드"}</button>
      <button onClick={() => printPdf(false)} disabled={pdfBusy}
        style={{ background: "var(--c-surface)", border: "1px solid var(--c-border)", borderRadius: 10, padding: "11px 18px", fontSize: 13.5, fontWeight: 800, cursor: "pointer", color: "var(--c-text)" }}>
        인쇄</button>
    </div>
  );

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "16px 14px 100px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <button onClick={() => nav(-1)} style={{ background: "none", border: 0, cursor: "pointer", padding: 4 }}>
          <ArrowLeft size={20} /></button>
        <h2 style={{ margin: 0, fontSize: 18, display: "flex", alignItems: "center", gap: 8 }}>
          <FileCheck2 size={20} /> 중개대상물 확인·설명서 {form === "R02" ? "[Ⅱ] 비주거용" : form === "R03" ? "[Ⅲ] 토지" : form === "R04" ? "[Ⅳ] 입목·광업재단·공장재단" : "[Ⅰ] 주거용"}</h2>
        <span style={{ display: "flex", gap: 4 }}>
          {(["R01", "R02", "R03", "R04"] as const).map(f => (
            <button key={f} type="button" onClick={() => setForm(f)}
              style={{ padding: "5px 12px", borderRadius: 8, fontSize: 12, cursor: "pointer", fontWeight: 800,
                border: `1.5px solid ${form === f ? "var(--c-primary)" : "var(--c-border)"}`,
                background: form === f ? "var(--c-primary)" : "var(--c-surface)",
                color: form === f ? "#fff" : "var(--c-text)" }}>
              {f === "R01" ? "주거용" : f === "R02" ? "비주거용" : f === "R03" ? "토지" : "재단·입목"}</button>
          ))}
        </span>
        {wc && <span style={{ fontSize: 12.5, color: "var(--c-muted)" }}>계약서 #{wid} · {wc.title || ""}</span>}
      </div>
      <div style={{ fontSize: 12, color: "var(--c-muted)", marginTop: 4 }}>
        인쇄물은 {form === "R02" ? "별지 제20호의2서식(개정 2021.12.31)" : form === "R03" ? "별지 제20호의3서식(개정 2020.2.21)" : form === "R04" ? "별지 제20호의4서식(개정 2017.6.8)" : "별지 제20호서식(개정 2026.8.11)"} 법정 양식 그대로 출력됩니다.
      </div>
      {actionBar}

      {errs.length > 0 && (
        <div style={{ background: "#fff1f0", border: "1px solid #ffa39e", borderRadius: 10, padding: "10px 14px", marginTop: 12, color: "#a8071a", fontSize: 13.5 }}>
          {errs.map((e, i) => <div key={i}>• {e}</div>)}
        </div>
      )}
      {toast && <div style={{ position: "fixed", bottom: 84, left: "50%", transform: "translateX(-50%)", background: "#111", color: "#fff", padding: "10px 18px", borderRadius: 22, fontSize: 13.5, zIndex: 99 }}>{toast}</div>}

      {isR34 && (<>
      <Sec no="표지" title="거래 형태 · 확인·설명 자료">
        <Row>
          <RF {...fp} k="offer_section" label="거래 형태" opts={R.offer_section} />
          {form === "R04" && <RF {...fp} k="r4_kind" label="대상물 종별" opts={["입목", "광업재단", "공장재단"]} flex={1.6} />}
        </Row>
        <CKS {...fp} k="docs" label="확인·설명 근거자료 등" opts={DOCS_R34} />
        <TA {...fp} k="material_request" label="대상물건의 상태에 관한 자료요구 사항" />
      </Sec>

      <Sec no="①" title="대상물건의 표시">
        <Row>
          <TF {...fp} k="address" label={form === "R04" ? "소재지(등기·등록지)" : "소재지"} flex={2.2} />
          {form === "R03" && <TF {...fp} k="land_py" label="면적(㎡)" flex={0.6} />}
        </Row>
        {form === "R03" && <Row>
          <TF {...fp} k="jimok" label="지목(공부상)" />
          <TF {...fp} k="r_jimok" label="실제이용 상태" />
        </Row>}
      </Sec>

      <Sec no="②" title="권리관계(등기부 기재사항)">
        {form === "R04" ? (<>
          <Row>
            <TF {...fp} k="r4_own_name" label="소유권에 관한 사항 — 성명" />
            <TF {...fp} k="r4_own_addr" label="소유권에 관한 사항 — 주소" flex={2} />
          </Row>
          <TA {...fp} k="land_out" label="소유권 외의 권리사항" />
        </>) : (<>
          <TA {...fp} k="land_in" label="소유권에 관한 사항(토지)" />
          <TA {...fp} k="land_out" label="소유권 외의 권리사항(토지)" />
        </>)}
      </Sec>

      {form === "R03" && (<>
      {isRent && !showR3Land ? (
        <div style={{ background: "var(--c-row-stripe, #f8fafc)", border: "1px solid var(--c-border)",
          borderRadius: 12, padding: "12px 16px", margin: "10px 0", fontSize: 13, display: "flex",
          alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
          <span><b>③ 토지이용계획·공법상 제한</b> — 임대차는 <b>생략 가능</b>합니다(작성방법). 기재하려면 열어주세요.</span>
          <button type="button" onClick={() => setShowR3Land(true)}
            style={{ background: "var(--c-surface)", border: "1.5px solid var(--c-primary)", color: "var(--c-primary)",
              borderRadius: 9, padding: "7px 14px", fontSize: 12.5, fontWeight: 800, cursor: "pointer" }}>입력하기</button>
        </div>
      ) : (
      <Sec no="③" title={`토지이용계획, 공법상 이용제한 및 거래규제에 관한 사항(토지)${isRent ? " — 임대차 생략 가능" : ""}`}>
        <Row>
          <TF {...fp} k="yongdo_jiyok" label="용도지역" />
          <TF {...fp} k="yongdo_jigu" label="용도지구" />
          <TF {...fp} k="yongdo_guyok" label="용도구역" />
        </Row>
        <Row>
          <TF {...fp} k="land_build_per" label="건폐율 상한(%)" flex={0.7} />
          <TF {...fp} k="info_per" label="용적률 상한(%)" flex={0.7} />
          <label style={{ flex: 1, display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
            <input type="checkbox" checked={!!b.toji_heoga} onChange={e => set("toji_heoga", e.target.checked)} />토지거래허가구역</label>
        </Row>
        <Row>
          {(["toji_tugi", "jutak_tugi", "tugi_kwayol"] as const).map((k, i) => (
            <label key={k} style={{ flex: 1, display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={!!b[k]} onChange={e => set(k, e.target.checked)} />
              {["토지투기지역", "주택투기지역", "투기과열지구"][i]}</label>
          ))}
        </Row>
        <TA {...fp} k="city_build" label="도시·군계획 시설" />
        <TA {...fp} k="biz_safe" label="지구단위계획구역, 그 밖의 도시·군관리계획" />
        <TA {...fp} k="infor" label="그 밖의 이용제한 및 거래규제사항" />
      </Sec>
      )}

      <Sec no="④⑤" title="입지조건 · 비선호시설">
        <Row>
          <TF {...fp} k="doro" label="도로와의 관계" ph="예: 8m × 6m" />
          <RF {...fp} k="doro_pojang" label="포장" opts={R.pojang} />
          <RF {...fp} k="doro3" label="접근성" opts={R.access} />
        </Row>
        <Row>
          <TF {...fp} k="bus" label="버스 정류장" flex={1.3} /><TF {...fp} k="bus_t" label="약(분)" flex={0.5} />
          <RF {...fp} k="inwater1" label="" opts={R.dobo} flex={0.8} />
          <TF {...fp} k="subway" label="지하철역" flex={1.3} /><TF {...fp} k="subway_t" label="약(분)" flex={0.5} />
          <RF {...fp} k="inwater2" label="" opts={R.dobo} flex={0.8} />
        </Row>
        <Row>
          <RF {...fp} k="noview_s" label="비선호시설(1km이내)" opts={R.noview} />
          <TF {...fp} k="noview" label="있음 — 종류 및 위치" flex={1.6} />
        </Row>
      </Sec>
      </>)}

      {form === "R04" && (
      <Sec no="③④" title="재단목록·생육상태 · 그 밖의 참고사항">
        <TA {...fp} k="r4_list" label="재단목록 또는 입목의 생육상태" />
        <TA {...fp} k="r4_etc" label="그 밖의 참고사항" />
      </Sec>
      )}

      <Sec no={form === "R03" ? "⑥⑦" : "⑤⑥"} title="거래예정금액 · 취득 조세">
        <Row>
          <TF {...fp} k="cost" label="거래예정금액(원)" />
          <TF {...fp} k="person_gongsi_jiga" label={isRent ? "개별공시지가(㎡당) — 임대차 생략 가능" : "개별공시지가(㎡당) *"} ph="금액 또는 '해당없음'" />
          <TF {...fp} k="build_gongsi_price" label={isRent ? "건물(주택)공시가격 — 임대차 생략 가능" : "건물(주택)공시가격 *"} ph="금액 또는 '해당없음'" />
        </Row>
        {!isRent ? (
        <Row>
          <TF {...fp} k="real_property_tax" label="취득세(%)" flex={0.7} />
          <TF {...fp} k="farm_tax" label="농어촌특별세(%)" flex={0.7} />
          <TF {...fp} k="education_tax" label="지방교육세(%)" flex={0.7} />
        </Row>
        ) : (
        <div style={{ fontSize: 12.5, color: "var(--c-muted)", marginTop: 4 }}>
          취득 시 부담할 조세는 <b>임대차에서는 기재하지 않습니다</b>(작성방법) — 인쇄물에는 빈 칸으로 나갑니다.
        </div>
        )}
      </Sec>

      <Sec no={form === "R03" ? "⑧" : "⑦"} title="실제 권리관계 또는 공시되지 않은 물건의 권리 사항">
        <TA {...fp} k="etc1" label="매도(임대)의뢰인이 고지한 사항" ph={form === "R03" ? "임대차, 지상에 점유권 행사여부, 구축물, 적치물, 진입로, 경작물, 계약 전 소유권 변동여부 등" : "임대차, 법정지상권, 유치권 등"} />
      </Sec>

      <Sec no={form === "R03" ? "⑨" : "⑧"} title="중개보수 및 실비의 금액과 산출내역">
        {feeGuide}
        <Row>
          <TF {...fp} k="charge" label="중개보수(원)" />
          <TF {...fp} k="expense" label="실비(원)" />
          <TF {...fp} k="t_cost" label="계(원)" />
          <TF {...fp} k="charge_sigi" label="지급시기" ph="예: 잔금일" />
        </Row>
        <TA {...fp} k="susuryo" label="산출내역 — 중개보수" ph="예: 거래예정금액 × 0.9% 이내 협의" />
        <TA {...fp} k="silbi_comment" label="산출내역 — 실비" />
        <Row>
          <TF {...fp} k="wdate" label="작성일(교부일)" type="date" flex={0.8} />
          <div style={{ flex: 2.4, fontSize: 12, color: "var(--c-muted)" }}>
            서명란(매도·매수인, 개업공인중개사)은 계약서의 당사자·중개사 정보로 채워집니다.
          </div>
        </Row>
      </Sec>
      </>)}

      {!isR34 && (<>
      <Sec no="표지" title={isR02 ? "용도 구분 · 거래 형태 · 확인·설명 자료" : "주택 유형 · 거래 형태 · 확인·설명 자료"}>
        <Row>
          {isR02
            ? <RF {...fp} k="gubun2" label="용도 구분" opts={R02_GUBUN} flex={2} />
            : <RF {...fp} k="pyo_si" label="주택 유형" opts={R.pyo_si} flex={1.8} />}
          <RF {...fp} k="offer_section" label="거래 형태" opts={R.offer_section} />
        </Row>
        <CKS {...fp} k="docs" label="확인·설명 근거자료 등" opts={isR02 ? DOCS_R02 : DOCS} />
        <Row><TF {...fp} k="etc_document_cont" label="그 밖의 자료 내용" flex={2} /></Row>
        <TA {...fp} k="material_request" label="대상물건의 상태에 관한 자료요구 사항" />
      </Sec>

      <Sec no="①" title="대상물건의 표시">
        <Row><TF {...fp} k="address" label="소재지" flex={3} /></Row>
        <Row>
          <TF {...fp} k="land_py" label="토지 면적(㎡)" />
          <TF {...fp} k="jimok" label="공부(公簿)상 지목" ph="대" />
          <TF {...fp} k="r_jimok" label="실제 이용 상태" ph="대" />
        </Row>
        <Row>
          <TF {...fp} k="build_py" label="전용면적(㎡)" />
          <TF {...fp} k="land_py2" label="대지지분(㎡)" />
          <TF {...fp} k="build_date" label="준공년도(증개축년도)" type="date" />
        </Row>
        <Row>
          <TF {...fp} k="build1" label="건축물대장상 용도" />
          <TF {...fp} k="build2" label="실제 용도" />
          <TF {...fp} k="build3" label="구조" />
        </Row>
        <Row>
          <TF {...fp} k="build_eye" label="방향" ph="예: 남향" />
          <TF {...fp} k="build_eye_std" label="방향 기준" ph="예: 거실 앞 발코니 기준" />
        </Row>
        <Row>
          <RF {...fp} k="seidesign" label="내진설계 적용여부" opts={["적용", "미적용"]} />
          <TF {...fp} k="seicapacity" label="내진능력" />
        </Row>
        <Row>
          <RF {...fp} k="wiban" label="건축물대장상 위반건축물 여부" opts={R.wiban} />
          <TF {...fp} k="wiban_content" label="위반내용" flex={2} />
        </Row>
      </Sec>

      <Sec no="②" title="권리관계 (등기부 기재사항)">
        <TA {...fp} k="land_in" label="토지 — 소유권에 관한 사항" />
        <TA {...fp} k="land_out" label="토지 — 소유권 외의 권리사항" />
        <TA {...fp} k="build_in" label="건축물 — 소유권에 관한 사항" />
        <TA {...fp} k="build_out" label="건축물 — 소유권 외의 권리사항" />
        {!isR02 && (<>
          <Row>
            <RF {...fp} k="trust_reg_yn" label="신탁등기 여부" opts={R.trust} flex={2} />
          </Row>
          <Row>
            <RF {...fp} k="joint_collateral_yn" label="공동담보 여부" opts={R.joint} flex={2} />
          </Row>
        </>)}
        <Row>
          <RF {...fp} k="renewal_gb" label="계약갱신요구권 행사 여부" opts={isR02 ? R.renewal_r02 : R.renewal} flex={2} />
        </Row>
        {isR02 && isRent && (<>
          <Row>
            <RF {...fp} k="prv_rent_gb" label="민간임대 등록여부" opts={R.prv_rent} flex={2.6} />
          </Row>
          <Row>
            <TF {...fp} k="prv_rent_nm" label="그 밖의 유형(내용)" />
            <TF {...fp} k="rent_period" label="임대의무기간" />
            <TF {...fp} k="rent_date" label="임대개시일" type="date" />
          </Row>
        </>)}
      </Sec>

      <Sec no="③" title="토지이용계획, 공법상 이용제한 및 거래규제에 관한 사항(토지)">
        <Row>
          <TF {...fp} k="yongdo_jiyok" label="용도지역" />
          <TF {...fp} k="yongdo_jigu" label="용도지구" />
          <TF {...fp} k="yongdo_guyok" label="용도구역" />
        </Row>
        <Row>
          <TF {...fp} k="land_build_per" label="건폐율 상한(%)" flex={0.7} />
          <TF {...fp} k="info_per" label="용적률 상한(%)" flex={0.7} />
          <label style={{ flex: 1, display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
            <input type="checkbox" checked={!!b.toji_heoga} onChange={e => set("toji_heoga", e.target.checked)} />토지거래허가구역
            <em style={{ fontWeight: 400, fontStyle: "normal", fontSize: 10, color: "var(--c-faint, #94a3b8)" }}>· 토지이음</em></label>
        </Row>
        <Row>
          {(["toji_tugi", "jutak_tugi", "tugi_kwayol"] as const).map((k, i) => (
            <label key={k} style={{ flex: 1, display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={!!b[k]} onChange={e => set(k, e.target.checked)} />
              {["토지투기지역", "주택투기지역", "투기과열지구"][i]}</label>
          ))}
        </Row>
        <TA {...fp} k="city_build" label="도시·군계획 시설" />
        <TA {...fp} k="biz_safe" label="지구단위계획구역, 그 밖의 도시·군관리계획" />
        <TA {...fp} k="infor" label="그 밖의 이용제한 및 거래규제사항" />
      </Sec>

      {isRent && !isR02 && (
        <Sec no="④" title="임대차 확인사항">
          <Row>
            <RF {...fp} k="decide_day" label="확정일자 부여현황 정보" opts={R.decide} flex={1.6} />
            <label style={{ flex: 1, display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={!!b.decide_explain} onChange={e => set("decide_explain", e.target.checked)} />임차인 권리 설명</label>
          </Row>
          <Row>
            <RF {...fp} k="tax_info" label="국세 및 지방세 체납정보" opts={R.decide} flex={1.6} />
            <label style={{ flex: 1, display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={!!b.tax_explain} onChange={e => set("tax_explain", e.target.checked)} />임차인 권리 설명</label>
          </Row>
          <Row>
            <RF {...fp} k="move_confirm" label="전입세대 확인서" opts={R.move} flex={2.4} />
          </Row>
          <Row>
            <TF {...fp} k="small_sum" label="최우선변제금 — 소액임차인범위(만원 이하)" />
            <TF {...fp} k="repayment" label="최우선변제금액(만원 이하)" />
          </Row>
          <Row>
            <RF {...fp} k="prv_rent_gb" label="민간임대 등록여부" opts={R.prv_rent} flex={2.6} />
          </Row>
          <Row>
            <TF {...fp} k="prv_rent_nm" label="그 밖의 유형(내용)" />
            <TF {...fp} k="rent_period" label="임대의무기간" />
            <TF {...fp} k="rent_date" label="임대개시일" type="date" />
            <label style={{ flex: 1, display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={!!b.rent_guarantee} onChange={e => set("rent_guarantee", e.target.checked)} />임대보증금 보증 설명</label>
          </Row>
          <div style={{ fontSize: 12, color: "var(--c-muted)", marginTop: 8 }}>
            인쇄물에는 "④ 임대차 확인사항을 임대인 및 임차인에게 설명하였음을 확인함" 서명란이 서식대로 포함됩니다.
          </div>
        </Sec>
      )}

      <Sec no="⑤" title="입지조건">
        <Row>
          <TF {...fp} k="doro" label="도로와의 관계" ph="예: 8m × 6m" />
          <RF {...fp} k="doro_pojang" label="포장" opts={R.pojang} />
          <RF {...fp} k="doro3" label="접근성" opts={R.access} />
        </Row>
        <Row>
          <TF {...fp} k="bus" label="버스 정류장" flex={1.3} /><TF {...fp} k="bus_t" label="약(분)" flex={0.5} />
          <RF {...fp} k="inwater1" label="" opts={R.dobo} flex={0.8} />
          <TF {...fp} k="subway" label="지하철역" flex={1.3} /><TF {...fp} k="subway_t" label="약(분)" flex={0.5} />
          <RF {...fp} k="inwater2" label="" opts={R.dobo} flex={0.8} />
        </Row>
        <Row>
          <RF {...fp} k="carzone" label="주차장" opts={R.carzone} flex={2.4} />
          <TF {...fp} k="carzone_etc" label="그 밖의 주차시설" />
        </Row>
        {!isR02 && (["1", "2", "3"] as const).map(n => (
          <Row key={n}>
            <TF {...fp} k={`edu${n}`} label={["초등학교", "중학교", "고등학교"][Number(n) - 1]} flex={1.3} />
            <TF {...fp} k={`edu${n}_t`} label="약(분)" flex={0.5} />
            <RF {...fp} k={`edu${n}_dobo`} label="" opts={R.dobo} flex={0.8} />
          </Row>
        ))}
      </Sec>

      <Sec no="⑥" title="관리에 관한 사항">
        <Row>
          <RF {...fp} k="safer" label="경비실" opts={R.safer} />
          <RF {...fp} k="safer2" label="관리주체" opts={R.safer2} flex={1.8} />
        </Row>
        {!isR02 && (<>
          <Row>
            <TF {...fp} k="manage_total" label="관리비 금액: 총(원)" />
            <TF {...fp} k="manage_common" label="공동관리비 금액: 총(원)" />
          </Row>
          <CKS {...fp} k="manage_include" label="관리비 포함 비목" opts={MANAGE_ITEMS} />
          <Row><TF {...fp} k="manage_include_etc" label="그 밖의 비목(내용)" flex={2} /></Row>
          <CKS {...fp} k="manage_usage" label="사용량 또는 비용: 확인가능 비목" opts={MANAGE_ITEMS} />
          <Row><TF {...fp} k="manage_usage_etc" label="그 밖의 비목(내용)" flex={2} /></Row>
          <Row>
            <RF {...fp} k="manage_levy" label="관리비 부과방식" opts={R.levy} flex={2.4} />
            <TF {...fp} k="manage_levy_etc" label="그 밖의 부과 방식(내용)" />
          </Row>
        </>)}
      </Sec>

      <Sec no={isR02 ? "⑥⑦" : "⑦⑧⑨"} title={isR02 ? "거래예정금액 · 취득 조세" : "비선호시설 · 거래예정금액 · 취득 조세"}>
        {!isR02 && <Row>
          <RF {...fp} k="noview_s" label="비선호시설(1km이내)" opts={R.noview} />
          <TF {...fp} k="noview" label="종류 및 위치" flex={2} />
        </Row>}
        <Row>
          <TF {...fp} k="cost" label="거래예정금액(원)" flex={1.4} />
          <TF {...fp} k="person_gongsi_jiga" label={isRent ? "개별공시지가(㎡당) — 임대차 생략 가능" : "개별공시지가(㎡당) *"} ph="금액 또는 '해당없음'" />
          <TF {...fp} k="build_gongsi_price" label={isRent ? "건물(주택)공시가격 — 임대차 생략 가능" : "건물(주택)공시가격 *"} ph="금액 또는 '해당없음'" />
        </Row>
        {!isRent ? (
        <Row>
          <TF {...fp} k="real_property_tax" label="취득세(%)" flex={0.7} />
          <TF {...fp} k="farm_tax" label="농어촌특별세(%)" flex={0.7} />
          <TF {...fp} k="education_tax" label="지방교육세(%)" flex={0.7} />
        </Row>
        ) : (
        <div style={{ fontSize: 12.5, color: "var(--c-muted)", marginTop: 4 }}>
          취득 시 부담할 조세(취득세·농어촌특별세·지방교육세)는 <b>임대차에서는 기재하지 않습니다</b>(작성방법) — 인쇄물에는 빈 칸으로 나갑니다.
        </div>
        )}
      </Sec>

      <Sec no={isR02 ? "⑧" : "⑩"} title="실제 권리관계 또는 공시되지 않은 물건의 권리 사항">
        <TA {...fp} k="etc1" label="내용" rows={3}
          ph="법정지상권·유치권·임대차·계약 전 소유권 변동여부·권리 승계 여부 등" />
        {!isR02 && (<>
          <Row>
            <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13.5 }}>
              <input type="checkbox" checked={!!b.dagagu_gb} onChange={e => set("dagagu_gb", e.target.checked)} />
              다가구주택 — 별지(선순위 임대차 현황) 작성
              <em style={{ fontWeight: 400, fontStyle: "normal", fontSize: 10, color: "var(--c-faint, #94a3b8)" }}>· 임대차는 필수, 인쇄 시 별지 첨부+"별지 참고" 자동 표기</em>
            </label>
          </Row>
          {!!b.dagagu_gb && (<>
            <ByuljiRows rows={b.byulji_rows || []} onChange={r => set("byulji_rows", r)} />
            <TA {...fp} k="byulji_text" label="별지 — 그 밖의 기재사항" rows={2}
              ph="예: 상기 현황은 임대인 고지 및 확정일자 부여현황에 근거함" />
          </>)}
        </>)}
      </Sec>

      <Sec no="⑪" title="내부·외부 시설물의 상태(건축물)">
        <Grp title="수도">
          <Row>
            <RF {...fp} k="water_p" label="파손 여부" opts={R.water_p} />
            <TF {...fp} k="water_pos" label="파손 위치" />
            <RF {...fp} k="water_su" label="용수량" opts={R.water_su} />
            <TF {...fp} k="water_su_pos" label="부족한 곳 위치" />
          </Row>
        </Grp>
        <Grp title="전기">
          <Row>
            <RF {...fp} k="elect" label="공급상태" opts={R.elect} />
            <TF {...fp} k="elect_part" label="교체 필요 시 — 교체할 부분" flex={2} />
          </Row>
        </Grp>
        <Grp title="가스(취사용)">
          <Row>
            <RF {...fp} k="gas" label="공급방식" opts={R.gas} />
            <TF {...fp} k="gas_etc" label="그 밖의 방식 — 내용" flex={2} />
          </Row>
        </Grp>
        <Grp title="소방">
          {!isR02 ? (
            <Row>
              <RF {...fp} k="firealarm_yn" label="단독경보형감지기" opts={R.firealarm} />
              <TF {...fp} k="firealarm_cnt" label="수량(개)" flex={0.5} />
            </Row>
          ) : (
            <Row>
              <RF {...fp} k="fire_hydrant" label="소화전" opts={R.firealarm} />
              <TF {...fp} k="fire_hydrant_pos" label="소화전 위치" flex={0.8} />
              <RF {...fp} k="emergency_bell" label="비상벨" opts={R.firealarm} />
              <TF {...fp} k="emergency_bell_pos" label="비상벨 위치" flex={0.8} />
            </Row>
          )}
        </Grp>
        <Grp title="난방방식 및 연료공급">
          <Row>
            <RF {...fp} k="boil" label="공급방식" opts={isR02 ? R.boil_r02 : R.boil} flex={1.8} />
            <RF {...fp} k="boil_etc2" label="시설작동" opts={R.state2} />
            <TF {...fp} k="boil_fix" label="수선 필요 시 — 내용" flex={0.9} />
          </Row>
          <Row>
            <TF {...fp} k="use_term" label="사용연한(개별 공급인 경우)" />
            <label style={{ flex: 0.8, display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={!!b.use_term_na} onChange={e => set("use_term_na", e.target.checked)} />확인불가</label>
            <RF {...fp} k="boil_etc" label="연료 종류" opts={R.boil_fuel} flex={3} />
          </Row>
        </Grp>
        <Grp title="승강기 · 배수">
          <Row>
            <RF {...fp} k="eleb" label="승강기" opts={R.eleb} />
            <RF {...fp} k="eleb_state" label="승강기 상태(있음일 때)" opts={R.eleb_state} />
            <RF {...fp} k="baesu" label="배수" opts={R.state2} />
            <TF {...fp} k="baesu_p" label="배수 수선 필요 시 — 내용" />
          </Row>
        </Grp>
        <TA {...fp} k="etc_struct" label="그 밖의 시설물" />
      </Sec>

      <Sec no={isR02 ? "⑩" : "⑫"} title={isR02 ? "벽면 및 바닥면" : "벽면·바닥면 및 도배 상태"}>
        <Row>
          <RF {...fp} k="crack" label="벽면 균열" opts={R.water_p} />
          <TF {...fp} k="crack_t" label="균열 위치" />
          <RF {...fp} k="leak" label="누수" opts={R.water_p} />
          <TF {...fp} k="leak_t" label="누수 위치" />
        </Row>
        <Row>
          <RF {...fp} k="bottom" label="바닥면" opts={R.bottom} flex={1.5} />
          <TF {...fp} k="bottom_t" label="수리 필요 위치" />
          {!isR02 && <RF {...fp} k="block_paper" label="도배" opts={R.paper} flex={1.5} />}
        </Row>
      </Sec>

      {!isR02 && <Sec no="⑬⑭" title="환경조건 · 현장안내">
        <Row>
          <RF {...fp} k="ilzo" label="일조량" opts={R.ilzo} flex={1.4} />
          <TF {...fp} k="ilzo_etc" label="불충분 이유" />
        </Row>
        <Row>
          <RF {...fp} k="soum" label="소음" opts={R.soum} flex={1.4} />
          <RF {...fp} k="jindong" label="진동" opts={R.soum} flex={1.4} />
        </Row>
        <Row>
          <RF {...fp} k="guide" label="현장안내자" opts={R.guide} flex={2.6} />
          {String(b.guide) === "3" && <RF {...fp} k="guide_id" label="신분고지 여부" opts={R.yesno} />}
        </Row>
      </Sec>}

      <Sec no={isR02 ? "⑪" : "⑮"} title="중개보수 및 실비의 금액과 산출내역">
        {feeGuide}
        <Row>
          <TF {...fp} k="charge" label="중개보수(원)" />
          <TF {...fp} k="expense" label="실비(원)" />
          <TF {...fp} k="t_cost" label="계(원)" />
          <TF {...fp} k="charge_sigi" label="지급시기" ph="예: 잔금일" />
        </Row>
        <TA {...fp} k="susuryo" label="산출내역 — 중개보수" ph="예: 거래예정금액 × 0.4%" />
        <TA {...fp} k="silbi_comment" label="산출내역 — 실비" />
        <Row>
          <TF {...fp} k="wdate" label="작성일(교부일)" type="date" flex={0.8} />
          <div style={{ flex: 2.4, fontSize: 12, color: "var(--c-muted)" }}>
            서명란(매도·매수인, 개업공인중개사)은 계약서의 당사자·중개사 정보로 채워지며 생년월일은 주민번호 앞자리로 표기됩니다.
          </div>
        </Row>
      </Sec>
      </>)}

      {actionBar}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// 인쇄 — 별지 제20호서식 <개정 2026.8.11> 법정 양식 복제(본문 4쪽)
// 표기 규칙(작성방법): 해당 항목의 [ ] 안에 √ 표시
// ───────────────────────────────────────────────────────────────────
function oesc(v: any): string {
  return String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function ck(on: boolean, label: string): string {
  return `[<b>${on ? "√" : "&nbsp;&nbsp;"}</b>]${label}`;
}
function ckR(opts: readonly string[], code: any, gap = "&nbsp;&nbsp;"): string {
  return opts.map((o, i) => ck(String(code ?? "") === String(i + 1), o)).join(gap);
}
function won(v: any): string {
  const n = Number(String(v ?? "").replace(/[^0-9]/g, ""));
  return n ? `${n.toLocaleString()}원` : oesc(v);
}
function birth(jumin?: string): string {
  const m = String(jumin || "").match(/^(\d{2})(\d{2})(\d{2})/);
  if (!m) return "";
  return `${m[1]}.${m[2]}.${m[3]}.`;
}
function dateK(d?: string): string {
  if (!d) return "년&nbsp;&nbsp;&nbsp;&nbsp;월&nbsp;&nbsp;&nbsp;&nbsp;일";
  const [y, mo, da] = d.split("-");
  return `${y}년&nbsp;&nbsp;${Number(mo)}월&nbsp;&nbsp;${Number(da)}일`;
}

export function buildOfferHtml(b: Body, form: "R01" | "R02" | "R03" | "R04" = "R01"): string {
  if (form === "R02") return buildOfferR02Html(b);
  if (form === "R03") return buildOfferR03Html(b);
  if (form === "R04") return buildOfferR04Html(b);
  const isRent = String(b.offer_section) === "2";
  const docs: string[] = b.docs || [];
  const mi: string[] = b.manage_include || [];
  const mu: string[] = b.manage_usage || [];
  const v = (k: string) => oesc(b[k]);
  const hdrLine = (n: number) =>
    `<div class="hd"><span>■ 공인중개사법 시행규칙 [별지 제20호서식] &lt;개정 2026. 8. 11.&gt;</span><span>(6쪽 중 제${n}쪽)</span></div>`;

  // 서명 블록(4쪽): 매도/매수/개공×N — 생년월일은 주민 앞 6자리
  const sp: Party[] = b.sell_parties || [];
  const bp: Party[] = b.buy_parties || [];
  const bks: Broker[] = ((b.brokers || []) as Broker[]).filter(k => k.company || k.owner);
  const partyBlock = (p: Party | undefined, role: string) => `
  <table class="tb sign"><tbody>
    <tr><th class="rh" rowspan="2">${role}</th><th style="width:14%">주소</th><td style="width:36%">${oesc(p?.addr || "")}</td>
      <th style="width:12%">성명</th><td>${oesc(p?.name || "")}<span class="sgn">(서명 또는 날인)</span></td></tr>
    <tr><th>생년월일</th><td>${birth(p?.jumin)}</td><th>전화번호</th><td>${oesc(p?.tel || "")}</td></tr>
  </tbody></table>`;
  const brokerBlock = (k: Broker | undefined) => `
  <table class="tb sign"><tbody>
    <tr><th class="rh" rowspan="3">개업<br>공인중개사</th><th style="width:14%">등록번호</th><td style="width:36%">${oesc(k?.reg_no || "")}</td>
      <th style="width:14%">성명(대표자)</th><td>${oesc(k?.owner || "")}<span class="sgn">(서명 및 날인)</span></td></tr>
    <tr><th>사무소 명칭</th><td>${oesc(k?.company || "")}</td><th>소속공인중개사</th><td>${oesc(k?.belong || "")}<span class="sgn">(서명 및 날인)</span></td></tr>
    <tr><th>사무소 소재지</th><td>${oesc(k?.addr || "")}</td><th>전화번호</th><td>${oesc(k?.tel || "")}</td></tr>
  </tbody></table>`;

  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>중개대상물 확인·설명서</title>
<style>
  @page{size:A4;margin:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{margin:0;padding:7mm 9mm;box-sizing:border-box;
    font-family:'AppleGothic','Malgun Gothic','NanumGothic','나눔고딕','돋움',sans-serif;color:#000}
  .pg{width:192mm;min-height:282mm;box-sizing:border-box;display:flex;flex-direction:column}
  .pg + .pg{page-break-before:always}
  .hd{display:flex;justify-content:space-between;font-size:7.6pt;margin-bottom:1mm}
  h1{text-align:center;font-size:14pt;margin:0 0 1mm;font-weight:900;letter-spacing:0.5px}
  .htype{text-align:center;font-size:9pt;margin:0 0 1.5mm;line-height:1.6}
  .tb{width:100%;border-collapse:collapse;table-layout:fixed}
  .tb th,.tb td{border:0.5px solid #000;padding:0.8mm 1.2mm;font-size:8pt;line-height:1.35;
    word-break:break-all;vertical-align:middle;text-align:left}
  .tb th{font-weight:700;text-align:center;background:#fff}
  .tb th.rh{width:11%;font-weight:800}
  .tb + .tb{margin-top:0}
  .sect{font-weight:900;font-size:9.5pt;border-bottom:1.6px solid #000;padding:1.2mm 0 0.6mm;margin-top:1.6mm}
  .gray{background:#e8e8e8;text-align:center;font-weight:800}
  b{font-weight:900}
  .nt{font-size:7.3pt;line-height:1.4;margin:0.5mm 0}
  .grow{flex:1}
  .sgn{float:right;font-size:7pt;color:#333}
  .att{font-size:8.2pt;line-height:1.5;margin:1.5mm 0;text-align:justify}
</style></head><body>

<div class="pg">
  ${hdrLine(1)}
  <h1>중개대상물 확인·설명서[Ⅰ] (주거용 건축물)</h1>
  <div class="htype">( 주택 유형: ${ckR(R.pyo_si, b.pyo_si, "&nbsp;&nbsp;&nbsp;")} )<br>
  ( 거래 형태: ${ckR(R.offer_section, b.offer_section, "&nbsp;&nbsp;&nbsp;")} )</div>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">확인·설명<br>자료</th>
      <th style="width:15%">확인·설명<br>근거자료 등</th>
      <td colspan="4">${DOCS.slice(0, 12).map(d => ck(docs.includes(d), d)).join(" ")} ${ck(docs.includes("그 밖의 자료"), `그 밖의 자료(${v("etc_document_cont") || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"})`)}</td></tr>
    <tr><th>대상물건의<br>상태에 관한<br>자료요구 사항</th><td colspan="4">${v("material_request")}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><td colspan="2" class="gray">유의사항</td></tr>
    <tr><th class="rh" style="width:20%">개업공인중개사의<br>확인·설명 의무</th>
      <td style="font-size:7.6pt">개업공인중개사는 중개대상물에 관한 권리를 취득하려는 중개의뢰인에게 성실·정확하게 설명하고, 토지대장 등본, 등기사항증명서 등 설명의 근거자료를 제시해야 합니다.</td></tr>
    <tr><th class="rh">실제 거래가격<br>신고</th>
      <td style="font-size:7.6pt">「부동산 거래신고 등에 관한 법률」 제3조 및 같은 법 시행령 별표 1 제1호마목에 따른 실제 거래가격은 매수인이 매수한 부동산을 양도하는 경우 「소득세법」 제97조제1항 및 제7항과 같은 법 시행령 제163조제11항제2호에 따라 취득 당시의 실제 거래가액으로 보아 양도차익이 계산될 수 있음을 유의하시기 바랍니다.</td></tr>
  </tbody></table>

  <div class="sect">Ⅰ. 개업공인중개사 기본 확인사항</div>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="9">① 대상물건<br>의 표시</th>
      <th rowspan="3" style="width:10%">토지</th><th style="width:14%">소재지</th><td colspan="4">${v("address")}</td></tr>
    <tr><th rowspan="2">면적(㎡)</th><td rowspan="2" style="width:16%">${v("land_py")}</td><th rowspan="2" style="width:9%">지목</th><th style="width:17%">공부(公簿)상 지목</th><td>${v("jimok")}</td></tr>
    <tr><th>실제 이용 상태</th><td>${v("r_jimok")}</td></tr>
    <tr><th rowspan="6">건축물</th><th>전용면적(㎡)</th><td colspan="2">${v("build_py")}</td><th>대지지분(㎡)</th><td>${v("land_py2")}</td></tr>
    <tr><th rowspan="2">준공년도<br>(증개축년도)</th><td rowspan="2" colspan="2">${v("build_date")}</td><th style="width:17%">건축물대장상 용도</th><td>${v("build1")}</td></tr>
    <tr><th>실제 용도</th><td>${v("build2")}</td></tr>
    <tr><th>구조</th><td colspan="2">${v("build3")}</td><th>방향</th><td>${v("build_eye")} &nbsp;(기준: ${v("build_eye_std")})</td></tr>
    <tr><th>내진설계 적용여부</th><td colspan="2">${b.seidesign ? ckR(["적용", "미적용"], b.seidesign) : ""}</td><th>내진능력</th><td>${v("seicapacity")}</td></tr>
    <tr><th>건축물대장상<br>위반건축물 여부</th><td colspan="2">${ckR(R.wiban, b.wiban)}</td><th>위반내용</th><td>${v("wiban_content")}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="6">② 권리관계</th>
      <th rowspan="3" style="width:12%">등기부<br>기재사항</th><th style="width:9%" rowspan="1"></th><th colspan="2">소유권에 관한 사항</th><th colspan="2">소유권 외의 권리사항</th></tr>
    <tr><th>토지</th><td colspan="2">${v("land_in")}</td><td colspan="2"><b>토지</b>&nbsp; ${v("land_out")}</td></tr>
    <tr><th>건축물</th><td colspan="2">${v("build_in")}</td><td colspan="2"><b>건축물</b>&nbsp; ${v("build_out")}</td></tr>
    <tr><th colspan="2">신탁등기 여부</th><td colspan="4">${ckR(R.trust, b.trust_reg_yn)}</td></tr>
    <tr><th colspan="2">공동담보 여부</th><td colspan="4">${ckR(R.joint, b.joint_collateral_yn)}</td></tr>
    <tr><th colspan="2">계약갱신요구권<br>행사 여부</th><td colspan="4">${ckR(R.renewal, b.renewal_gb)}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="5">③ 토지이용<br>계획, 공법상<br>이용제한 및<br>거래규제에<br>관한 사항<br>(토지)</th>
      <th rowspan="3" style="width:10%">지역·지구</th><th style="width:12%">용도지역</th><td colspan="2">${v("yongdo_jiyok")}</td><th style="width:13%">건폐율 상한</th><th style="width:13%">용적률 상한</th></tr>
    <tr><th>용도지구</th><td colspan="2">${v("yongdo_jigu")}</td><td rowspan="2" style="text-align:right">${v("land_build_per")} %</td><td rowspan="2" style="text-align:right">${v("info_per")} %</td></tr>
    <tr><th>용도구역</th><td colspan="2">${v("yongdo_guyok")}</td></tr>
    <tr><th rowspan="2">도시·군<br>계획 시설</th><td rowspan="2">${v("city_build")}</td><th style="width:14%">허가·신고<br>구역 여부</th><td colspan="3">${ck(!!b.toji_heoga, "토지거래허가구역")}</td></tr>
    <tr><th>투기지역 여부</th><td colspan="3">${ck(!!b.toji_tugi, "토지투기지역")} ${ck(!!b.jutak_tugi, "주택투기지역")} ${ck(!!b.tugi_kwayol, "투기과열지구")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" style="width:24%">지구단위계획구역,<br>그 밖의 도시·군관리계획</th><td style="width:32%">${v("biz_safe")}</td>
      <th style="width:16%">그 밖의 이용제한<br>및 거래규제사항</th><td>${v("infor")}</td></tr>
  </tbody></table>
  <div class="grow"></div>
  <div class="nt" style="text-align:right">210㎜×297㎜[백상지(80g/㎡) 또는 중질지(80g/㎡)]</div>
</div>

<div class="pg">
  ${hdrLine(2)}
  ${isRent ? `
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="7">④ 임대차<br>확인사항</th>
      <th colspan="2" style="width:24%">확정일자 부여현황 정보</th><td style="width:40%">${ckR(R.decide, b.decide_day)}</td><td>${ck(!!b.decide_explain, "임차인 권리 설명")}</td></tr>
    <tr><th colspan="2">국세 및 지방세 체납정보</th><td>${ckR(R.decide, b.tax_info)}</td><td>${ck(!!b.tax_explain, "임차인 권리 설명")}</td></tr>
    <tr><th colspan="2">전입세대 확인서</th><td colspan="2">${ckR(R.move, b.move_confirm)}</td></tr>
    <tr><th colspan="2">최우선변제금</th><td colspan="2">소액임차인범위: ${v("small_sum") || "&nbsp;&nbsp;&nbsp;&nbsp;"} 만원 이하 &nbsp;&nbsp; 최우선변제금액: ${v("repayment") || "&nbsp;&nbsp;&nbsp;&nbsp;"} 만원 이하</td></tr>
    <tr><th rowspan="2" style="width:8%">민간<br>임대<br>등록<br>여부</th><th style="width:16%">등록</th>
      <td>${ck(String(b.prv_rent_gb) === "1", "장기일반민간임대주택")} ${ck(String(b.prv_rent_gb) === "2", "공공지원민간임대주택")}<br>${ck(String(b.prv_rent_gb) === "3", `그 밖의 유형(${v("prv_rent_nm") || "&nbsp;&nbsp;&nbsp;&nbsp;"})`)}</td>
      <td>${ck(!!b.rent_guarantee, "임대보증금 보증 설명")}</td></tr>
    <tr><td colspan="2">임대의무기간: ${v("rent_period")} &nbsp;&nbsp;&nbsp; 임대개시일: ${v("rent_date")}</td></tr>
    <tr><th>미등록</th><td colspan="3">${ck(String(b.prv_rent_gb) === "4", "")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><td rowspan="4" style="width:56%;border-right:0.5px solid #000">개업공인중개사가 &nbsp;“④ 임대차 확인사항”을 임대인 및 임차인에게 설명하였음을 확인함</td>
      <th style="width:20%">임대인</th><td><span class="sgn">(서명 또는 날인)</span></td></tr>
    <tr><th>임차인</th><td><span class="sgn">(서명 또는 날인)</span></td></tr>
    <tr><th>개업공인중개사</th><td><span class="sgn">(서명 또는 날인)</span></td></tr>
    <tr><th>개업공인중개사</th><td><span class="sgn">(서명 또는 날인)</span></td></tr>
  </tbody></table>
  <div class="nt">※ 민간임대주택의 임대사업자는 「민간임대주택에 관한 특별법」 제49조에 따라 임대보증금에 대한 보증에 가입해야 합니다.<br>
  ※ 임차인은 주택도시보증공사(HUG) 등이 운영하는 전세보증금반환보증에 가입할 것을 권고합니다.<br>
  ※ 임대차 계약 후 「부동산 거래신고 등에 관한 법률」 제6조의2에 따라 30일 이내 신고해야 합니다(신고 시 확정일자 자동부여).<br>
  ※ 최우선변제금은 근저당권 등 선순위 담보물권 설정 당시의 소액임차인범위 및 최우선변제금액을 기준으로 합니다.</div>
  ` : ""}

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="7">⑤ 입지조건</th>
      <th style="width:12%">도로와의<br>관계</th><td colspan="2">( ${v("doro") || "&nbsp;&nbsp;m ×&nbsp;&nbsp;m"} )도로에 접함 &nbsp; ${ckR(R.pojang, b.doro_pojang)}</td>
      <th style="width:11%">접근성</th><td>${ckR(R.access, b.doro3)}</td></tr>
    <tr><th rowspan="2">대중교통</th><th style="width:11%">버스</th><td colspan="3">( ${v("bus")} ) 정류장, &nbsp;소요시간: ( ${ckR(R.dobo, b.inwater1)} ) 약 ${v("bus_t")} 분</td></tr>
    <tr><th>지하철</th><td colspan="3">( ${v("subway")} ) 역, &nbsp;소요시간: ( ${ckR(R.dobo, b.inwater2)} ) 약 ${v("subway_t")} 분</td></tr>
    <tr><th>주차장</th><td colspan="4">${ck(String(b.carzone) === "1", "없음")} ${ck(String(b.carzone) === "2", "전용주차시설")} ${ck(String(b.carzone) === "3", "공동주차시설")} ${ck(String(b.carzone) === "4", `그 밖의 주차시설 (${v("carzone_etc")})`)}</td></tr>
    <tr><th rowspan="3">교육시설</th><th>초등학교</th><td colspan="3">( ${v("edu1")} ) 학교, &nbsp;소요시간: ( ${ckR(R.dobo, b.edu1_dobo)} ) 약 ${v("edu1_t")} 분</td></tr>
    <tr><th>중학교</th><td colspan="3">( ${v("edu2")} ) 학교, &nbsp;소요시간: ( ${ckR(R.dobo, b.edu2_dobo)} ) 약 ${v("edu2_t")} 분</td></tr>
    <tr><th>고등학교</th><td colspan="3">( ${v("edu3")} ) 학교, &nbsp;소요시간: ( ${ckR(R.dobo, b.edu3_dobo)} ) 약 ${v("edu3_t")} 분</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="5">⑥ 관리에<br>관한 사항</th>
      <th style="width:12%">경비실</th><td style="width:24%">${ckR(R.safer, b.safer)}</td><th style="width:11%">관리주체</th><td>${ckR(R.safer2, b.safer2)}</td></tr>
    <tr><th rowspan="4">관리비</th><td colspan="3">관리비 금액: 총 ${won(b.manage_total) || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;원"} &nbsp;&nbsp;&nbsp; 공동관리비 금액: 총 ${won(b.manage_common) || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;원"}</td></tr>
    <tr><td colspan="3">관리비 포함 비목: ${MANAGE_ITEMS.slice(0, 6).map(x => ck(mi.includes(x), x)).join(" ")} ${ck(mi.includes("그 밖의 비목"), `그 밖의 비목(${v("manage_include_etc")})`)}</td></tr>
    <tr><td colspan="3">사용량 또는 비용: 확인가능 비목 &nbsp; ${MANAGE_ITEMS.slice(0, 6).map(x => ck(mu.includes(x), x)).join(" ")} ${ck(mu.includes("그 밖의 비목"), `그 밖의 비목(${v("manage_usage_etc")})`)}</td></tr>
    <tr><td colspan="3">관리비 부과방식: ${ck(String(b.manage_levy) === "1", "임대인이 직접 부과")} ${ck(String(b.manage_levy) === "2", "관리규약에 따라 부과")}<br>${ck(String(b.manage_levy) === "3", `그 밖의 부과 방식(${v("manage_levy_etc")})`)}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" style="width:22%">⑦ 비선호시설(1㎞이내)</th>
      <td>${ck(String(b.noview_s) === "1", "없음")} &nbsp;&nbsp; ${ck(String(b.noview_s) === "2", `있음 (종류 및 위치: ${v("noview")})`)}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">⑧ 거래예정금액 등</th>
      <th style="width:15%">거래예정금액</th><td colspan="3">${won(b.cost)}</td></tr>
    <tr><th>개별공시지가<br>(㎡당)</th><td>${won(b.person_gongsi_jiga)}</td><th style="width:14%">건물(주택)<br>공시가격</th><td>${won(b.build_gongsi_price)}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2" style="width:22%">⑨ 취득 시 부담할<br>조세의 종류 및 세율</th>
      <th style="width:10%">취득세</th><td style="width:12%;text-align:right">${v("real_property_tax")} %</td>
      <th style="width:13%">농어촌특별세</th><td style="width:12%;text-align:right">${v("farm_tax")} %</td>
      <th style="width:12%">지방교육세</th><td style="text-align:right">${v("education_tax")} %</td></tr>
    <tr><td colspan="6">※ 재산세와 종합부동산세는 6월 1일 기준으로 대상물건 소유자가 납세의무를 부담합니다.</td></tr>
  </tbody></table>
  <div class="grow"></div>
</div>

<div class="pg">
  ${hdrLine(3)}
  <div class="sect">Ⅱ. 개업공인중개사 세부 확인사항</div>
  <table class="tb"><tbody>
    <tr><th style="text-align:left;background:#fff;border-bottom:0.5px solid #000">⑩ 실제 권리관계 또는 공시되지 않은 물건의 권리 사항</th></tr>
    <tr><td style="height:28mm;vertical-align:top">${b.dagagu_gb ? "[√ 다가구주택] " : ""}${(b.byulji_rows || []).length ? "『별지 참고』 " : ""}${v("etc1")}</td></tr>
  </tbody></table>

  <table class="tb" style="margin-top:1.5mm"><tbody>
    <tr><th class="rh" rowspan="10">⑪ 내부·<br>외부 시설<br>물의 상태<br>(건축물)</th>
      <th rowspan="2" style="width:12%">수도</th><th style="width:13%">파손 여부</th><td colspan="3">${ckR(R.water_p, b.water_p)} ${b.water_pos ? `(위치: ${v("water_pos")})` : "(위치:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th>용수량</th><td colspan="3">${ckR(R.water_su, b.water_su)} ${b.water_su_pos ? `(위치: ${v("water_su_pos")})` : "(위치:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th>전기</th><th>공급상태</th><td colspan="3">${ckR(R.elect, b.elect)} ${b.elect_part ? `(교체할 부분: ${v("elect_part")})` : "(교체할 부분:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th>가스(취사용)</th><th>공급방식</th><td colspan="3">${ck(String(b.gas) === "1", "도시가스")} &nbsp; ${ck(String(b.gas) === "2", `그 밖의 방식 (${v("gas_etc")})`)}</td></tr>
    <tr><th>소방</th><th>단독경보형<br>감지기</th><td style="width:26%">${ck(String(b.firealarm_yn) === "1", "없음")}<br>${ck(String(b.firealarm_yn) === "2", `있음(수량: ${v("firealarm_cnt")} 개)`)}</td>
      <td colspan="2" style="font-size:7.2pt">※ 「소방시설 설치 및 관리에 관한 법률」 제10조 및 같은 법 시행령 제10조에 따른 주택용 소방시설로서 아파트(주택으로 사용하는 층수가 5개층 이상인 주택을 말한다)를 제외한 주택의 경우만 적습니다.</td></tr>
    <tr><th rowspan="2">난방방식 및<br>연료공급</th><th>공급방식</th>
      <td>${ck(String(b.boil) === "1", "중앙공급")}<br>${ck(String(b.boil) === "2", "개별공급")}<br>${ck(String(b.boil) === "3", "지역난방")}</td>
      <th style="width:11%">시설작동</th>
      <td>${ck(String(b.boil_etc2) === "1", "정상")} ${ck(String(b.boil_etc2) === "2", `수선 필요 (${v("boil_fix")})`)}<br>
      ※ 개별 공급인 경우 사용연한 ( ${v("use_term")} ) &nbsp; ${ck(!!b.use_term_na, "확인불가")}</td></tr>
    <tr><th>종류</th><td colspan="3">${ck(String(b.boil_etc) === "1", "도시가스")} ${ck(String(b.boil_etc) === "2", "기름")} ${ck(String(b.boil_etc) === "3", "프로판가스")} ${ck(String(b.boil_etc) === "4", "연탄")} ${ck(String(b.boil_etc) === "5", "그 밖의 종류 (&nbsp;&nbsp;&nbsp;)")}</td></tr>
    <tr><th colspan="2">승강기</th><td colspan="3">${ck(String(b.eleb) === "1", "있음")} &nbsp;( ${ck(String(b.eleb_state) === "1", "양호")} ${ck(String(b.eleb_state) === "2", "불량")} ) &nbsp;&nbsp; ${ck(String(b.eleb) === "2", "없음")}</td></tr>
    <tr><th colspan="2">배수</th><td colspan="3">${ck(String(b.baesu) === "1", "정상")} ${ck(String(b.baesu) === "2", `수선 필요 (${v("baesu_p")})`)}</td></tr>
    <tr><th colspan="2">그 밖의<br>시설물</th><td colspan="3">${v("etc_struct")}</td></tr>
  </tbody></table>

  <table class="tb" style="margin-top:1.5mm"><tbody>
    <tr><th class="rh" rowspan="4">⑫ 벽면·<br>바닥면 및<br>도배 상태</th>
      <th rowspan="2" style="width:12%">벽면</th><th style="width:13%">균열</th><td>${ckR(R.water_p, b.crack)} ${b.crack_t ? `(위치: ${v("crack_t")})` : "(위치:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th>누수</th><td>${ckR(R.water_p, b.leak)} ${b.leak_t ? `(위치: ${v("leak_t")})` : "(위치:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th colspan="2">바닥면</th><td>${ck(String(b.bottom) === "1", "깨끗함")} ${ck(String(b.bottom) === "2", "보통임")} ${ck(String(b.bottom) === "3", `수리 필요 (위치: ${v("bottom_t")})`)}</td></tr>
    <tr><th colspan="2">도배</th><td>${ckR(R.paper, b.block_paper)}</td></tr>
  </tbody></table>

  <table class="tb" style="margin-top:1.5mm"><tbody>
    <tr><th class="rh" rowspan="2">⑬ 환경<br>조건</th>
      <th style="width:12%">일조량</th><td colspan="3">${ck(String(b.ilzo) === "1", "풍부함")} ${ck(String(b.ilzo) === "2", "보통임")} ${ck(String(b.ilzo) === "3", `불충분 (이유: ${v("ilzo_etc")})`)}</td></tr>
    <tr><th>소음</th><td>${ckR(R.soum, b.soum)}</td><th style="width:9%">진동</th><td>${ckR(R.soum, b.jindong)}</td></tr>
  </tbody></table>

  <table class="tb" style="margin-top:1.5mm"><tbody>
    <tr><th class="rh">⑭ 현장안내</th><th style="width:12%">현장안내자</th>
      <td>${ck(String(b.guide) === "1", "개업공인중개사")} ${ck(String(b.guide) === "2", "소속공인중개사")} ${ck(String(b.guide) === "3", `중개보조원(신분고지 여부: ${ck(String(b.guide_id) === "1", "예")} ${ck(String(b.guide_id) === "2", "아니오")})`)}<br>${ck(String(b.guide) === "4", "해당 없음")}</td></tr>
  </tbody></table>
  <div class="nt">※ “중개보조원”이란 공인중개사가 아닌 사람으로서 개업공인중개사에 소속되어 중개대상물에 대한 현장안내 및 일반서무 등 개업공인중개사의 중개업무와 관련된 단순한 업무를 보조하는 사람을 말합니다.<br>
  ※ 중개보조원은 「공인중개사법」 제18조의4에 따라 현장안내 등 중개업무를 보조하는 경우 중개의뢰인에게 본인이 중개보조원이라는 사실을 미리 알려야 합니다.</div>
  <div class="grow"></div>
</div>

<div class="pg">
  ${hdrLine(4)}
  <div class="sect">Ⅲ. 중개보수 등에 관한 사항</div>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="4">⑮ 중개보수<br>및 실비의<br>금액과<br>산출내역</th>
      <th style="width:13%">중개보수</th><td style="width:37%">${won(b.charge)}</td>
      <td rowspan="4" style="vertical-align:top;font-size:7.8pt">&lt;산출내역&gt;<br>중개보수: ${v("susuryo")}<br><br>실&nbsp;&nbsp;&nbsp;&nbsp;비: ${v("silbi_comment")}<br><br>※ 중개보수는 시·도 조례로 정한 요율한도에서 중개의뢰인과 개업공인중개사가 서로 협의하여 결정하며 부가가치세는 별도로 부과될 수 있습니다.</td></tr>
    <tr><th>실비</th><td>${won(b.expense)}</td></tr>
    <tr><th>계</th><td>${won(b.t_cost)}</td></tr>
    <tr><th>지급시기</th><td>${v("charge_sigi")}</td></tr>
  </tbody></table>

  <div class="att">「공인중개사법」 제25조제3항 및 제30조제5항에 따라 거래당사자는 개업공인중개사로부터 위 중개대상물에 관한 확인·설명 및 손해배상책임의 보장에 관한 설명을 듣고, 같은 법 시행령 제21조제3항에 따른 본 확인·설명서와 같은 법 시행령 제24조제2항에 따른 손해배상책임 보장 증명서류(사본 또는 전자문서)를 수령합니다.</div>
  <div style="text-align:right;font-size:9pt;margin:1mm 0 2mm">${dateK(b.wdate)}</div>

  ${sp.length ? sp.map(p => partyBlock(p, isRent ? "매도인<br>(임대인)" : "매도인<br>(임대인)")).join("") : partyBlock(undefined, "매도인<br>(임대인)")}
  ${bp.length ? bp.map(p => partyBlock(p, "매수인<br>(임차인)")).join("") : partyBlock(undefined, "매수인<br>(임차인)")}
  ${bks.length ? bks.map(k => brokerBlock(k)).join("") : brokerBlock(undefined)}
  ${bks.length < 2 ? brokerBlock(undefined) : ""}
  <div class="grow"></div>
</div>
${byuljiPage(b)}
</body></html>`;
}

// 별지 — 다가구 선순위 임대차 현황(자유 서식, 작성방법 "별지로 작성하여 첨부" 근거)
function byuljiPage(b: Body): string {
  const rows: { ho: string; deposit: string; rent: string; period: string; fix: string; note: string }[] = b.byulji_rows || [];
  if (!rows.length && !b.byulji_text) return "";
  const man = (x: string) => { const n = Number(String(x).replace(/[^0-9]/g, "")); return n ? n.toLocaleString() : oesc(x); };
  return `<div class="pg">
  <div class="hd"><span>■ 중개대상물 확인·설명서 [Ⅰ] 별지</span><span>(별지)</span></div>
  <h1 style="font-size:12.5pt">별지 — 실제 권리관계 또는 공시되지 않은 물건의 권리 사항</h1>
  <div style="text-align:center;font-size:9pt;margin-bottom:2mm">(다가구주택 선순위 임대차 현황)</div>
  <table class="tb"><tbody>
    <tr><th style="width:6%">연번</th><th style="width:12%">호수</th><th style="width:16%">보증금(만원)</th>
      <th style="width:13%">차임(만원)</th><th style="width:22%">임대차기간</th><th style="width:14%">확정일자</th><th>비고</th></tr>
    ${rows.map((r, i) => `<tr><td style="text-align:center">${i + 1}</td><td>${oesc(r.ho)}</td>
      <td style="text-align:right">${man(r.deposit)}</td><td style="text-align:right">${man(r.rent)}</td>
      <td>${oesc(r.period)}</td><td class="num">${oesc(r.fix)}</td><td>${oesc(r.note)}</td></tr>`).join("")}
    <tr><th>합계</th><td></td><td style="text-align:right;font-weight:800">${rows.reduce((a, r) => a + (Number(String(r.deposit).replace(/[^0-9]/g, "")) || 0), 0).toLocaleString()}</td>
      <td style="text-align:right;font-weight:800">${rows.reduce((a, r) => a + (Number(String(r.rent).replace(/[^0-9]/g, "")) || 0), 0).toLocaleString()}</td><td colspan="3"></td></tr>
  </tbody></table>
  ${b.byulji_text ? `<div style="font-size:8.4pt;margin-top:2mm;line-height:1.5">${oesc(b.byulji_text)}</div>` : ""}
  <div class="nt" style="margin-top:2mm">※ 위 현황은 임대인의 고지 및 확정일자 부여현황 등 확인 자료에 근거하여 작성한 것입니다.</div>
  <div class="grow"></div>
</div>`;
}


// ───────────────────────────────────────────────────────────────────
// 인쇄 — 별지 제20호의2서식 <개정 2021.12.31> 비주거용 건축물(본문 3쪽) 복제
// ───────────────────────────────────────────────────────────────────
function buildOfferR02Html(b: Body): string {
  const docs: string[] = b.docs || [];
  const v = (k: string) => oesc(b[k]);
  const hdr2 = (n: number) =>
    `<div class="hd"><span>■ 공인중개사법 시행규칙 [별지 제20호의2서식] &lt;개정 2021. 12. 31.&gt;</span><span>(4쪽 중 제${n}쪽)</span></div>`;
  const sp: Party[] = b.sell_parties || [];
  const bp: Party[] = b.buy_parties || [];
  const bks: Broker[] = ((b.brokers || []) as Broker[]).filter(k => k.company || k.owner);
  const partyBlock = (p: Party | undefined, role: string) => `
  <table class="tb sign"><tbody>
    <tr><th class="rh" rowspan="2">${role}</th><th style="width:14%">주소</th><td style="width:36%">${oesc(p?.addr || "")}</td>
      <th style="width:12%">성명</th><td>${oesc(p?.name || "")}<span class="sgn">(서명 또는 날인)</span></td></tr>
    <tr><th>생년월일</th><td>${birth(p?.jumin)}</td><th>전화번호</th><td>${oesc(p?.tel || "")}</td></tr>
  </tbody></table>`;
  const brokerBlock = (k: Broker | undefined) => `
  <table class="tb sign"><tbody>
    <tr><th class="rh" rowspan="3">개업<br>공인중개사</th><th style="width:14%">등록번호</th><td style="width:36%">${oesc(k?.reg_no || "")}</td>
      <th style="width:14%">성명(대표자)</th><td>${oesc(k?.owner || "")}<span class="sgn">(서명 및 날인)</span></td></tr>
    <tr><th>사무소 명칭</th><td>${oesc(k?.company || "")}</td><th>소속공인중개사</th><td>${oesc(k?.belong || "")}<span class="sgn">(서명 및 날인)</span></td></tr>
    <tr><th>사무소 소재지</th><td>${oesc(k?.addr || "")}</td><th>전화번호</th><td>${oesc(k?.tel || "")}</td></tr>
  </tbody></table>`;

  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>중개대상물 확인·설명서[Ⅱ]</title>
<style>
  @page{size:A4;margin:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{margin:0;padding:7mm 9mm;box-sizing:border-box;
    font-family:'AppleGothic','Malgun Gothic','NanumGothic','나눔고딕','돋움',sans-serif;color:#000}
  .pg{width:192mm;min-height:282mm;box-sizing:border-box;display:flex;flex-direction:column}
  .pg + .pg{page-break-before:always}
  .hd{display:flex;justify-content:space-between;font-size:7.6pt;margin-bottom:1mm}
  h1{text-align:center;font-size:14pt;margin:0 0 1mm;font-weight:900;letter-spacing:0.5px}
  .htype{text-align:center;font-size:9pt;margin:0 0 1.5mm;line-height:1.6}
  .tb{width:100%;border-collapse:collapse;table-layout:fixed}
  .tb th,.tb td{border:0.5px solid #000;padding:0.9mm 1.2mm;font-size:8.2pt;line-height:1.38;
    word-break:break-all;vertical-align:middle;text-align:left}
  .tb th{font-weight:700;text-align:center;background:#fff}
  .tb th.rh{width:11%;font-weight:800}
  .sect{font-weight:900;font-size:9.5pt;border-bottom:1.6px solid #000;padding:1.2mm 0 0.6mm;margin-top:1.6mm}
  .gray{background:#e8e8e8;text-align:center;font-weight:800}
  b{font-weight:900}
  .nt{font-size:7.3pt;line-height:1.4;margin:0.5mm 0}
  .grow{flex:1}
  .sgn{float:right;font-size:7pt;color:#333}
  .att{font-size:8.2pt;line-height:1.5;margin:1.5mm 0;text-align:justify}
</style></head><body>

<div class="pg">
  ${hdr2(1)}
  <h1>중개대상물 확인·설명서[Ⅱ] (비주거용 건축물)</h1>
  <div class="htype">( ${ckR(R02_GUBUN.slice(0, 3), b.gubun2, "&nbsp;")} ${ckR(R.offer_section, b.offer_section, "&nbsp;")} ${ck(String(b.gubun2) === "4", "그 밖의 경우")} )</div>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">확인·설명<br>자료</th>
      <th style="width:15%">확인·설명<br>근거자료 등</th>
      <td colspan="4">${DOCS_R02.slice(0, 7).map(d => ck(docs.includes(d), d)).join(" ")} ${ck(docs.includes("그 밖의 자료"), `그 밖의 자료(${v("etc_document_cont") || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"})`)}</td></tr>
    <tr><th>대상물건의<br>상태에 관한<br>자료요구 사항</th><td colspan="4">${v("material_request")}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><td colspan="2" class="gray">유의사항</td></tr>
    <tr><th class="rh" style="width:20%">개업공인중개사의<br>확인·설명 의무</th>
      <td style="font-size:7.6pt">개업공인중개사는 중개대상물에 관한 권리를 취득하려는 중개의뢰인에게 성실·정확하게 설명하고, 토지대장 등본, 등기사항증명서 등 설명의 근거자료를 제시해야 합니다.</td></tr>
    <tr><th class="rh">실제 거래가격<br>신고</th>
      <td style="font-size:7.6pt">「부동산 거래신고 등에 관한 법률」 제3조 및 같은 법 시행령 별표 1 제1호마목에 따른 실제 거래가격은 매수인이 매수한 부동산을 양도하는 경우 「소득세법」 제97조제1항 및 제7항과 같은 법 시행령 제163조제11항제2호에 따라 취득 당시의 실제 거래가액으로 보아 양도차익이 계산될 수 있음을 유의하시기 바랍니다.</td></tr>
  </tbody></table>

  <div class="sect">Ⅰ. 개업공인중개사 기본 확인사항</div>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="9">① 대상물건<br>의 표시</th>
      <th rowspan="3" style="width:10%">토지</th><th style="width:14%">소재지</th><td colspan="4">${v("address")}</td></tr>
    <tr><th rowspan="2">면적(㎡)</th><td rowspan="2" style="width:16%">${v("land_py")}</td><th rowspan="2" style="width:9%">지목</th><th style="width:17%">공부상 지목</th><td>${v("jimok")}</td></tr>
    <tr><th>실제이용 상태</th><td>${v("r_jimok")}</td></tr>
    <tr><th rowspan="6">건축물</th><th>전용면적(㎡)</th><td colspan="2">${v("build_py")}</td><th>대지지분(㎡)</th><td>${v("land_py2")}</td></tr>
    <tr><th rowspan="2">준공년도<br>(증개축년도)</th><td rowspan="2" colspan="2">${v("build_date")}</td><th style="width:17%">건축물대장상 용도</th><td>${v("build1")}</td></tr>
    <tr><th>실제 용도</th><td>${v("build2")}</td></tr>
    <tr><th>구조</th><td colspan="2">${v("build3")}</td><th>방향</th><td>${v("build_eye")} &nbsp;(기준: ${v("build_eye_std")})</td></tr>
    <tr><th>내진설계 적용여부</th><td colspan="2">${b.seidesign ? ckR(["적용", "미적용"], b.seidesign) : ""}</td><th>내진능력</th><td>${v("seicapacity")}</td></tr>
    <tr><th>건축물대장상<br>위반건축물 여부</th><td colspan="2">${ckR(R.wiban, b.wiban)}</td><th>위반내용</th><td>${v("wiban_content")}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="7">② 권리관계</th>
      <th rowspan="3" style="width:12%">등기부<br>기재사항</th><th style="width:9%"></th><th colspan="2">소유권에 관한 사항</th><th colspan="2">소유권 외의 권리사항</th></tr>
    <tr><th>토지</th><td colspan="2">${v("land_in")}</td><td colspan="2"><b>토지</b>&nbsp; ${v("land_out")}</td></tr>
    <tr><th>건축물</th><td colspan="2">${v("build_in")}</td><td colspan="2"><b>건축물</b>&nbsp; ${v("build_out")}</td></tr>
    <tr><th rowspan="3" style="width:8%">민간<br>임대<br>등록<br>여부</th><th>등록</th>
      <td colspan="4">${ck(String(b.prv_rent_gb) === "1", "장기일반민간임대주택")} ${ck(String(b.prv_rent_gb) === "2", "공공지원민간임대주택")}<br>${ck(String(b.prv_rent_gb) === "3", `그 밖의 유형(${v("prv_rent_nm") || "&nbsp;&nbsp;&nbsp;&nbsp;"})`)}</td></tr>
    <tr><td colspan="5">임대의무기간: ${v("rent_period")} &nbsp;&nbsp;&nbsp; 임대개시일: ${v("rent_date")}</td></tr>
    <tr><th>미등록</th><td colspan="4">${ck(String(b.prv_rent_gb) === "4" || !b.prv_rent_gb, "해당사항 없음")}</td></tr>
    <tr><th colspan="2">계약갱신<br>요구권<br>행사여부</th><td colspan="4">${ckR(R.renewal_r02, b.renewal_gb)}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="5">③ 토지이용<br>계획, 공법<br>상 이용제한<br>및 거래규제<br>에 관한 사<br>항(토지)</th>
      <th rowspan="3" style="width:10%">지역·<br>지구</th><th style="width:12%">용도지역</th><td colspan="2">${v("yongdo_jiyok")}</td><th style="width:13%">건폐율 상한</th><th style="width:13%">용적률 상한</th></tr>
    <tr><th>용도지구</th><td colspan="2">${v("yongdo_jigu")}</td><td rowspan="2" style="text-align:right">${v("land_build_per")} %</td><td rowspan="2" style="text-align:right">${v("info_per")} %</td></tr>
    <tr><th>용도구역</th><td colspan="2">${v("yongdo_guyok")}</td></tr>
    <tr><th rowspan="2">도시·군<br>계획시설</th><td rowspan="2">${v("city_build")}</td><th style="width:14%">허가·신고<br>구역 여부</th><td colspan="3">${ck(!!b.toji_heoga, "토지거래허가구역")}</td></tr>
    <tr><th>투기지역 여부</th><td colspan="3">${ck(!!b.toji_tugi, "토지투기지역")} ${ck(!!b.jutak_tugi, "주택투기지역")} ${ck(!!b.tugi_kwayol, "투기과열지구")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" style="width:24%">지구단위계획구역,<br>그 밖의 도시·군관리계획</th><td style="width:32%">${v("biz_safe")}</td>
      <th style="width:16%">그 밖의 이용제한<br>및 거래규제사항</th><td>${v("infor")}</td></tr>
  </tbody></table>
  <div class="grow"></div>
  <div class="nt" style="text-align:right">210㎜×297㎜[백상지(80g/㎡) 또는 중질지(80g/㎡)]</div>
</div>

<div class="pg">
  ${hdr2(2)}
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="4">④ 입지조건</th>
      <th style="width:12%">도로와의<br>관계</th><td colspan="2">( ${v("doro") || "&nbsp;&nbsp;m ×&nbsp;&nbsp;m"} )도로에 접함 &nbsp; ${ckR(R.pojang, b.doro_pojang)}</td>
      <th style="width:11%">접근성</th><td>${ckR(R.access, b.doro3)}</td></tr>
    <tr><th rowspan="2">대중교통</th><th style="width:11%">버스</th><td colspan="3">( ${v("bus")} ) 정류장, &nbsp;소요시간: ( ${ckR(R.dobo, b.inwater1)} ) 약 ${v("bus_t")} 분</td></tr>
    <tr><th>지하철</th><td colspan="3">( ${v("subway")} ) 역, &nbsp;소요시간: ( ${ckR(R.dobo, b.inwater2)} ) 약 ${v("subway_t")} 분</td></tr>
    <tr><th>주차장</th><td colspan="4">${ck(String(b.carzone) === "1", "없음")} ${ck(String(b.carzone) === "2", "전용주차시설")} ${ck(String(b.carzone) === "3", "공동주차시설")} ${ck(String(b.carzone) === "4", `그 밖의 주차시설 (${v("carzone_etc")})`)}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh">⑤ 관리에<br>관한사항</th>
      <th style="width:12%">경비실</th><td style="width:24%">${ckR(R.safer, b.safer)}</td><th style="width:11%">관리주체</th><td>${ckR(R.safer2, b.safer2)}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">⑥ 거래예정금액 등</th>
      <th style="width:15%">거래예정금액</th><td colspan="3">${won(b.cost)}</td></tr>
    <tr><th>개별공시지가<br>(㎡당)</th><td>${won(b.person_gongsi_jiga)}</td><th style="width:14%">건물(주택)<br>공시가격</th><td>${won(b.build_gongsi_price)}</td></tr>
  </tbody></table>

  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2" style="width:22%">⑦ 취득 시 부담할<br>조세의 종류 및 세율</th>
      <th style="width:10%">취득세</th><td style="width:12%;text-align:right">${v("real_property_tax")} %</td>
      <th style="width:13%">농어촌특별세</th><td style="width:12%;text-align:right">${v("farm_tax")} %</td>
      <th style="width:12%">지방교육세</th><td style="text-align:right">${v("education_tax")} %</td></tr>
    <tr><td colspan="6">※ 재산세와 종합부동산세는 6월 1일 기준 대상물건 소유자가 납세의무를 부담</td></tr>
  </tbody></table>

  <div class="sect">Ⅱ. 개업공인중개사 세부 확인사항</div>
  <table class="tb"><tbody>
    <tr><th style="text-align:left;background:#fff;border-bottom:0.5px solid #000">⑧ 실제 권리관계 또는 공시되지 않은 물건의 권리 사항</th></tr>
    <tr><td style="height:24mm;vertical-align:top">${v("etc1")}</td></tr>
  </tbody></table>

  <table class="tb" style="margin-top:1.5mm"><tbody>
    <tr><th class="rh" rowspan="10">⑨ 내부·외<br>부 시설물의<br>상태<br>(건축물)</th>
      <th rowspan="2" style="width:12%">수도</th><th style="width:13%">파손 여부</th><td colspan="3">${ckR(R.water_p, b.water_p)} ${b.water_pos ? `(위치: ${v("water_pos")})` : "(위치:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th>용수량</th><td colspan="3">${ckR(R.water_su, b.water_su)} ${b.water_su_pos ? `(위치: ${v("water_su_pos")})` : "(위치:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th>전기</th><th>공급상태</th><td colspan="3">${ckR(R.elect, b.elect)} ${b.elect_part ? `(교체할 부분: ${v("elect_part")})` : "(교체할 부분:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th>가스(취사용)</th><th>공급방식</th><td colspan="3">${ck(String(b.gas) === "1", "도시가스")} &nbsp; ${ck(String(b.gas) === "2", `그 밖의 방식 (${v("gas_etc")})`)}</td></tr>
    <tr><th rowspan="2">소방</th><th>소화전</th><td colspan="3">${ck(String(b.fire_hydrant) === "1", "없음")} &nbsp; ${ck(String(b.fire_hydrant) === "2", `있음 (위치: ${v("fire_hydrant_pos")})`)}</td></tr>
    <tr><th>비상벨</th><td colspan="3">${ck(String(b.emergency_bell) === "1", "없음")} &nbsp; ${ck(String(b.emergency_bell) === "2", `있음 (위치: ${v("emergency_bell_pos")})`)}</td></tr>
    <tr><th rowspan="2">난방방식 및<br>연료공급</th><th>공급방식</th>
      <td>${ck(String(b.boil) === "1", "중앙공급")} ${ck(String(b.boil) === "2", "개별공급")}</td>
      <th style="width:11%">시설작동</th>
      <td>${ck(String(b.boil_etc2) === "1", "정상")} ${ck(String(b.boil_etc2) === "2", `수선 필요 (${v("boil_fix")})`)}<br>※개별공급인 경우 사용연한 ( ${v("use_term")} ) ${ck(!!b.use_term_na, "확인불가")}</td></tr>
    <tr><th>종류</th><td colspan="3">${ck(String(b.boil_etc) === "1", "도시가스")} ${ck(String(b.boil_etc) === "2", "기름")} ${ck(String(b.boil_etc) === "3", "프로판가스")} ${ck(String(b.boil_etc) === "4", "연탄")} ${ck(String(b.boil_etc) === "5", "그 밖의 종류(&nbsp;&nbsp;&nbsp;)")}</td></tr>
    <tr><th colspan="2">승강기</th><td colspan="3">${ck(String(b.eleb) === "1", "있음")} &nbsp;( ${ck(String(b.eleb_state) === "1", "양호")} ${ck(String(b.eleb_state) === "2", "불량")} ) &nbsp;&nbsp; ${ck(String(b.eleb) === "2", "없음")}</td></tr>
    <tr><th colspan="2">배수</th><td colspan="3">${ck(String(b.baesu) === "1", "정상")} ${ck(String(b.baesu) === "2", `수선 필요(${v("baesu_p")})`)}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" style="width:23%">그 밖의 시설물</th><td>${v("etc_struct")}</td></tr>
  </tbody></table>

  <table class="tb" style="margin-top:1.5mm"><tbody>
    <tr><th class="rh" rowspan="3">⑩ 벽면 및<br>바닥면</th>
      <th rowspan="2" style="width:12%">벽면</th><th style="width:13%">균열</th><td>${ckR(R.water_p, b.crack)} ${b.crack_t ? `(위치: ${v("crack_t")})` : "(위치:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th>누수</th><td>${ckR(R.water_p, b.leak)} ${b.leak_t ? `(위치: ${v("leak_t")})` : "(위치:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)"}</td></tr>
    <tr><th colspan="2">바닥면</th><td>${ck(String(b.bottom) === "1", "깨끗함")} ${ck(String(b.bottom) === "2", "보통임")} ${ck(String(b.bottom) === "3", `수리 필요 (위치: ${v("bottom_t")})`)}</td></tr>
  </tbody></table>
  <div class="grow"></div>
</div>

<div class="pg">
  ${hdr2(3)}
  <div class="sect">Ⅲ. 중개보수 등에 관한 사항</div>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="4">⑪ 중개보수<br>및 실비의금<br>액과 산출내<br>역</th>
      <th style="width:13%">중개보수</th><td style="width:37%">${won(b.charge)}</td>
      <td rowspan="4" style="vertical-align:top;font-size:7.8pt">&lt;산출내역&gt;<br><br>중개보수: ${v("susuryo")}<br><br>실&nbsp;&nbsp;&nbsp;&nbsp;비: ${v("silbi_comment")}</td></tr>
    <tr><th>실비</th><td>${won(b.expense)}</td></tr>
    <tr><th>계</th><td>${won(b.t_cost)}</td></tr>
    <tr><th>지급시기</th><td>${v("charge_sigi")}</td></tr>
  </tbody></table>

  <div class="att">「공인중개사법」 제25조제3항 및 제30조제5항에 따라 거래당사자는 개업공인중개사로부터 위 중개대상물에 관한 확인·설명 및 손해배상책임의 보장에 관한 설명을 듣고, 같은 법 시행령 제21조제3항에 따른 본 확인·설명서와 같은 법 시행령 제24조제2항에 따른 손해배상책임 보장 증명서류(사본 또는 전자문서)를 수령합니다.</div>
  <div style="text-align:right;font-size:9pt;margin:1mm 0 2mm">${dateK(b.wdate)}</div>

  ${sp.length ? sp.map(p => partyBlock(p, "매도인<br>(임대인)")).join("") : partyBlock(undefined, "매도인<br>(임대인)")}
  ${bp.length ? bp.map(p => partyBlock(p, "매수인<br>(임차인)")).join("") : partyBlock(undefined, "매수인<br>(임차인)")}
  ${bks.length ? bks.map(k => brokerBlock(k)).join("") : brokerBlock(undefined)}
  ${bks.length < 2 ? brokerBlock(undefined) : ""}
  <div class="grow"></div>
</div>
</body></html>`;
}

// ───────────────────────────────────────────────────────────────────
// 인쇄 — 별지 제20호의3서식 <개정 2020.2.21> (토지, 본문 2쪽) 법정 양식 복제
// KSRC: law.go.kr flSeq=82247907 (hanbang/sample/확인설명서양식/별지20호의3_토지_20200221.pdf)
// ───────────────────────────────────────────────────────────────────
const OFFER_CSS_R34 = `
  @page{size:A4;margin:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{margin:0;padding:8mm 10mm;box-sizing:border-box;
    font-family:'AppleGothic','Malgun Gothic','NanumGothic','나눔고딕','돋움',sans-serif;color:#000}
  .pg{width:190mm;min-height:280mm;box-sizing:border-box;display:flex;flex-direction:column}
  .pg + .pg{page-break-before:always}
  .hd{display:flex;justify-content:space-between;font-size:7.8pt;margin-bottom:1mm}
  h1{text-align:center;font-size:14.5pt;margin:0 0 1mm;font-weight:900}
  .htype{text-align:center;font-size:9.5pt;margin:0 0 2mm}
  .tb{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:1.2mm}
  .tb th,.tb td{border:0.5px solid #000;padding:1.2mm 1.5mm;font-size:8.2pt;word-break:break-all;vertical-align:middle}
  .tb th{font-weight:700;text-align:center;background:#f5f5f5}
  .tb th.rh{width:16%}
  .sh{font-weight:900;font-size:10pt;margin:2.5mm 0 0.5mm}
  .notice{background:#e8e8e8;border:0.5px solid #000;text-align:center;font-weight:900;font-size:9pt;padding:1mm}
  .small{font-size:7.6pt}
  .grow{flex:1}
  .sgn{float:right;font-size:7pt;color:#333}
  .agree{font-size:8.6pt;line-height:1.6;text-align:justify;margin:2.5mm 0 1mm}
  b{font-weight:900}`;

function offerSignR34(b: Body): string {
  const sp: Party[] = b.sell_parties || [];
  const bp: Party[] = b.buy_parties || [];
  const bks: Broker[] = ((b.brokers || []) as Broker[]).filter(k => k.company || k.owner);
  const party = (p: Party | undefined, role: string) => `
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">${role}</th><th style="width:14%">주소</th><td style="width:36%">${oesc(p?.addr || "")}</td>
      <th style="width:12%">성명</th><td>${oesc(p?.name || "")}<span class="sgn">(서명 또는 날인)</span></td></tr>
    <tr><th>생년월일</th><td>${birth(p?.jumin)}</td><th>전화번호</th><td>${oesc(p?.tel || "")}</td></tr>
  </tbody></table>`;
  const broker = (k: Broker | undefined) => `
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="3">개업<br>공인중개사</th><th style="width:14%">등록번호</th><td style="width:36%">${oesc(k?.reg_no || "")}</td>
      <th style="width:14%">성명(대표자)</th><td>${oesc(k?.owner || "")}<span class="sgn">(서명 및 날인)</span></td></tr>
    <tr><th>사무소 명칭</th><td>${oesc(k?.company || "")}</td><th>소속공인중개사</th><td>${oesc(k?.belong || "")}<span class="sgn">(서명 및 날인)</span></td></tr>
    <tr><th>사무소 소재지</th><td>${oesc(k?.addr || "")}</td><th>전화번호</th><td>${oesc(k?.tel || "")}</td></tr>
  </tbody></table>`;
  return `
  <div class="agree">「공인중개사법」 제25조제3항 및 제30조제5항에 따라 거래당사자는 개업공인중개사로부터 위 중개대상물에 관한
  확인·설명 및 손해배상책임의 보장에 관한 설명을 듣고, 같은 법 시행령 제21조제3항에 따른 본 확인·설명서와 같은 법
  시행령 제24조제2항에 따른 손해배상책임 보장 증명서류(사본 또는 전자문서)를 수령합니다.
  <div style="text-align:right;margin-top:1mm">${dateK(b.wdate)}</div></div>
  ${party(sp[0], "매도인<br>(임대인)")}
  ${party(bp[0], "매수인<br>(임차인)")}
  ${broker(bks[0])}
  ${broker(bks[1])}`;
}

function offerHeadR34(b: Body, title: string): string {
  const isRent = String(b.offer_section) === "2";
  const docs: string[] = b.docs || [];
  return `
  <h1>${title}</h1>
  <div class="htype">( ${ck(!isRent, "매매·교환")} &nbsp;&nbsp; ${ck(isRent, "임대")} )</div>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">확인·설명<br>자료</th><th style="width:16%">확인·설명<br>근거자료 등</th>
      <td colspan="2" class="small">${DOCS_R34.map(d => ck(docs.includes(d), d)).join(" &nbsp;")} &nbsp;[&nbsp;&nbsp;]그 밖의 자료(&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)</td></tr>
    <tr><th>대상물건의 상태에<br>관한 자료요구 사항</th><td colspan="2">${oesc(b.material_request || "")}</td></tr>
  </tbody></table>
  <div class="notice" style="margin-top:1.5mm">유의사항</div>
  <table class="tb" style="margin-top:0"><tbody>
    <tr><th class="rh">개업공인중개사의<br>확인·설명 의무</th><td class="small">개업공인중개사는 중개대상물에 관한 권리를 취득하려는 중개의뢰인에게 성실·정확하게 설명하고,
      토지대장등본, 등기사항증명서 등 설명의 근거자료를 제시해야 합니다.</td></tr>
    <tr><th>실제 거래가격<br>신고</th><td class="small">「부동산 거래신고 등에 관한 법률」 제3조 및 같은 법 시행령 제3조제1항제5호에 따른 실제 거래가격은
      매수인이 매수한 부동산을 양도하는 경우 「소득세법」 제97조제1항 및 제7항과 같은 법 시행령 제163조제11항제2호에 따라
      취득 당시의 실제 거래가액으로 보아 양도차익이 계산될 수 있음을 유의하시기 바랍니다.</td></tr>
  </tbody></table>`;
}

function offerMoneyTaxR34(b: Body, no1: string, no2: string): string {
  const v = (k: string) => oesc(b[k]);
  return `
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">${no1} 거래예정금액 등</th><th style="width:18%">거래예정금액</th><td colspan="3">${won(b.cost)}</td></tr>
    <tr><th>개별공시지가(㎡당)</th><td>${v("person_gongsi_jiga")}</td><th style="width:18%">건물(주택)공시가격</th><td>${v("build_gongsi_price")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">${no2} 취득 시 부담할<br>조세의 종류 및 세율</th>
      <th style="width:10%">취득세</th><td style="width:12%;text-align:right">${v("real_property_tax")} %</td>
      <th style="width:14%">농어촌특별세</th><td style="width:12%;text-align:right">${v("farm_tax")} %</td>
      <th style="width:12%">지방교육세</th><td style="text-align:right">${v("education_tax")} %</td></tr>
    <tr><td colspan="6" class="small">※ 재산세는 6월 1일 기준 대상물건 소유자가 납세의무를 부담</td></tr>
  </tbody></table>`;
}

function offerFeeR34(b: Body, no: string): string {
  const v = (k: string) => oesc(b[k]);
  return `
  <div class="sh">Ⅲ. 중개보수 등에 관한 사항</div>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="4">${no} 중개보수 및 실비의<br>금액과 산출내역</th>
      <th style="width:14%">중개보수</th><td style="width:30%;text-align:right">${won(b.charge)}</td>
      <td rowspan="4" colspan="2" style="vertical-align:top" class="small">&lt;산출내역&gt;<br>
        중개보수: ${v("susuryo")}<br><br>실&nbsp;&nbsp;&nbsp;&nbsp;비: ${v("silbi_comment")}<br><br>
        ※ 중개보수는 거래금액의 1천분의 9 이내에서 중개의뢰인과 개업공인중개사가 서로 협의하여 결정하며,
        부가가치세는 별도로 부과될 수 있습니다.</td></tr>
    <tr><th>실비</th><td style="text-align:right">${won(b.expense)}</td></tr>
    <tr><th>계</th><td style="text-align:right">${won(b.t_cost)}</td></tr>
    <tr><th>지급시기</th><td>${v("charge_sigi")}</td></tr>
  </tbody></table>`;
}

export function buildOfferR03Html(b: Body): string {
  const v = (k: string) => oesc(b[k]);
  const hdr = (n: number) =>
    `<div class="hd"><span>■ 공인중개사법 시행규칙 [별지 제20호의3서식] &lt;개정 2020. 2. 21.&gt;</span><span>(3쪽 중 제${n}쪽)</span></div>`;
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>중개대상물 확인·설명서[Ⅲ] 토지</title>
<style>${OFFER_CSS_R34}</style></head><body>
<div class="pg">
  ${hdr(1)}
  ${offerHeadR34(b, "중개대상물 확인·설명서[Ⅲ] (토지)")}
  <div class="sh">Ⅰ. 개업공인중개사 기본 확인사항</div>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">① 대상물건의 표시</th><th rowspan="2" style="width:10%">토지</th>
      <th style="width:12%">소재지</th><td colspan="4">${v("address")}</td></tr>
    <tr><th>면적(㎡)</th><td style="width:18%">${v("land_py")}</td>
      <th style="width:10%">지목</th><td class="small">공부상 지목: ${v("jimok")}<br>실제이용 상태: ${v("r_jimok")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">② 권리관계</th><th rowspan="2" style="width:12%">등기부<br>기재사항</th>
      <th style="width:14%">소유권에 관한 사항</th><td>${v("land_in")}</td></tr>
    <tr><th>소유권 외의 권리사항</th><td>${v("land_out")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="5">③ 토지이용계획,<br>공법상 이용 제한 및<br>거래규제에 관한 사항<br>(토지)</th>
      <th rowspan="3" style="width:12%">지역·지구</th><th style="width:12%">용도지역</th><td colspan="2">${v("yongdo_jiyok")}</td>
      <th style="width:13%">건폐율 상한</th><th style="width:13%">용적률 상한</th></tr>
    <tr><th>용도지구</th><td colspan="2">${v("yongdo_jigu")}</td>
      <td rowspan="2" style="text-align:right">${v("land_build_per")} %</td><td rowspan="2" style="text-align:right">${v("info_per")} %</td></tr>
    <tr><th>용도구역</th><td colspan="2">${v("yongdo_guyok")}</td></tr>
    <tr><th style="width:12%">도시·군계획 시설</th><td style="width:22%">${v("city_build")}</td>
      <th style="width:14%">허가·신고<br>구역 여부</th><td colspan="3">${ck(!!b.toji_heoga, "토지거래허가구역")}</td></tr>
    <tr><th>투기지역 여부</th><td colspan="5">${ck(!!b.toji_tugi, "토지투기지역")} &nbsp;${ck(!!b.jutak_tugi, "주택투기지역")} &nbsp;${ck(!!b.tugi_kwayol, "투기과열지구")}</td></tr>
  </tbody></table>
  <table class="tb" style="margin-top:0"><tbody>
    <tr><th class="rh" style="width:28%">지구단위계획구역,<br>그 밖의 도시·군관리계획</th><td style="width:26%">${v("biz_safe")}</td>
      <th style="width:20%">그 밖의 이용제한 및<br>거래규제사항</th><td>${v("infor")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="3">④ 입지조건</th><th style="width:14%">도로와의 관계</th>
      <td colspan="3">( ${v("doro")} ) 도로에 접함 &nbsp; ${ckR(R.pojang, b.doro_pojang)}</td>
      <th style="width:11%">접근성</th><td>${ckR(R.access, b.doro3)}</td></tr>
    <tr><th rowspan="2">대중교통</th><th style="width:9%">버스</th>
      <td colspan="2">( ${v("bus")} ) 정류장, &nbsp;소요시간: ( ${ckR(R.dobo, b.inwater1)} ) 약 ${v("bus_t")} 분</td><td colspan="2"></td></tr>
    <tr><th>지하철</th><td colspan="2">( ${v("subway")} ) 역, &nbsp;소요시간: ( ${ckR(R.dobo, b.inwater2)} ) 약 ${v("subway_t")} 분</td><td colspan="2"></td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh">⑤ 비선호시설(1㎞이내)</th>
      <td>${ck(String(b.noview_s) === "1", "없음")} &nbsp;&nbsp;${ck(String(b.noview_s) === "2", `있음(종류 및 위치: ${oesc(b.noview || "")})`)}</td></tr>
  </tbody></table>
  ${offerMoneyTaxR34(b, "⑥", "⑦")}
  <div class="grow"></div>
</div>
<div class="pg">
  ${hdr(2)}
  <div class="sh">Ⅱ. 개업공인중개사 세부 확인사항</div>
  <table class="tb"><tbody>
    <tr><th class="rh" style="width:24%">⑧ 실제 권리관계<br>또는 공시되지 않은<br>물건의 권리 사항</th>
      <td style="height:26mm;vertical-align:top">${v("etc1")}</td></tr>
  </tbody></table>
  ${offerFeeR34(b, "⑨")}
  ${offerSignR34(b)}
  <div class="grow"></div>
</div>
</body></html>`;
}

// ───────────────────────────────────────────────────────────────────
// 인쇄 — 별지 제20호의4서식 <개정 2017.6.8> (입목·광업재단·공장재단, 본문 2쪽) 법정 양식 복제
// KSRC: law.go.kr flSeq=42848904 (hanbang/sample/확인설명서양식/별지20호의4_재단_20170608.pdf)
// ───────────────────────────────────────────────────────────────────
export function buildOfferR04Html(b: Body): string {
  const v = (k: string) => oesc(b[k]);
  const hdr = (n: number) =>
    `<div class="hd"><span>■ 공인중개사법 시행규칙 [별지 제20호의4서식] &lt;개정 2017. 6. 8.&gt;</span><span>(3쪽 중 제${n}쪽)</span></div>`;
  const kinds = ["입목", "광업재단", "공장재단"];
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>중개대상물 확인·설명서[Ⅳ]</title>
<style>${OFFER_CSS_R34}</style></head><body>
<div class="pg">
  ${hdr(1)}
  ${offerHeadR34(b, "중개대상물 확인·설명서[Ⅳ] (입목·광업재단·공장재단)")}
  <div class="sh">Ⅰ. 개업공인중개사 기본 확인사항</div>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="2">① 대상물건의 표시</th><th rowspan="2" style="width:10%">토지</th>
      <th style="width:16%">대상물 종별</th><td>${kinds.map((k, i) => ck(String(b.r4_kind) === String(i + 1), k)).join(" &nbsp;&nbsp;")}</td></tr>
    <tr><th>소재지<br>(등기·등록지)</th><td>${v("address")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" rowspan="3">② 권리관계</th><th rowspan="3" style="width:12%">등기부<br>기재사항</th>
      <th rowspan="2" style="width:16%">소유권에 관한 사항</th><th style="width:10%">성명</th><td>${v("r4_own_name")}</td></tr>
    <tr><th>주소</th><td>${v("r4_own_addr")}</td></tr>
    <tr><th>소유권 외의 권리사항</th><td colspan="2" style="height:16mm;vertical-align:top">${v("land_out")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" style="width:22%">③ 재단목록 또는<br>입목의 생육상태</th><td style="height:24mm;vertical-align:top">${v("r4_list")}</td></tr>
  </tbody></table>
  <table class="tb"><tbody>
    <tr><th class="rh" style="width:22%">④ 그 밖의 참고사항</th><td style="height:20mm;vertical-align:top">${v("r4_etc")}</td></tr>
  </tbody></table>
  <div class="grow"></div>
</div>
<div class="pg">
  ${hdr(2)}
  ${offerMoneyTaxR34(b, "⑤", "⑥")}
  <div class="sh">Ⅱ. 개업공인중개사 세부 확인사항</div>
  <table class="tb"><tbody>
    <tr><th class="rh" style="width:24%">⑦ 실제권리관계 또는<br>공시되지 않은<br>물건의 권리 사항</th>
      <td style="height:24mm;vertical-align:top">${v("etc1")}</td></tr>
  </tbody></table>
  ${offerFeeR34(b, "⑧")}
  ${offerSignR34(b)}
  <div class="grow"></div>
</div>
</body></html>`;
}
