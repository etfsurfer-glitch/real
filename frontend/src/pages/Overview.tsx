import { useEffect, useMemo, useRef, useState } from "react";
import FetchError from "../components/FetchError";
import { Loading } from "../components/Loading";
import ShareBar from "../components/ShareBar";
import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { TxRegionPulse } from "./TxRegionPulse";
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { supabase, TRADE_LABEL } from "../supabase";

type RegionAgg = {
  cortar_no: string;
  trade_type: string;
  listing_count: number;
  complex_count: number;
};

type Region = {
  cortar_no: string;
  cortar_name: string;
  cortar_type: "city" | "dvsn" | "sec";
};

type ComplexHit = {
  complex_no: string;
  complex_name: string;
  total_household_count: number | null;
  use_approve_ymd: string | null;
  cortar_no: string | null;
};

type RecentTx = { days: number; sale: number; jeonse: number; wolse: number };
type Freshness = { new_sale: number; new_jeonse: number; new_wolse: number; last_updated: string | null };

type TopComplex = { complex_no: string; complex_name: string; count: number };
type TopComplexes = { days: number; sale: TopComplex[]; jeonse: TopComplex[]; wolse: TopComplex[] };

type TopListings = {
  snapshot_date: string | null;
  A1: TopComplex[]; B1: TopComplex[]; B2: TopComplex[];
};
type TrendPoint = { snapshot_date: string; A1: number; B1: number; B2: number };
type ListingTrend = { days: number; series: TrendPoint[] };

const API_BASE = import.meta.env.VITE_API_BASE;

const WEEKDAYS_KO = ["일", "월", "화", "수", "목", "금", "토"];

function formatKoCount(v: number): string {
  if (v === 0) return "0";
  const sign = v < 0 ? "-" : "";
  const a = Math.abs(v);
  if (a >= 1_000_000) {
    const n = a / 1_000_000;
    return `${sign}${n % 1 === 0 ? n.toFixed(0) : n.toFixed(1)}백만`;
  }
  if (a >= 10_000) return `${sign}${Math.round(a / 10_000)}만`;
  if (a >= 1_000) return `${sign}${Math.round(a / 1_000)}천`;
  return `${sign}${a}`;
}

function formatSnapshotDate(d: string | null): string {
  if (!d) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
  if (!m) return d;
  const [, y, mm, dd] = m;
  const wd = WEEKDAYS_KO[new Date(`${d}T00:00:00`).getDay()];
  return `${y}년 ${Number(mm)}월 ${Number(dd)}일 (${wd})`;
}

function describeError(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (e && typeof e === "object") {
    const o = e as Record<string, unknown>;
    const parts = [o.message, o.details, o.hint, o.code].filter(Boolean);
    if (parts.length) return parts.join(" · ");
    try { return JSON.stringify(e); } catch { /* ignore */ }
  }
  return String(e);
}

// "오늘 공개된 실거래" 신선도 배지 (silgga 벤치마크). last_updated 는 UTC 저장이라
// 'Z' 를 붙여 파싱한 뒤 한국 날짜로 표시. 매일 새벽 daily_run 으로 갱신됨을 안내.
function FreshBadge({ fresh }: { fresh: Freshness }) {
  const asOf = (() => {
    if (!fresh.last_updated) return null;
    const d = new Date(fresh.last_updated.replace(" ", "T") + "Z");
    return isNaN(d.getTime()) ? null
      : d.toLocaleDateString("ko-KR", { month: "long", day: "numeric", weekday: "short" });
  })();
  const fmt = (n: number) => n.toLocaleString();
  return (
    <div className="fresh-badge">
      <div className="fresh-badge-head">
        <Sparkles size={15} strokeWidth={2.3} aria-hidden />
        <b>오늘 공개된 실거래</b>
        {asOf && <span className="fresh-badge-date">{asOf} 기준</span>}
      </div>
      <div className="fresh-badge-nums">
        <Link to="/tx-stats" className="fresh-num sale"><span>매매</span><b>{fmt(fresh.new_sale)}</b></Link>
        <Link to="/tx-stats" className="fresh-num jeonse"><span>전세</span><b>{fmt(fresh.new_jeonse)}</b></Link>
        <Link to="/tx-stats" className="fresh-num wolse"><span>월세</span><b>{fmt(fresh.new_wolse)}</b></Link>
      </div>
      <div className="fresh-badge-foot">매일 새벽 국토부 신규 신고분을 자동 반영합니다</div>
    </div>
  );
}

