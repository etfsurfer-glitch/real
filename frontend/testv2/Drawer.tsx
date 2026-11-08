// 단지 서랍 — 요약(역대 최고가·최근 실거래·실매물·역·학교) · 급매 · 실거래(매매+분양권·전세·월세, 신고가·등기·갱신권) ·
// 호가추이(매물수·평균 호가) · 인근단지 · 중개사 · 단지정보(건축물대장·평형별 호가·같은 건물).
import { useEffect, useMemo, useState, type ReactNode } from "react";
import type React from "react";
import { ComposedChart, Scatter, Line, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { wonShort } from "../src/lib/kakaomap";
import { areaLabel } from "../src/lib/area";
import { RequestModal, type ReqTarget } from "./Request";

export const API = "https://api.koczip.com";
const SITE = "https://koczip.com";
export const getJson = (u: string) => fetch(API + u).then((r) => (r.ok ? r.json() : Promise.reject(r.status)));
const q = (body: object) => fetch(API + "/q", { method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body) }).then((r) => r.json()).then((j) => j.data);
const pct = (r: number | null | undefined, d = 1) => (r == null ? "-" : `${r > 0 ? "+" : ""}${(r * 100).toFixed(d)}%`);
const ymdDot = (s: string | null | undefined) => (s ? s.slice(2, 10).replace(/-/g, ".") : "-");
const ymd8 = (s: string | null | undefined) => (s && s.length >= 8 ? `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}` : "-");

export type DrawerCx = { complex_no: string; name: string; lat: number; lng: number; households?: number; listings?: number };

type Info = {
  complex_name: string; real_estate_type_name?: string; cortar_no?: string; road_address?: string; raw?: string;
  total_household_count?: number; total_building_count?: number; high_floor?: number; low_floor?: number;
  use_approve_ymd?: string; batl_ratio?: number; btl_ratio?: number; parking_per_household?: number;
  parking_possible_count?: number; construction_company?: string; management_office_tel?: string;
};
type AggRow = { area_name: string; trade_type: string; listing_count: number; price_min: number; price_max: number; price_avg?: number | null;
  rent_min?: number | null; rent_max?: number | null; rent_avg?: number | null };
type Area = { pyeong_name: string; supply_area: number; exclusive_area: number; household_count: number };
type DealRow = {
  article_no: string; area_name: string; floor_info: string; direction?: string; price: number; price_text: string;
  discount: number; avg_real: number; n_real: number; realtor_id: string; realtor_name: string; tel?: string;
  confirm_ymd?: string; naver_url?: string; dong?: string; realtor_count?: number; dup_count?: number;
  // 콕집 직접 등록 매물 표시용 — 원천이 생기면 서버가 채운다(지금은 없음)
  koczip?: boolean; source?: string; kok_url?: string;
};
// /complex/{no}/summary 중 서랍이 쓰는 부분
type Summary = {
  region?: string;
  record_high?: { area_key: number; price: number; date: string; prev_high: number | null } | null;
  recent_tx?: { date: string; price: number; area: number; floor: number; is_silv: boolean }[];
  listing_counts?: { A1: number; B1: number; B2: number; total: number };
  listing_units?: { A1: number; B1: number; B2: number; total: number };
  subway?: { station: string; lines: string; distance_m: number; walk_min: number } | null;
  school?: { name: string; names_all: string; n: number; distance_m: number; walk_min: number; src: string } | null;
};

// 드롭다운 칩: 버튼 하나 + 눌렀을 때만 메뉴. 지도 필터 바와 서랍 필터가 같이 쓴다.
export function Dd({ id, open, setOpen, label, active, children }: { id: string; open: string | null; setOpen: (v: string | null) => void; label: string; active: boolean; children: ReactNode }) {
  // 메뉴는 버튼 자리에서 fixed 로 띄운다 — 바·서랍의 overflow 에 잘리지 않게
  const [pos, setPos] = useState({ l: 0, t: 0 });
  const toggle = (e: React.MouseEvent<HTMLButtonElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    setPos({ l: Math.max(8, Math.min(r.left, window.innerWidth - 200)), t: r.bottom + 4 });
    setOpen(open === id ? null : id);
  };
  return (
    <span className="t2-dd">
      <button className={"t2-fdd" + (active ? " on" : "")} aria-expanded={open === id} onClick={toggle}>{label}<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
      {open === id && <span className="t2-ddm" style={{ "--dd-l": `${pos.l}px`, "--dd-t": `${pos.t}px` } as React.CSSProperties} onClick={() => setOpen(null)}>{children}</span>}
    </span>
  );
}

export function Skel() {
  return <div className="t2-skel"><i /><i /><i /></div>;
}

export type DrawerTab = "deals" | "tx" | "hoga" | "nearby" | "realtor" | "info";

