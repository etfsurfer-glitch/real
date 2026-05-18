import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { supabase, TRADE_LABEL } from "../supabase";

type RegionAgg = {
  snapshot_date: string;
  cortar_no: string;
  trade_type: string;
  listing_count: number;
  complex_count: number;
};

type ComplexRow = {
  complex_no: string;
  complex_name: string;
  total_household_count: number | null;
  use_approve_ymd: string | null;
  cortar_no: string | null;
  a1: number;
  b1: number;
  b2: number;
};

export default function Overview() {
  const [regionAgg, setRegionAgg] = useState<RegionAgg[]>([]);
  const [complexes, setComplexes] = useState<ComplexRow[]>([]);
  const [search, setSearch] = useState("");
  const [snapshotDate, setSnapshotDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        if (!date) {
          setLoading(false);
          return;
        }

        const aggRes = await supabase
          .from("region_daily_agg")
          .select("*")
          .eq("snapshot_date", date);
        if (aggRes.error) throw aggRes.error;
        if (cancelled) return;
        setRegionAgg(aggRes.data ?? []);

        const cdaRes = await supabase
          .from("complex_daily_agg")
          .select("complex_no, trade_type, listing_count")
          .eq("snapshot_date", date);
        if (cdaRes.error) throw cdaRes.error;
        const byComplex = new Map<string, { a1: number; b1: number; b2: number }>();
        for (const row of cdaRes.data ?? []) {
          const cur = byComplex.get(row.complex_no) ?? { a1: 0, b1: 0, b2: 0 };
          if (row.trade_type === "A1") cur.a1 += row.listing_count;
          else if (row.trade_type === "B1") cur.b1 += row.listing_count;
          else if (row.trade_type === "B2") cur.b2 += row.listing_count;
          byComplex.set(row.complex_no, cur);
        }
        const ids = Array.from(byComplex.keys());
        if (ids.length === 0) {
          setComplexes([]);
          setLoading(false);
          return;
        }
        const cplxRes = await supabase
          .from("complexes")
          .select("complex_no, complex_name, total_household_count, use_approve_ymd, cortar_no")
          .in("complex_no", ids);
        if (cplxRes.error) throw cplxRes.error;
        if (cancelled) return;
        const merged: ComplexRow[] = (cplxRes.data ?? []).map((c) => ({
          ...c,
          ...byComplex.get(c.complex_no)!,
        }));
        merged.sort((a, b) => b.a1 + b.b1 + b.b2 - (a.a1 + a.b1 + a.b2));
        setComplexes(merged);
        setLoading(false);
      } catch (e: unknown) {
        if (!cancelled) {
          let msg = "unknown";
          if (e instanceof Error) msg = e.message;
          else if (e && typeof e === "object") {
            const o = e as Record<string, unknown>;
            const parts = [o.message, o.details, o.hint, o.code].filter(Boolean);
            msg = parts.length ? parts.join(" · ") : JSON.stringify(e);
          } else msg = String(e);
          setError(msg);
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const totals = useMemo(() => {
    const map: Record<string, RegionAgg> = {};
    for (const r of regionAgg) map[r.trade_type] = r;
    return map;
  }, [regionAgg]);

  const filtered = useMemo(() => {
    if (!search.trim()) return complexes;
    const q = search.trim().toLowerCase();
    return complexes.filter((c) => c.complex_name?.toLowerCase().includes(q));
  }, [complexes, search]);

  if (loading) return <div className="muted">불러오는 중...</div>;
  if (error) return <div style={{ color: "crimson" }}>오류: {error}</div>;
  if (!snapshotDate) return <div className="muted">데이터가 아직 없습니다.</div>;

  return (
    <>
      <div className="muted" style={{ marginBottom: 12 }}>
        스냅샷 {snapshotDate} · 서초동(1165010800)
      </div>
      <div className="cards">
        {["A1", "B1", "B2"].map((t) => {
          const r = totals[t];
          return (
            <div className="card" key={t}>
              <div className="label">
                <span className={`badge ${t.toLowerCase()}`}>{TRADE_LABEL[t]}</span>
              </div>
              <div className="num">{r?.listing_count?.toLocaleString() ?? 0}</div>
              <div className="sub">{r?.complex_count ?? 0}개 단지</div>
            </div>
          );
        })}
      </div>

      <div className="section-title">단지 ({filtered.length})</div>
      <input
        className="search"
        placeholder="단지명 검색"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <table>
        <thead>
          <tr>
            <th>단지</th>
            <th className="num">세대</th>
            <th className="num">준공</th>
            <th className="num">매매</th>
            <th className="num">전세</th>
            <th className="num">월세</th>
            <th className="num">합계</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((c) => (
            <tr key={c.complex_no}>
              <td>
                <Link to={`/complex/${c.complex_no}`}>{c.complex_name}</Link>
              </td>
              <td className="num">{c.total_household_count?.toLocaleString() ?? "-"}</td>
              <td className="num">{c.use_approve_ymd?.slice(0, 4) ?? "-"}</td>
              <td className="num">{c.a1}</td>
              <td className="num">{c.b1}</td>
              <td className="num">{c.b2}</td>
              <td className="num"><b>{c.a1 + c.b1 + c.b2}</b></td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
