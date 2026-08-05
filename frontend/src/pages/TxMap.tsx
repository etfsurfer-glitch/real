// 실거래 지도 — 지역 내 실거래를 건물(단지/지번) 단위로 지도에 찍는다.
// 아파트·오피스텔=단지 좌표(99%), 빌라·상가=지번 좌표매칭(부분). 단독은 지번이 없어 미지원.
// 핀 = 최근 N개월 평균 실거래가(억), 색은 평당가 4분위(같은 화면 안에서 상대 비교).
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { loadKakao, wonShort, escapeHtml, attachMapControls, coordToRegion } from "../lib/kakaomap";
import { RegionSelect, useRegionFilter } from "../components/RegionSelect";
import { areaLabel } from "../lib/area";
import { Select } from "./TxStats";
import { MapPin, X, Building2 } from "lucide-react";

const API = import.meta.env.VITE_API_BASE;

type Pin = {
  lat: number; lng: number; name: string; ref: string;
  n: number; last: number | null; avg: number | null; ppy: number | null;
  latest: string | null; built?: string | null; deposit?: number | null; kind: string;
};
// 핀 표시 모드
const DISPLAYS = [
  { value: "last", label: "최근 실거래" },
  { value: "avg", label: "기간 평균가" },
  { value: "ppy", label: "평단가" },
  { value: "built", label: "준공연도" },
];
// 핀 위/아래 2줄 라벨 (모드별)
function pinLabels(p: Pin, disp: string, wonShort: (v: number | null) => string): [string, string] {
  const ym = p.latest ? `${p.latest.slice(0, 4)}.${+p.latest.slice(5, 7)}` : "";
  if (disp === "avg") return ["평균", wonShort(p.avg)];
  if (disp === "ppy") return [ym, p.ppy ? `평 ${wonShort(p.ppy)}` : "-"];
  if (disp === "built") return ["준공", p.built ? `${p.built}년` : "-"];
  return [ym, wonShort(p.last)];
}
type Resp = { asset: string; items: Pin[]; note: string | null };
type Deal = {
  date: string; price?: number; deposit?: number; rent?: number;
  area?: number | null; land?: number | null; floor?: number | null;
  dealing?: string; dong?: string; registered?: boolean; buyer?: string; seller?: string;
  contract?: string; term?: string; rr_right?: string | null;
  pre_deposit?: number | null; pre_rent?: number | null;
  htype?: string; use?: string; btype?: string; land_use?: string;
};
type Ledger = {
  bld_nm?: string | null; main_purps?: string | null; etc_purps?: string | null;
  structure?: string | null; roof?: string | null; grnd_flr?: number | null; ugrnd_flr?: number | null;
  hhld_cnt?: number | null; fmly_cnt?: number | null; ho_cnt?: number | null; heit?: number | null;
  bc_rat?: number | null; vl_rat?: number | null; arch_area?: number | null; plat_area?: number | null;
  tot_area?: number | null; elvt?: number | null; parking?: number | null;
  pms_day?: string | null; stcns_day?: string | null; use_apr_day?: string | null; n_dong?: number | null;
};
type Floor = { flr_gb?: string; flr_no?: number | null; flr_no_nm?: string; purps?: string | null; etc?: string | null; area?: number | null };
type Detail = {
  building: { kind?: string; complex_no?: string; name?: string | null; households?: number;
    built?: string | null; buildings?: number; parking?: number; builder?: string | null;
    type?: string; dong_name?: string; purpose?: string | null;
    tot_area?: number | null; plat_area?: number | null };
  ledger?: Ledger | null; floors?: Floor[] | null;
  deals: Deal[]; stat: { max?: number; min?: number; n?: number };
};

const ymd8 = (s?: string | null) =>
  s && s.length >= 8 ? `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}` : s || "";
const m2 = (v?: number | null) => (v ? `${Math.round(v).toLocaleString()}㎡` : "");

