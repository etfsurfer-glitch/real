// 하단 고정 비교 바 + 결과 팝업. App 전역에 1회 마운트하면 어느 페이지든 담긴 단지가 뜬다.
// 팝업의 핵심은 '가격이 어떻게 움직였나' 차트. 기본정보 표는 핵심 몇 줄만 펴고 나머지는 접는다.
import { useEffect, useMemo, useState } from "react";
import { GitCompare, X, ChevronDown } from "lucide-react";
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  subscribeCompare, compareItems, removeCompare, clearCompare, MAX_COMPARE,
} from "../lib/comparestore";

const API_BASE = import.meta.env.VITE_API_BASE;
const COLORS = ["#1268d3", "#e2882e", "#1f9d63", "#8b5cf6"];

// ComplexCompare 와 동일한 표기 규칙
function won(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 1e8) {
    const eok = Math.floor(v / 1e8), man = Math.round((v % 1e8) / 1e4);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}
const dot = (d?: string | null) => (d ? d.slice(2).replace(/-/g, ".") : "-");
const eok1 = (v?: number | null) => (v != null ? +(v / 1e8).toFixed(2) : null); // 원 → 억(소수1)

type Row = { label: string; get: (c: any) => string; key?: boolean };
const ROWS: Row[] = [
  { label: "세대수", get: (c) => c.households?.toLocaleString() ?? "-", key: true },
  { label: "매매 호가 (최저~평균)", get: (c) => (c.listings?.A1 ? `${won(c.listings.A1.min)} ~ ${won(c.listings.A1.avg)}` : "-"), key: true },
  { label: "최근 실거래", get: (c) => (c.tx?.latest ? `${won(c.tx.latest.price)} · ${dot(c.tx.latest.date)}` : "-"), key: true },
  { label: "평당 실거래가 (3.3㎡)", get: (c) => won(c.tx?.pyeong6m), key: true },
  { label: "갭 (매매-전세 평균)", get: (c) => won(c.gap), key: true },
  { label: "급매 (실거래 대비 저가)", get: (c) => (c.quick_deals != null ? `${c.quick_deals}건` : "-"), key: true },
  { label: "준공", get: (c) => c.built ?? "-" },
  { label: "동 수", get: (c) => (c.buildings != null ? `${c.buildings}동` : "-") },
  { label: "세대당 주차", get: (c) => (c.parking != null ? `${c.parking}대` : "-") },
  { label: "시공사", get: (c) => (c.builder ?? "-").split(",")[0] },
  { label: "전세 호가 (최저~평균)", get: (c) => (c.listings?.B1 ? `${won(c.listings.B1.min)} ~ ${won(c.listings.B1.avg)}` : "-") },
  { label: "매매 매물 (광고/실)", get: (c) => (c.listings?.A1 ? `${c.listings.A1.n} / ${c.listings.A1.units ?? "-"}건` : "-") },
  { label: "전세가율 (호가)", get: (c) => (c.jeonse_rate != null ? `${c.jeonse_rate}%` : "-") },
  { label: "6개월 실거래 평균", get: (c) => won(c.tx?.avg6m) },
  { label: "역대 신고가", get: (c) => (c.tx?.record ? `${won(c.tx.record.price)} · ${dot(c.tx.record.date)}` : "-") },
  { label: "12개월 거래량", get: (c) => (c.tx?.n12 != null ? `${c.tx.n12.toLocaleString()}건` : "-") },
  { label: "연 회전율 (거래/세대)", get: (c) => (c.tx?.turnover != null ? `${c.tx.turnover}%` : "-") },
  { label: "지하철", get: (c) => (c.subway ? `${c.subway.station} 도보 ${c.subway.walk}분` : "-") },
  { label: "배정 초등학교", get: (c) => (c.school ? `${c.school.name.replace("등학교", "")} 도보 ${c.school.walk}분` : "-") },
  { label: "취급 중개사무소", get: (c) => (c.n_realtors != null ? `${c.n_realtors}곳` : "-") },
];

// 월별 실거래 시세를 단지별 열로 병합해 recharts 데이터로. mode: idx(지수 100) | pyeong(억/평)
function buildChart(items: any[], mode: "idx" | "pyeong") {
  const map = new Map<string, any>();
  items.forEach((c, i) => {
    (c.price_series || []).forEach((r: any) => {
      if (!map.has(r.ym)) map.set(r.ym, { ym: r.ym });
      const v = mode === "idx" ? r.idx : eok1(r.pyeong);
      if (v != null) map.get(r.ym)[`c${i}`] = v;
    });
  });
  return [...map.values()].sort((a, b) => (a.ym < b.ym ? -1 : 1));
}

