import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { supabase, TRADE_LABEL } from "../supabase";

type ChangeRow = {
  article_no: string;
  complex_no: string;
  trade_type: string;
  area_name: string | null;
  floor_info: string | null;
  deal_or_warrant_price_text: string | null;
  rent_price: number | null;
  article_confirm_ymd: string | null;
  price_change_state: string;
  article_feature_desc: string | null;
};

const LIMIT = 200;

export default function Changes() {
  const [rows, setRows] = useState<ChangeRow[]>([]);
  const [complexNames, setComplexNames] = useState<Record<string, string>>({});
  const [snapshotDate, setSnapshotDate] = useState<string | null>(null);
  const [stateFilter, setStateFilter] = useState<"BOTH" | "INCREASE" | "DECREASE">("BOTH");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const latestRes = await supabase
          .from("listings_current")
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

        const ltRes = await supabase
          .from("listings_current")
          .select(
            "article_no, complex_no, trade_type, area_name, floor_info, " +
              "deal_or_warrant_price_text, rent_price, article_confirm_ymd, " +
              "price_change_state, article_feature_desc",
          )
          .eq("snapshot_date", date)
          .in("price_change_state", ["INCREASE", "DECREASE"])
          .order("article_confirm_ymd", { ascending: false })
          .limit(LIMIT);
        if (ltRes.error) throw ltRes.error;
        if (cancelled) return;
        const data = (ltRes.data ?? []) as unknown as ChangeRow[];
        setRows(data);

        const cnos = Array.from(new Set(data.map((r) => r.complex_no)));
        if (cnos.length) {
          const cnRes = await supabase
            .from("complexes")
            .select("complex_no, complex_name")
            .in("complex_no", cnos);
          if (cnRes.error) throw cnRes.error;
          const map: Record<string, string> = {};
          for (const c of cnRes.data ?? []) map[c.complex_no] = c.complex_name;
          if (!cancelled) setComplexNames(map);
        }
        setLoading(false);
      } catch (e: unknown) {
        if (!cancelled) {
          let msg = "unknown";
          if (e instanceof Error) msg = e.message;
          else if (e && typeof e === "object") {
            const o = e as Record<string, unknown>;
            const parts = [o.message, o.details, o.hint, o.code].filter(Boolean);
            msg = parts.length ? parts.join(" · ") : JSON.stringify(e);
          }
          setError(msg);
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    if (stateFilter === "BOTH") return rows;
    return rows.filter((r) => r.price_change_state === stateFilter);
  }, [rows, stateFilter]);

  const inc = rows.filter((r) => r.price_change_state === "INCREASE").length;
  const dec = rows.filter((r) => r.price_change_state === "DECREASE").length;

  if (loading) return <div className="muted">불러오는 중...</div>;
  if (error) return <div style={{ color: "crimson" }}>오류: {error}</div>;

  return (
    <>
      <Link to="/" className="back">← 전체 보기</Link>
      <h2 style={{ margin: "0 0 4px" }}>가격 변동 매물</h2>
      <div className="muted" style={{ marginBottom: 12 }}>
        스냅샷 {snapshotDate} · 네이버가 표시한 가격 변동 상태 (최대 {LIMIT}건)
      </div>

      <div style={{ marginBottom: 12, display: "flex", gap: 6 }}>
        {([
          ["BOTH", `전체 (${inc + dec})`],
          ["INCREASE", `▲ 오름 (${inc})`],
          ["DECREASE", `▼ 내림 (${dec})`],
        ] as const).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setStateFilter(k)}
            style={{
              padding: "5px 14px",
              border: "1px solid #ccc",
              borderRadius: 16,
              background: stateFilter === k ? "#1268d3" : "white",
              color: stateFilter === k ? "white" : "#333",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <table>
        <thead>
          <tr>
            <th style={{ textAlign: "center", width: 30 }}>변동</th>
            <th>단지</th>
            <th>거래</th>
            <th>평형</th>
            <th>층</th>
            <th className="num">가격</th>
            <th>특징</th>
            <th>등록</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((l) => (
            <tr key={l.article_no}>
              <td style={{ textAlign: "center" }}>
                {l.price_change_state === "INCREASE" ? (
                  <span style={{ color: "#c0392b", fontWeight: 700 }}>▲</span>
                ) : (
                  <span style={{ color: "#1e6fd6", fontWeight: 700 }}>▼</span>
                )}
              </td>
              <td>
                <Link to={`/complex/${l.complex_no}`}>
                  {complexNames[l.complex_no] ?? l.complex_no}
                </Link>
              </td>
              <td>
                <span className={`badge ${l.trade_type.toLowerCase()}`}>
                  {TRADE_LABEL[l.trade_type]}
                </span>
              </td>
              <td>{l.area_name ?? "-"}</td>
              <td>{l.floor_info ?? "-"}</td>
              <td className="num">{l.deal_or_warrant_price_text ?? "-"}</td>
              <td style={{ fontSize: 12, color: "#555", maxWidth: 280, overflow: "hidden",
                          textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {l.article_feature_desc ?? ""}
              </td>
              <td>{l.article_confirm_ymd ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
