import { useParams } from "react-router-dom";
import { BarChart, Bar, Cell, LabelList, ReferenceArea, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { useEffect, useState } from "react";
import { useStickyState } from "../hooks/useStickyState";
import FetchError from "../components/FetchError";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";

// 지역별 거래량 — 기간단위별 별도 페이지(/tx-stats/volume/daily|weekly|monthly|quarterly|yearly).
// 카테고리 6종(아파트~상가·사무실) × 지역(전국/시도/시군구) 선택. 데이터: /stats/tx-region-series.
const API_BASE = import.meta.env.VITE_API_BASE;

const UNITS: { key: string; path: string; label: string; desc: string }[] = [
  { key: "day", path: "daily", label: "일별", desc: "최근 60일" },
  { key: "week", path: "weekly", label: "주간", desc: "최근 52주" },
  { key: "month", path: "monthly", label: "월별", desc: "최근 36개월" },
  { key: "quarter", path: "quarterly", label: "분기별", desc: "최근 20분기" },
  { key: "year", path: "yearly", label: "연도별", desc: "전체 연도" },
];
const ASSETS: [string, string][] = [
  ["apt", "아파트"], ["offi", "오피스텔"], ["silv", "분양권"],
  ["villa", "빌라·다세대"], ["house", "단독·다가구"], ["nrg", "상가·사무실"]];

type SeriesResp = { unit: string; asset: string; items: { period: string; count: number; avg_amt: number | null }[] };
type Region = { code: string; name: string };

// 한국 공휴일(대체공휴일 포함) — 일별 차트 표시용. 2025~2026 확정, 2027은 근사(연말 갱신).
const KR_HOLIDAYS = new Set<string>([
  // 2025
  "2025-01-01", "2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30",
  "2025-03-01", "2025-03-03", "2025-05-05", "2025-05-06", "2025-06-03", "2025-06-06",
  "2025-08-15", "2025-10-03", "2025-10-05", "2025-10-06", "2025-10-07", "2025-10-08",
  "2025-10-09", "2025-12-25",
  // 2026 (3·1 대체 3/2, 부처님오신날 5/24→5/25 대체, 6/3 지방선거, 광복절 8/15토→8/17 대체, 개천절 10/3토→10/5 대체)
  "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-01", "2026-03-02",
  "2026-05-05", "2026-05-24", "2026-05-25", "2026-06-03", "2026-06-06",
  "2026-08-15", "2026-08-17", "2026-09-24", "2026-09-25", "2026-09-26",
  "2026-10-03", "2026-10-05", "2026-10-09", "2026-12-25",
  // 2027 근사
  "2027-01-01", "2027-02-06", "2027-02-07", "2027-02-08", "2027-02-09",
  "2027-03-01", "2027-05-05", "2027-05-13", "2027-06-06", "2027-08-15", "2027-08-16",
  "2027-09-14", "2027-09-15", "2027-09-16", "2027-10-03", "2027-10-04",
  "2027-10-09", "2027-10-11", "2027-12-25", "2027-12-27",
]);
// 일별 마크: 공휴일="공"(우선) / 일요일="일" / 그 외 ""
const dayMark = (ymd: string): string => {
  if (KR_HOLIDAYS.has(ymd)) return "공";
  return new Date(ymd + "T00:00:00").getDay() === 0 ? "일" : "";
};
const RED = "#d23b3b";

// 신고기간 — 계약 후 30일 이내 신고 의무라, 오늘로부터 30일 안에 끝나는 버킷은 수치가 아직 차오르는 중.
// 버킷의 '기간 종료일'이 (오늘-30일) 이후면 신고기간에 걸친 것으로 본다.
function bucketEnd(period: string, unitKey: string): Date {
  if (unitKey === "day") return new Date(period + "T23:59:59");
  if (unitKey === "month") {
    const [y, m] = period.split("-").map(Number);
    return new Date(y, m, 0, 23, 59, 59);
  }
  if (unitKey === "quarter") {
    const [y, q] = period.split("-Q").map(Number);
    return new Date(y, q * 3, 0, 23, 59, 59);
  }
  if (unitKey === "year") return new Date(Number(period), 11, 31, 23, 59, 59);
  // week "YYYY-WNN" (%W: 월요일 시작) — 해당 주 일요일 근사
  const [y, w] = period.split("-W").map(Number);
  const jan1 = new Date(y, 0, 1);
  return new Date(jan1.getTime() + ((w * 7 + (7 - jan1.getDay())) % 400 + w * 0) * 86400000 + 6 * 86400000);
}
function inFilingWindow(period: string, unitKey: string): boolean {
  const cutoff = Date.now() - 30 * 86400000;
  try { return bucketEnd(period, unitKey).getTime() >= cutoff; } catch { return false; }
}

const eokShort = (v: number | null | undefined): string =>
  !v ? "-" : v >= 1e8 ? `${(v / 1e8).toFixed(1)}억` : `${Math.round(v / 1e4).toLocaleString()}만`;

export default function TxVolumePeriod() {
  const { unit: unitPath } = useParams<{ unit: string }>();
  const unit = UNITS.find((u) => u.path === unitPath) ?? UNITS[2];
  const [asset, setAsset] = useStickyState("txvol:asset", "apt");
  const [sido, setSido] = useStickyState("txvol:sido", "");
  const [sigungu, setSigungu] = useState("");

  const [sidos, setSidos] = useState<Region[]>([]);
  const [sggs, setSggs] = useState<Region[]>([]);
  useEffect(() => {
    fetch(`${API_BASE}/stats/changes/sido-list`).then((r) => r.json())
      .then((j) => setSidos(j.items ?? [])).catch(() => {});
  }, []);
  useEffect(() => {
    setSigungu("");
    if (!sido) { setSggs([]); return; }
    fetch(`${API_BASE}/stats/sigungu-list?sido=${sido.slice(0, 2)}`).then((r) => r.json())
      .then((j) => setSggs(j.items ?? [])).catch(() => {});
  }, [sido]);

  const p = new URLSearchParams({ unit: unit.key, asset });
  if (sigungu) p.set("sigungu", sigungu.slice(0, 5));
  else if (sido) p.set("sido", sido.slice(0, 2));
  const { data, loading, error } = useFetchJson<SeriesResp>(`${API_BASE}/stats/tx-region-series?${p}`);
  const items = data?.items ?? [];
  const isDay = unit.key === "day";
  const chartData = isDay ? items.map((it) => ({ ...it, mark: dayMark(it.period) })) : items;
  const last = items[items.length - 1];
  // 신고기간에 걸친 첫 버킷(이후 끝까지 음영)
  const filingStart = items.find((it) => inFilingWindow(it.period, unit.key))?.period;
  const regionName = sigungu ? (sggs.find((s) => s.code === sigungu)?.name ?? "")
    : sido ? (sidos.find((s) => s.code === sido)?.name ?? "") : "전국";
  const assetName = ASSETS.find(([k]) => k === asset)?.[1] ?? "";

  return (
    <div className="txvol">
      <div className="filter-bar" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", margin: "12px 0" }}>
        <select value={asset} onChange={(e) => setAsset(e.target.value)}>
          {ASSETS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <select value={sido} onChange={(e) => setSido(e.target.value)}>
          <option value="">전국</option>
          {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} disabled={!sido}>
          <option value="">시·군·구 전체</option>
          {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <span className="muted" style={{ fontSize: 12 }}>
          {regionName} {assetName} · {unit.desc}
          {last && <> · 최신 {last.period} <b>{last.count.toLocaleString()}건</b></>}
        </span>
      </div>

      {error && <FetchError message={error} inline />}
      {loading && <Loading />}
      {!loading && !error && items.length === 0 && (
        <p className="muted">해당 조건의 실거래가 없습니다.</p>
      )}

      {items.length > 0 && (
        <>
          <div style={{ width: "100%", height: 300 }}>
            <ResponsiveContainer>
              <BarChart data={chartData} margin={{ top: isDay ? 16 : 6, right: 8, left: 0, bottom: 0 }}>
                <XAxis dataKey="period" tick={{ fontSize: 10 }} minTickGap={18}
                  tickFormatter={(v: string) => unit.key === "day" ? v.slice(5) : unit.key === "month" ? v.slice(2) : v} />
                <YAxis tick={{ fontSize: 10 }} width={48} tickFormatter={(v: number) => v.toLocaleString()} />
                <Tooltip formatter={(v: any) => [`${Number(v).toLocaleString()}건`, "거래량"]} />
                {filingStart && last && (
                  <ReferenceArea x1={filingStart} x2={last.period} fill="#f2b25c" fillOpacity={0.13}
                    label={{ value: "신고기간", position: "insideTopRight", fill: "#b45309", fontSize: 11, fontWeight: 800 }} />
                )}
                <Bar dataKey="count" fill="#1268d3" radius={[3, 3, 0, 0]}>
                  {isDay && chartData.map((it: any) => (
                    <Cell key={it.period} fill={it.mark ? RED : "#1268d3"} />
                  ))}
                  {isDay && <LabelList dataKey="mark" position="top" fill={RED} fontSize={10} fontWeight={800} />}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={{ overflowX: "auto", marginTop: 14 }}>
            <table className="txvol-table">
              <thead><tr><th>기간</th><th>거래량</th><th>평균가</th><th>전기 대비</th></tr></thead>
              <tbody>
                {items.slice().reverse().map((it, i, arr) => {
                  const prev = arr[i + 1];
                  const chg = prev && prev.count > 0 ? (it.count - prev.count) / prev.count * 100 : null;
                  return (
                    <tr key={it.period}>
                      <td style={isDay && dayMark(it.period) ? { color: RED, fontWeight: 700 } : undefined}>
                        {it.period}{isDay && dayMark(it.period) ? ` (${dayMark(it.period)})` : ""}
                        {inFilingWindow(it.period, unit.key) && (
                          <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 800, color: "#b45309",
                            background: "#fff7ea", border: "1px solid #f3ddba", borderRadius: 6, padding: "1px 6px" }}>신고중</span>
                        )}
                      </td>
                      <td className="num strong">{it.count.toLocaleString()}</td>
                      <td className="num">{eokShort(it.avg_amt)}</td>
                      <td className="num" style={{ color: chg == null ? "#94a3b8" : chg >= 0 ? "#c0392b" : "#1268d3" }}>
                        {chg == null ? "-" : `${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>
            해제거래 제외 · 주황 음영/신고중 표시는 <b>신고기간</b>(계약 후 30일 이내 신고 진행 중)으로, 수치가 아직 확정되지 않고 계속 늘어납니다. 평균가는 해당 기간 실거래 평균입니다.
          </p>
        </>
      )}

      <style>{`
        .txvol-tabs{display:flex;gap:0;border:1px solid #dbe3ec;border-radius:10px;overflow:hidden;width:fit-content}
        .txvol-tab{padding:8px 18px;font-size:13px;font-weight:700;color:#5a6b80;text-decoration:none;background:#fff}
        .txvol-tab+.txvol-tab{border-left:1px solid #dbe3ec}
        .txvol-tab.on{background:#1268d3;color:#fff}
        .txvol-table{border-collapse:collapse;font-size:13px;min-width:420px}
        .txvol-table th{color:#7a8aa0;font-size:11.5px;text-align:right;padding:6px 14px;border-bottom:1px solid #e3e9f1}
        .txvol-table th:first-child{text-align:left}
        .txvol-table td{padding:6px 14px;border-bottom:1px solid #f0f3f8;text-align:right}
        .txvol-table td:first-child{text-align:left}
        .txvol-table .num.strong{font-weight:800;color:#13294b}
      `}</style>
    </div>
  );
}
