import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { createPortal } from "react-dom";
import {
  LineChart, Line, XAxis, YAxis, Tooltip as ChartTooltip, Legend, ResponsiveContainer, CartesianGrid,
} from "recharts";
import {
  Heart, MapPin, Flame, Trophy, ReceiptText,
  MessageSquareText, ChevronRight, Search, X, Map as MapIcon, TrainFront, BarChart3, School,
} from "lucide-react";
import { useAuth, loginKakao } from "../auth";
import { Loading } from "../components/Loading";
import { toggleFav } from "../lib/favstore";
import SubwayModal from "../components/SubwayModal";
import SchoolModal from "../components/SchoolModal";
import { areaLabel } from "../lib/area";

const API = import.meta.env.VITE_API_BASE;

// 나의 관심단지 대시보드 (관리자 가오픈) — 등록한 단지마다 콕집이 제공하는
// 서비스(매물·최저호가·급매·신고가·실거래·전세가율·리뷰·AI)를 한 카드에 요약.
type Dash = {
  complex_no: string; complex_name: string; region: string;
  households: number | null; approve_year: string | null;
  subway: { station: string; lines: string; distance_m: number; walk_min: number } | null;
  school: { name: string; names_all: string; n: number; distance_m: number; walk_min: number; src: string } | null;
  areas: { pyeong_name: string; exclusive_area: number | null }[];
  area_name: string | null;
  listings: { total: number; units: number; A1: number; B1: number; B2: number;
    day_change: number | null; new_week: number };
  ask_min: { A1: number | null; B1: number | null; B2: { deposit: number; rent: number } | null };
  ask_min_7d: { date: string; price: number } | null;
  last_tx: { price: number; date: string; area: number; floor: number | null; kind?: string } | null;
  tx_90d: { avg: number | null; n: number };
  jeonse_ratio: number | null;
  jeonse_src: "tx" | "ask" | null;
  record_high: { area_key: string; price: number; date: string } | null;
  quick_deals: { n: number; best_discount: number | null };
  reviews: number;
};

function eok(won: number | null | undefined): string {
  if (won == null) return "—";
  if (won >= 100_000_000) {
    const e = won / 100_000_000;
    return `${e >= 100 ? Math.round(e).toLocaleString() : (e % 1 === 0 ? e.toFixed(0) : e.toFixed(1))}억`;
  }
  return `${Math.round(won / 10_000).toLocaleString()}만`;
}