// initialTab: 지도 레이어에 맞춰 시작 탭을 정한다(매물찾기→급매, 시세분석→실거래, 중개사랭킹→중개사). 단지가 바뀌면 다시 적용.
// onPick: 인근단지·같은 건물에서 다른 단지를 고르면 지도가 그 단지로 옮겨 간다.
export function ComplexDrawer({ cx, onClose, onPick, initialTab = "deals" }: { cx: DrawerCx; onClose: () => void; onPick?: (c: DrawerCx) => void; initialTab?: DrawerTab }) {
  const [tab, setTab] = useState<DrawerTab>(initialTab);
  const [info, setInfo] = useState<Info | null>(null);
  const [sum, setSum] = useState<Summary | null>(null);
  const [agg, setAgg] = useState<AggRow[] | null>(null);
  const [areas, setAreas] = useState<Area[]>([]);
  const [deals, setDeals] = useState<DealRow[] | null>(null);
  const [tx, setTx] = useState<{ sale: any[]; jeonse: any[]; wolse: any[] } | null>(null);
  const [rk, setRk] = useState<any[] | null>(null);
  const [req, setReq] = useState<ReqTarget | null>(null);

  useEffect(() => {
    const no = cx.complex_no;
    setTab(initialTab);
    setInfo(null); setSum(null); setAgg(null); setAreas([]); setDeals(null); setTx(null); setRk(null);
    q({ table: "complexes", select: "*", filters: [{ op: "eq", col: "complex_no", val: no }], limit: 1, single: true })
      .then(setInfo).catch(() => {});
    getJson(`/complex/${no}/summary`).then(setSum).catch(() => setSum({}));
    q({ table: "complex_daily_agg", select: "snapshot_date", filters: [{ op: "eq", col: "complex_no", val: no }],
      order: { col: "snapshot_date", ascending: false }, limit: 1 })
      .then((d) => d?.[0]?.snapshot_date
        ? q({ table: "complex_daily_agg", select: "*", filters: [{ op: "eq", col: "complex_no", val: no },
            { op: "eq", col: "snapshot_date", val: d[0].snapshot_date }] }) : [])
      .then((rows) => setAgg(rows || [])).catch(() => setAgg([]));
    getJson(`/complex/${no}/areas`).then((j) => setAreas(j.items || [])).catch(() => {});
    getJson(`/complex/${no}/quick-deals?min_discount=0.03`).then((j) => setDeals(j.items || [])).catch(() => setDeals([]));
    getJson(`/complex/${no}/transactions?months=36`).then((j) => {
      // 분양권·입주권 거래는 매매 목록에 섞어 보인다(신축 단지는 이것뿐이라 비어 보이던 것)
      const silv = (j.silv || []).map((s: any) => ({ ...s, silv: s.kind || "분양권" }));
      setTx({ sale: [...(j.sale || []), ...silv].sort((a: any, b: any) => (b.deal_ymd || "").localeCompare(a.deal_ymd || "")),
        jeonse: j.jeonse || [], wolse: j.wolse || [] });
    }).catch(() => setTx({ sale: [], jeonse: [], wolse: [] }));
    getJson(`/complex/${no}/realtors?limit=50`).then((j) => setRk(j.items || [])).catch(() => setRk([]));
  }, [cx.complex_no]);   // eslint-disable-line react-hooks/exhaustive-deps

  // 평형 이름(84A 등) → 전용㎡
  const exclOf = useMemo(() => new Map(areas.map((a) => [a.pyeong_name, a.exclusive_area])), [areas]);
  const cnt = useMemo(() => {
    const c = { A1: 0, B1: 0, B2: 0 } as Record<string, number>;
    (agg || []).forEach((r) => { c[r.trade_type] = (c[r.trade_type] || 0) + r.listing_count; });
    return c;
  }, [agg]);
  const raw = useMemo(() => { try { return JSON.parse(info?.raw || "{}"); } catch { return {}; } }, [info]);
  const name = info?.complex_name || cx.name;
  const ymd = info?.use_approve_ymd || "";
  const age = ymd ? new Date().getFullYear() - +ymd.slice(0, 4) : null;
  const regionName = { name, cortar: info?.cortar_no || "", addr: raw.cortarAddress || "" };
  const asset = (info?.real_estate_type_name || "").includes("오피스텔") ? "offi" : "apt";
  const rh = sum?.record_high, rt = sum?.recent_tx?.[0];
  const units = sum?.listing_units?.total;

  return (
    <div className="t2-dr">
      <div className="t2-dr-h">
        <div className="t2-dr-ttl">
          <h2>{name}</h2>
          <p>{[info?.real_estate_type_name, raw.cortarAddress, info?.road_address].filter(Boolean).join(" · ")}</p>
        </div>
        <button className="t2-x" onClick={onClose} aria-label="닫기">×</button>
      </div>
      {/* 역·학교: 운영 단지 페이지의 위치 칩 */}
      {(sum?.subway || sum?.school) && (
        <div className="t2-loc">
          {sum?.subway && <span><i className="st">역</i>{sum.subway.station} <small>{sum.subway.lines.split("·")[0]} · 도보 {sum.subway.walk_min}분</small></span>}
          {sum?.school && <span><i className="sc">초</i>{sum.school.src === "near" ? "인근 " : ""}{sum.school.name.replace("등학교", "")}{sum.school.n > 1 ? ` 외 ${sum.school.n - 1}` : ""} <small>도보 {sum.school.walk_min}분</small></span>}
        </div>
      )}
      <dl className="t2-facts">
        <div><dt>준공</dt><dd>{ymd ? `${ymd.slice(0, 4)}.${ymd.slice(4, 6)}` : "-"}{age != null && <small> {age}년차</small>}</dd></div>
        <div><dt>세대</dt><dd>{(info?.total_household_count ?? cx.households)?.toLocaleString() ?? "-"}<small> · {info?.total_building_count ?? "-"}개동</small></dd></div>
        <div><dt>층수</dt><dd>{info?.low_floor && info?.high_floor ? `${info.low_floor}~${info.high_floor}층` : "-"}</dd></div>
        <div><dt>역대 최고가</dt><dd>{rh ? <>{wonShort(rh.price)}<small> {areaLabel(rh.area_key)} · {ymdDot(rh.date).slice(0, 5)}</small></> : sum ? "-" : "…"}</dd></div>
        <div><dt>최근 실거래</dt><dd>{rt ? <>{wonShort(rt.price)}<small> {areaLabel(rt.area)} · {ymdDot(rt.date).slice(0, 5)}{rt.is_silv ? " 분양권" : ""}</small></> : sum ? "-" : "…"}</dd></div>
        <div><dt>매물</dt><dd>
          {agg == null ? "…" : <>매매 <b>{cnt.A1}</b> · 전세 <b>{cnt.B1}</b> · 월세 <b>{cnt.B2}</b>{units != null && <small> · 실매물 {units.toLocaleString()}채</small>}</>}
        </dd></div>
      </dl>
      <div className="t2-tabs" role="tablist">
        {([["deals", `급매${deals ? ` ${deals.length}` : ""}`], ["tx", "실거래"], ["hoga", "호가추이"], ["nearby", "인근단지"], ["realtor", "중개사"], ["info", "단지정보"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      <div className="t2-dr-b">
        {tab === "deals" && <DealsTab deals={deals} exclOf={exclOf} onRequest={(d) => setReq({
          realtor_id: d.realtor_id, realtor_name: d.realtor_name, complex: regionName,
          listing: { article_no: d.article_no, area_name: d.area_name, excl: exclOf.get(d.area_name) ?? null,
            floor_info: d.floor_info, price_text: d.price_text } })} />}
        {tab === "tx" && <TxTab tx={tx} />}
        {tab === "hoga" && <HogaTab no={cx.complex_no} exclOf={exclOf} />}
        {tab === "nearby" && <NearbyTab no={cx.complex_no} areas={areas} onPick={onPick} />}
        {tab === "realtor" && <RealtorTab rk={rk} total={cnt.A1 + cnt.B1 + cnt.B2 || cx.listings || 0}
          onRequest={(r) => setReq({ realtor_id: r.realtor_id, realtor_name: r.realtor_name, complex: regionName })} />}
        {tab === "info" && <InfoTab no={cx.complex_no} asset={asset} info={info} raw={raw} agg={agg} areas={areas} sum={sum} onPick={onPick} />}
      </div>
      <a className="t2-dr-link" href={`${SITE}/complex/${cx.complex_no}`} target="_blank" rel="noreferrer">단지 페이지 전체 보기 ↗</a>
      {req && <RequestModal target={req} onClose={() => setReq(null)} />}
    </div>
  );
}

// ── 급매: 필터 + 카드 ──────────────────────────────────
function floorBand(f: string): "저" | "중" | "고" | "" {
  const [a, b] = (f || "").split("/");
  if (a === "저" || a === "중" || a === "고") return a;
  const n = parseInt(a), t = parseInt(b);
  if (isNaN(n) || isNaN(t) || !t) return "";
  return n / t <= 1 / 3 ? "저" : n / t <= 2 / 3 ? "중" : "고";
}

const SORTS = { disc: "할인 큰 순", price: "가격 낮은 순", recent: "최근 확인 순" } as const;
function DealsTab({ deals, exclOf, onRequest }: { deals: DealRow[] | null; exclOf: Map<string, number>; onRequest: (d: DealRow) => void }) {
  const [type, setType] = useState("");
  const [size, setSize] = useState("");
  const [floor, setFloor] = useState("");
  const [minDisc, setMinDisc] = useState(0.03);
  const [sort, setSort] = useState<keyof typeof SORTS>("disc");
  const [more, setMore] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const opt = (l: string, on: boolean, f: () => void) => <button key={l} className={on ? "on" : ""} onClick={f}>{l}</button>;

  const sizeOf = (d: DealRow) => { const e = exclOf.get(d.area_name); return e ? String(Math.round(e)) : ""; };
  const types = useMemo(() => [...new Set((deals || []).map((d) => d.area_name))].sort((a, b) => parseFloat(a) - parseFloat(b)), [deals]);
  const sizes = useMemo(() => [...new Set((deals || []).map(sizeOf).filter(Boolean))].sort((a, b) => +a - +b), [deals, exclOf]);   // eslint-disable-line react-hooks/exhaustive-deps
  const rows = useMemo(() => {
    let xs = (deals || []).filter((d) => -d.discount >= minDisc - 1e-9
      && (!type || d.area_name === type) && (!size || sizeOf(d) === size) && (!floor || floorBand(d.floor_info) === floor));
    xs = [...xs].sort(sort === "price" ? (a, b) => a.price - b.price
      : sort === "recent" ? (a, b) => (b.confirm_ymd || "").localeCompare(a.confirm_ymd || "")
      : (a, b) => a.discount - b.discount);
    return xs;
  }, [deals, type, size, floor, minDisc, sort, exclOf]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (deals == null) return <Skel />;
  if (deals.length === 0) return <p className="t2-empty">지금 이 단지엔 급매가 없어요.</p>;
  const shown = more ? rows : rows.slice(0, 20);
  return (
    <>
      <div className="t2-dr-flt" onMouseLeave={() => setOpen(null)}>
        <Dd id="size" open={open} setOpen={setOpen} label={size ? areaLabel(+size) : "전용면적"} active={!!size}>
          {opt("전체", !size, () => setSize(""))}
          {sizes.map((x) => opt(areaLabel(+x), size === x, () => setSize(x)))}
        </Dd>
        <Dd id="type" open={open} setOpen={setOpen} label={type || "타입"} active={!!type}>
          {opt("전체", !type, () => setType(""))}
          {types.map((t) => opt(`${t}${exclOf.get(t) ? ` (${areaLabel(exclOf.get(t)!)})` : ""}`, type === t, () => setType(t)))}
        </Dd>
        <Dd id="floor" open={open} setOpen={setOpen} label={floor ? `${floor}층` : "층"} active={!!floor}>
          {opt("전체", !floor, () => setFloor(""))}
          {(["저", "중", "고"] as const).map((f) => opt(`${f}층`, floor === f, () => setFloor(f)))}
        </Dd>
        <Dd id="disc" open={open} setOpen={setOpen} label={`${Math.round(minDisc * 100)}% 이상`} active={minDisc > 0.03}>
          {[0.03, 0.05, 0.1].map((v) => opt(`${Math.round(v * 100)}% 이상`, minDisc === v, () => setMinDisc(v)))}
        </Dd>
        <Dd id="sort" open={open} setOpen={setOpen} label={SORTS[sort]} active={sort !== "disc"}>
          {(Object.keys(SORTS) as (keyof typeof SORTS)[]).map((k) => opt(SORTS[k], sort === k, () => setSort(k)))}
        </Dd>
        {(size || type || floor || minDisc !== 0.03 || sort !== "disc") &&
          <button className="t2-freset" onClick={() => { setSize(""); setType(""); setFloor(""); setMinDisc(0.03); setSort("disc"); }}>초기화</button>}
      </div>
      <p className="t2-note">{rows.length}건 · 할인율은 같은 평형 최근 실거래 평균 대비</p>
      {rows.length === 0 ? <p className="t2-empty">조건에 맞는 급매가 없어요. 필터를 넓혀 보세요.</p> : (
        <ul className="t2-deals">
          {shown.map((d) => {
            const e = exclOf.get(d.area_name);
            const kok = d.koczip === true || d.source === "koczip";
            const others = (d.realtor_count || 1) - 1;
            return (
              <li key={d.article_no} className={kok ? "kok" : ""}>
                <div className="t2-dl-top">
                  <b className="pr">{d.price_text}</b>
                  <span className="dc">{pct(d.discount)}</span>
                  <span className="t2-dl-btns">
                    {kok && <a className="t2-kokbtn" href={d.kok_url || undefined} target="_blank" rel="noreferrer" title="콕집 매물 보기">콕</a>}
                    {d.naver_url && <a className="t2-nbtn" href={d.naver_url} target="_blank" rel="noreferrer" title="네이버 매물 바로가기" aria-label="네이버 매물 바로가기">N</a>}
                  </span>
                </div>
                <div className="t2-dl-mid">
                  {e ? areaLabel(e) : d.area_name} · {d.area_name}타입 · {d.dong ? `${d.dong} · ` : ""}{d.floor_info}층{d.direction ? ` · ${d.direction}` : ""}
                </div>
                <div className="t2-dl-sub">실거래 평균 {wonShort(d.avg_real)} ({d.n_real}건) 대비</div>
                <div className="t2-dl-bot">
                  <span className="rt">{d.realtor_name}{others > 0 && <em> 외 {others}곳</em>}{d.confirm_ymd ? <em> · 확인 {d.confirm_ymd.slice(4, 6)}.{d.confirm_ymd.slice(6, 8)}</em> : null}</span>
                  {d.tel && <a className="t2-telbtn" href={`tel:${d.tel.replace(/[^0-9+]/g, "")}`} title={d.tel}>전화</a>}
                  <button className="t2-reqbtn" onClick={() => onRequest(d)}>콕집요청</button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {!more && rows.length > 20 && <button className="t2-more-btn" onClick={() => setMore(true)}>{rows.length}건 모두 보기</button>}
    </>
  );
}

// ── 실거래: 매매(+분양권)·전세·월세 그래프 + 표 ─────────────────────
type Kind = "sale" | "jeonse" | "wolse";
function TxTab({ tx }: { tx: { sale: any[]; jeonse: any[]; wolse: any[] } | null }) {
  const [kind, setKind] = useState<Kind>("sale");
  const [size, setSize] = useState("");
  const [more, setMore] = useState(false);
  const list = tx ? tx[kind] : [];
  const sizes = useMemo(() => {
    const m = new Map<string, number>();
    list.forEach((t: any) => { const k = String(Math.round(t.excl_use_ar)); m.set(k, (m.get(k) || 0) + 1); });
    return [...m.entries()].sort((a, b) => +a[0] - +b[0]);
  }, [list]);
  useEffect(() => {   // 거래가 가장 많은 면적을 기본으로
    const top = [...sizes].sort((a, b) => b[1] - a[1])[0];
    setSize(top ? top[0] : ""); setMore(false);
  }, [kind, tx]);   // eslint-disable-line react-hooks/exhaustive-deps

  // 신고가: 같은 면적(반올림 ㎡)에서 그 시점까지의 최고가를 넘긴 중개거래(불러온 3년 안에서 판정)
  const rhSet = useMemo(() => {
    const s = new Set<any>();
    if (kind !== "sale") return s;
    const mx = new Map<string, number>();
    [...list].sort((a: any, b: any) => (a.deal_ymd || "").localeCompare(b.deal_ymd || "")).forEach((t: any) => {
      if (t.silv || t.dealing_gbn === "직거래") return;
      const k = String(Math.round(t.excl_use_ar)), prev = mx.get(k);
      if (prev != null && t.deal_amount > prev) s.add(t);
      mx.set(k, Math.max(prev ?? 0, t.deal_amount));
    });
    return s;
  }, [list, kind]);

  const rows = useMemo(() => list.filter((t: any) => !size || String(Math.round(t.excl_use_ar)) === size), [list, size]);
  const val = (t: any) => (kind === "sale" ? t.deal_amount : kind === "jeonse" ? t.deposit : t.monthly_rent) / (kind === "wolse" ? 1e4 : 1e8);
  const unit = kind === "wolse" ? "만원" : "억";
  // 직거래는 '직', 분양권·입주권은 '분'으로 따로 찍는다(시세와 동떨어진 값이 섞이기 쉬움)
  const pts = rows.map((t: any) => ({ x: new Date(t.deal_ymd).getTime(), y: +val(t).toFixed(kind === "wolse" ? 0 : 2),
    direct: t.dealing_gbn === "직거래", silv: t.silv || "", dong: t.dong || "", est: t.dong_est || "", floor: t.floor, reg: !!t.registered, rh: rhSet.has(t) }));
  const ptsBroker = pts.filter((p) => !p.direct && !p.silv), ptsDirect = pts.filter((p) => p.direct && !p.silv), ptsSilv = pts.filter((p) => p.silv);
  const monthly = useMemo(() => {
    const m = new Map<string, number[]>();
    rows.forEach((t: any) => { if (t.dealing_gbn === "직거래" || t.silv) return;   // 중앙값 선은 중개거래만
      const k = t.deal_ymd.slice(0, 7); m.set(k, [...(m.get(k) || []), val(t)]); });
    return [...m.entries()].sort().map(([k, v]) => {
      const s = [...v].sort((a, b) => a - b); const md = s[Math.floor(s.length / 2)];
      return { x: new Date(k + "-15").getTime(), m: +md.toFixed(kind === "wolse" ? 0 : 2) };
    });
  }, [rows]);   // eslint-disable-line react-hooks/exhaustive-deps

  // 날짜축 눈금: 기간에 맞춰 3·6·12개월 간격(자동 눈금은 하나만 찍히거나 빽빽해짐)
  const ticks = useMemo(() => {
    if (!pts.length) return [];
    const lo = Math.min(...pts.map((p) => p.x)), hi = Math.max(...pts.map((p) => p.x));
    const months = (hi - lo) / 2.63e9, step = months > 30 ? 12 : months > 12 ? 6 : 3;
    const d = new Date(lo); d.setDate(1); d.setMonth(Math.ceil(d.getMonth() / step) * step);
    const out: number[] = [];
    while (d.getTime() <= hi) { out.push(d.getTime()); d.setMonth(d.getMonth() + step); }
    return out;
  }, [pts]);

  if (tx == null) return <Skel />;
  const fmt = (t: any) => kind === "sale" ? wonShort(t.deal_amount)
    : kind === "jeonse" ? wonShort(t.deposit) : `${wonShort(t.deposit)} / ${Math.round(t.monthly_rent / 1e4)}만`;
  // 전월세 갱신: 직전 보증금 대비 인상률
  const rise = (t: any) => {
    const p = t.pre_deposit, c = t.deposit;
    if (!p || !c) return null;
    return (c - p) / p;
  };
  const nSilv = tx.sale.filter((t: any) => t.silv).length;
  return (
    <>
      <div className="t2-dr-flt col">
        <div className="t2-seg">
          {([["sale", "매매"], ["jeonse", "전세"], ["wolse", "월세"]] as [Kind, string][]).map(([k, l]) => (
            <button key={k} className={kind === k ? "on" : ""} onClick={() => setKind(k)}>{l} <small>{tx[k].length}</small></button>
          ))}
        </div>
        {sizes.length > 0 && (
          <div className="t2-chips sm">
            {sizes.map(([s, n]) => (
              <button key={s} className={size === s ? "on" : ""} onClick={() => setSize(s)}>{areaLabel(+s)} <small>{n}</small></button>
            ))}
          </div>
        )}
      </div>
      {rows.length === 0 ? <p className="t2-empty">최근 3년 {kind === "sale" ? "매매" : kind === "jeonse" ? "전세" : "월세"} 실거래가 없어요.</p> : (
        <>
          <div className="t2-chart">
            <ResponsiveContainer width="100%" height={190}>
              <ComposedChart margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                <CartesianGrid stroke="#eef1f5" vertical={false} />
                <XAxis dataKey="x" type="number" scale="time" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11 }} ticks={ticks}
                  tickFormatter={(v) => { const d = new Date(v); return `${String(d.getFullYear()).slice(2)}.${d.getMonth() + 1}`; }} />
                <YAxis dataKey="y" tick={{ fontSize: 11 }} domain={["auto", "auto"]} unit={unit === "억" ? "억" : ""} width={52} />
                <Tooltip content={({ active, payload }: any) => {
                  const p = active && payload?.[0]?.payload;
                  if (!p || p.y == null) return null;
                  return (
                    <div className="t2-tip">
                      <b>{p.y}{unit}</b>{p.direct && <span className="t2-direct">직거래</span>}{p.silv && <span className="t2-tag silv">{p.silv}</span>}{p.rh && <span className="t2-tag rh">신고가</span>}
                      <div>{new Date(p.x).toISOString().slice(0, 10)}{p.floor != null ? ` · ${p.floor}층` : ""}{p.dong ? ` · ${p.dong}동` : p.est ? ` · ${p.est}동(추정)` : kind === "sale" && !p.silv ? " · 동 미공개(등기 전)" : ""}</div>
                    </div>);
                }} />
                <Scatter data={ptsBroker} dataKey="y" fill={kind === "sale" ? "#d23b3b" : kind === "jeonse" ? "#1268d3" : "#1f9d63"} fillOpacity={0.45} isAnimationActive={false} />
                <Scatter data={ptsDirect} dataKey="y" isAnimationActive={false} shape={(sp: any) => (
                  <g><rect x={sp.cx - 7} y={sp.cy - 7} width={14} height={14} rx={3} fill="#f59e0b" />
                    <text x={sp.cx} y={sp.cy + 4} textAnchor="middle" fontSize={10} fontWeight={800} fill="#fff">직</text></g>)} />
                <Scatter data={ptsSilv} dataKey="y" isAnimationActive={false} shape={(sp: any) => (
                  <g><rect x={sp.cx - 7} y={sp.cy - 7} width={14} height={14} rx={3} fill="#7c3aed" />
                    <text x={sp.cx} y={sp.cy + 4} textAnchor="middle" fontSize={10} fontWeight={800} fill="#fff">분</text></g>)} />
                <Line data={monthly} dataKey="m" stroke="#16202e" strokeWidth={1.6} dot={false} isAnimationActive={false} name="월 중앙값" />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="t2-note">점 = 거래 한 건 · <span className="t2-direct">직</span> = 직거래{kind === "sale" && nSilv > 0 ? <> · <span className="t2-tag silv">분</span> = 분양권·입주권</> : null} · 선 = 월 중앙값(중개거래만){kind === "wolse" ? " (월세액)" : ""}</p>
          </div>
          <table className="t2-tbl">
            <thead><tr><th>계약일</th><th>면적</th><th>동</th><th>층</th><th className="num">{kind === "sale" ? "거래가" : kind === "jeonse" ? "보증금" : "보증금/월세"}</th>{kind !== "sale" && <th>구분</th>}</tr></thead>
            <tbody>
              {(more ? rows : rows.slice(0, 15)).map((t: any, i: number) => {
                const r = kind !== "sale" ? rise(t) : null;
                return (
                  <tr key={i}>
                    <td>{t.deal_ymd.slice(2).replace(/-/g, ".")}</td>
                    <td>{areaLabel(t.excl_use_ar)}</td>
                    <td>{t.silv ? <span className="t2-tag silv">{t.silv}</span>
                      : t.dong ? `${t.dong}동`
                      : t.dong_est ? <span className="t2-est" title="계약 전후 내려간 매물의 층·가격 단서로 추정한 동. 매매는 등기가 끝나면 실제 동으로 바뀌어요">{t.dong_est}동<small>(추정)</small></span>
                      : <span className="t2-muted" title={kind === "sale" ? "동은 등기가 끝나면 공개돼요" : "전월세는 동이 공개되지 않아요. 단서가 충분한 거래만 추정해요"}>{kind === "sale" ? "등기 전" : "-"}</span>}</td>
                    <td>{t.floor}</td>
                    <td className="num">{t.dealing_gbn === "직거래" && <span className="t2-direct">직</span>}{rhSet.has(t) && <span className="t2-tag rh">신고가</span>}{t.registered && <span className="t2-tag reg" title="등기 완료">등기</span>}{fmt(t)}
                      {r != null && <small className={"t2-rise" + (r > 0 ? " up" : r < 0 ? " down" : "")}>{pct(r, 0)}</small>}</td>
                    {kind !== "sale" && <td>{t.contract_type || "-"}{t.use_rr_right === "사용" || t.use_rr_right === true ? <span className="t2-tag rr" title="계약갱신요구권 사용">갱신권</span> : null}{t.contract_term ? <small className="t2-muted"> {t.contract_term}</small> : null}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!more && rows.length > 15 && <button className="t2-more-btn" onClick={() => setMore(true)}>{rows.length}건 모두 보기</button>}
        </>
      )}
    </>
  );
}

// ── 호가추이: 최근 92일 매물수·실매물·평균 호가(면적별) ─────────────────────
type DailyRow = { d: string; area: string; t: string; n: number; u: number; avg: number | null; min: number | null; max: number | null };
function HogaTab({ no, exclOf }: { no: string; exclOf: Map<string, number> }) {
  const [rows, setRows] = useState<DailyRow[] | null>(null);
  const [t, setT] = useState<"A1" | "B1" | "B2">("A1");
  const [area, setArea] = useState("");
  useEffect(() => {
    setRows(null);
    getJson(`/complex/${no}/listing-daily?days=92`).then((j) => setRows(j.rows || [])).catch(() => setRows([]));
  }, [no]);
  const byT = useMemo(() => (rows || []).filter((r) => r.t === t), [rows, t]);
  const areas = useMemo(() => {
    const last = byT.reduce((m, r) => (r.d > m ? r.d : m), "");
    return byT.filter((r) => r.d === last).sort((a, b) => b.n - a.n).map((r) => r.area);
  }, [byT]);
  useEffect(() => { setArea(areas[0] || ""); }, [areas]);
  const data = useMemo(() => byT.filter((r) => r.area === area).sort((a, b) => a.d.localeCompare(b.d))
    .map((r) => ({ d: r.d, n: r.n, u: r.u, avg: r.avg ? +(r.avg / 1e8).toFixed(2) : null, min: r.min, max: r.max })), [byT, area]);
  if (rows == null) return <Skel />;
  if (byT.length === 0) return <p className="t2-empty">최근 3개월 {t === "A1" ? "매매" : t === "B1" ? "전세" : "월세"} 매물 기록이 없어요.</p>;
  const last = data[data.length - 1], first = data[0];
  const ago30 = data.filter((r) => r.d <= new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10)).pop() || first;
  const chg = last?.avg && ago30?.avg ? last.avg / ago30.avg - 1 : null;
  return (
    <>
      <div className="t2-dr-flt col">
        <div className="t2-seg">
          {([["A1", "매매"], ["B1", "전세"], ["B2", "월세"]] as const).map(([k, l]) => (
            <button key={k} className={t === k ? "on" : ""} onClick={() => setT(k)}>{l}</button>
          ))}
        </div>
        <div className="t2-chips sm">
          {areas.map((a) => <button key={a} className={area === a ? "on" : ""} onClick={() => setArea(a)}>{a}{exclOf.get(a) ? <small>{areaLabel(exclOf.get(a)!)}</small> : null}</button>)}
        </div>
      </div>
      {last && (
        <dl className="t2-facts in">
          <div><dt>오늘 매물</dt><dd>{last.n}건<small> · 실매물 {last.u}채</small></dd></div>
          <div><dt>평균 호가</dt><dd>{last.avg != null ? `${last.avg}억` : "-"}{chg != null && <small className={chg > 0 ? "up" : chg < 0 ? "down" : ""}> 30일 {pct(chg)}</small>}</dd></div>
          <div><dt>호가 범위</dt><dd>{last.min && last.max ? `${wonShort(last.min)}~${wonShort(last.max)}` : "-"}</dd></div>
        </dl>
      )}
      <div className="t2-chart">
        <ResponsiveContainer width="100%" height={190}>
          <ComposedChart data={data} margin={{ top: 8, right: 0, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#eef1f5" vertical={false} />
            <XAxis dataKey="d" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5).replace("-", ".")} minTickGap={28} />
            <YAxis yAxisId="p" tick={{ fontSize: 11 }} domain={["auto", "auto"]} unit={t === "B2" ? "" : "억"} width={52} />
            <YAxis yAxisId="n" orientation="right" tick={{ fontSize: 11 }} width={34} allowDecimals={false} />
            <Tooltip content={({ active, payload }: any) => {
              const p = active && payload?.[0]?.payload;
              if (!p) return null;
              return <div className="t2-tip"><b>{p.avg != null ? `평균 ${p.avg}억` : "-"}</b><div>{p.d} · 매물 {p.n}건 · 실매물 {p.u}채</div></div>;
            }} />
            <Bar yAxisId="n" dataKey="n" fill="#dbe6f5" isAnimationActive={false} />
            <Line yAxisId="p" dataKey="avg" stroke="#1268d3" strokeWidth={1.8} dot={false} connectNulls isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
        <p className="t2-note">선 = 평균 호가 · 막대 = 매물 건수(광고 기준) · 최근 92일</p>
      </div>
    </>
  );
}

// ── 인근단지: 1.5km 안 단지의 12개월 실거래·매물 비교 ─────────────────────
function NearbyTab({ no, areas, onPick }: { no: string; areas: Area[]; onPick?: (c: DrawerCx) => void }) {
  const [area, setArea] = useState(0);
  const [d, setD] = useState<any | null>(null);
  useEffect(() => {
    setD(null);
    getJson(`/complex/${no}/nearby-transactions?area=${area}&months=12&radius_km=1.5&limit=12&include_listings=1`).then(setD).catch(() => setD({ nearby: [] }));
  }, [no, area]);
  const opts = useMemo(() => {
    const m = new Map<number, string>();
    areas.forEach((a) => { const k = Math.round(a.exclusive_area); if (!m.has(k)) m.set(k, a.pyeong_name); });
    return [...m.keys()].sort((a, b) => a - b);
  }, [areas]);
  const self = d?.self;
  return (
    <>
      <div className="t2-dr-flt col">
        <div className="t2-chips sm">
          <button className={!area ? "on" : ""} onClick={() => setArea(0)}>전체 면적</button>
          {opts.map((k) => <button key={k} className={area === k ? "on" : ""} onClick={() => setArea(k)}>{areaLabel(k)}</button>)}
        </div>
      </div>
      {d == null ? <Skel /> : (
        <>
          <p className="t2-note">반경 1.5km · 최근 12개월 매매 실거래{area ? ` · ${areaLabel(area)} ±1.5㎡` : ""}
            {self ? <> · 이 단지 {self.deal_count}건{self.avg_amount ? ` 평균 ${wonShort(self.avg_amount)}` : ""}</> : null}</p>
          {(d.nearby || []).length === 0 ? <p className="t2-empty">근처에 비교할 단지가 없어요.</p> : (
            <ul className="t2-nb">
              {d.nearby.map((c: any) => (
                <li key={c.complex_no} className={onPick ? "t2-click" : ""} onClick={() => onPick?.({ complex_no: c.complex_no, name: c.complex_name, lat: c.lat, lng: c.lng, households: c.households })}>
                  <div className="t2-nb-top">
                    <b>{c.complex_name}</b>
                    <span className="t2-nb-dist">{c.distance_m}m{c.subway ? ` · ${c.subway.station} ${c.subway.walk_min}분` : ""}</span>
                  </div>
                  <div className="t2-nb-mid">
                    {c.households ? `${c.households.toLocaleString()}세대` : ""}{c.use_approve_ymd ? ` · ${c.use_approve_ymd.slice(0, 4)}년` : ""}
                    {c.listings?.n ? ` · 매물 ${c.listings.n}${c.listings.ask_min ? ` (최저 ${wonShort(c.listings.ask_min)})` : ""}` : ""}
                  </div>
                  <div className="t2-nb-bot">
                    {c.deal_count ? <><b>{wonShort(c.avg_amount)}</b><small> 평균 · {c.deal_count}건 · 최고 {wonShort(c.max_amount)}</small></>
                      : <small className="t2-muted">12개월 거래 없음{c.all_time_max ? ` · 역대 최고 ${wonShort(c.all_time_max)}` : ""}</small>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </>
  );
}

// ── 중개사 랭킹 ───────────────────────────────────────
function RealtorTab({ rk, total, onRequest }: { rk: any[] | null; total: number; onRequest: (r: any) => void }) {
  const [all, setAll] = useState(false);
  if (rk == null) return <Skel />;
  const max = Math.max(1, ...rk.map((r) => r.count));
  const shown = all ? rk : rk.slice(0, 10);
  const meta = (r: any) => [r.established_year ? `개업 ${r.established_year}` : "", r.staff_count ? `직원 ${r.staff_count}` : "",
    r.total_listings ? `전국 ${r.total_listings}건` : ""].filter(Boolean).join(" · ");
  return (
    <>
      <div className="t2-dr-flt"><div className="t2-ph"><h3>이 단지 중개사 랭킹</h3><small>기준: 이 단지 매물 수</small></div></div>
      {rk.length === 0 ? <p className="t2-empty">이 단지에 매물을 올린 중개사가 없어요.</p> : (
        <ol className="t2-rank withreq">
          {shown.map((r, i) => (
            <li key={r.realtor_id} className={i === 0 ? "top1" : ""}>
              <a href={`${SITE}/realtor/${encodeURIComponent(r.realtor_id)}`} target="_blank" rel="noreferrer">
                <span className="n">{i + 1}</span>
                <span className="o"><b>{r.realtor_name}</b><em>매매 {r.n_sale} · 전세 {r.n_jeonse} · 월세 {r.n_wolse}</em>{meta(r) && <em>{meta(r)}</em>}</span>
                <span className="bm"><i style={{ width: `${(r.count / max) * 100}%` }} /></span>
                <span className="c">{r.count}<small>{total ? Math.round((r.count / total) * 100) : 0}%</small></span>
              </a>
              {r.tel && <a className="t2-telbtn sm" href={`tel:${String(r.tel).replace(/[^0-9+]/g, "")}`} title={r.tel}>전화</a>}
              <button className="t2-reqbtn sm" onClick={() => onRequest(r)}>요청</button>
            </li>
          ))}
        </ol>
      )}
      {!all && rk.length > 10 && <button className="t2-more-btn" onClick={() => setAll(true)}>{rk.length >= 50 ? "상위 50곳 보기" : `${rk.length}곳 전체 보기`}</button>}
      <div className="t2-ad">
        <div className="t2-ph"><h3>근처 분양·광고 단지</h3><span className="t2-adtag">광고</span></div>
        <div className="t2-adslot">광고 단지 자리 (시험판 표시) — 실제로는 광고가 없으면 이 칸을 숨겨요. 랭킹 순위와는 섞지 않아요.</div>
      </div>
    </>
  );
}

// ── 단지정보: 대장 요약 + 교통·학군 + 건축물대장 + 평형별 세대·호가 + 같은 건물 ─────────────────────
type Ledger = { structure?: string; roof?: string; grnd_flr?: number; ugrnd_flr?: number; heit?: number; bc_rat?: number | null; vl_rat?: number | null;
  arch_area?: number; plat_area?: number | null; tot_area?: number; elvt?: number; pms_day?: string; stcns_day?: string; use_apr_day?: string; n_dong?: number; main_purps?: string; etc_purps?: string };
function InfoTab({ no, asset, info, raw, agg, areas, sum, onPick }: { no: string; asset: string; info: Info | null; raw: any; agg: AggRow[] | null; areas: Area[]; sum: Summary | null; onPick?: (c: DrawerCx) => void }) {
  const [ledger, setLedger] = useState<Ledger | null | undefined>(undefined);
  const [sibs, setSibs] = useState<any[]>([]);
  useEffect(() => {
    setLedger(undefined); setSibs([]);
    getJson(`/stats/tx-map/detail?asset=${asset}&trade=A1&ref=${no}&months=1`).then((j) => setLedger(j.ledger || null)).catch(() => setLedger(null));
    getJson(`/complexes/${no}/siblings`).then((j) => setSibs(j.items || [])).catch(() => {});
  }, [no, asset]);
  if (!info) return <Skel />;
  const by = (name: string, tt: string) => (agg || []).find((r) => r.area_name === name && r.trade_type === tt);
  const rng = (r?: AggRow) => (!r ? "-" : r.price_min === r.price_max ? wonShort(r.price_min) : `${wonShort(r.price_min)}~${wonShort(r.price_max)}`);
  const rentRng = (r?: AggRow) => (!r ? "-" : `${wonShort(r.price_min)}~${wonShort(r.price_max)}${r.rent_min && r.rent_max ? ` / ${Math.round(r.rent_min / 1e4)}~${Math.round(r.rent_max / 1e4)}만` : ""}`);
  const ymd = info.use_approve_ymd || "";
  const L = ledger;
  const m2 = (v?: number | null) => (v ? `${v.toLocaleString(undefined, { maximumFractionDigits: 1 })}㎡` : "-");
  return (
    <>
      <table className="t2-kv">
        <tbody>
          <tr><th>주소</th><td>{[raw.cortarAddress, info.road_address].filter(Boolean).join(" · ") || "-"}</td></tr>
          <tr><th>사용승인</th><td>{ymd ? ymd8(ymd) : "-"}</td></tr>
          <tr><th>규모</th><td>{info.total_household_count?.toLocaleString()}세대 · {info.total_building_count}개동 · {info.low_floor}~{info.high_floor}층</td></tr>
          <tr><th>용적률 / 건폐율</th><td>{info.batl_ratio ? `${Math.round(info.batl_ratio)}% / ${Math.round(info.btl_ratio || 0)}%` : "-"}</td></tr>
          <tr><th>주차</th><td>{info.parking_possible_count ? `${info.parking_possible_count.toLocaleString()}대 (세대당 ${info.parking_per_household}대)` : "-"}</td></tr>
          <tr><th>건설사</th><td>{info.construction_company || "-"}</td></tr>
          <tr><th>관리사무소</th><td>{info.management_office_tel || "-"}</td></tr>
          {sum?.subway && <tr><th>지하철</th><td>{sum.subway.station} ({sum.subway.lines}) · {sum.subway.distance_m}m · 도보 {sum.subway.walk_min}분</td></tr>}
          {sum?.school && <tr><th>{sum.school.src === "near" ? "인근 초등학교" : "배정 초등학교"}</th><td>{sum.school.names_all || sum.school.name} · {sum.school.distance_m}m · 도보 {sum.school.walk_min}분</td></tr>}
        </tbody>
      </table>

      <div className="t2-ph" style={{ marginTop: 14 }}><h3>건축물대장</h3><small>표제부 · 국토부 건축HUB</small></div>
      {L === undefined ? <Skel /> : L === null ? <p className="t2-empty">건축물대장을 못 찾았어요.</p> : (
        <table className="t2-kv">
          <tbody>
            <tr><th>용도</th><td>{[L.main_purps, L.etc_purps].filter(Boolean).join(" · ") || "-"}</td></tr>
            <tr><th>구조 / 지붕</th><td>{[L.structure, L.roof].filter(Boolean).join(" / ") || "-"}</td></tr>
            <tr><th>층수 / 높이</th><td>지상 {L.grnd_flr ?? "-"}층{L.ugrnd_flr ? ` · 지하 ${L.ugrnd_flr}층` : ""}{L.heit ? ` · ${L.heit}m` : ""}{L.n_dong ? ` · ${L.n_dong}개 동(대장)` : ""}</td></tr>
            <tr><th>건축 / 연면적</th><td>{m2(L.arch_area)} / {m2(L.tot_area)}{L.plat_area ? ` · 대지 ${m2(L.plat_area)}` : ""}</td></tr>
            {(L.bc_rat || L.vl_rat) && <tr><th>건폐율 / 용적률</th><td>{L.bc_rat ?? "-"}% / {L.vl_rat ?? "-"}%</td></tr>}
            <tr><th>승강기</th><td>{L.elvt ? `${L.elvt}대` : "-"}</td></tr>
            <tr><th>허가·착공·승인</th><td>{ymd8(L.pms_day)} → {ymd8(L.stcns_day)} → {ymd8(L.use_apr_day)}</td></tr>
          </tbody>
        </table>
      )}

      <div className="t2-ph" style={{ marginTop: 14 }}><h3>평형별 세대·호가</h3><small>오늘 매물 기준 · 괄호는 건수</small></div>
      <table className="t2-tbl">
        <thead><tr><th>타입</th><th>전용</th><th className="num">세대</th><th className="num">매매</th><th className="num">전세</th><th className="num">월세</th></tr></thead>
        <tbody>
          {areas.map((a) => {
            const s = by(a.pyeong_name, "A1"), j = by(a.pyeong_name, "B1"), w = by(a.pyeong_name, "B2");
            return (
              <tr key={a.pyeong_name}>
                <td>{a.pyeong_name}</td>
                <td>{areaLabel(a.exclusive_area)}</td>
                <td className="num">{a.household_count?.toLocaleString() ?? "-"}</td>
                <td className="num">{rng(s)}{s ? <small> ({s.listing_count}){s.price_avg ? ` 평균 ${wonShort(s.price_avg)}` : ""}</small> : null}</td>
                <td className="num">{rng(j)}{j ? <small> ({j.listing_count})</small> : null}</td>
                <td className="num">{rentRng(w)}{w ? <small> ({w.listing_count})</small> : null}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {sibs.length > 0 && (
        <>
          <div className="t2-ph" style={{ marginTop: 14 }}><h3>같은 건물</h3><small>아파트·오피스텔이 한 건물</small></div>
          <ul className="t2-nb">
            {sibs.map((s: any) => (
              <li key={s.complex_no} className={onPick ? "t2-click" : ""} onClick={() => onPick?.({ complex_no: s.complex_no, name: s.complex_name, lat: 0, lng: 0, households: s.households })}>
                <div className="t2-nb-top"><b>{s.complex_name}</b><span className="t2-nb-dist">{s.type_name || s.type}{s.households ? ` · ${s.households.toLocaleString()}세대` : ""}</span></div>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
