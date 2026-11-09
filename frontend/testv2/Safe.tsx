// 안심 창(등기·전세안심) — 절충안의 2번 카테고리. 지도 레이어가 아니라 지도 위 창으로 연다.
// 탭: 등기변동 알림 · 등기분석(준비 중) · 깡통전세지수 · 매수계산기·안전특약
// 깡통전세지수·매수계산기는 운영 화면을 부르지 않고 같은 API·같은 산식(lib/buycalc)으로 다시 그린다.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { Dd, getJson, API } from "./Drawer";
import { LoginBox, authHeaders } from "./Request";
import { geocodeRegion } from "../src/lib/kakaomap";
import { areaLabel } from "../src/lib/area";
import { type CalcInput, DEFAULT_INPUT, calculate, loanRegulation, maxAffordablePrice, STAGE_LABEL, STAGE_ORDER, fmtEok } from "../src/lib/buycalc";
import { classifyRegion } from "../src/lib/buyregion";

export type SafeTab = "alert" | "ledger" | "jeonse" | "calc";
const TABS: { k: SafeTab; l: string }[] = [{ k: "alert", l: "등기변동 알림" }, { k: "ledger", l: "등기분석" }, { k: "jeonse", l: "깡통전세지수" }, { k: "calc", l: "매수계산기·안전특약" }];

const won = (v: number | null | undefined): string => {
  if (!v) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8); const m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
};

