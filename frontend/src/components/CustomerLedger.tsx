// 고객 원장 — 고객 1명 = 행 1개가 아니다. 요건(구함·내놓음)이 하위 행으로 붙는다.
// 설계안 design/lounge_customer_ledger_설계안.md §3-1.
//
// 매물장과 따로 놀지 않게, 내놓은 요건은 우리 매물장 행을 그대로 물고 온다.
import { useCallback, useEffect, useMemo, useState } from "react";
import { UserRound, Search, Loader2, Building2, Link2, Phone, RefreshCw, Pencil } from "lucide-react";
import CustomerEdit, { type EditCustomer } from "./CustomerEdit";

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

// role 은 우선순위다. 예전 값(주안·대안·보유)이 남아 있어도 번호로 읽는다
const ROLE_OLD: Record<string, string> = { 주안: "1안", 대안: "2안", 보유: "1안" };
const roleLabel = (r?: string | null) => ROLE_OLD[r || ""] || r || "";
/** 몇 번째 안인지. 저장된 값이 있으면 그걸, 없으면 순서로 매긴다. */
function planLabel(n: Need | null, i: number): string {
  return (n && roleLabel(n.role)) || `${i + 1}안`;
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
  const [edit, setEdit] = useState<EditCustomer | null>(null);
  const openEdit = (c: Customer) => setEdit({
    id: c.id, name: c.name, phone: c.phone, memo: c.memo,
    needs: c.needs.map((n) => ({
      id: n.id, kind: n.kind, trade: n.trade, role: n.role,
      budget_min: n.budget_min, budget_max: n.budget_max, ask_price: n.ask_price,
      sigungu: n.sigungu, dong: n.dong, address: n.address,
      area_min: n.area_min, area_max: n.area_max,
      status: n.status, settle_date: n.settle_date,
    })),
  });

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

      {shown.length > 0 && (
        <div className="cldt">
          <div className="cldt-head">
            <span>고객</span>
            <span className="h-kd">구분</span>
            <span className="h-tr">거래</span>
            <span className="h-pr">예산·호가</span>
            <span className="h-rg">지역·단지</span>
            <span className="h-st">잔금</span>
            <span className="h-lk">매칭 매물</span>
            <span className="h-ct">연락처</span>
          </div>
          {shown.flatMap((c) => {
            const rows = c.needs.length ? c.needs : [null];
            return rows.map((n, i) => (
              <div key={`${c.id}-${n?.id ?? "x"}`} className={"cldt-r" + (i ? " cont" : "")}
                onClick={() => openEdit(c)}>
                <span className="c-nm">
                  {i === 0 ? (
                    <>
                      {c.name || "이름 미상"}
                      <em className={"c-tp t-" + (c.ctype === "양쪽" ? "both" : c.ctype === "내놓음" ? "sell" : "buy")}>
                        {c.ctype}</em>
                      <Pencil size={11} className="c-pen" />
                    </>
                  ) : (
                    // 이어지는 요건 — 종속선에 몇 번째 안인지를 얹는다
                    <em className="c-sub"><i />{planLabel(n, i)}</em>
                  )}
                </span>
                <span className="cldt-meta">
                  <span className="c-kd">
                    {n ? <em className={"cled-k" + (n.kind === "내놓음" ? " sell" : "")}>{n.kind || "요건"}</em>
                      : <em className="c-none">요건 없음</em>}
                  </span>
                  <span className="c-tr">{n ? (TRADE_KOR[n.trade || ""] || n.trade || "-") : ""}</span>
                  <span className="c-pr">{n ? priceOf(n) : ""}</span>
                  <span className="c-rg">{n ? whereOf(n) : ""}</span>
                  <span className="c-st">{n?.settle_date
                    ? <><em className="lb">잔금</em>{n.settle_date}</> : ""}</span>
                  <span className="c-lk">{n?.listing ? (
                    <em className="cled-link" title="우리 매물장의 물건입니다">
                      <Link2 size={10} />
                      {n.listing.complex_name}{n.listing.dong ? ` ${n.listing.dong}` : ""}
                      {n.listing.ho ? ` ${n.listing.ho}` : ""}
                    </em>
                  ) : n?.kind === "내놓음" ? <em className="cled-nolink">매물장에 없음</em> : ""}</span>
                </span>
                <span className="c-ct" onClick={(e) => e.stopPropagation()}>
                  {i === 0 && c.phone ? (
                    <a className="mjt-call" href={`tel:${tel(c.phone)}`} title={`${fmtTel(c.phone)} 로 전화`}>
                      <Phone size={12} /><b>{fmtTel(c.phone)}</b>
                    </a>
                  ) : null}
                </span>
              </div>
            ));
          })}
        </div>
      )}

      {edit && (
        <CustomerEdit authH={authH} cust={edit} onClose={() => setEdit(null)} onSaved={load} />
      )}

      {onGoListings && shown.length > 0 && (
        <button className="cled-foot" onClick={onGoListings}>
          <Building2 size={13} /> 매물장에서 물건 보기
        </button>
      )}
    </div>
  );
}
