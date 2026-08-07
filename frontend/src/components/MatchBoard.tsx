// 고객·물건 매칭 — 손님 요건으로 ① 우리 매물장 ② 전국 매물을 찾는다.
// 설계안 design/lounge_customer_ledger_설계안.md §5.
//
// 우리 것만 보여 주면 "우리 물건이 없다"로 끝나지만, 전국을 같이 보면
// 공동중개로 손님을 붙일 수 있다 — 중개사가 실제로 하는 일이 그것이다.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles, Loader2, Building2, UserRound, Phone, RefreshCw, ChevronRight, Search,
  Handshake,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

type FitStatus = "ok" | "near" | "miss" | "unknown";
type Fit = { key: string; label: string; status: FitStatus; note?: string };
type Hit = {
  src: "ours" | "market"; id: number | string; name: string; where?: string;
  trade?: string; price_man?: number | null; rent_man?: number | null;
  area?: number | null; supply?: number | null; floor?: string; direction?: string;
  settle?: string; n_in_complex?: number; complex_no?: string; fit?: Fit[];
  ptype?: string; premium_man?: number | null;      // 종류·권리금(상가·사무실)
  // 우리 매물
  total_floor?: number | null; rooms?: number | null; baths?: number | null;
  approve?: string; parking?: number | null; move_in?: string; mgmt?: number | null;
  manager?: string; feature?: string;
  // 전국 매물
  households?: number | null; same_addr?: number | null; confirm?: string;
  range_man?: [number, number]; tx_avg_man?: number | null; vs_tx_pct?: number | null;
  office?: string; office_tel?: string; office_id?: string; article_no?: string;
};
type Criteria = { used: string[]; skipped: string[]; unavailable: string[] };
// role 은 우선순위. 예전 값도 번호로 읽는다
const ROLE_OLD: Record<string, string> = { 주안: "1안", 대안: "2안", 보유: "1안" };
const roleLabel = (r?: string | null) => ROLE_OLD[r || ""] || r || "";
type Need = {
  id: number; kind?: string; ptype?: string | null; trade?: string; role?: string;
  budget_min?: number | null; budget_max?: number | null;
  sigungu?: string | null; dong?: string | null; address?: string | null;
  area_min?: number | null; area_max?: number | null; settle_date?: string | null;
  cname?: string | null; cphone?: string | null;
};
type Item = {
  need: Need; ours: Hit[]; market: Hit[]; n_ours: number; n_market: number; criteria?: Criteria;
};

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
  // 확대 검색 — 요건별로 단계와 결과를 따로 들고 있는다
  const [exp, setExp] = useState<Record<number, { level: number; label: string; items: Hit[]; has_more: boolean }>>({});
  const [expBusy, setExpBusy] = useState<number | null>(null);

  const expand = useCallback(async (needId: number, level: number) => {
    setExpBusy(needId);
    try {
      const r = await fetch(`${API_BASE}/lounge/match/expand?need_id=${needId}&level=${level}`,
        { headers: authH() });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || `오류 ${r.status}`);
      setExp((e) => ({ ...e, [needId]: j }));
    } catch (e: any) {
      setErr(e?.message || "확대 검색에 실패했어요");
    } finally { setExpBusy(null); }
  }, [authH]);

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
          <i>공동중개 {totalMkt}</i>
        </span>
        <button className="cled-refresh" onClick={load} disabled={busy} aria-label="다시 찾기">
          {busy ? <Loader2 size={14} className="txm-spin" /> : <RefreshCw size={14} />}
        </button>
      </div>
      <p className="mtb-lead">
        고객원장의 <b>구함</b> 요건으로 우리 매물장을 먼저 찾고, 없거나 부족하면 다른 사무소
        매물에서 같은 조건을 찾아 드립니다. <b>공동중개</b>로 붙일 수 있는 후보입니다.
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
                {n.ptype && <em className="pt">{n.ptype}</em>}
                <em>{TRADE_KOR[n.trade || ""] || n.trade || "-"}</em>
                {/* 몇 번째 안인지 — 어느 조건을 먼저 밀지가 여기서 갈린다 */}
                {n.role && <i className="mtb-pri">{roleLabel(n.role)}</i>}
                {eokWonRange(n)}
                {(n.dong || n.sigungu || n.address) && <i>{[n.sigungu, n.dong, n.address].filter(Boolean).join(" ")}</i>}
                {(n.area_min || n.area_max) && <i>{[n.area_min, n.area_max].filter(Boolean).map((a) => `${Math.round(Number(a) / 3.3058)}평`).join("~")}</i>}
                {n.settle_date && <i>잔금 {n.settle_date}</i>}
              </span>
              <span className="mtb-cnt">
                {it.n_ours > 0 && <b className="ours">우리 {it.n_ours}</b>}
                {it.n_market > 0 && <b className="mkt">공동 {it.n_market}</b>}
                {total === 0 && <b className="zero">맞는 매물 없음</b>}
                <ChevronRight size={14} className={opened ? "rot" : ""} />
              </span>
            </button>

            {opened && it.criteria && (
              <div className="mtb-crit">
                <span><b>이 조건으로 찾았어요</b> {it.criteria.used.join(" · ") || "없음"}</span>
                {it.criteria.skipped.length > 0 && (
                  <span className="skip"><b>요건에 없어 못 건 조건</b> {it.criteria.skipped.join(" · ")}</span>
                )}
                {it.criteria.unavailable.length > 0 && (
                  <span className="na"><b>매물 데이터에 없어 확인 못 함</b> {it.criteria.unavailable.join(" · ")}</span>
                )}
              </div>
            )}
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
                    <div className="mtb-sec mkt"><Handshake size={12} /> 공동중개 {it.market.length}건
                      <span>다른 사무소 매물</span></div>
                    {it.market.map((h) => <HitRow key={`m${h.id}`} h={h} />)}
                  </>
                )}
                <ExpandBox nid={n.id} state={exp[n.id]} busy={expBusy === n.id} onRun={expand} />
              </div>
            )}
            {opened && total === 0 && (
              <div className="mtb-hits">
                <p className="mtb-empty">조건에 딱 맞는 매물이 없어요. 범위를 넓혀 찾아볼 수 있습니다.</p>
                <ExpandBox nid={n.id} state={exp[n.id]} busy={expBusy === n.id} onRun={expand} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** 공동가능매물 확대 검색 — 우리 매물장에 없을 때 남의 물건으로 손님을 붙인다.
 *  무엇을 풀었는지 밝히고, 어느 사무소에 전화해야 하는지까지 보여 준다. */
function ExpandBox({ nid, state, busy, onRun }: {
  nid: number;
  state?: { level: number; label: string; items: Hit[]; has_more: boolean };
  busy: boolean;
  onRun: (nid: number, level: number) => void;
}) {
  return (
    <div className="mtb-exp">
      {state && (
        <>
          <div className="mtb-sec exp">
            <Handshake size={12} /> 공동중개 확대 {state.items.length}건
            <span>{state.label}</span>
          </div>
          {state.items.length === 0 && (
            <p className="mtb-empty">이 범위에도 맞는 매물이 없어요.</p>
          )}
          {state.items.map((h, i) => <HitRow key={`e${h.id}-${i}`} h={h} />)}
        </>
      )}
      <button className="mtb-more" disabled={busy}
        onClick={() => onRun(nid, state ? Math.min(state.level + 1, 2) : 1)}>
        {busy ? <Loader2 size={13} className="txm-spin" /> : <Handshake size={13} />}
        {busy ? "찾는 중…"
          : !state ? "공동중개 범위 넓혀 찾기"
            : state.has_more ? "더 넓게 찾기" : "가장 넓은 범위입니다"}
      </button>
    </div>
  );
}

const FIT_MARK: Record<FitStatus, string> = { ok: "✓", near: "≈", miss: "✕", unknown: "?" };

function HitRow({ h }: { h: Hit }) {
  const price = h.trade === "월세"
    ? `${eok(h.price_man)}${h.rent_man ? ` / ${Math.round(h.rent_man).toLocaleString()}만` : ""}`
    : eok(h.price_man);
  // 스펙 — 손님에게 전화로 읽어 줄 만한 것들만 순서대로
  const spec = [
    h.ptype || "",
    h.area ? py(h.area) : "",
    h.floor ? `${h.floor}${h.total_floor ? `/${h.total_floor}` : ""}층` : "",
    h.rooms ? `방${h.rooms}${h.baths ? `/욕${h.baths}` : ""}` : "",
    h.direction || "",
    h.parking ? `주차 ${h.parking}` : "",
    h.approve ? `${h.approve}년` : "",
    h.households ? `${h.households.toLocaleString()}세대` : "",
    h.settle ? `잔금 ${h.settle}` : "",
    h.move_in ? `입주 ${h.move_in}` : "",
    h.mgmt ? `관리비 ${h.mgmt}만` : "",
    h.premium_man ? `권리금 ${Math.round(h.premium_man).toLocaleString()}만` : "",
    h.where || "",
  ].filter(Boolean).join(" · ");
  // 전국 매물은 단지 안 시세 폭과 실거래 대비를 같이 준다 — '싸다'를 근거로 말하게
  const tel2 = (h.office_tel || "").replace(/[^0-9+]/g, "");
  const market = h.src === "market" ? [
    h.n_in_complex && h.n_in_complex > 1
      ? `단지 내 ${h.n_in_complex}건${h.range_man ? ` (${eok(h.range_man[0])}~${eok(h.range_man[1])})` : ""}`
      : "",
    h.vs_tx_pct != null
      ? `실거래 평균 ${eok(h.tx_avg_man)} 대비 ${h.vs_tx_pct > 0 ? "+" : ""}${h.vs_tx_pct}%`
      : "",
  ].filter(Boolean).join(" · ") : (h.manager ? `담당 ${h.manager}` : "");

  const body = (
    <>
      <div className="mtb-hit-top">
        <span className={"mtb-src " + (h.src === "ours" ? "ours" : "coop")}>
          {h.src === "ours" ? "우리" : "공동"}</span>
        <b className="mtb-nm">{h.name}</b>
        <span className="mtb-price">{price}</span>
        {h.src === "market" && h.complex_no && <Search size={12} />}
      </div>
      {spec && <div className="mtb-spec">{spec}</div>}
      {market && <div className={"mtb-mkt" + (h.vs_tx_pct != null && h.vs_tx_pct < -3 ? " cheap" : "")}>{market}</div>}
      {h.feature && <div className="mtb-feat">{h.feature}</div>}
      {h.office && (
        <div className="mtb-office">
          <Building2 size={11} /> {h.office}
          {h.office_tel && (
            <a href={`tel:${tel2}`} onClick={(e) => e.stopPropagation()}>
              <Phone size={10} /> {h.office_tel}
            </a>
          )}
        </div>
      )}
      {h.fit && h.fit.length > 0 && (
        <div className="mtb-fit">
          {h.fit.map((f) => (
            <span key={f.key} className={"f-" + f.status} title={f.note || ""}>
              {FIT_MARK[f.status]} {f.label}{f.note && f.status !== "ok" ? ` ${f.note}` : ""}
            </span>
          ))}
        </div>
      )}
    </>
  );
  if (h.src === "market" && h.complex_no) {
    return <Link className="mtb-hit" to={`/complex/${h.complex_no}`}>{body}</Link>;
  }
  return <div className="mtb-hit">{body}</div>;
}
