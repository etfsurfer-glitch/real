import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { supabase, TRADE_LABEL } from "../supabase";

type Complex = {
  complex_no: string;
  complex_name: string;
  total_household_count: number | null;
  total_building_count: number | null;
  use_approve_ymd: string | null;
  detail_address: string | null;
};

type AggRow = {
  area_name: string;
  trade_type: string;
  listing_count: number;
  price_min: number | null;
  price_max: number | null;
  price_avg: number | null;
  rent_min: number | null;
  rent_max: number | null;
};

type Listing = {
  article_no: string;
  trade_type: string;
  area_name: string | null;
  floor_info: string | null;
  direction: string | null;
  deal_or_warrant_price_text: string | null;
  rent_price: number | null;
  realtor_name: string | null;
  article_confirm_ymd: string | null;
};

function formatWon(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 100_000_000) {
    const eok = Math.floor(v / 100_000_000);
    const man = Math.floor((v % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.floor(v / 10_000).toLocaleString()}만`;
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

export default function ComplexDetail() {
  const { complexNo } = useParams();
  const [complex, setComplex] = useState<Complex | null>(null);
  const [agg, setAgg] = useState<AggRow[]>([]);
  const [listings, setListings] = useState<Listing[]>([]);
  const [snapshotDate, setSnapshotDate] = useState<string | null>(null);
  const [tradeFilter, setTradeFilter] = useState<string>("A1");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!complexNo) return;
      try {
        const latestRes = await supabase
          .from("complex_daily_agg")
          .select("snapshot_date")
          .eq("complex_no", complexNo)
          .order("snapshot_date", { ascending: false })
          .limit(1);
        if (latestRes.error) throw latestRes.error;
        const date = latestRes.data?.[0]?.snapshot_date ?? null;
        if (cancelled) return;
        setSnapshotDate(date);

        const cplxRes = await supabase
          .from("complexes")
          .select("*")
          .eq("complex_no", complexNo)
          .single();
        if (cplxRes.error) throw cplxRes.error;
        if (cancelled) return;
        setComplex(cplxRes.data as Complex);

        if (date) {
          const aggRes = await supabase
            .from("complex_daily_agg")
            .select("*")
            .eq("complex_no", complexNo)
            .eq("snapshot_date", date);
          if (aggRes.error) throw aggRes.error;
          if (cancelled) return;
          setAgg((aggRes.data ?? []) as AggRow[]);
        }

        const ltRes = await supabase
          .from("listings_current")
          .select(
            "article_no, trade_type, area_name, floor_info, direction, " +
              "deal_or_warrant_price_text, rent_price, realtor_name, article_confirm_ymd",
          )
          .eq("complex_no", complexNo)
          .order("article_confirm_ymd", { ascending: false });
        if (ltRes.error) throw ltRes.error;
        if (cancelled) return;
        setListings((ltRes.data ?? []) as unknown as Listing[]);
        setLoading(false);
      } catch (e: unknown) {
        if (!cancelled) {
          setError(describeError(e));
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [complexNo]);

  if (loading) return <div className="muted">불러오는 중...</div>;
  if (error) return <div style={{ color: "crimson" }}>오류: {error}</div>;
  if (!complex) return <div className="muted">단지를 찾지 못했습니다.</div>;

  const tradeAggs: Record<string, AggRow[]> = { A1: [], B1: [], B2: [] };
  for (const r of agg) {
    if (tradeAggs[r.trade_type]) tradeAggs[r.trade_type].push(r);
  }
  for (const k of Object.keys(tradeAggs)) {
    tradeAggs[k].sort((a, b) => b.listing_count - a.listing_count);
  }
  const filteredListings = listings.filter((l) => l.trade_type === tradeFilter);

  return (
    <>
      <Link to="/" className="back">← 전체 보기</Link>
      <h2 style={{ margin: "0 0 4px" }}>{complex.complex_name}</h2>
      <div className="muted" style={{ marginBottom: 16 }}>
        {complex.detail_address ?? ""} · 세대 {complex.total_household_count ?? "?"} · 동{" "}
        {complex.total_building_count ?? "?"} · 준공 {complex.use_approve_ymd?.slice(0, 4) ?? "?"}{" "}
        · 스냅샷 {snapshotDate ?? "-"}
      </div>

      {(["A1", "B1", "B2"] as const).map((t) => (
        <div key={t} style={{ marginBottom: 28 }}>
          <div className="section-title">
            <span className={`badge ${t.toLowerCase()}`}>{TRADE_LABEL[t]}</span>{" "}
            평형별 집계
          </div>
          {tradeAggs[t].length === 0 ? (
            <div className="muted">매물 없음</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>평형</th>
                  <th className="num">매물</th>
                  <th className="num">최저</th>
                  <th className="num">평균</th>
                  <th className="num">최고</th>
                  {t === "B2" && <th className="num">월세 최저</th>}
                  {t === "B2" && <th className="num">월세 최고</th>}
                </tr>
              </thead>
              <tbody>
                {tradeAggs[t].map((r) => (
                  <tr key={`${t}-${r.area_name}`}>
                    <td>{r.area_name || "-"}</td>
                    <td className="num">{r.listing_count}</td>
                    <td className="num">{formatWon(r.price_min)}</td>
                    <td className="num">{formatWon(r.price_avg)}</td>
                    <td className="num">{formatWon(r.price_max)}</td>
                    {t === "B2" && <td className="num">{formatWon(r.rent_min)}</td>}
                    {t === "B2" && <td className="num">{formatWon(r.rent_max)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}

      <div className="section-title">매물 상세</div>
      <div style={{ marginBottom: 8 }}>
        {(["A1", "B1", "B2"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTradeFilter(t)}
            style={{
              marginRight: 6,
              padding: "4px 12px",
              border: "1px solid #ccc",
              borderRadius: 16,
              background: tradeFilter === t ? "#1268d3" : "white",
              color: tradeFilter === t ? "white" : "#333",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            {TRADE_LABEL[t]} ({listings.filter((l) => l.trade_type === t).length})
          </button>
        ))}
      </div>
      <table>
        <thead>
          <tr>
            <th>평형</th>
            <th>층</th>
            <th>방향</th>
            <th className="num">가격</th>
            {tradeFilter === "B2" && <th className="num">월세</th>}
            <th>중개사</th>
            <th>등록</th>
          </tr>
        </thead>
        <tbody>
          {filteredListings.map((l) => (
            <tr key={l.article_no}>
              <td>{l.area_name ?? "-"}</td>
              <td>{l.floor_info ?? "-"}</td>
              <td>{l.direction ?? "-"}</td>
              <td className="num">{l.deal_or_warrant_price_text ?? "-"}</td>
              {tradeFilter === "B2" && <td className="num">{formatWon(l.rent_price)}</td>}
              <td>{l.realtor_name ?? "-"}</td>
              <td>{l.article_confirm_ymd ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