function Sec({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return <section className="t2-safe-sec"><h3>{title}{sub && <small>{sub}</small>}</h3>{children}</section>;
}

// ── 등기변동 알림 ─────────────────────────────────────
function AlertTab({ session }: { session: Session | null }) {
  const [state, setState] = useState<"idle" | "open" | "closed">("idle");
  const [watches, setWatches] = useState<any[]>([]);
  useEffect(() => {
    if (!session) { setState("idle"); return; }
    fetch(`${API}/iros/watches`, { headers: authHeaders(session) }).then(async (r) => {
      if (!r.ok) { setState("closed"); return; }
      const j = await r.json().catch(() => ({}));
      setWatches(j.items || []); setState("open");
    }).catch(() => setState("closed"));
  }, [session]);
  return (
    <>
      <p className="t2-safe-lead">계약한 집의 등기에 새 사건이 생기면 알려 드려요. 잔금일·전입신고 전후에 집주인이 몰래 대출을 받거나 소유자가 바뀌는 일을 놓치지 않게요.</p>
      <div className="t2-safe-steps">
        <div><b>1</b><span>주소와 동·호를 넣어요</span></div>
        <div><b>2</b><span>휴대폰 번호를 한 번 인증해요</span></div>
        <div><b>3</b><span>등기에 새 신청사건이 접수되면 바로 알림이 와요</span></div>
      </div>
      {!session ? <LoginBox why="등기변동 알림은 로그인한 계정에 저장돼요. 콕집 계정 그대로 쓰세요." />
        : state === "open" ? (
          <Sec title="내 감시 대상" sub={`${watches.length}곳`}>
            {watches.length === 0 ? <p className="t2-sempty">아직 등록한 집이 없어요.</p> : (
              <table className="t2-tbl"><thead><tr><th>주소</th><th>동·호</th><th className="num">마지막 확인</th><th>상태</th></tr></thead>
                <tbody>{watches.map((w: any, i: number) => <tr key={i}><td>{w.address}</td><td>{w.unit}</td><td className="num mut">{w.checked_at ?? "-"}</td><td className={w.changed ? "up" : "mut"}>{w.changed ? "변동 있음" : "변동 없음"}</td></tr>)}</tbody></table>
            )}
            <p className="t2-snote">새 집 등록과 알림 설정은 곧 이 창에서 바로 할 수 있어요.</p>
          </Sec>
        ) : (
          <div className="t2-safe-soon"><b>회원 신청을 준비하고 있어요.</b><p>열리면 이 자리에서 바로 주소를 넣고 감시를 시작할 수 있어요. 안드로이드 앱·웹은 푸시로, 아이폰은 앱 업데이트 뒤 받을 수 있어요.</p></div>
        )}
      <p className="t2-snote">최근 접수된 신청사건만 봅니다. 등기부 전체 권리관계를 보장하지 않으니 계약 전에는 등기부등본을 직접 확인하세요.</p>
    </>
  );
}

// ── 깡통전세지수 ──────────────────────────────────────
type Unit = { area_m2: number | null; gongsi: number; hug_limit: number; n: number; whole?: boolean };
type JResp = { ok: boolean; error?: string; resolved?: { text: string; building: string | null; kind: string | null }; units?: Unit[];
  verdict?: { grade: string | null; hug_limit: number; gongsi: number } | null;
  nearby?: { scope: string; sale_median: number | null; jeonse_median: number | null; risky_pct: number | null };
  building_deals?: { sales: { date: string; amount: number; area_m2: number | null; floor: number | null }[]; rents: { date: string; deposit: number; monthly: number; area_m2: number | null; floor: number | null }[] };
  building_listings?: { article_no: string; trade: string; area_m2: number | null; price: number; rent: number; dup?: number; ratio?: number; grade?: string; naver_url: string }[] };
const GRADE_C: Record<string, string> = { "양호": "#1f9d63", "보증한도 확인": "#b7791f", "HUG 초과 가능": "#e0701e", "고위험": "#d23b3b" };
// HUG 보증한도 = 공시가격 × 140%(주택가격 환산) × 90%(담보인정) = 공시가격 × 126%
function judge(total: number, gongsi: number) {
  const r = total / gongsi;
  if (r <= 1.15) return { grade: "양호", msg: "공시가격 기준으로도 여유가 있어요." };
  if (r <= 1.26) return { grade: "보증한도 확인", msg: "HUG 보증한도(공시가 × 126%)에 가까워요. 선순위 채권·근저당을 꼭 확인하세요." };
  if (r <= 1.4) return { grade: "HUG 초과 가능", msg: "공시가격 기준 HUG 보증한도를 넘을 수 있어요. KB시세·감정가 같은 다른 기준 확인이 필요해요." };
  return { grade: "고위험", msg: "공시가 환산 주택가격(140%)을 넘는 수준이에요. 깡통·보증 거절 가능성이 큽니다." };
}
function JeonseTab({ at }: { at: { lat: number; lng: number; name: string } | null }) {
  const [addr, setAddr] = useState("");
  const [target, setTarget] = useState<{ lat: number; lng: number; name: string } | null>(at);
  const [res, setRes] = useState<JResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [unit, setUnit] = useState<Unit | null>(null);
  const [dep, setDep] = useState("");
  const [lien, setLien] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!target) return;
    setRes(null); setUnit(null); setDep(""); setLien(""); setLoading(true);
    getJson(`/tools/jeonse-check?lat=${target.lat}&lng=${target.lng}`).then((d: JResp) => { setRes(d); if (d.units?.length === 1) setUnit(d.units[0]); })
      .catch(() => setRes({ ok: false, error: "조회하지 못했어요" })).finally(() => setLoading(false));
  }, [target]);
  const search = async () => {
    const kw = addr.trim(); if (!kw) return;
    setErr("");
    const c = await geocodeRegion(kw);
    if (!c) { setErr(`'${kw}' 주소를 찾지 못했어요`); return; }
    setTarget({ lat: c.lat, lng: c.lng, name: kw });
  };
  const depWon = dep ? Number(dep) * 1e4 : 0, lienWon = lien ? Number(lien) * 1e4 : 0, total = depWon + lienWon;
  const v = unit && depWon ? { ...judge(total, unit.gongsi), ratio: Math.round(total / unit.gongsi * 100) } : null;
  const isHouse = !!res?.resolved?.kind?.includes("단독") || !!res?.units?.some((u) => u.whole);
  return (
    <>
      <p className="t2-safe-lead">빌라 주소를 넣고 면적을 고른 뒤 전세 보증금을 적으면, 공시가격(HUG 기준)으로 깡통전세 위험을 판정해요. 지도에서 빌라를 고른 채 열면 그 건물이 바로 들어와요.</p>
      <div className="t2-safe-search">
        <input value={addr} onChange={(e) => setAddr(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} placeholder="주소 (예: 화곡동 102-119)" aria-label="주소" />
        <button onClick={search}>조회</button>
        {err && <span className="t2-err">{err}</span>}
      </div>
      {target && <p className="t2-safe-target"><b>{res?.resolved?.building || target.name}</b>{res?.resolved?.kind && <small> · {res.resolved.kind}</small>}</p>}
      {loading && <div className="t2-sload"><i /><i /></div>}
      {res && !res.ok && <p className="t2-sempty">{res.error}</p>}
      {res?.ok && res.units && res.units.length > 0 && (isHouse ? (
        <Sec title="단독·다가구는 판정하지 않아요">
          <p className="t2-snote">한 건물에 여러 세입자 보증금이 쌓이는 구조라 공시가격만으로는 깡통 여부를 가릴 수 없어요. 전입세대 열람원·확정일자 부여현황으로 선순위 보증금 총액을 꼭 확인하세요.</p>
          <div className="t2-kpis"><div><span>건물 전체 공시가격</span><b>{won(res.units[0].gongsi)}</b></div><div><span>HUG 보증한도(참고)</span><b>{won(res.units[0].hug_limit)}</b></div></div>
        </Sec>
      ) : (
        <>
          <Sec title="전용면적" sub="면적마다 공시가격이 달라요">
            <div className="t2-fseg wrap">{res.units.map((u) => <button key={u.area_m2 ?? "w"} className={unit?.area_m2 === u.area_m2 ? "on" : ""} onClick={() => setUnit(u)}>{u.area_m2 == null ? "건물 전체" : areaLabel(u.area_m2)} <small>{won(u.gongsi)}</small></button>)}</div>
          </Sec>
          {unit && (
            <Sec title="보증금 넣기">
              <div className="t2-kpis"><div><span>공시가격 ({unit.area_m2 == null ? "건물 전체" : areaLabel(unit.area_m2)})</span><b>{won(unit.gongsi)}</b></div><div><span>HUG 보증한도 (공시가 × 126%)</span><b>{won(unit.hug_limit)}</b></div></div>
              <div className="t2-safe-inputs">
                <label>전세 보증금 (만원)<input type="number" value={dep} onChange={(e) => setDep(e.target.value)} placeholder="예: 25000" />{depWon > 0 && <small>{won(depWon)}</small>}</label>
                <label>선순위 채권 (만원)<input type="number" value={lien} onChange={(e) => setLien(e.target.value)} placeholder="등기부 채권최고액 합계, 없으면 0" />{lienWon > 0 && <small>{won(lienWon)}</small>}</label>
              </div>
              {v && (
                <div className="t2-verdict" style={{ borderColor: GRADE_C[v.grade] }}>
                  <b style={{ color: GRADE_C[v.grade] }}>{v.grade}</b>
                  <span>{lienWon ? "부채비율" : "전세가율"} {v.ratio}%</span>
                  <p>{v.msg}</p>
                  {lienWon > 0 && <small>전세 {won(depWon)} + 선순위 {won(lienWon)} = {won(total)} · 보증한도 {won(unit.hug_limit)}</small>}
                  <div className="t2-gauge"><i style={{ width: `${Math.min(v.ratio / 1.6, 100)}%`, background: GRADE_C[v.grade] }} /><em style={{ left: `${126 / 1.6}%` }}>126%</em><em style={{ left: `${140 / 1.6}%` }}>140%</em></div>
                </div>
              )}
            </Sec>
          )}
        </>
      ))}
      {res?.ok && res.building_deals && (res.building_deals.sales.length > 0 || res.building_deals.rents.length > 0) && (
        <Sec title="이 건물 실거래">
          <table className="t2-tbl"><tbody>
            {res.building_deals.sales.slice(0, 3).map((s, i) => <tr key={"s" + i}><td className="up">매매</td><td className="mut">{s.date}</td><td>{areaLabel(s.area_m2)}{s.floor ? ` · ${s.floor}층` : ""}</td><td className="num b">{won(s.amount)}</td></tr>)}
            {res.building_deals.rents.slice(0, 4).map((r, i) => <tr key={"r" + i}><td className={r.monthly ? "" : "down"}>{r.monthly ? "월세" : "전세"}</td><td className="mut">{r.date}</td><td>{areaLabel(r.area_m2)}{r.floor ? ` · ${r.floor}층` : ""}</td><td className="num b">{won(r.deposit)}{r.monthly ? ` / ${won(r.monthly)}` : ""}</td></tr>)}
          </tbody></table>
        </Sec>
      )}
      {res?.ok && res.building_listings && res.building_listings.length > 0 && (
        <Sec title="현재 매물" sub={`${res.building_listings.length}건`}>
          <table className="t2-tbl"><tbody>
            {res.building_listings.slice(0, 6).map((l) => <tr key={l.article_no}><td>{l.trade}</td><td>{areaLabel(l.area_m2)}{l.dup && l.dup > 1 ? ` · ${l.dup}곳` : ""}</td><td style={l.grade ? { color: GRADE_C[l.grade] } : undefined}>{l.grade ? `${l.grade} ${l.ratio}%` : ""}</td><td className="num b">{won(l.price)}{l.trade === "월세" && l.rent ? ` / ${won(l.rent)}` : ""}</td><td className="num"><a href={l.naver_url} target="_blank" rel="noreferrer">매물 보기</a></td></tr>)}
          </tbody></table>
        </Sec>
      )}
      {res?.ok && res.nearby && (
        <Sec title={`${res.nearby.scope} 시세`} sub="이 건물이 아닌 동네 평균">
          <div className="t2-kpis"><div><span>매매 중위</span><b>{won(res.nearby.sale_median)}</b></div><div><span>전세 중위</span><b>{won(res.nearby.jeonse_median)}</b></div><div><span>위험 건물 비율</span><b className={(res.nearby.risky_pct || 0) >= 30 ? "up" : ""}>{res.nearby.risky_pct ?? "-"}%</b><small>전세가율 80% 이상 빌라</small></div></div>
        </Sec>
      )}
      {res?.ok && <p className="t2-snote">공시가격 기준 단순 추정이에요. 실제 HUG 가입 여부는 KB시세·부동산테크 시세·선순위 채권·주택 유형에 따라 달라질 수 있어요. 계약 전 등기부등본 확인은 필수.</p>}
    </>
  );
}