// 건축물대장 표제부 → 라벨/값 쌍(빈 값은 생략)
function ledgerRows(l: Ledger): [string, string][] {
  const rows: [string, string][] = [];
  const flr = [l.grnd_flr ? `지상 ${l.grnd_flr}층` : null, l.ugrnd_flr ? `지하 ${l.ugrnd_flr}층` : null]
    .filter(Boolean).join(" · ");
  if (l.main_purps) rows.push(["주용도", l.main_purps + (l.etc_purps && l.etc_purps !== l.main_purps ? ` (${l.etc_purps})` : "")]);
  if (l.structure) rows.push(["구조", l.structure + (l.roof ? ` · 지붕 ${l.roof}` : "")]);
  if (flr) rows.push(["층수", flr + (l.heit ? ` · 높이 ${l.heit}m` : "")]);
  const units = [l.hhld_cnt ? `${l.hhld_cnt.toLocaleString()}세대` : null, l.fmly_cnt ? `${l.fmly_cnt}가구` : null,
    l.ho_cnt ? `${l.ho_cnt}호` : null].filter(Boolean).join(" · ");
  if (units) rows.push(["세대/가구/호", units]);
  if (l.bc_rat || l.vl_rat) rows.push(["건폐율/용적률", `${l.bc_rat ? l.bc_rat.toFixed(1) + "%" : "-"} / ${l.vl_rat ? l.vl_rat.toFixed(1) + "%" : "-"}`]);
  if (l.arch_area || l.tot_area) rows.push(["건축/연면적", `${m2(l.arch_area) || "-"} / ${m2(l.tot_area) || "-"}`]);
  if (l.plat_area) rows.push(["대지면적", m2(l.plat_area)]);
  const pk = [l.parking ? `주차 ${l.parking}대` : null, l.elvt ? `승강기 ${l.elvt}대` : null].filter(Boolean).join(" · ");
  if (pk) rows.push(["주차/승강기", pk]);
  if (l.use_apr_day) rows.push(["사용승인", ymd8(l.use_apr_day) + (l.n_dong && l.n_dong > 1 ? ` · ${l.n_dong}개 동` : "")]);
  return rows;
}

const ASSETS = [
  { value: "apt", label: "아파트" }, { value: "offi", label: "오피스텔" },
  { value: "villa", label: "빌라·다세대" }, { value: "nrg", label: "상가·사무실" },
  { value: "house", label: "단독·다가구" },
];
const TIER_COLOR = ["#1f9d63", "#1268d3", "#e08a1e", "#d23b3b"]; // 저→고 평당가
const TRADES = [
  { value: "A1", label: "매매" }, { value: "B1", label: "전세" }, { value: "B2", label: "월세" },
];

function tiers(pins: Pin[]): (p: Pin) => number {
  const ys = pins.map((p) => p.ppy || 0).filter((x) => x > 0).sort((a, b) => a - b);
  if (ys.length < 4) return () => 1;
  const q = [ys[Math.floor(ys.length * 0.25)], ys[Math.floor(ys.length * 0.5)], ys[Math.floor(ys.length * 0.75)]];
  return (p) => {
    const v = p.ppy || 0;
    return v <= q[0] ? 0 : v <= q[1] ? 1 : v <= q[2] ? 2 : 3;
  };
}

