// 고객 원장 — 고객 1명 = 행 1개가 아니다. 요건(구함·내놓음)이 하위 행으로 붙는다.
// 설계안 design/lounge_customer_ledger_설계안.md §3-1.
//
// 매물장과 따로 놀지 않게, 내놓은 요건은 우리 매물장 행을 그대로 물고 온다.
import { useCallback, useEffect, useMemo, useState } from "react";
import { UserRound, Search, Loader2, Building2, Link2, Phone, RefreshCw } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

type Listing = {
  id: number; complex_name?: string; dong?: string; ho?: string;
  trade_type?: string; price?: any; deposit?: any; rent_price?: any; area2_m2?: any;
};
type Need = {
  id: number; kind?: string; trade?: string; role?: string;
  budget_min?: number | null; budget_max?: number | null; ask_price?: number | null;
  sigungu?: string | null; dong?: string | null; address?: string | null;
  area_min?: number | null; area_max?: number | null; settle_date?: string | null;
  status?: string; listing_id?: number | null; listing?: Listing | null; raw_text?: string | null;
};
type Customer = {
  id: number; name?: string; phone?: string; memo?: string; updated_at?: string;
  ctype: string; needs: Need[];
};

const TRADE_KOR: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세", B3: "단기임대" };
const won = (v: any): string => {
  const n = Number(v);
  if (!n) return "";
  if (n >= 1e8) {
    const e = Math.floor(n / 1e8), m = Math.round((n % 1e8) / 1e4);
    return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`;
  }
  return `${Math.round(n / 1e4).toLocaleString()}만`;
};
const tel = (p?: string) => (p || "").replace(/[^0-9+]/g, "");
const fmtTel = (p?: string) => {
  const d = (p || "").replace(/[^0-9]/g, "");
  if (d.length === 11) return `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}`;
  return p || "";
};

// 요건 한 줄에 쓸 값들 — 구함이면 예산 범위, 내놓음이면 호가
function priceOf(n: Need): string {
  if (n.kind === "내놓음") return won(n.ask_price) || "-";
  const lo = won(n.budget_min), hi = won(n.budget_max);
  if (lo && hi) return `${lo} ~ ${hi}`;
  return lo || hi ? `${lo || ""}${hi ? `~ ${hi}` : " 이상"}` : "-";
}
function whereOf(n: Need): string {
  return [n.sigungu, n.dong, n.address].filter(Boolean).join(" ") || "-";
}

const FILTERS = [
  { v: "", label: "전체" }, { v: "구함", label: "구함" },
  { v: "양쪽", label: "양쪽" }, { v: "내놓음", label: "내놓음" },
];

export default function CustomerLedger({ authH, onGoListings }: {
  authH: () => Record<string, string>; onGoListings?: () => void;
}) {
  const [items, setItems] = useState<Customer[] | null>(null);
  const [q, setQ] = useState("");
  const [ct, setCt] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setBusy(true); setErr("");
    fetch(`${API_BASE}/lounge/customers`, { headers: authH() })
      .then((r) => { if (!r.ok) throw new Error(`오류 ${r.status}`); return r.json(); })
      .then((d) => setItems(d.items ?? []))
      .catch((e) => { setErr(e.message); setItems([]); })
      .finally(() => setBusy(false));
  }, [authH]);
  useEffect(() => { load(); }, [load]);

  const shown = useMemo(() => {
    const ql = q.trim();
    return (items || []).filter((c) => {
      if (ct && c.ctype !== ct) return false;
      if (!ql) return true;
      const hay = [c.name, c.phone, c.memo,
        ...c.needs.map((n) => [whereOf(n), n.listing?.complex_name].join(" "))].join(" ");
      return hay.includes(ql);
    });
  }, [items, q, ct]);

  const counts = useMemo(() => {
    const need = (items || []).reduce((a, c) => a + c.needs.length, 0);
    const sell = (items || []).reduce((a, c) => a + c.needs.filter((n) => n.kind === "내놓음").length, 0);
    return { cust: (items || []).length, need, buy: need - sell, sell };
  }, [items]);

  return (
    <div className="cled">
      <div className="cled-h">
        <h3><UserRound size={16} strokeWidth={2.3} /> 고객 원장</h3>
        <span className="cled-kpi">
          <b>고객 {counts.cust}</b>
          <i>구하는 조건 {counts.buy}</i>
          <i>내놓은 물건 {counts.sell}</i>
        </span>
        <button className="cled-refresh" onClick={load} disabled={busy} aria-label="새로고침">
          {busy ? <Loader2 size={14} className="txm-spin" /> : <RefreshCw size={14} />}
        </button>
      </div>

      <div className="cled-bar">
        <span className="cled-search">
          <Search size={15} />
          <input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="고객·전화·지역·단지 검색" />
        </span>
        <span className="cled-seg">
          {FILTERS.map((f) => (
            <button key={f.v} className={ct === f.v ? "on" : ""} onClick={() => setCt(f.v)}>{f.label}</button>
          ))}
        </span>
      </div>

      {err && <p className="cled-empty">{err}</p>}
      {items === null && <p className="cled-empty">불러오는 중…</p>}
      {items !== null && shown.length === 0 && !err && (
        <p className="cled-empty">
          아직 등록된 고객이 없어요. 대시보드 <b>빠른 입력</b>에 손님 문자나 매물을 넣으시면
          여기에 쌓입니다.
        </p>
      )}

      {shown.map((c) => (
        <div key={c.id} className="cled-row">
          <div className="cled-cust">
            <span className="cled-av">{(c.name || "?").slice(0, 1)}</span>
            <span className="cled-nm">
              <b>{c.name || "이름 미상"}</b>
              {c.phone && <a href={`tel:${tel(c.phone)}`}><Phone size={11} /> {fmtTel(c.phone)}</a>}
            </span>
            <span className={"cled-type t-" + (c.ctype === "양쪽" ? "both" : c.ctype === "내놓음" ? "sell" : "buy")}>
              {c.ctype}
            </span>
          </div>

          <div className="cled-needs">
            {c.needs.length === 0 && <div className="cled-need muted">요건이 없습니다</div>}
            {c.needs.map((n, i) => (
              <div key={n.id} className="cled-need">
                <span className={"cled-k" + (n.kind === "내놓음" ? " sell" : "")}>
                  {n.kind || "요건"}{c.needs.filter((x) => x.kind === n.kind).length > 1
                    ? ` ${c.needs.filter((x) => x.kind === n.kind).indexOf(n) + 1}` : ""}
                </span>
                <span className="cled-tr">{TRADE_KOR[n.trade || ""] || n.trade || "-"}</span>
                {n.role && <span className="cled-role">{n.role}</span>}
                <span className="cled-price">{priceOf(n)}</span>
                <span className="cled-where">{whereOf(n)}</span>
                {n.settle_date && <span className="cled-move">잔금 {n.settle_date}</span>}
                {n.listing ? (
                  <span className="cled-link" title="이 요건은 우리 매물장의 물건입니다">
                    <Link2 size={11} />
                    {n.listing.complex_name}
                    {n.listing.dong ? ` ${n.listing.dong}` : ""}{n.listing.ho ? ` ${n.listing.ho}호` : ""}
                    {n.listing.area2_m2 ? ` · 전용 ${Math.round(Number(n.listing.area2_m2))}㎡` : ""}
                  </span>
                ) : n.kind === "내놓음" ? (
                  <span className="cled-nolink">매물장에 없음</span>
                ) : null}
                {i === 0 && c.memo && <span className="cled-memo">{c.memo}</span>}
              </div>
            ))}
          </div>
        </div>
      ))}

      {onGoListings && shown.length > 0 && (
        <button className="cled-foot" onClick={onGoListings}>
          <Building2 size={13} /> 매물장에서 물건 보기
        </button>
      )}
    </div>
  );
}