export default function Overview() {
  const shareRef = useRef<HTMLDivElement>(null);
  // Snapshot summary (top cards)
  const [snapshotDate, setSnapshotDate] = useState<string | null>(null);
  const [regionAgg, setRegionAgg] = useState<RegionAgg[]>([]);
  const [recentTx, setRecentTx] = useState<RecentTx | null>(null);
  const [fresh, setFresh] = useState<Freshness | null>(null);
  const [topComplexes, setTopComplexes] = useState<TopComplexes | null>(null);
  const [topListings, setTopListings] = useState<TopListings | null>(null);
  const [listingTrend, setListingTrend] = useState<ListingTrend | null>(null);

  // Search
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<ComplexHit[]>([]);
  const [searching, setSearching] = useState(false);

  // Region drill-down
  const [cities, setCities] = useState<Region[]>([]);
  const [dvsns, setDvsns] = useState<Region[]>([]);
  const [secs, setSecs] = useState<Region[]>([]);
  const [secComplexes, setSecComplexes] = useState<ComplexHit[]>([]);
  const [selectedCity, setSelectedCity] = useState<Region | null>(null);
  const [selectedDvsn, setSelectedDvsn] = useState<Region | null>(null);
  const [selectedSec, setSelectedSec] = useState<Region | null>(null);

  // Chart series visibility (default: all on)
  const [showSeries, setShowSeries] = useState<Record<"A1" | "B1" | "B2", boolean>>({
    A1: true, B1: true, B2: true,
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Bootstrap: latest snapshot + region totals + city list
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const latestRes = await supabase
          .from("region_daily_agg")
          .select("snapshot_date")
          .order("snapshot_date", { ascending: false })
          .limit(1);
        if (latestRes.error) throw latestRes.error;
        const date = latestRes.data?.[0]?.snapshot_date ?? null;
        if (cancelled) return;
        setSnapshotDate(date);

        if (date) {
          const aggRes = await supabase
            .from("region_daily_agg")
            .select("cortar_no, trade_type, listing_count, complex_count")
            .eq("snapshot_date", date);
          if (aggRes.error) throw aggRes.error;
          if (cancelled) return;
          setRegionAgg(aggRes.data ?? []);
        }

        const citiesRes = await supabase
          .from("regions")
          .select("cortar_no, cortar_name, cortar_type")
          .eq("cortar_type", "city")
          .order("cortar_name", { ascending: true });
        if (citiesRes.error) throw citiesRes.error;
        if (cancelled) return;
        setCities(citiesRes.data ?? []);

        // Stats endpoints (local_api only). Production Supabase returns no
        // /stats routes so the cards just stay placeholder.
        if (API_BASE) {
          try {
            const [rTx, rTop, rLT, rTL, rF] = await Promise.all([
              fetch(`${API_BASE}/stats/recent-tx?days=7`),
              fetch(`${API_BASE}/stats/top-complexes?days=7`),
              fetch(`${API_BASE}/stats/listing-trend?days=60`),
              fetch(`${API_BASE}/stats/top-listings?limit=5`),
              fetch(`${API_BASE}/stats/freshness`),
            ]);
            if (rTx.ok && !cancelled) setRecentTx(await rTx.json());
            if (rTop.ok && !cancelled) setTopComplexes(await rTop.json());
            if (rLT.ok && !cancelled) setListingTrend(await rLT.json());
            if (rTL.ok && !cancelled) setTopListings(await rTL.json());
            if (rF.ok && !cancelled) setFresh(await rF.json());
          } catch { /* ignore — cards will stay placeholder */ }
        }

        setLoading(false);
      } catch (e: unknown) {
        if (!cancelled) {
          setError(describeError(e));
          setLoading(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Debounce search input
  useEffect(() => {
    const t = window.setTimeout(() => setSearchTerm(searchInput.trim()), 300);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  // Search complexes by name
  useEffect(() => {
    let cancelled = false;
    if (searchTerm.length < 1) {
      setSearchResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    (async () => {
      try {
        const r = await supabase
          .from("complexes")
          .select("complex_no, complex_name, total_household_count, use_approve_ymd, cortar_no")
          .ilike("complex_name", `%${searchTerm}%`)
          .order("complex_name", { ascending: true })
          .limit(30);
        if (r.error) throw r.error;
        if (!cancelled) setSearchResults(r.data ?? []);
      } catch (e: unknown) {
        if (!cancelled) setError(describeError(e));
      } finally {
        if (!cancelled) setSearching(false);
      }
    })();
    return () => { cancelled = true; };
  }, [searchTerm]);

  // When a city is picked, fetch its dvsns
  useEffect(() => {
    let cancelled = false;
    setDvsns([]); setSelectedDvsn(null);
    setSecs([]); setSelectedSec(null); setSecComplexes([]);
    if (!selectedCity) return;
    (async () => {
      const r = await supabase
        .from("regions")
        .select("cortar_no, cortar_name, cortar_type")
        .eq("parent_cortar_no", selectedCity.cortar_no)
        .order("cortar_name", { ascending: true });
      if (r.error) { if (!cancelled) setError(describeError(r.error)); return; }
      if (!cancelled) setDvsns(r.data ?? []);
    })();
    return () => { cancelled = true; };
  }, [selectedCity]);

  // When a dvsn is picked, fetch its secs
  useEffect(() => {
    let cancelled = false;
    setSecs([]); setSelectedSec(null); setSecComplexes([]);
    if (!selectedDvsn) return;
    (async () => {
      const r = await supabase
        .from("regions")
        .select("cortar_no, cortar_name, cortar_type")
        .eq("parent_cortar_no", selectedDvsn.cortar_no)
        .order("cortar_name", { ascending: true });
      if (r.error) { if (!cancelled) setError(describeError(r.error)); return; }
      if (!cancelled) setSecs(r.data ?? []);
    })();
    return () => { cancelled = true; };
  }, [selectedDvsn]);

  // When a sec is picked, fetch its complexes
  useEffect(() => {
    let cancelled = false;
    setSecComplexes([]);
    if (!selectedSec) return;
    (async () => {
      const r = await supabase
        .from("complexes")
        .select("complex_no, complex_name, total_household_count, use_approve_ymd, cortar_no")
        .eq("cortar_no", selectedSec.cortar_no)
        .order("complex_name", { ascending: true });
      if (r.error) { if (!cancelled) setError(describeError(r.error)); return; }
      if (!cancelled) setSecComplexes(r.data ?? []);
    })();
    return () => { cancelled = true; };
  }, [selectedSec]);

  const totals = useMemo(() => {
    const map: Record<string, { listing_count: number; complex_count: number }> = {
      A1: { listing_count: 0, complex_count: 0 },
      B1: { listing_count: 0, complex_count: 0 },
      B2: { listing_count: 0, complex_count: 0 },
    };
    for (const r of regionAgg) {
      if (!map[r.trade_type]) continue;
      map[r.trade_type].listing_count += r.listing_count;
      map[r.trade_type].complex_count += r.complex_count;
    }
    return map;
  }, [regionAgg]);

  if (loading) return <Loading />;
  if (error) return <FetchError message={error} />;
  if (!snapshotDate) return <div className="muted">데이터가 아직 없습니다.</div>;

  const showSearch = searchTerm.length > 0;

  return (
    <div ref={shareRef} className="share-target">
      {fresh && (fresh.new_sale + fresh.new_jeonse + fresh.new_wolse) > 0 && (
        <FreshBadge fresh={fresh} />
      )}
      <ShareBar targetRef={shareRef} title="전국 부동산 현황" fileName="콕집_전국현황" />
      <div className="section-title" style={{ marginTop: 4 }}>지역별 거래량 · 국민평형 시세</div>
      <TxRegionPulse />

      <div className="muted" style={{ margin: "18px 0 12px" }}>
        {formatSnapshotDate(snapshotDate)}
      </div>
      <div className="section-title">전국 아파트 매물 통계</div>
      <div className="cards">
        {(["A1", "B1", "B2"] as const).map((t) => {
          const r = totals[t];
          const top = (topListings?.[t] ?? []);
          return (
            <div className="card" key={t}>
              <div className="label">
                <span className={`badge ${t.toLowerCase()}`}>{TRADE_LABEL[t]}</span>
              </div>
              <div className="num">{r?.listing_count?.toLocaleString() ?? 0}</div>
              <div className="sub">{r?.complex_count ?? 0}개 단지</div>
              {top.length > 0 && (
                <ol style={{ margin: "10px 0 0", padding: 0, listStyle: "none", fontSize: 12 }}>
                  {top.map((c, i) => (
                    <li key={c.complex_no ?? i} style={{
                      display: "flex", justifyContent: "space-between", gap: 8,
                      padding: "2px 0", color: "#444",
                    }}>
                      <span style={{
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      }}>
                        <span style={{ color: "#999", marginRight: 4 }}>{i + 1}</span>
                        {c.complex_no ? (
                          <Link to={`/complex/${c.complex_no}`} style={{ color: "#1268d3" }}>
                            {c.complex_name ?? c.complex_no}
                          </Link>
                        ) : (
                          <span>{c.complex_name ?? "—"}</span>
                        )}
                      </span>
                      <span style={{ color: "#666", flexShrink: 0 }}>{c.count.toLocaleString()}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          );
        })}
      </div>

      {listingTrend && listingTrend.series.length > 0 && (
        <>
          <div
            style={{
              marginTop: 16, display: "flex", alignItems: "center",
              justifyContent: "flex-end", flexWrap: "wrap", gap: 6,
            }}
          >
            {([
              { key: "A1" as const, label: "매매", color: "#c0392b" },
              { key: "B1" as const, label: "전세", color: "#1268d3" },
              { key: "B2" as const, label: "월세", color: "#27ae60" },
            ]).map((s) => {
              const on = showSeries[s.key];
              return (
                <button
                  key={s.key}
                  onClick={() => setShowSeries((p) => ({ ...p, [s.key]: !p[s.key] }))}
                  style={{
                    padding: "3px 10px",
                    border: `1px solid ${on ? s.color : "#ccc"}`,
                    borderRadius: 14,
                    background: on ? s.color : "white",
                    color: on ? "white" : "#888",
                    cursor: "pointer",
                    fontSize: 12,
                    fontWeight: 500,
                  }}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
          <div style={{ width: "100%", height: 240 }}>
            <ResponsiveContainer>
              <LineChart
                data={listingTrend.series}
                margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
              >
                <CartesianGrid stroke="#eee" />
                <XAxis
                  dataKey="snapshot_date"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(s: string) => s.slice(5)}
                />
                <YAxis
                  yAxisId="sale"
                  hide={!showSeries.A1}
                  tick={{ fontSize: 11, fill: "#c0392b" }}
                  width={50}
                  domain={["auto", "auto"]}
                  tickFormatter={formatKoCount}
                />
                <YAxis
                  yAxisId="rent"
                  orientation="right"
                  hide={!showSeries.B1 && !showSeries.B2}
                  tick={{ fontSize: 11, fill: "#1268d3" }}
                  width={50}
                  domain={["auto", "auto"]}
                  tickFormatter={formatKoCount}
                />
                <Tooltip
                  formatter={(v) => (typeof v === "number" ? v.toLocaleString() : String(v))}
                  labelFormatter={(label) => {
                    const s = String(label);
                    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
                    if (!m) return s;
                    const wd = WEEKDAYS_KO[new Date(`${s}T00:00:00`).getDay()];
                    return `${Number(m[2])}월 ${Number(m[3])}일 (${wd})`;
                  }}
                  labelStyle={{ fontSize: 12 }}
                  contentStyle={{ fontSize: 12 }}
                />
                <Legend
                  verticalAlign="top"
                  align="right"
                  wrapperStyle={{ fontSize: 11, paddingBottom: 4 }}
                  iconSize={10}
                />
                {showSeries.A1 && (
                  <Line yAxisId="sale" type="monotone" dataKey="A1" name="매매(좌)" stroke="#c0392b" strokeWidth={2} dot={{ r: 3 }} />
                )}
                {showSeries.B1 && (
                  <Line yAxisId="rent" type="monotone" dataKey="B1" name="전세(우)" stroke="#1268d3" strokeWidth={2} dot={{ r: 3 }} />
                )}
                {showSeries.B2 && (
                  <Line yAxisId="rent" type="monotone" dataKey="B2" name="월세(우)" stroke="#27ae60" strokeWidth={2} dot={{ r: 3 }} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {recentTx && (
        <>
          <div className="section-title" style={{ marginTop: 16 }}>
            최근 {recentTx.days}일 실거래 신고 (국토부 등록 기준)
          </div>
          <div className="cards">
            {([
              { key: "sale" as const, label: "매매", t: "A1", count: recentTx.sale, top: topComplexes?.sale ?? [] },
              { key: "jeonse" as const, label: "전세", t: "B1", count: recentTx.jeonse, top: topComplexes?.jeonse ?? [] },
              { key: "wolse" as const, label: "월세", t: "B2", count: recentTx.wolse, top: topComplexes?.wolse ?? [] },
            ]).map((r) => (
              <div className="card" key={r.key}>
                <div className="label">
                  <span className={`badge ${r.t.toLowerCase()}`}>{r.label}</span>
                </div>
                <div className="num">{r.count.toLocaleString()}</div>
                <div className="sub">{r.count === 0 ? "수집 예정" : "건 신고"}</div>
                {r.top.length > 0 && (
                  <ol style={{ margin: "10px 0 0", padding: 0, listStyle: "none", fontSize: 12 }}>
                    {r.top.map((c, i) => (
                      <li key={c.complex_no ?? i} style={{
                        display: "flex", justifyContent: "space-between", gap: 8,
                        padding: "2px 0", color: "#444",
                      }}>
                        <span style={{
                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}>
                          <span style={{ color: "#999", marginRight: 4 }}>{i + 1}</span>
                          {c.complex_no ? (
                            <Link to={`/complex/${c.complex_no}`} style={{ color: "#1268d3" }}>
                              {c.complex_name ?? c.complex_no}
                            </Link>
                          ) : (
                            <span>{c.complex_name ?? "—"}</span>
                          )}
                        </span>
                        <span style={{ color: "#666", flexShrink: 0 }}>{c.count.toLocaleString()}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      <input
        className="search"
        placeholder="단지명 검색 (예: 래미안, 자이, …)"
        value={searchInput}
        onChange={(e) => setSearchInput(e.target.value)}
        style={{ marginTop: 16 }}
      />

      {showSearch ? (
        <>
          <div className="section-title">
            검색 결과 ({searching ? "…" : searchResults.length}
            {searchResults.length === 30 ? "+" : ""})
          </div>
          {searchResults.length === 0 && !searching && (
            <div className="muted">일치하는 단지가 없습니다.</div>
          )}
          <ComplexList items={searchResults} />
        </>
      ) : (
        <>
          <div className="section-title">지역으로 찾기</div>
          <ChipRow
            items={cities}
            selected={selectedCity}
            onPick={(r) => setSelectedCity(r === selectedCity ? null : r)}
          />
          {selectedCity && (
            <ChipRow
              items={dvsns}
              selected={selectedDvsn}
              onPick={(r) => setSelectedDvsn(r === selectedDvsn ? null : r)}
            />
          )}
          {selectedDvsn && (
            <ChipRow
              items={secs}
              selected={selectedSec}
              onPick={(r) => setSelectedSec(r === selectedSec ? null : r)}
            />
          )}
          {selectedSec && (
            <>
              <div className="section-title" style={{ marginTop: 16 }}>
                {selectedSec.cortar_name} 단지 ({secComplexes.length})
              </div>
              <ComplexList items={secComplexes} />
            </>
          )}
        </>
      )}
    </div>
  );
}

function ChipRow({
  items,
  selected,
  onPick,
}: {
  items: Region[];
  selected: Region | null;
  onPick: (r: Region) => void;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
      {items.map((r) => {
        const active = selected?.cortar_no === r.cortar_no;
        return (
          <button
            key={r.cortar_no}
            onClick={() => onPick(r)}
            style={{
              padding: "5px 12px",
              border: "1px solid #ccc",
              borderRadius: 16,
              background: active ? "#1268d3" : "white",
              color: active ? "white" : "#333",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            {r.cortar_name}
          </button>
        );
      })}
    </div>
  );
}

function ComplexList({ items }: { items: ComplexHit[] }) {
  if (items.length === 0) return null;
  return (
    <table>
      <thead>
        <tr>
          <th>단지</th>
          <th className="num">세대</th>
          <th className="num">준공</th>
        </tr>
      </thead>
      <tbody>
        {items.map((c) => (
          <tr key={c.complex_no}>
            <td><Link to={`/complex/${c.complex_no}`}>{c.complex_name}</Link></td>
            <td className="num">{c.total_household_count?.toLocaleString() ?? "-"}</td>
            <td className="num">{c.use_approve_ymd?.slice(0, 4) ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