// ── 매수계산기 ────────────────────────────────────────
type Opt = { code: string; name: string };
const EOK = 1e8;
function Money({ label, v, onChange, quick }: { label: string; v: number; onChange: (n: number) => void; quick: { l: string; v: number }[] }) {
  const [txt, setTxt] = useState(v ? (v / EOK).toString() : "");
  useEffect(() => { setTxt(v ? String(Math.round(v / 1e6) / 100) : ""); }, [v]);
  return (
    <label className="t2-money">{label}
      <span className="in"><input inputMode="decimal" value={txt} onChange={(e) => { setTxt(e.target.value); const n = parseFloat(e.target.value); onChange(isNaN(n) ? 0 : Math.round(n * EOK)); }} placeholder="0" /><em>억</em></span>
      <span className="t2-fseg">{quick.map((q) => <button key={q.l} onClick={() => onChange(v + q.v)}>{q.l}</button>)}<button onClick={() => onChange(0)}>지움</button></span>
    </label>
  );
}
function CalcTab() {
  const [inp, setInp] = useState<CalcInput>(DEFAULT_INPUT);
  const set = (p: Partial<CalcInput>) => setInp((s) => ({ ...s, ...p }));
  const [sidos, setSidos] = useState<Opt[]>([]);
  const [sggs, setSggs] = useState<Opt[]>([]);
  const [sido, setSido] = useState("");
  const [sgg, setSgg] = useState<Opt | null>(null);
  const [dd, setDd] = useState<string | null>(null);
  useEffect(() => { getJson("/stats/changes/sido-list").then((j) => setSidos(j.items || [])).catch(() => {}); }, []);
  useEffect(() => { if (!sido) { setSggs([]); return; } getJson(`/stats/sigungu-list?sido=${sido.slice(0, 2)}`).then((j) => setSggs(j.items || [])).catch(() => {}); }, [sido]);
  const cls = useMemo(() => (sido && sgg ? classifyRegion(sido, sgg.code) : null), [sido, sgg]);
  const pickSgg = (r: Opt) => { setSgg(r); const c = classifyRegion(sido, r.code); set({ loanRegion: c.loanRegion, regionalType: c.regionalType, isAdjustedArea: c.isRegulated }); };
  // 시가표준액은 매매가의 70%로 본다(등록면허세·채권 기준). 직접 아는 값이 있으면 그 값을 넣는 칸은 다음 단계.
  const calcInp = useMemo(() => ({ ...inp, standardPrice: Math.floor(inp.salePrice * 0.7) }), [inp]);
  const res = useMemo(() => calculate(calcInp), [calcInp]);
  const reg = useMemo(() => loanRegulation(calcInp), [calcInp]);
  const maxP = useMemo(() => maxAffordablePrice(calcInp), [calcInp]);
  const over = !reg.banned && inp.loanAmount > reg.maxLoan;
  const byStage = STAGE_ORDER.map((s) => ({ s, items: res.items.filter((i) => i.stage === s) })).filter((g) => g.items.length);
  return (
    <>
      <p className="t2-safe-lead">매매가·대출·현금을 넣으면 취득세부터 등기·이사까지 단계별 비용과 모자라는 현금을 바로 계산해요. 지역을 고르면 규제지역·대출 한도가 자동으로 들어가요.</p>
      <div className="t2-calc">
        <div className="t2-calc-in">
          <Money label="매매가" v={inp.salePrice} onChange={(n) => set({ salePrice: n })} quick={[{ l: "+1억", v: EOK }, { l: "+5억", v: 5 * EOK }, { l: "+10억", v: 10 * EOK }]} />
          <Money label="대출금" v={inp.loanAmount} onChange={(n) => set({ loanAmount: n })} quick={[{ l: "+1억", v: EOK }, { l: "+2억", v: 2 * EOK }, { l: "+5억", v: 5 * EOK }]} />
          <Money label="보유 현금" v={inp.currentCash} onChange={(n) => set({ currentCash: n })} quick={[{ l: "+5천", v: EOK / 2 }, { l: "+1억", v: EOK }, { l: "+2억", v: 2 * EOK }]} />
          <div className="t2-calc-row"><span>매수 지역</span>
            <Dd id="sido" open={dd} setOpen={setDd} label={sidos.find((s) => s.code === sido)?.name ?? "시·도"} active={!!sido}>
              {sidos.map((s) => <button key={s.code} className={s.code === sido ? "on" : ""} onClick={() => { setSido(s.code); setSgg(null); }}>{s.name}</button>)}
            </Dd>
            {sido && <Dd id="sgg" open={dd} setOpen={setDd} label={sgg?.name ?? "시·군·구"} active={!!sgg}>
              {sggs.map((s) => <button key={s.code} className={s.code === sgg?.code ? "on" : ""} onClick={() => pickSgg(s)}>{s.name}</button>)}
            </Dd>}
            {cls && <small>{cls.regLabel}</small>}
          </div>
          <div className="t2-calc-row"><span>보유 주택</span>
            <div className="t2-fseg">{[0, 1, 2].map((n) => <button key={n} className={inp.houseCount === n ? "on" : ""} onClick={() => set({ houseCount: n })}>{n === 2 ? "2채 이상" : `${n}채`}</button>)}</div>
            {inp.houseCount === 1 && <button className={"t2-tog" + (inp.isTempTwoHouse ? " on" : "")} onClick={() => set({ isTempTwoHouse: !inp.isTempTwoHouse })}>일시적 2주택(처분 조건)</button>}
          </div>
          <div className="t2-calc-row"><span>조건</span>
            <button className={"t2-tog" + (inp.isFirstTime ? " on" : "")} onClick={() => set({ isFirstTime: !inp.isFirstTime })}>생애최초</button>
            <button className={"t2-tog" + (inp.isOver85m2 ? " on" : "")} onClick={() => set({ isOver85m2: !inp.isOver85m2 })}>전용 85㎡ 초과</button>
            <button className={"t2-tog" + (inp.hasDefenseFund ? " on" : "")} onClick={() => set({ hasDefenseFund: !inp.hasDefenseFund })}>방공제 적용</button>
          </div>
        </div>
        <div className="t2-calc-out">
          <div className="t2-kpis big">
            <div><span>최소 필요 현금</span><b>{fmtEok(res.minRequiredCash)}</b><small>대출 뺀 전체</small></div>
            <div><span>대출 포함 총 자금</span><b>{fmtEok(res.totalWithLoan)}</b></div>
            <div><span>{res.cashGap >= 0 ? "현금 여유" : "모자라는 현금"}</span><b className={res.cashGap >= 0 ? "down" : "up"}>{fmtEok(Math.abs(res.cashGap))}</b></div>
            <div><span>이 조건으로 살 수 있는 최대</span><b>{fmtEok(maxP)}</b><small>대출 한도 자동 반영</small></div>
          </div>
          {reg.banned ? <p className="t2-calc-warn">{reg.reason}</p>
            : <p className="t2-snote">대출 한도 {fmtEok(reg.maxLoan)} (LTV {Math.round(reg.ltv * 100)}%{reg.cap ? ` · 총액 ${fmtEok(reg.cap)}` : ""}, {reg.buyerLabel}){over && <b className="up"> · 입력한 대출금이 한도를 넘어요</b>}. 실제 한도는 DSR·소득에 따라 더 낮을 수 있어요.</p>}
          {byStage.map((g) => (
            <table className="t2-tbl" key={g.s}>
              <thead><tr><th>{STAGE_LABEL[g.s]}</th><th className="num">{fmtEok(g.items.reduce((a, b) => a + b.amount, 0))}</th></tr></thead>
              <tbody>{g.items.map((it) => <tr key={it.id}><td>{it.label}{(it.formula || it.note) && <small className="blk">{it.formula || it.note}</small>}</td><td className="num">{fmtEok(it.amount)}</td></tr>)}</tbody>
            </table>
          ))}
          <p className="t2-snote">시가표준액은 매매가의 70%로 가정. 중개보수·법무사 비용은 요율 상한 기준 자동 계산이라 실제와 다를 수 있어요.</p>
        </div>
      </div>
      <Sec title="전세 안전특약" sub="등기 확인 뒤 계약서에 넣을 문구">
        <p className="t2-snote">아래는 널리 쓰이는 특약의 예시예요. 실제 문구는 상황에 맞게 중개사·법률 전문가와 다듬어 쓰세요.</p>
        <ol className="t2-terms">
          <li><b>권리 변동 금지</b> 임대인은 잔금일 다음 날까지 본 주택에 근저당권·전세권 등 새로운 권리를 설정하지 않으며, 위반 시 임차인은 계약을 해제하고 계약금의 배액을 받는다.</li>
          <li><b>등기 상태 유지</b> 계약일 현재 등기부등본상 권리관계(근저당 채권최고액 ○○원 등)가 잔금일까지 그대로 유지되어야 하며, 다른 권리가 생기면 임차인은 계약을 해제할 수 있다.</li>
          <li><b>보증보험 가입 협조</b> 임대인은 임차인의 전세보증금 반환보증 가입에 필요한 서류 제공 등에 협조하고, 가입이 거절되면 임차인은 위약금 없이 계약을 해제할 수 있다.</li>
          <li><b>세금 체납 확인</b> 임대인은 국세·지방세 완납증명서를 잔금일 전에 제시하며, 체납이 확인되면 임차인은 계약을 해제할 수 있다.</li>
          <li><b>소유권 이전 시 승계</b> 임대차 기간 중 소유자가 바뀌어도 새 소유자가 본 계약을 승계하며, 임대인은 매도 사실을 즉시 임차인에게 알린다.</li>
          <li><b>보증금 반환 지연</b> 계약 종료 후 보증금 반환이 지연되면 임대인은 지연일수만큼 연 ○%의 지연이자를 지급한다.</li>
          <li><b>수리 책임</b> 입주 전 확인한 하자(목록 첨부)는 임대인이 잔금일 전에 수리하며, 주요 설비 고장은 임대인이 부담한다.</li>
        </ol>
      </Sec>
    </>
  );
}

