// 고객·물건 매칭 — 손님 요건으로 ① 우리 매물장 ② 전국 매물을 찾는다.
// 설계안 design/lounge_customer_ledger_설계안.md §5.
//
// 우리 것만 보여 주면 "우리 물건이 없다"로 끝나지만, 전국을 같이 보면
// 공동중개로 손님을 붙일 수 있다 — 중개사가 실제로 하는 일이 그것이다.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles, Loader2, Building2, Globe, UserRound, Phone, RefreshCw, ChevronRight, Search,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

type Hit = {
  src: "ours" | "market"; id: number | string; name: string; where?: string;
  trade?: string; price_man?: number | null; rent_man?: number | null;
  area?: number | null; supply?: number | null; floor?: string; direction?: string;
  settle?: string; n_in_complex?: number; complex_no?: string;
};
type Need = {
  id: number; kind?: string; trade?: string; role?: string;
  budget_min?: number | null; budget_max?: number | null;
  sigungu?: string | null; dong?: string | null; address?: string | null;
  area_min?: number | null; area_max?: number | null; settle_date?: string | null;
  cname?: string | null; cphone?: string | null;
};
type Item = { need: Need; ours: Hit[]; market: Hit[]; n_ours: number; n_market: number };

const TRADE_KOR: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세" };
const eok = (man?: number | null): string => {
  if (!man) return "";
  const won = man * 10000;
  if (won >= 1e8) {
    const e = Math.floor(won / 1e8), m = Math.round((won % 1e8) / 1e4);
    return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`;
  }
  return `${Math.round(man).toLocaleString()}만`;
};
const eokWonRange = (n: Need): string => {
  const f = (v?: number | null) => (v ? eok(v / 10000) : "");
  const lo = f(n.budget_min), hi = f(n.budget_max);
  if (lo && hi) return `${lo} ~ ${hi}`;
  return lo ? `${lo} 이상` : hi ? `${hi} 이하` : "예산 미정";
};
const py = (m2?: number | null) => (m2 ? `${Math.round(m2 / 3.3058)}평(${Math.round(m2)}㎡)` : "");
const tel = (p?: string | null) => (p || "").replace(/[^0-9+]/g, "");

export default function MatchBoard({ authH, onGoLedger }: {
  authH: () => Record<string, string>; onGoLedger?: () => void;
}) {
  const [items, setItems] = useState<Item[] | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<Record<number, boolean>>({});

  const load = useCallback(() => {
    setBusy(true); setErr("");
    fetch(`${API_BASE}/lounge/match`, { headers: authH() })
      .then((r) => { if (!r.ok) throw new Error(`오류 ${r.status}`); return r.json(); })
      .then((d) => {
        const list: Item[] = d.items ?? [];
        setItems(list);
        // 맞는 게 있는 요건은 처음부터 펼쳐 둔다 — 찾으러 온 사람에게 한 번 더 누르게 하지 않는다
        const o: Record<number, boolean> = {};
        list.forEach((x) => { if (x.n_ours + x.n_market > 0) o[x.need.id] = true; });
        setOpen(o);
      })
      .catch((e) => { setErr(e.message); setItems([]); })
      .finally(() => setBusy(false));
  }, [authH]);
  useEffect(() => { load(); }, [load]);

  const totalOurs = (items || []).reduce((a, x) => a + x.n_ours, 0);
  const totalMkt = (items || []).reduce((a, x) => a + x.n_market, 0);

  return (
    <div className="mtb">
      <div className="mtb-h">
        <h3><Sparkles size={16} strokeWidth={2.3} /> 고객·물건 매칭</h3>
        <span className="mtb-kpi">
          <b>구하는 손님 {(items || []).length}</b>
          <i>우리 매물 {totalOurs}</i>
          <i>전국 매물 {totalMkt}</i>
        </span>
        <button className="cled-refresh" onClick={load} disabled={busy} aria-label="다시 찾기">
          {busy ? <Loader2 size={14} className="txm-spin" /> : <RefreshCw size={14} />}
        </button>
      </div>
      <p className="mtb-lead">
        고객원장의 <b>구함</b> 요건으로 우리 매물장을 먼저 찾고, 없거나 부족하면 전국 매물에서
        같은 조건을 찾아 드립니다. 전국 매물은 공동중개로 붙일 수 있는 후보입니다.
      </p>

      {err && <p className="cled-empty">{err}</p>}
      {items === null && <p className="cled-empty">찾는 중…</p>}
      {items !== null && items.length === 0 && !err && (
        <p className="cled-empty">
          구하는 손님이 아직 없어요. 대시보드 <b>빠른 입력</b>에 손님 문자를 넣으면
          요건이 만들어지고 여기서 매물을 찾아 드립니다.
          {onGoLedger && <> <button className="mtb-link" onClick={onGoLedger}>고객원장 보기</button></>}
        </p>
      )}

      {(items || []).map((it) => {
        const n = it.need;
        const total = it.n_ours + it.n_market;
        const opened = !!open[n.id];
        return (
          <div key={n.id} className={"mtb-card" + (total ? "" : " none")}>
            <button className="mtb-need" onClick={() => setOpen((o) => ({ ...o, [n.id]: !opened }))}>
              <span className="mtb-av"><UserRound size={13} /></span>
              <span className="mtb-who">
                <b>{n.cname || "이름 미상"}</b>
                {n.cphone && <a href={`tel:${tel(n.cphone)}`} onClick={(e) => e.stopPropagation()}>
                  <Phone size={10} /> {n.cphone}</a>}
              </span>
              <span className="mtb-cond">
                <em>{TRADE_KOR[n.trade || ""] || n.trade || "-"}</em>
                {eokWonRange(n)}
                {(n.dong || n.sigungu || n.address) && <i>{[n.sigungu, n.dong, n.address].filter(Boolean).join(" ")}</i>}
                {(n.area_min || n.area_max) && <i>{[n.area_min, n.area_max].filter(Boolean).map((a) => `${Math.round(Number(a) / 3.3058)}평`).join("~")}</i>}
                {n.settle_date && <i>잔금 {n.settle_date}</i>}
              </span>
              <span className="mtb-cnt">
                {it.n_ours > 0 && <b className="ours">우리 {it.n_ours}</b>}
                {it.n_market > 0 && <b className="mkt">전국 {it.n_market}</b>}
                {total === 0 && <b className="zero">맞는 매물 없음</b>}
                <ChevronRight size={14} className={opened ? "rot" : ""} />
              </span>
            </button>

            {opened && total > 0 && (
              <div className="mtb-hits">
                {it.ours.length > 0 && (
                  <>
                    <div className="mtb-sec"><Building2 size={12} /> 우리 매물장 {it.ours.length}건</div>
                    {it.ours.map((h) => <HitRow key={`o${h.id}`} h={h} />)}
                  </>
                )}
                {it.market.length > 0 && (
                  <>
                    <div className="mtb-sec mkt"><Globe size={12} /> 전국 매물 {it.market.length}건
                      <span>공동중개 후보</span></div>
                    {it.market.map((h) => <HitRow key={`m${h.id}`} h={h} />)}
                  </>
                )}
              </div>
            )}
            {opened && total === 0 && (
              <div className="mtb-hits">
                <p className="mtb-empty">
                  조건에 맞는 매물이 없어요. 예산이나 면적을 조금 넓히면 후보가 생길 수 있습니다.
                </p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function HitRow({ h }: { h: Hit }) {
  const price = h.trade === "월세"
    ? `${eok(h.price_man)}${h.rent_man ? ` / ${Math.round(h.rent_man).toLocaleString()}만` : ""}`
    : eok(h.price_man);
  const body = (
    <>
      <span className={"mtb-src " + h.src}>{h.src === "ours" ? "우리" : "전국"}</span>
      <b className="mtb-nm">{h.name}</b>
      <span className="mtb-meta">
        {h.area ? py(h.area) : ""}
        {h.floor ? ` · ${h.floor}층` : ""}
        {h.direction ? ` · ${h.direction}` : ""}
        {h.where ? ` · ${h.where}` : ""}
        {h.settle ? ` · 잔금 ${h.settle}` : ""}
        {h.n_in_complex && h.n_in_complex > 1 ? ` · 단지 내 ${h.n_in_complex}건` : ""}
      </span>
      <span className="mtb-price">{price}</span>
    </>
  );
  if (h.src === "market" && h.complex_no) {
    return <Link className="mtb-hit" to={`/complex/${h.complex_no}`}>{body}<Search size={12} /></Link>;
  }
  return <div className="mtb-hit">{body}</div>;
}
