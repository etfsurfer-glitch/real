// 관심단지 대시보드 창 — 운영 /my/favorites 를 지도 안에서 다시 그린다(같은 API /me/favorites/dashboard).
import { useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { Dd, getJson, API, type DrawerTab } from "./Drawer";
import { LoginBox, authHeaders } from "./Request";
import { areaLabel } from "../src/lib/area";

type Dash = {
  complex_no: string; complex_name: string; region: string; households: number | null; approve_year: string | null;
  subway: { station: string; lines: string; distance_m: number; walk_min: number } | null;
  school: { name: string; names_all: string; n: number; distance_m: number; walk_min: number; src: string } | null;
  areas: { pyeong_name: string; exclusive_area: number | null }[]; area_name: string | null;
  listings: { total: number; units: number; A1: number; B1: number; B2: number; day_change: number | null; new_week: number };
  ask_min: { A1: number | null; B1: number | null; B2: { deposit: number; rent: number } | null };
  ask_min_7d: { date: string; price: number } | null;
  last_tx: { price: number; date: string; area: number; floor: number | null; kind?: string } | null;
  tx_90d: { avg: number | null; n: number }; jeonse_ratio: number | null; jeonse_src: "tx" | "ask" | null;
  record_high: { area_key: string; price: number; date: string } | null;
  quick_deals: { n: number; best_discount: number | null }; reviews: number;
};
const eok = (won: number | null | undefined) => {
  if (won == null) return "-";
  if (won >= 1e8) { const e = won / 1e8; return `${e >= 100 ? Math.round(e).toLocaleString() : e % 1 === 0 ? e.toFixed(0) : e.toFixed(1)}억`; }
  return `${Math.round(won / 1e4).toLocaleString()}만`;
};
const CMP_COLORS = ["#1268d3", "#d23b3b", "#159570", "#b25d00"];

function Spark({ data }: { data: number[] }) {
  if (data.length < 2) return null;
  const n = data.length, min = Math.min(...data), max = Math.max(...data), span = max - min || 1;
  const pts = data.map((v, i) => `${((i / (n - 1)) * 100).toFixed(2)},${(4 + (1 - (v - min) / span) * 22).toFixed(2)}`).join(" ");
  const col = data[n - 1] >= data[0] ? "#d23b3b" : "#1268d3";
  return <svg className="t2-spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden><polygon points={`0,30 ${pts} 100,30`} fill={col} fillOpacity=".1" /><polyline points={pts} fill="none" stroke={col} strokeWidth="1.6" vectorEffect="non-scaling-stroke" /></svg>;
}

export function FavWindow({ onClose, phone, session, onGo, onRemoved }: {
  onClose: () => void; phone: boolean; session: Session | null;
  onGo: (no: string, name: string, tab?: DrawerTab) => void; onRemoved: (no: string) => void;
}) {
  const [items, setItems] = useState<Dash[] | null>(null);
  const [err, setErr] = useState("");
  const [spark, setSpark] = useState<Record<string, number[]>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [cmp, setCmp] = useState<string[]>([]);
  const [cmpOpen, setCmpOpen] = useState(false);
  const [dd, setDd] = useState<string | null>(null);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h); return () => document.removeEventListener("keydown", h);
  }, [onClose]);
  useEffect(() => {
    if (!session) { setItems(null); return; }
    fetch(`${API}/me/favorites/dashboard`, { headers: authHeaders(session) }).then((r) => { if (!r.ok) throw new Error(`오류 ${r.status}`); return r.json(); })
      .then((d) => setItems(d.items || [])).catch((e: Error) => setErr(e.message));
  }, [session]);
  const key = (items || []).map((i) => i.complex_no).join(",");
  useEffect(() => {
    const nos = key ? key.split(",") : []; if (!nos.length) return;
    const chunks: string[][] = []; for (let i = 0; i < nos.length; i += 6) chunks.push(nos.slice(i, i + 6));
    let alive = true;
    Promise.all(chunks.map((c) => getJson(`/stats/px-series?nos=${c.join(",")}&years=3&mode=sqm`).catch(() => ({ items: [] })))).then((rs) => {
      if (!alive) return;
      const m: Record<string, number[]> = {};
      for (const r of rs) for (const it of r.items || []) { const v = (it.series || []).map((p: [string, number]) => p[1]); if (v.length >= 2) m[it.complex_no] = v; }
      setSpark(m);
    });
    return () => { alive = false; };
  }, [key]);
  const changeArea = async (no: string, area: string) => {
    if (!session) return; setBusy(no);
    try {
      const r = await fetch(`${API}/me/favorites/dashboard?complex_no=${encodeURIComponent(no)}${area ? `&area_name=${encodeURIComponent(area)}` : ""}`, { headers: authHeaders(session) });
      const d = await r.json(); const fresh: Dash | undefined = (d.items || [])[0];
      if (fresh) setItems((p) => p?.map((x) => (x.complex_no === no ? fresh : x)) ?? p);
    } catch { /* 유지 */ }
    setBusy(null);
  };
  const remove = async (no: string) => {
    if (!session) return;
    await fetch(`${API}/me/favorites/${no}`, { method: "DELETE", headers: authHeaders(session) }).catch(() => null);
    setItems((p) => p?.filter((x) => x.complex_no !== no) ?? p); setCmp((c) => c.filter((x) => x !== no)); onRemoved(no);
  };
  const picks = useMemo(() => (items || []).filter((x) => cmp.includes(x.complex_no)), [items, cmp]);

  return (
    <section className={"t2-win" + (phone ? " phone" : "")} role="dialog" aria-label="관심단지">
      <header className="t2-win-h">
        <button className="t2-win-x" onClick={onClose} aria-label="지도로 돌아가기"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>지도</button>
        <h2>관심단지</h2>
        {items && <span className="t2-win-cnt">{items.length} / 20</span>}
        {cmp.length >= 2 && !cmpOpen && <button className="t2-win-act" onClick={() => setCmpOpen(true)}>{cmp.length}개 나란히 비교</button>}
        {cmpOpen && <button className="t2-win-act" onClick={() => setCmpOpen(false)}>목록으로</button>}
      </header>
      <div className="t2-win-b">
        <div className="t2-win-in">
          {!session ? <div style={{ maxWidth: 420 }}><LoginBox why="로그인하면 관심단지의 매물·급매·신고가·실거래를 한눈에 볼 수 있어요." /></div>
            : err ? <p className="t2-sempty">{err}</p>
            : !items ? <div className="t2-sload"><i /><i /><i /></div>
            : items.length === 0 ? <p className="t2-sempty">아직 관심단지가 없어요. 단지 서랍의 하트를 누르면 여기에 모여요(최대 20곳).</p>
            : cmpOpen ? <Compare picks={picks} onGo={onGo} />
            : (
              <>
                <p className="t2-snote">단지 서랍의 하트를 누르면 여기에 모여요. 비교에 체크하면 위 버튼으로 나란히 볼 수 있어요.</p>
                <div className="t2-favgrid">
                  {items.map((it) => {
                    const delta = it.ask_min_7d?.price && it.ask_min.A1 ? it.ask_min.A1 - it.ask_min_7d.price : null;
                    return (
                      <div className="t2-favcard" key={it.complex_no}>
                        <div className="t2-favh">
                          <button className="t2-favname" onClick={() => onGo(it.complex_no, it.complex_name)}>{it.complex_name}</button>
                          <div className="t2-favtools">
                            {it.areas.length > 0 && (
                              <Dd id={`a${it.complex_no}`} open={dd} setOpen={setDd} label={busy === it.complex_no ? "…" : it.area_name || "전체 면적"} active={!!it.area_name}>
                                <button className={!it.area_name ? "on" : ""} onClick={() => changeArea(it.complex_no, "")}>전체 면적</button>
                                {it.areas.map((a) => <button key={a.pyeong_name} className={a.pyeong_name === it.area_name ? "on" : ""} onClick={() => changeArea(it.complex_no, a.pyeong_name)}>{a.pyeong_name}{a.exclusive_area ? ` · ${areaLabel(a.exclusive_area)}` : ""}</button>)}
                              </Dd>
                            )}
                            <label className="t2-favcmp"><input type="checkbox" checked={cmp.includes(it.complex_no)} onChange={() => setCmp((c) => (c.includes(it.complex_no) ? c.filter((x) => x !== it.complex_no) : c.length >= 4 ? c : [...c, it.complex_no]))} />비교</label>
                            <button className="t2-lnk mut" onClick={() => remove(it.complex_no)}>해제</button>
                          </div>
                        </div>
                        <p className="t2-favmeta">{[it.region || "-", it.households ? `${it.households.toLocaleString()}세대` : "", it.approve_year ? `${it.approve_year}년` : "", it.subway ? `${it.subway.station} ${it.subway.walk_min}분` : "", it.school ? `${it.school.src === "near" ? "인근 " : ""}${it.school.name.replace("등학교", "")}${it.school.n > 1 ? ` 외 ${it.school.n - 1}` : ""} ${it.school.walk_min}분` : ""].filter(Boolean).join(" · ")}</p>
                        <p className="t2-favsum">매물 <b>{it.listings.total.toLocaleString()}건</b> · 실매물 {Math.round(it.listings.units).toLocaleString()}{it.listings.day_change ? <em className={it.listings.day_change > 0 ? "up" : "down"}> 전일 {it.listings.day_change > 0 ? "+" : ""}{it.listings.day_change}</em> : null}{it.listings.new_week > 0 && <> · 이번주 신규 {it.listings.new_week}</>}</p>
                        <table className="t2-tbl t2-favtr"><tbody>
                          <tr><th>매매</th><td className="num">{it.listings.A1.toLocaleString()}건</td><td>{it.ask_min.A1 != null ? <>최저 <b>{eok(it.ask_min.A1)}</b></> : "-"}</td><td>{delta ? <em className={delta > 0 ? "up" : "down"}>{delta > 0 ? "+" : "-"}{eok(Math.abs(delta))} / 7일</em> : ""}</td></tr>
                          <tr><th>전세</th><td className="num">{it.listings.B1.toLocaleString()}건</td><td>{it.ask_min.B1 != null ? <>최저 <b>{eok(it.ask_min.B1)}</b></> : "-"}</td><td className="mut">{it.jeonse_ratio != null ? `전세가율${it.jeonse_src === "ask" ? "(호가)" : ""} ${it.jeonse_ratio}%` : ""}</td></tr>
                          <tr><th>월세</th><td className="num">{it.listings.B2.toLocaleString()}건</td><td>{it.ask_min.B2 ? <>최저 <b>{eok(it.ask_min.B2.deposit)}/{Math.round(it.ask_min.B2.rent / 1e4).toLocaleString()}만</b></> : "-"}</td><td /></tr>
                        </tbody></table>
                        {spark[it.complex_no] && <div className="t2-favspark"><span>시세 흐름 <small>3년 · ㎡당</small></span><Spark data={spark[it.complex_no]} /></div>}
                        <div className="t2-kpis small">
                          <div><span>최근 실거래</span><b>{it.last_tx ? eok(it.last_tx.price) : "-"}</b><small>{it.last_tx ? `${it.last_tx.date} · ${areaLabel(it.last_tx.area)}${it.last_tx.floor ? ` ${it.last_tx.floor}층` : ""}${it.last_tx.kind === "silv" ? " · 분양권" : ""}` : "거래 없음"}</small></div>
                          <div><span>신고가</span><b>{it.record_high ? eok(it.record_high.price) : "-"}</b><small>{it.record_high ? `${areaLabel(Number(it.record_high.area_key))} · ${it.record_high.date}` : ""}</small></div>
                          <div><span>급매</span><b className={it.quick_deals.n > 0 ? "up" : ""}>{it.quick_deals.n}건</b><small>{it.quick_deals.best_discount ? `최대 ${it.quick_deals.best_discount}% 저렴` : "실거래 평균 -5% 기준"}</small></div>
                          <div><span>90일 매매 실거래</span><b>{it.tx_90d.n}건</b><small>{it.tx_90d.avg ? `평균 ${eok(it.tx_90d.avg)}` : ""}</small></div>
                        </div>
                        <div className="t2-favlinks">
                          <button className="t2-lnk" onClick={() => onGo(it.complex_no, it.complex_name, "info")}>단지 분석</button>
                          <button className="t2-lnk" onClick={() => onGo(it.complex_no, it.complex_name, "deals")}>급매{it.quick_deals.n > 0 ? ` ${it.quick_deals.n}건` : ""}</button>
                          <button className="t2-lnk" onClick={() => onGo(it.complex_no, it.complex_name, "review")}>리뷰{it.reviews > 0 ? ` ${it.reviews}` : ""}</button>
                          <button className="t2-lnk" onClick={() => onGo(it.complex_no, it.complex_name, "nearby")}>주변단지</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
        </div>
      </div>
    </section>
  );
}

function Compare({ picks, onGo }: { picks: Dash[]; onGo: (no: string, name: string) => void }) {
  const [chart, setChart] = useState<{ ym: string; [k: string]: string | number }[] | null>(null);
  useEffect(() => {
    getJson(`/stats/px-series?nos=${picks.map((p) => p.complex_no).join(",")}&years=3&mode=sqm`).then((d) => {
      const m = new Map<string, { ym: string; [k: string]: string | number }>();
      for (const it of d.items || []) for (const [ym, v] of it.series as [string, number][]) { const row = m.get(ym) || { ym }; row[it.complex_name] = Math.round(v / 1e4); m.set(ym, row); }
      setChart([...m.values()].sort((a, b) => String(a.ym).localeCompare(String(b.ym))));
    }).catch(() => setChart([]));
  }, [picks]);
  const rows: [string, (d: Dash) => string][] = [
    ["지역", (d) => d.region || "-"], ["세대수", (d) => (d.households ? `${d.households.toLocaleString()}세대` : "-")], ["연식", (d) => (d.approve_year ? `${d.approve_year}년` : "-")],
    ["지하철", (d) => (d.subway ? `${d.subway.station} ${d.subway.walk_min}분` : "-")], ["매물(실매물)", (d) => `${d.listings.total.toLocaleString()}건 (${Math.round(d.listings.units).toLocaleString()})`],
    ["매매 최저호가", (d) => eok(d.ask_min.A1)], ["전세 최저호가", (d) => eok(d.ask_min.B1)], ["전세가율", (d) => (d.jeonse_ratio != null ? `${d.jeonse_ratio}%${d.jeonse_src === "ask" ? " (호가)" : ""}` : "-")],
    ["최근 실거래", (d) => (d.last_tx ? `${eok(d.last_tx.price)} · ${d.last_tx.date.slice(2)}${d.last_tx.kind === "silv" ? " (분양권)" : ""}` : "-")],
    ["90일 평균(건수)", (d) => (d.tx_90d.avg ? `${eok(d.tx_90d.avg)} (${d.tx_90d.n}건)` : `- (${d.tx_90d.n}건)`)],
    ["신고가", (d) => (d.record_high ? `${eok(d.record_high.price)} · ${areaLabel(Number(d.record_high.area_key))}` : "-")],
    ["급매", (d) => (d.quick_deals.n > 0 ? `${d.quick_deals.n}건${d.quick_deals.best_discount ? ` · 최대 ${d.quick_deals.best_discount}%` : ""}` : "0건")],
  ];
  return (
    <>
      <h3 className="t2-win-ttl">단지 비교 <small>{picks.length}곳</small></h3>
      <table className="t2-tbl t2-cmptbl">
        <thead><tr><th /><th>{picks.map((p, i) => <th key={p.complex_no}><button className="t2-lnk" style={{ color: CMP_COLORS[i], textDecoration: "none" }} onClick={() => onGo(p.complex_no, p.complex_name)}>{p.complex_name}</button>{p.area_name && <small className="blk">{p.area_name} 기준</small>}</th>)}</th></tr></thead>
        <tbody>{rows.map(([l, f]) => <tr key={l}><th>{l}</th>{picks.map((p) => <td key={p.complex_no}>{f(p)}</td>)}</tr>)}</tbody>
      </table>
      <div className="t2-sh"><h3>㎡당 실거래가 추이 <small>최근 3년 · 만원/㎡ · 전 평형</small></h3></div>
      {chart == null ? <div className="t2-sload"><i /><i /></div> : chart.length === 0 ? <p className="t2-sempty">추이 자료가 없어요.</p> : (
        <div className="t2-chart" style={{ height: 260 }}>
          <ResponsiveContainer><LineChart data={chart} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef1f6" /><XAxis dataKey="ym" tick={{ fontSize: 10 }} minTickGap={28} /><YAxis tick={{ fontSize: 10 }} width={46} domain={["auto", "auto"]} />
            <Tooltip contentStyle={{ fontSize: 12, border: "1px solid #e3e8ee", borderRadius: 4, boxShadow: "none" }} />
            {picks.map((p, i) => <Line key={p.complex_no} name={p.complex_name} type="monotone" dataKey={p.complex_name} stroke={CMP_COLORS[i]} strokeWidth={2} dot={false} connectNulls />)}
          </LineChart></ResponsiveContainer>
        </div>
      )}
    </>
  );
}