// 카드 안 초소형 가격 흐름 스파크라인 — 축·격자·값라벨 없이 '흐름'만(공간이 작다).
// 단일 시계열. 색은 카드 관례(상승=빨강·하락=파랑)를 따라 순변화 방향으로.
function Sparkline({ data }: { data: number[] }) {
  if (!data || data.length < 2) return null;
  const n = data.length;
  const min = Math.min(...data), max = Math.max(...data);
  const span = max - min || 1;
  const X = (i: number) => (i / (n - 1)) * 100;
  const Y = (v: number) => 4 + (1 - (v - min) / span) * 22;   // 30높이 안 4~26
  const line = data.map((v, i) => `${X(i).toFixed(2)},${Y(v).toFixed(2)}`).join(" ");
  const col = data[n - 1] >= data[0] ? "#c0392b" : "#1268d3";   // 상승 빨강 / 하락 파랑
  return (
    <svg className="spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden>
      <polygon points={`0,30 ${line} 100,30`} fill={col} fillOpacity="0.10" />
      <polyline points={line} fill="none" stroke={col} strokeWidth="1.6"
        vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export default function MyFavorites() {
  const { token } = useAuth();
  const [items, setItems] = useState<Dash[] | null>(null);
  const [err, setErr] = useState("");
  const [spark, setSpark] = useState<Record<string, number[]>>({});   // 단지별 ㎡당 실거래 시계열

  const load = useCallback(() => {
    if (!token) return;
    fetch(`${API}/me/favorites/dashboard`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { if (!r.ok) throw new Error(`오류 ${r.status}`); return r.json(); })
      .then((d) => setItems(d.items || []))
      .catch((e) => setErr(e instanceof Error ? e.message : "불러오기 실패"));
  }, [token]);
  useEffect(load, [load]);

  // 관심단지 집합이 바뀔 때만 가격 흐름 시계열을 한 번에 받아둔다(면적 전환엔 재요청 안 함).
  // /stats/px-series 는 호출당 최대 6단지 → 6개씩 나눠 조회. 공개 엔드포인트(토큰 불필요).
  const sparkKey = (items || []).map((i) => i.complex_no).join(",");
  useEffect(() => {
    const nos = sparkKey ? sparkKey.split(",") : [];
    if (nos.length === 0) return;
    const chunks: string[][] = [];
    for (let i = 0; i < nos.length; i += 6) chunks.push(nos.slice(i, i + 6));
    let alive = true;
    Promise.all(chunks.map((c) =>
      fetch(`${API}/stats/px-series?nos=${c.join(",")}&years=3&mode=sqm`)
        .then((r) => r.json()).catch(() => ({ items: [] })),
    )).then((results) => {
      if (!alive) return;
      const map: Record<string, number[]> = {};
      for (const res of results)
        for (const it of (res.items || [])) {
          const vals = (it.series || []).map((p: [string, number]) => p[1]);
          if (vals.length >= 2) map[it.complex_no] = vals;
        }
      setSpark(map);
    });
    return () => { alive = false; };
  }, [sparkKey]);

  const [nearbyOf, setNearbyOf] = useState<{ no: string; name: string } | null>(null);
  const [subwayOf, setSubwayOf] = useState<string | null>(null);
  const [schoolOf, setSchoolOf] = useState<string | null>(null);
  const [cmp, setCmp] = useState<string[]>([]);          // 비교 선택(최대 4)
  const [cmpOpen, setCmpOpen] = useState(false);

  const toggleCmp = (cno: string) => {
    setCmp((prev) => prev.includes(cno)
      ? prev.filter((x) => x !== cno)
      : prev.length >= 4 ? (alert("비교는 최대 4개 단지까지예요"), prev) : [...prev, cno]);
  };
  const [areaBusy, setAreaBusy] = useState<string | null>(null);   // 전환 중인 complex_no

  // 카드 하나만 선택 면적 기준으로 다시 계산해 교체
  const changeArea = async (cno: string, areaName: string) => {
    if (!token) return;
    setAreaBusy(cno);
    try {
      const qs = `complex_no=${encodeURIComponent(cno)}${areaName ? `&area_name=${encodeURIComponent(areaName)}` : ""}`;
      const r = await fetch(`${API}/me/favorites/dashboard?${qs}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error(`오류 ${r.status}`);
      const d = await r.json();
      const fresh: Dash | undefined = (d.items || [])[0];
      if (fresh) setItems((prev) => prev?.map((x) => (x.complex_no === cno ? fresh : x)) ?? prev);
    } catch { /* 전환 실패 시 기존 카드 유지 */ }
    setAreaBusy(null);
  };

  const remove = async (cno: string) => {
    if (!token) return;
    if (!confirm("관심단지에서 해제할까요?")) return;
    await toggleFav(token, cno);
    setItems((prev) => prev?.filter((x) => x.complex_no !== cno) ?? prev);
  };

  if (!token) {
    return (
      <section>
        <div className="myfav-head">
          <h2 style={{ display: "flex", alignItems: "center", gap: 7, margin: 0 }}>
            <Heart size={19} strokeWidth={2.4} fill="currentColor" style={{ color: "#d6336c" }} aria-hidden />
            나의 관심단지
          </h2>
        </div>
        <div className="myfav-empty">
          <p>로그인하면 관심단지의 매물·급매·신고가·실거래를 한눈에 볼 수 있어요.</p>
          <button className="auth-btn kakao" onClick={loginKakao}
                  style={{ display: "inline-flex", alignItems: "center", gap: 6, border: "none", cursor: "pointer" }}>
            <span className="kakao-icon" aria-hidden>💬</span> 카카오로 로그인
          </button>
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="myfav-head">
        <h2 style={{ display: "flex", alignItems: "center", gap: 7, margin: 0 }}>
          <Heart size={19} strokeWidth={2.4} fill="currentColor" style={{ color: "#d6336c" }} aria-hidden />
          나의 관심단지
        </h2>
        <span className="myfav-count">{items ? `${items.length} / 20` : ""}</span>
      </div>
      <p className="muted" style={{ margin: "6px 0 14px", fontSize: 13 }}>
        단지 목록 어디서든 <Heart size={12} style={{ verticalAlign: -1, color: "#d6336c" }} aria-hidden /> 하트를 누르면
        여기에 모입니다.
      </p>

      {err && <div className="modal-msg">{err}</div>}
      {!items && !err && <Loading label="관심단지 요약을 모으는 중…" />}

      {items && items.length === 0 && (
        <div className="myfav-empty">
          <p>아직 관심단지가 없어요.</p>
          <Link to="/today/find" className="auth-btn kakao" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Search size={14} /> 단지 찾아보기
          </Link>
        </div>
      )}

      <div className="myfav-grid">
        {items?.map((it) => {
          const askDelta = it.ask_min_7d?.price && it.ask_min.A1
            ? it.ask_min.A1 - it.ask_min_7d.price : null;
          return (
            <div className="myfav-card" key={it.complex_no}>
              <div className="myfav-top">
                <div>
                  <Link to={`/complex/${it.complex_no}`} className="myfav-name">{it.complex_name}</Link>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
                  {it.areas.length > 0 && (
                    <select
                      className="myfav-area-sel"
                      value={it.area_name ?? ""}
                      disabled={areaBusy === it.complex_no}
                      onChange={(e) => changeArea(it.complex_no, e.target.value)}
                    >
                      <option value="">전체 면적</option>
                      {it.areas.map((a) => (
                        <option key={a.pyeong_name} value={a.pyeong_name}>
                          {a.pyeong_name}{a.exclusive_area ? ` · 전용 ${Math.round(a.exclusive_area)}㎡` : ""}
                        </option>
                      ))}
                    </select>
                  )}
                  <label className={`myfav-cmp-check${cmp.includes(it.complex_no) ? " on" : ""}`} title="비교 대상으로 선택">
                    <input type="checkbox" checked={cmp.includes(it.complex_no)} onChange={() => toggleCmp(it.complex_no)} />
                    비교
                  </label>
                  <button className="myfav-x" title="관심단지 해제" onClick={() => remove(it.complex_no)}>
                    <X size={14} />
                  </button>
                </div>
              </div>

              <div className="myfav-meta">
                <MapPin size={11} aria-hidden style={{ flexShrink: 0 }} />
                <span>{[it.region || "—", it.households ? `${it.households.toLocaleString()}세대` : null, it.approve_year ? `${it.approve_year}년` : null].filter(Boolean).join(" · ")}</span>
              </div>
              {(it.subway || it.school) && (
                <div className="myfav-chips">
                  {it.subway && (
                    <button type="button" className="myfav-chip" title="주변 지하철역 지도 보기" onClick={() => setSubwayOf(it.complex_no)}>
                      <TrainFront size={11} aria-hidden /> {it.subway.station} {it.subway.walk_min}분
                    </button>
                  )}
                  {it.school && (
                    <button type="button" className="myfav-chip green" title="학구도·배정 초등학교 지도 보기" onClick={() => setSchoolOf(it.complex_no)}>
                      <School size={11} aria-hidden /> {it.school.src === "near" ? "인근 " : ""}{it.school.name.replace("등학교", "")}{it.school.n > 1 ? ` 외 ${it.school.n - 1}` : ""} {it.school.walk_min}분
                    </button>
                  )}
                </div>
              )}

              <div className="myfav-sumline">
                매물 <b>{it.listings.total.toLocaleString()}건</b>
                <span> · 실매물 {Math.round(it.listings.units).toLocaleString()}</span>
                {it.listings.day_change != null && it.listings.day_change !== 0 && (
                  <em className={it.listings.day_change > 0 ? "up" : "down"}>
                    {" "}전일 {it.listings.day_change > 0 ? "+" : ""}{it.listings.day_change}
                  </em>
                )}
                {it.listings.new_week > 0 && <span> · 이번주 신규 {it.listings.new_week.toLocaleString()}</span>}
              </div>

              <div className="myfav-types">
                <div className="mft-row">
                  <span className="mft-t sale">매매</span>
                  <span className="mft-n">{it.listings.A1.toLocaleString()}건</span>
                  <span className="mft-p">{it.ask_min.A1 != null ? <>최저 <b>{eok(it.ask_min.A1)}</b></> : "—"}</span>
                  <span className="mft-x">
                    {askDelta != null && askDelta !== 0 && (
                      <em className={askDelta > 0 ? "up" : "down"}>{askDelta > 0 ? "▲" : "▼"} {eok(Math.abs(askDelta))}/7일</em>
                    )}
                  </span>
                </div>
                <div className="mft-row">
                  <span className="mft-t jeonse">전세</span>
                  <span className="mft-n">{it.listings.B1.toLocaleString()}건</span>
                  <span className="mft-p">{it.ask_min.B1 != null ? <>최저 <b>{eok(it.ask_min.B1)}</b></> : "—"}</span>
                  <span className="mft-x">{it.jeonse_ratio != null && <span className="muted">전세가율{it.jeonse_src === "ask" ? "(호가)" : ""} {it.jeonse_ratio}%</span>}</span>
                </div>
                <div className="mft-row">
                  <span className="mft-t wolse">월세</span>
                  <span className="mft-n">{it.listings.B2.toLocaleString()}건</span>
                  <span className="mft-p">{it.ask_min.B2 ? <>최저 <b>{eok(it.ask_min.B2.deposit)}/{Math.round(it.ask_min.B2.rent / 10_000).toLocaleString()}만</b></> : "—"}</span>
                  <span className="mft-x" />
                </div>
              </div>

              {spark[it.complex_no] && (
                <div className="myfav-spark" title="최근 3년 ㎡당 실거래가 흐름">
                  <span className="myfav-spark-k">시세 흐름<em>3년·㎡당</em></span>
                  <Sparkline data={spark[it.complex_no]} />
                </div>
              )}

              <div className="myfav-stats four">
                <div className="mf-stat">
                  <span className="mf-k"><ReceiptText size={11} aria-hidden /> 최근 실거래</span>
                  <b>{it.last_tx ? eok(it.last_tx.price) : "—"}</b>
                  <span className="mf-s">{it.last_tx ? `${it.last_tx.date} · ${areaLabel(it.last_tx.area)}${it.last_tx.floor ? ` ${it.last_tx.floor}층` : ""}${it.last_tx.kind === "silv" ? " · 분양권" : ""}` : "거래 없음"}</span>
                </div>
                <div className="mf-stat">
                  <span className="mf-k"><Trophy size={11} aria-hidden /> 신고가</span>
                  <b>{it.record_high ? eok(it.record_high.price) : "—"}</b>
                  <span className="mf-s">{it.record_high ? `${areaLabel(Number(it.record_high.area_key))} · ${it.record_high.date}` : ""}</span>
                </div>
                <div className="mf-stat">
                  <span className="mf-k"><Flame size={11} aria-hidden /> 급매</span>
                  <b className={it.quick_deals.n > 0 ? "hot" : ""}>{it.quick_deals.n}건</b>
                  <span className="mf-s">{it.quick_deals.best_discount ? `최대 ${it.quick_deals.best_discount}% 저렴` : "실거래평균 -5% 기준"}</span>
                </div>
                <div className="mf-stat">
                  <span className="mf-k">90일 매매 실거래</span>
                  <b>{it.tx_90d.n}건</b>
                  <span className="mf-s">{it.tx_90d.avg ? `평균 ${eok(it.tx_90d.avg)}` : ""}</span>
                </div>
              </div>

              <div className="myfav-links">
                <Link to={`/complex/${it.complex_no}`}>단지 분석 <ChevronRight size={12} /></Link>
                <Link to={`/complex/${it.complex_no}#quick`}>급매 {it.quick_deals.n > 0 ? `${it.quick_deals.n}건` : ""} <Flame size={12} /></Link>
                <Link to={`/complex/${it.complex_no}#reviews`}>리뷰 {it.reviews > 0 ? it.reviews : ""} <MessageSquareText size={12} /></Link>
                <button type="button" className="myfav-nearby-btn" onClick={() => setNearbyOf({ no: it.complex_no, name: it.complex_name })}>
                  주변단지 <MapIcon size={12} />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {cmp.length >= 2 && (
        <div className="myfav-cmpbar">
          <span>{cmp.length}개 단지 선택됨</span>
          <button type="button" onClick={() => setCmpOpen(true)}>
            <BarChart3 size={14} aria-hidden /> 나란히 비교하기
          </button>
          <button type="button" className="ghost" onClick={() => setCmp([])}>선택 해제</button>
        </div>
      )}

      {nearbyOf && <NearbyModal target={nearbyOf} onClose={() => setNearbyOf(null)} />}
      {subwayOf && <SubwayModal complexNo={subwayOf} onClose={() => setSubwayOf(null)} />}
      {schoolOf && <SchoolModal complexNo={schoolOf} onClose={() => setSchoolOf(null)} />}
      {cmpOpen && items && (
        <CompareModal picks={items.filter((x) => cmp.includes(x.complex_no))} onClose={() => setCmpOpen(false)} />
      )}
    </section>
  );
}

// 지정단지 비교 — 선택한 관심단지들을 지표 표 + ㎡당 실거래가 추이로 나란히
const CMP_COLORS = ["#1268d3", "#e0245e", "#1a7f4b", "#b25d00"];

function CompareModal({ picks, onClose }: { picks: Dash[]; onClose: () => void }) {
  const [chart, setChart] = useState<{ ym: string; [k: string]: string | number }[] | null>(null);

  useEffect(() => {
    fetch(`${API}/stats/px-series?nos=${picks.map((p) => p.complex_no).join(",")}&years=3&mode=sqm`)
      .then((r) => r.json())
      .then((d) => {
        const map = new Map<string, { ym: string; [k: string]: string | number }>();
        for (const it of d.items || []) {
          for (const [ym, v] of it.series as [string, number][]) {
            const row = map.get(ym) || { ym };
            row[it.complex_name] = Math.round(v / 10_000);   // ㎡당 만원
            map.set(ym, row);
          }
        }
        setChart([...map.values()].sort((a, b) => String(a.ym).localeCompare(String(b.ym))));
      })
      .catch(() => setChart([]));
  }, [picks]);

  const rows: [string, (d: Dash) => React.ReactNode][] = [
    ["지역", (d) => d.region || "—"],
    ["세대수", (d) => d.households ? `${d.households.toLocaleString()}세대` : "—"],
    ["연식", (d) => d.approve_year ? `${d.approve_year}년` : "—"],
    ["지하철", (d) => d.subway ? `${d.subway.station} ${d.subway.walk_min}분` : "—"],
    ["매물(실매물)", (d) => `${d.listings.total.toLocaleString()}건 (${Math.round(d.listings.units).toLocaleString()})`],
    ["매매 최저호가", (d) => eok(d.ask_min.A1)],
    ["전세 최저호가", (d) => eok(d.ask_min.B1)],
    ["전세가율", (d) => d.jeonse_ratio != null ? `${d.jeonse_ratio}%${d.jeonse_src === "ask" ? " (호가)" : ""}` : "—"],
    ["최근 실거래", (d) => d.last_tx ? `${eok(d.last_tx.price)} · ${d.last_tx.date.slice(2)}${d.last_tx.kind === "silv" ? " (분양권)" : ""}` : "—"],
    ["90일 평균(건수)", (d) => d.tx_90d.avg ? `${eok(d.tx_90d.avg)} (${d.tx_90d.n}건)` : `— (${d.tx_90d.n}건)`],
    ["신고가", (d) => d.record_high ? `${eok(d.record_high.price)} · ${areaLabel(Number(d.record_high.area_key))}` : "—"],
    ["급매", (d) => d.quick_deals.n > 0 ? `${d.quick_deals.n}건${d.quick_deals.best_discount ? ` · 최대 ${d.quick_deals.best_discount}%↓` : ""}` : "0건"],
  ];

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card myfav-cmp-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title"><BarChart3 size={15} aria-hidden /> 단지 비교 ({picks.length})</span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="table-scroll">
          <table className="myfav-cmp-table">
            <thead>
              <tr>
                <th />
                {picks.map((p, i) => (
                  <th key={p.complex_no}>
                    <Link to={`/complex/${p.complex_no}`} style={{ color: CMP_COLORS[i] }}>{p.complex_name}</Link>
                    {p.area_name && <div className="muted" style={{ fontSize: 10.5, fontWeight: 500 }}>{p.area_name} 기준</div>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(([label, fn]) => (
                <tr key={label}>
                  <td className="cmp-k">{label}</td>
                  {picks.map((p) => <td key={p.complex_no}>{fn(p)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 12.5, fontWeight: 700, color: "#46566b", marginBottom: 4 }}>
            ㎡당 실거래가 추이 (최근 3년 · 만원/㎡ · 전 평형)
          </div>
          {chart == null ? <div className="muted" style={{ fontSize: 12 }}>차트 로딩…</div> : (
            <div style={{ width: "100%", height: 260 }}>
              <ResponsiveContainer>
                <LineChart data={chart} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef1f6" />
                  <XAxis dataKey="ym" tick={{ fontSize: 10 }} minTickGap={28} />
                  <YAxis tick={{ fontSize: 10 }} width={46} domain={["auto", "auto"]} />
                  <ChartTooltip labelStyle={{ fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 11.5 }} />
                  {picks.map((p, i) => (
                    <Line key={p.complex_no} name={p.complex_name} type="monotone"
                      dataKey={p.complex_name} stroke={CMP_COLORS[i]} strokeWidth={2} dot={false} connectNulls />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

// 주변단지 팝업 — 반경 1.5km 같은 유형 단지의 거리·세대·매물·시세 요약 (거리순)
type Nearby = {
  complex_no: string; complex_name: string; dong_name: string | null;
  distance_m: number; households: number | null; use_approve_ymd: string | null;
  lat: number; lng: number;
  deal_count: number; avg_amount: number | null;
  listings?: { n: number; ask_min: number | null };
  subway?: { station: string; walk_min: number } | null;
};

type NearbySelf = { deal_count: number; avg_amount: number | null; listings?: { n: number; ask_min: number | null } };

function NearbyModal({ target, onClose }: { target: { no: string; name: string }; onClose: () => void }) {
  const [data, setData] = useState<{ nearby: Nearby[]; radius_km: number; months: number; lat: number; lng: number; self?: NearbySelf } | null>(null);
  const [err, setErr] = useState("");
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);

  useEffect(() => {
    fetch(`${API}/complex/${target.no}/nearby-transactions?months=12&include_listings=1&limit=15`)
      .then((r) => { if (!r.ok) throw new Error(`오류 ${r.status}`); return r.json(); })
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "불러오기 실패"));
  }, [target.no]);

  // 카카오지도 — 기준 아파트 + 주변단지 시세 마커(호버 시 상세 오버레이, 클릭 시 이동)
  useEffect(() => {
    if (!data || !mapEl.current) return;
    let cancelled = false;
    import("../lib/kakaomap").then(({ loadKakao, escapeHtml, attachMapControls }) => loadKakao().then(() => {
      if (cancelled || !mapEl.current) return;
      const kakao = window.kakao;
      const map = new kakao.maps.Map(mapEl.current, {
        center: new kakao.maps.LatLng(data.lat, data.lng), level: 5,
      });
      mapRef.current = map;
      attachMapControls(map, mapEl.current);
      const bounds = new kakao.maps.LatLngBounds();

      const aptPos = new kakao.maps.LatLng(data.lat, data.lng);
      bounds.extend(aptPos);
      // 기준단지도 같은 잣대의 시세·거래수를 달아 주변과 바로 비교되게
      const me = data.self;
      const mePx = me?.avg_amount ? eok(me.avg_amount) : (me?.listings?.ask_min ? eok(me.listings.ask_min) : "");
      const meStat = me && mePx ? `<span class="nbm-mepx">${mePx} · ${me.deal_count}건</span>` : "";
      new kakao.maps.CustomOverlay({
        map, position: aptPos, yAnchor: 1.15, zIndex: 20,
        content: `<div class="swm-apt">🏠 ${escapeHtml(target.name)}${meStat}</div>`,
      });

      for (const n of data.nearby) {
        if (!n.lat || !n.lng) continue;
        const pos = new kakao.maps.LatLng(n.lat, n.lng);
        bounds.extend(pos);
        const px = n.avg_amount ? eok(n.avg_amount) : (n.listings?.ask_min ? eok(n.listings.ask_min) : "—");
        const tip = [
          `<b>${escapeHtml(n.complex_name)}</b>`,
          `${n.distance_m >= 1000 ? (n.distance_m / 1000).toFixed(1) + "km" : n.distance_m + "m"}${n.households ? " · " + n.households.toLocaleString() + "세대" : ""}${n.use_approve_ymd ? " · " + String(n.use_approve_ymd).slice(0, 4) + "년" : ""}`,
          `실거래 ${n.deal_count}건${n.avg_amount ? " · 평균 " + eok(n.avg_amount) : ""} (12개월)`,
          n.listings ? `매물 ${n.listings.n}건${n.listings.ask_min ? " · 최저 " + eok(n.listings.ask_min) : ""}` : "",
          n.subway ? `${escapeHtml(n.subway.station)} ${n.subway.walk_min}분` : "",
        ].filter(Boolean).join("<br/>");
        // 오버레이는 마커마다 독립 레이어라 CSS z-index로는 이웃 마커를 못 덮는다 —
        // 호버 시 오버레이 자체를 최상단으로 올렸다가 벗어나면 되돌린다
        const el = document.createElement("a");
        el.className = "nbm-marker";
        el.href = `/complex/${n.complex_no}`;
        el.innerHTML = `<span class="nbm-px">${px}</span><span class="nbm-n">${n.deal_count}건</span>` +
          `<span class="nbm-tip">${tip}</span>`;
        const ov = new kakao.maps.CustomOverlay({ map, position: pos, yAnchor: 0.5, zIndex: 5, content: el });
        el.addEventListener("mouseenter", () => ov.setZIndex(120));
        el.addEventListener("mouseleave", () => ov.setZIndex(5));
      }
      if (data.nearby.length > 0) map.setBounds(bounds, 30, 30, 30, 30);
    })).catch(() => setErr("지도 로드 실패 — 목록으로 확인해주세요"));
    return () => { cancelled = true; };
  }, [data, target.name]);

  const focus = (n: Nearby) => {
    const kakao = window.kakao;
    if (mapRef.current && kakao?.maps && n.lat) mapRef.current.panTo(new kakao.maps.LatLng(n.lat, n.lng));
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card myfav-nearby-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title"><MapIcon size={15} strokeWidth={2.2} aria-hidden /> {target.name} 주변단지</span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>
        {err && <div className="modal-msg">{err}</div>}
        {!data && !err && <div className="muted" style={{ padding: "18px 4px", fontSize: 13 }}>주변 단지를 찾는 중…</div>}
        {data && (
          <>
            <div ref={mapEl} className="swm-map" style={{ height: 300 }} />
            <div className="muted" style={{ fontSize: 11.5, margin: "0 0 6px" }}>
              마커 = 12개월 평균 실거래가·거래수 · 올리면 상세, 누르면 단지로 이동 · 반경 {data.radius_km}km 같은 유형
            </div>
            {data.nearby.length === 0 && <div className="muted" style={{ padding: "10px 4px", fontSize: 13 }}>반경 내 단지가 없어요.</div>}
            <div className="myfav-nearby-list">
              {data.nearby.map((n) => (
                <Link key={n.complex_no} to={`/complex/${n.complex_no}`} className="mfn-row"
                  onMouseEnter={() => focus(n)} onClick={onClose}>
                  <div className="mfn-main">
                    <b>{n.complex_name}</b>
                    <span className="mfn-meta">
                      {n.distance_m >= 1000 ? `${(n.distance_m / 1000).toFixed(1)}km` : `${n.distance_m}m`}
                      {n.dong_name ? ` · ${n.dong_name}` : ""}
                      {n.households ? ` · ${n.households.toLocaleString()}세대` : ""}
                      {n.use_approve_ymd ? ` · ${String(n.use_approve_ymd).slice(0, 4)}년` : ""}
                      {n.subway ? ` · ${n.subway.station} ${n.subway.walk_min}분` : ""}
                    </span>
                  </div>
                  <div className="mfn-nums">
                    <span className="mfn-ask">{n.listings?.ask_min != null ? <>매물 {n.listings.n}건 · 최저 <b>{eok(n.listings.ask_min)}</b></> : "매물 없음"}</span>
                    <span className="mfn-tx">{n.deal_count > 0 ? `실거래 ${n.deal_count}건 · 평균 ${eok(n.avg_amount)}` : "최근 실거래 없음"}</span>
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}