// ── 창 ────────────────────────────────────────────────
export function SafeWindow({ tab, onTab, onClose, phone, session, at }: { tab: SafeTab; onTab: (t: SafeTab) => void; onClose: () => void; phone: boolean;
  session: Session | null; at: { lat: number; lng: number; name: string } | null; onLogin?: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h); return () => document.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <section className={"t2-win" + (phone ? " phone" : "")} role="dialog" aria-label="안심">
      <header className="t2-win-h">
        <button className="t2-win-x" onClick={onClose} aria-label="지도로 돌아가기"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>지도</button>
        <h2>안심</h2>
        <nav className="t2-win-tabs" role="tablist">
          {TABS.map((t) => <button key={t.k} role="tab" aria-selected={t.k === tab} className={t.k === tab ? "on" : ""} onClick={() => onTab(t.k)}>{t.l}</button>)}
        </nav>
      </header>
      <div className="t2-win-b">
        <div className="t2-win-in narrow">
          <h3 className="t2-win-ttl">{TABS.find((t) => t.k === tab)?.l}</h3>
          {tab === "alert" && <AlertTab session={session} />}
          {tab === "ledger" && (
            <>
              <p className="t2-safe-lead">주소만 넣으면 등기부등본의 근저당·전세권·가압류·신탁 같은 권리관계 위험을 요약해 주는 기능이에요.</p>
              <div className="t2-safe-soon"><b>준비 중이에요.</b><p>등기 열람 비용과 하루 조회 한도를 정한 뒤 열어요. 그동안은 등기변동 알림과 깡통전세지수로 기본 위험을 먼저 확인하세요.</p></div>
            </>
          )}
          {tab === "jeonse" && <JeonseTab at={at} />}
          {tab === "calc" && <CalcTab />}
        </div>
      </div>
    </section>
  );
}