export default function TxMap() {
  const region = useRegionFilter();
  const [asset, setAsset] = useState("apt");
  const [trade, setTrade] = useState("A1");
  const [disp, setDisp] = useState("last");   // 핀 표시 모드
  const months = 24;   // 집계 창(기간 필터 제거 — 백엔드 최대치 24개월 고정)
  // 상가는 임대 원천 없음(주택만 신고제)·단독 임대는 지번 없음 → 매매 고정
  const rentOk = asset === "apt" || asset === "offi" || asset === "villa";
  const tradeEff = rentOk ? trade : "A1";
  const [data, setData] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(false);
  const [sel, setSel] = useState<Pin | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [dtLoading, setDtLoading] = useState(false);
  const elRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const ovsRef = useRef<any[]>([]);
  const fitRef = useRef<Pin[] | null>(null);   // 마지막으로 지도범위를 맞춘 pins — 표시모드 변경 땐 재조정 안 함
  // 내위치 이동 → 그 좌표의 시군구로 지역 필터 전환(데이터 자동 재조회). 컨트롤은 1회 부착이라 ref로 최신 세터 사용.
  const onLocateRef = useRef<(lat: number, lng: number) => void>(() => {});
  onLocateRef.current = (lat, lng) => {
    coordToRegion(lat, lng).then((r) => {
      if (!r) return;
      region.setSido(r.sido);       // 캐스케이드로 하위 초기화 후
      region.setSigungu(r.sigungu);
      region.setDong(r.dong);       // 읍면동까지 지정 → useEffect가 해당 지역 재조회
    });
  };

  const sgg = region.sigungu, dong = region.dong, sido = region.sido;
  const needRegion = asset === "villa" || asset === "nrg" || asset === "house" ? !sgg : !sido;

  useEffect(() => {
    if (!API || needRegion) { setData(null); return; }
    setLoading(true); setSel(null);
    const qs = new URLSearchParams({ asset, trade: tradeEff, months: String(months) });
    if (dong && (asset === "apt" || asset === "offi")) qs.set("dong", dong);
    if (sgg) qs.set("sigungu", sgg); if (sido) qs.set("sido", sido);
    let dead = false;
    fetch(`${API}/stats/tx-map?${qs}`).then((r) => r.json())
      .then((j) => { if (!dead) setData(j); })
      .catch(() => { if (!dead) setData({ asset, items: [], note: null }); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [asset, tradeEff, months, sido, sgg, dong, needRegion]); // eslint-disable-line

  const pins = data?.items ?? [];
  const tierOf = useMemo(() => tiers(pins), [pins]);

  // 핀 선택 → 상세(개별 거래 + 건물정보) 로드
  useEffect(() => {
    if (!sel || !API) { setDetail(null); return; }
    setDtLoading(true); setDetail(null);
    const qs = new URLSearchParams({ asset, trade: tradeEff, ref: sel.ref, months: String(months) });
    if (sgg) qs.set("sigungu", sgg);
    let dead = false;
    fetch(`${API}/stats/tx-map/detail?${qs}`).then((r) => r.json())
      .then((j) => { if (!dead) setDetail(j); })
      .catch(() => {})
      .finally(() => { if (!dead) setDtLoading(false); });
    return () => { dead = true; };
  }, [sel, asset, tradeEff, months, sgg]); // eslint-disable-line

  useEffect(() => {
    if (!elRef.current || pins.length === 0) return;
    let dead = false;
    loadKakao().then(() => {
      if (dead || !elRef.current) return;
      const kakao = (window as any).kakao;
      if (!mapRef.current) {
        mapRef.current = new kakao.maps.Map(elRef.current, {
          center: new kakao.maps.LatLng(pins[0].lat, pins[0].lng), level: 5,
        });
        attachMapControls(mapRef.current, elRef.current,
          { onLocate: (la, ln) => onLocateRef.current(la, ln) });
      }
      const map = mapRef.current;
      ovsRef.current.forEach((o) => o.setMap(null)); ovsRef.current = [];
      const bounds = new kakao.maps.LatLngBounds();
      for (const p of pins) {
        const pos = new kakao.maps.LatLng(p.lat, p.lng); bounds.extend(pos);
        const el = document.createElement("div");
        el.className = "txm-pin"; el.style.background = TIER_COLOR[tierOf(p)];
        const [top, bottom] = pinLabels(p, disp, wonShort);
        el.innerHTML =
          `${top ? `<em class="txm-pin-d">${escapeHtml(top)}</em>` : ""}`
          + `<span class="txm-pin-p">${escapeHtml(bottom)}${p.n > 1 ? `<i>${p.n}</i>` : ""}</span>`;
        el.addEventListener("click", (e) => { e.stopPropagation(); setSel(p); });
        const ov = new kakao.maps.CustomOverlay({ position: pos, content: el, yAnchor: 1.1, clickable: true });
        ov.setMap(map); ovsRef.current.push(ov);
      }
      if (fitRef.current !== pins) { map.setBounds(bounds, 40, 40, 40, 40); fitRef.current = pins; }
    }).catch(() => {});
    return () => { dead = true; };
  }, [pins, tierOf, disp]);

  return (
    <div>
      <Link to="/tx-stats" className="back">← 실거래 통계</Link>
      <div className="section-title" style={{ marginTop: 4 }}>
        <MapPin size={17} /> 실거래 지도 <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>지역·유형을 고르면 건물별 최근 실거래가를 지도에</span>
      </div>
      <div className="filter-bar">
        <Select label="유형" value={asset} onChange={setAsset} options={ASSETS} />
        <Select label="거래" value={tradeEff} onChange={setTrade}
          options={rentOk ? TRADES : TRADES.slice(0, 1)} />
        <RegionSelect {...region} />
        <Select label="표시" value={disp} onChange={setDisp} options={DISPLAYS} />
      </div>

      {(asset === "villa" || asset === "nrg") && (
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
          빌라·상가는 지번 좌표가 확인된 실거래만 표시됩니다.
        </div>
      )}
      {needRegion && (
        <div className="muted" style={{ padding: "40px 8px", textAlign: "center" }}>
          {asset === "apt" || asset === "offi" ? "시도 이상 지역" : "시군구"}를 선택하면 지도가 표시됩니다.
        </div>
      )}

      {!needRegion && (
        <>
          <div className="txm-legend">
            <span>{tradeEff === "B1" ? "평당 보증금" : tradeEff === "B2" ? "평당 월세" : "평당가"}</span>
            {["낮음", "", "", "높음"].map((lb, i) => (
              <span key={i} className="txm-leg"><i style={{ background: TIER_COLOR[i] }} />{lb}</span>
            ))}
            {data && <span className="muted" style={{ marginLeft: "auto", fontSize: 11.5 }}>
              {loading ? "불러오는 중…" : `핀 ${pins.length.toLocaleString()}개`}</span>}
          </div>
          <div ref={elRef} className="txm-map" aria-label="실거래 지도" />
          {data?.note && <div className="muted" style={{ fontSize: 11.5, marginTop: 6 }}>{data.note}</div>}
          {!loading && pins.length === 0 && <div className="muted" style={{ marginTop: 8 }}>해당 지역·기간의 실거래가 없습니다.</div>}
        </>
      )}

      {sel && (
        <div className="txm-detail txm-detail-rich">
          <button className="txm-detail-x" onClick={() => setSel(null)} aria-label="닫기"><X size={16} /></button>
          <div className="txm-detail-nm">{detail?.building?.name || sel.name}</div>
          <div className="txm-detail-body">
          {/* 건물 정보 */}
          {detail?.building && (
            <div className="txm-bld">
              {detail.building.kind === "complex" ? (
                <>
                  {[detail.building.type, detail.building.households ? `${detail.building.households.toLocaleString()}세대` : null,
                    detail.building.built ? `${detail.building.built}년 준공` : null,
                    detail.building.buildings ? `${detail.building.buildings}개동` : null,
                    detail.building.parking ? `세대당 주차 ${detail.building.parking}` : null,
                    detail.building.builder].filter(Boolean).join(" · ")}
                </>
              ) : (
                <>
                  {[detail.building.purpose, detail.building.built ? `${detail.building.built}년 준공` : null,
                    detail.building.tot_area ? `연면적 ${Math.round(detail.building.tot_area).toLocaleString()}㎡` : null,
                    detail.building.plat_area ? `대지 ${Math.round(detail.building.plat_area).toLocaleString()}㎡` : null,
                  ].filter(Boolean).join(" · ")}
                  {detail.building.kind === "ledger" && <span className="txm-bld-src"> · 건축물대장</span>}
                </>
              )}
            </div>
          )}
          {/* 건축물대장 표제부 상세 */}
          {detail?.ledger && ledgerRows(detail.ledger).length > 0 && (
            <div className="txm-ledger">
              <div className="txm-ledger-h"><Building2 size={13} /> 건축물대장</div>
              <div className="txm-ledger-grid">
                {ledgerRows(detail.ledger).map(([k, v]) => (
                  <div key={k} className="txm-lg-row"><span>{k}</span><b>{v}</b></div>
                ))}
              </div>
            </div>
          )}
          {/* 층별 용도(혼합건물만) */}
          {detail?.floors && detail.floors.length > 0 && (
            <details className="txm-floors">
              <summary>층별 용도 {detail.floors.length}개 층</summary>
              <div className="txm-floors-list">
                {detail.floors.map((f, i) => (
                  <div key={i} className="txm-flr">
                    <span className="txm-flr-n">{f.flr_no_nm}</span>
                    <span className="txm-flr-p">{f.purps}{f.etc && f.etc !== f.purps ? ` · ${f.etc}` : ""}</span>
                    <span className="txm-flr-a">{f.area ? `${f.area}㎡` : ""}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
          {/* 요약 */}
          <div className="txm-detail-rows">
            <div><span>최근 {months}개월 {tradeEff === "A1" ? "거래" : "계약"}</span><b>{sel.n.toLocaleString()}건</b></div>
            <div><span>{tradeEff === "B1" ? "최근 보증금" : tradeEff === "B2" ? "최근 월세" : "최근 거래가"}</span><b>{wonShort(sel.last)}{tradeEff === "B2" ? "/월" : ""}</b></div>
            {tradeEff === "A1" && sel.avg != null && <div><span>기간 평균</span><b>{wonShort(sel.avg)}</b></div>}
            {detail?.stat?.max != null && <div><span>최고</span><b>{wonShort(detail.stat.max)}</b></div>}
            {detail?.stat?.min != null && <div><span>최저</span><b>{wonShort(detail.stat.min)}</b></div>}
          </div>
          {/* 개별 거래 내역 */}
          {dtLoading && <div className="muted" style={{ padding: "10px 2px", fontSize: 12 }}>거래 내역 불러오는 중…</div>}
          {detail && detail.deals.length > 0 && (
            <div className="txm-deals">
              {detail.deals.map((dl, i) => (
                <div key={i} className="txm-deal">
                  <span className="txm-deal-d">{dl.date.slice(2).replace(/-/g, ".")}</span>
                  <span className="txm-deal-p">
                    {tradeEff === "A1" ? wonShort(dl.price ?? null)
                      : tradeEff === "B1" ? wonShort(dl.deposit ?? null)
                      : `${wonShort(dl.deposit ?? null)}/${dl.rent ? `${Math.round(dl.rent / 1e4)}만` : "-"}`}
                  </span>
                  <span className="txm-deal-m">
                    {[dl.area ? areaLabel(dl.area) : null,
                      tradeEff === "A1" && dl.price && dl.area ? `평당 ${wonShort(Math.round((dl.price / dl.area) * 3.3058))}` : null,
                      dl.floor != null && dl.floor !== 0 ? `${dl.floor}층` : null,
                      dl.dong ? `${dl.dong}동` : null,
                      dl.htype || dl.use || null,
                    ].filter(Boolean).join(" · ")}
                  </span>
                  <span className="txm-deal-t">
                    {tradeEff === "A1" ? (
                      <>
                        {dl.dealing === "직거래" && <em className="txm-tag warn">직거래</em>}
                        {dl.registered && <em className="txm-tag ok">등기</em>}
                        {dl.buyer === "법인" && <em className="txm-tag">법인매수</em>}
                      </>
                    ) : (
                      <>
                        {dl.contract && <em className={"txm-tag" + (dl.contract === "갱신" ? "" : " ok")}>{dl.contract}</em>}
                        {dl.contract === "갱신" && dl.pre_deposit && dl.deposit ? (
                          <em className="txm-tag warn">
                            {dl.deposit >= dl.pre_deposit ? "+" : ""}{Math.round((dl.deposit / dl.pre_deposit - 1) * 100)}%
                          </em>
                        ) : null}
                      </>
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}
          {detail && detail.deals.length === 0 && !dtLoading && (
            <div className="muted" style={{ padding: "8px 2px", fontSize: 12 }}>기간 내 개별 내역이 없습니다.</div>
          )}
          {sel.kind === "complex" && (
            <Link to={`/complex/${sel.ref}`} className="txm-detail-link">단지 상세 보기 →</Link>
          )}
          </div>
        </div>
      )}
    </div>
  );
}