function PriceChart({ items }: { items: any[] }) {
  const [mode, setMode] = useState<"idx" | "pyeong">("idx");
  const data = useMemo(() => buildChart(items, mode), [items, mode]);
  const withSeries = items.filter((c) => (c.price_series || []).length > 0);

  if (withSeries.length < 1 || data.length < 2) {
    return <div className="muted cmp-chart-empty">실거래가 적어 가격 추이를 그릴 수 없습니다.</div>;
  }
  const fmtY = (v: number) => (mode === "idx" ? String(v) : `${v}억`);
  const fmtTip = (v: any) => (mode === "idx" ? `${v}` : `${v}억/평`);

  return (
    <div className="cmp-chart">
      <div className="cmp-chart-head">
        <div className="cmp-chart-title">최근 2년 실거래 가격 추이</div>
        <div className="cmp-seg">
          <button className={mode === "idx" ? "on" : ""} onClick={() => setMode("idx")}>지수 (기준100)</button>
          <button className={mode === "pyeong" ? "on" : ""} onClick={() => setMode("pyeong")}>평당가 (억)</button>
        </div>
      </div>
      <div style={{ width: "100%", height: 240 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 6, right: 10, bottom: 2, left: -6 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef1f5" />
            <XAxis dataKey="ym" tick={{ fontSize: 11, fill: "#6b7280" }}
              tickFormatter={(v) => v.slice(2).replace("-", ".")} minTickGap={20} />
            <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} tickFormatter={fmtY}
              domain={mode === "idx" ? ["auto", "auto"] : [0, "auto"]} width={44} />
            <Tooltip formatter={(v: any, n: any) => [fmtTip(v), n]}
              labelFormatter={(l) => l} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {items.map((c, i) => (
              (c.price_series || []).length > 0 ? (
                <Line key={c.complex_no} type="monotone" dataKey={`c${i}`} name={c.name}
                  stroke={COLORS[i % 4]} strokeWidth={2.2} dot={false} connectNulls
                  activeDot={{ r: 4 }} />
              ) : null
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="cmp-chart-note muted">
        {mode === "idx"
          ? "각 단지의 첫 거래월을 100으로 둔 상대 지수 — 가격대가 달라도 상승·하락 폭을 나란히 비교합니다."
          : "3.3㎡당 실거래 평균가(월별). 거래 없는 달은 이어 그립니다."}
      </div>
    </div>
  );
}

function Modal({ ids, onClose }: { ids: string[]; onClose: () => void }) {
  const [items, setItems] = useState<any[] | null>(null);
  const [err, setErr] = useState(false);
  const [openAll, setOpenAll] = useState(false);
  useEffect(() => {
    setItems(null); setErr(false);
    fetch(`${API_BASE}/stats/complex-compare-multi?ids=${ids.join(",")}`)
      .then((r) => r.json()).then((j) => setItems(j.items ?? [])).catch(() => setErr(true));
  }, [ids.join(",")]); // eslint-disable-line

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const rows = openAll ? ROWS : ROWS.filter((r) => r.key);

  return (
    <div className="cmp-modal-back" onClick={onClose}>
      <div className="cmp-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cmp-modal-head">
          <div className="cmp-modal-title"><GitCompare size={17} /> 단지 비교</div>
          <button className="cmp-modal-x" onClick={onClose} aria-label="닫기"><X size={18} /></button>
        </div>
        <div className="cmp-modal-body">
          {items == null && !err && <div className="muted" style={{ padding: 24 }}>불러오는 중…</div>}
          {err && <div className="muted" style={{ padding: 24 }}>비교 정보를 불러오지 못했습니다.</div>}
          {items && items.length >= 2 && (
            <>
              <PriceChart items={items} />
              <div style={{ overflowX: "auto" }}>
                <table className="cmp-tbl">
                  <thead>
                    <tr>
                      <th className="cmp-tbl-lbl"></th>
                      {items.map((c, i) => (
                        <th key={c.complex_no} style={{ borderTopColor: COLORS[i % 4] }}>
                          <a href={`/complex/${c.complex_no}`} className="cmp-tbl-name">{c.name}</a>
                          <div className="cmp-tbl-region">{c.region}</div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.label}>
                        <td className="cmp-tbl-lbl">{r.label}</td>
                        {items.map((c) => <td key={c.complex_no}>{r.get(c)}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="cmp-more" onClick={() => setOpenAll((v) => !v)}>
                <ChevronDown size={15} style={{ transform: openAll ? "rotate(180deg)" : "none", transition: ".15s" }} />
                {openAll ? "기본정보 접기" : "기본정보 전체 보기"}
              </button>
            </>
          )}
          {items && items.length === 1 && (
            <div className="muted" style={{ padding: 24 }}>비교하려면 2개 이상 담아 주세요.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CompareBar() {
  const [, force] = useState(0);
  const [open, setOpen] = useState(false);
  useEffect(() => subscribeCompare(() => force((n) => n + 1)), []);

  const items = compareItems();
  if (items.length === 0) return null;

  return (
    <>
      <div className="cmp-bar">
        <div className="cmp-bar-chips">
          <GitCompare size={16} className="cmp-bar-ico" />
          {items.map((it, i) => (
            <span key={it.complex_no} className="cmp-chip" style={{ borderColor: COLORS[i % 4] }}>
              {it.complex_name}
              <button onClick={() => removeCompare(it.complex_no)} aria-label="빼기"><X size={12} /></button>
            </span>
          ))}
          <span className="cmp-bar-count muted">{items.length}/{MAX_COMPARE}</span>
        </div>
        <div className="cmp-bar-actions">
          <button className="cmp-bar-clear" onClick={clearCompare}>비우기</button>
          <button className="cmp-bar-go" disabled={items.length < 2} onClick={() => setOpen(true)}>
            비교하기
          </button>
        </div>
      </div>
      {open && <Modal ids={items.map((x) => x.complex_no)} onClose={() => setOpen(false)} />}
    </>
  );
}
