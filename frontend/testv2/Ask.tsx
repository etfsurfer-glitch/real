// 매물의뢰 창 — 중개사에게 매물의뢰 · AI 상담사 · 내 요청. 운영 화면을 부르지 않고 같은 API로 지도 안에서 다시 그린다.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { Dd, getJson, API } from "./Drawer";
import { useRegionLists, regionLabel, Seg, type RegionSel } from "./Stats";
import { LoginBox, PhoneBlock, authHeaders, login, sessionName } from "./Request";
import { visitorHeader } from "../src/lib/visitor";
import { OwnerTab } from "./Kok";

const SITE = "https://koczip.com";
export type AskTab = "req" | "ai" | "mine" | "owner";
export const ASK_TABS: { k: AskTab; l: string }[] = [{ k: "req", l: "중개사에게 매물의뢰" }, { k: "ai", l: "AI 상담사" }, { k: "mine", l: "내 요청" }, { k: "owner", l: "내 집 내놓기" }];
export const askTabOf = (s: string | null): AskTab | null => (s && ASK_TABS.some((t) => t.k === s) ? (s as AskTab) : null);

const ASSETS = [{ k: "apt", l: "아파트" }, { k: "offi", l: "오피스텔" }, { k: "villa", l: "빌라·연립" }, { k: "house", l: "단독·다가구" }, { k: "comm", l: "상가·사무실" }];
const TRADES = [{ k: "A1", l: "매매" }, { k: "B1", l: "전세" }, { k: "B2", l: "월세" }];
const lbl = (arr: { k: string; l: string }[], k: string) => arr.find((x) => x.k === k)?.l || "";
const errText = (d: any, status: number) => {
  const det = d?.detail;
  if (typeof det === "string") return det;
  if (det && typeof det === "object" && "message" in det) return String(det.message);
  return `오류 ${status}`;
};

// ── 중개사에게 매물의뢰 ───────────────────────────────
type Cand = { realtor_id: string; name: string; address: string | null; representative: string | null; listings: number; matched: boolean };
type Done = { sent_to: number; offices: { name: string }[]; proposals_url?: string };
const DRAFT_KEY = "t2_req_draft";

function ReqTab({ session, region, prefillQ, onSent }: { session: Session | null; region: RegionSel; prefillQ: string; onSent: () => void }) {
  // 로그인 왕복(OAuth) 동안 적어 둔 조건이 날아가지 않게 — 떠나기 직전에만 저장, 돌아와서 한 번 쓰고 지운다
  const draft = useMemo(() => {
    try { const d = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || "null") || {}; sessionStorage.removeItem(DRAFT_KEY); return d; } catch { return {}; }
  }, []);
  const [r, setR] = useState<RegionSel>(draft.r || region);
  const L = useRegionLists(r);
  const [dd, setDd] = useState<string | null>(null);
  const [asset, setAsset] = useState<string>(draft.asset || "apt");
  const [trade, setTrade] = useState<string>(draft.trade || "A1");
  const [areaTxt, setAreaTxt] = useState<string>(draft.areaTxt || "");
  const [budgetTxt, setBudgetTxt] = useState<string>(draft.budgetTxt || "");
  const [memo, setMemo] = useState<string>(draft.memo || "");
  const [mode, setMode] = useState<"recommend" | "choose">(draft.mode || "recommend");
  const [count, setCount] = useState<number>(draft.count || 30);
  const [picked, setPicked] = useState<string[]>(draft.picked || []);
  const [cands, setCands] = useState<Cand[]>([]);
  const [candsLoading, setCandsLoading] = useState(false);
  const [me, setMe] = useState<{ phone_verified?: boolean } | null>(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Done | null>(null);
  const [err, setErr] = useState("");
  const [prefill, setPrefill] = useState("");

  // 지도가 보던 동으로 시작한다(초안이 없을 때). 지도를 옮기면 따라가되 사용자가 손댄 뒤엔 그대로.
  const touched = useRef(!!draft.r);
  useEffect(() => { if (!touched.current) setR(region); }, [region.sido, region.sgg, region.dong]);   // eslint-disable-line react-hooks/exhaustive-deps
  const pickR = (v: RegionSel) => { touched.current = true; setR(v); };

  useEffect(() => {
    if (!session) { setMe(null); return; }
    fetch(`${API}/me`, { headers: authHeaders(session) }).then((x) => (x.ok ? x.json() : null)).then(setMe).catch(() => setMe(null));
  }, [session]);

  // AI에 물어본 문장을 조건으로 풀어 채운다
  useEffect(() => {
    if (!prefillQ || draft.r) return;
    getJson(`/requests/parse?q=${encodeURIComponent(prefillQ)}`).then((d) => {
      const got: string[] = [];
      if (d.sido_cortar) { touched.current = true; setR({ sido: d.sido_cortar, sgg: d.sigungu_cortar || "", dong: d.cortar || "" }); got.push(d.region_name || "지역"); }
      if (d.asset) { setAsset(d.asset); got.push(lbl(ASSETS, d.asset)); }
      if (d.trade) { setTrade(d.trade); got.push(lbl(TRADES, d.trade)); }
      if (d.area_txt) { setAreaTxt(d.area_txt); got.push(d.area_txt); }
      if (d.budget_txt) { setBudgetTxt(d.budget_txt); got.push(d.budget_txt); }
      if (!memo) setMemo(prefillQ);
      if (got.length) setPrefill(got.filter(Boolean).join(" · "));
    }).catch(() => {});
  }, [prefillQ]);   // eslint-disable-line react-hooks/exhaustive-deps

  // 받는 곳 후보 — 그 조건 매물을 지금 가진 사무소
  useEffect(() => {
    if (!r.sgg) { setCands([]); return; }
    const q = new URLSearchParams({ sigungu: r.sgg.slice(0, 5), asset, trade, limit: "20" });
    if (r.dong) q.set("cortar", r.dong.slice(0, 10));
    let live = true; setCandsLoading(true);
    getJson(`/requests/candidates?${q}`).then((d) => { if (live) setCands(d.items || []); }).catch(() => { if (live) setCands([]); })
      .finally(() => { if (live) setCandsLoading(false); });
    return () => { live = false; };
  }, [r.sgg, r.dong, asset, trade]);

  const targets = useMemo(() => (mode === "choose" ? cands.filter((c) => picked.includes(c.realtor_id)) : cands.slice(0, count)), [mode, picked, cands, count]);
  const regionName = regionLabel(r, L);
  const phoneOK = !!me?.phone_verified;
  const ready = !!r.sgg && targets.length > 0;
  const canSend = ready && !!session && phoneOK && consent && !busy;

  const saveDraft = () => { try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ r, asset, trade, areaTxt, budgetTxt, memo, mode, count, picked })); } catch { /* */ } };
  const submit = async () => {
    if (!session) return;
    setBusy(true); setErr("");
    try {
      const x = await fetch(`${API}/requests`, {
        method: "POST", headers: { "Content-Type": "application/json", ...authHeaders(session) },
        body: JSON.stringify({ sido: r.sido.slice(0, 2), sigungu: r.sgg.slice(0, 5), cortar: r.dong, region_name: regionName, asset, trade,
          area_txt: areaTxt, budget_txt: budgetTxt, memo, ai_query: prefillQ, pick_mode: mode, target_count: count, realtor_ids: mode === "choose" ? picked : [], consent: true }),
      });
      const d = await x.json().catch(() => ({}));
      if (!x.ok) throw new Error(errText(d, x.status));
      setDone(d);
    } catch (e: any) { setErr(e.message || "요청을 보내지 못했어요"); } finally { setBusy(false); }
  };

  if (done) {
    return (
      <div className="t2-ask">
        <div className="t2-verdict" style={{ borderColor: "var(--c-primary)" }}>
          <b>요청이 전달됐어요</b><span>{done.sent_to}곳</span>
          <p>중개사무소가 매물과 연락처를 제안으로 남기면 알려 드려요. 보통 하루 안에 와요. 확인하고 마음에 드는 곳에만 전화하면 돼요. 내 이름·전화번호는 전달되지 않았어요.</p>
        </div>
        <table className="t2-tbl"><tbody>{done.offices.map((o, i) => <tr key={i}><td>{o.name}</td></tr>)}</tbody></table>
        <p className="t2-snote" style={{ marginTop: 10 }}>제안이 오면 문자로 알려 드려요. 여기서는 아래 내 요청에서, 문자의 주소로는 로그인 없이 볼 수 있어요.</p>
        <button className="t2-cta1" style={{ marginTop: 14 }} onClick={onSent}>내 요청에서 진행 상황 보기</button>
      </div>
    );
  }

  return (
    <div className="t2-ask">
      <p className="t2-safe-lead">이름·전화번호 없이 <b>조건만</b> 그 동네 중개사무소로 가요. 중개사무소가 매물과 자기 연락처를 제안으로 남기면, 보고 마음에 드는 곳에만 직접 전화하면 돼요. 이용료는 없어요.</p>
      {prefill && <p className="t2-snote">AI에 물어본 「{prefillQ}」에서 {prefill} 을(를) 채워 뒀어요. 바꿔도 돼요.</p>}

      <div className="t2-ask-sec">
        <h3><i>1</i>어느 지역에서 찾으세요? <small>동까지 고르면 그 동네에서 실제로 매물을 가진 사무소로 가요</small></h3>
        <div className="t2-ask-region">
          <Dd id="a-sido" open={dd} setOpen={setDd} label={L.sidos.find((x) => x.code === r.sido)?.name ?? "시·도"} active={!!r.sido}>
            {L.sidos.map((s) => <button key={s.code} className={s.code === r.sido ? "on" : ""} onClick={() => pickR({ sido: s.code, sgg: "", dong: "" })}>{s.name}</button>)}
          </Dd>
          {r.sido && (
            <Dd id="a-sgg" open={dd} setOpen={setDd} label={L.sggs.find((x) => x.code === r.sgg)?.name ?? "시·군·구"} active={!!r.sgg}>
              {L.sggs.map((s) => <button key={s.code} className={s.code === r.sgg ? "on" : ""} onClick={() => pickR({ ...r, sgg: s.code, dong: "" })}>{s.name}</button>)}
            </Dd>
          )}
          {r.sgg && (
            <Dd id="a-dong" open={dd} setOpen={setDd} label={L.dongs.find((x) => x.code === r.dong)?.name ?? "읍·면·동 전체"} active={!!r.dong}>
              <button className={!r.dong ? "on" : ""} onClick={() => pickR({ ...r, dong: "" })}>읍·면·동 전체</button>
              {L.dongs.map((s) => <button key={s.code} className={s.code === r.dong ? "on" : ""} onClick={() => pickR({ ...r, dong: s.code })}>{s.name}</button>)}
            </Dd>
          )}
          {r.sgg && <span className="t2-ask-picked">{regionName}</span>}
        </div>
      </div>

      <div className="t2-ask-sec">
        <h3><i>2</i>어떤 집을 찾으세요?</h3>
        <div className="t2-calc-row"><span>유형</span><Seg opts={ASSETS} value={asset} onChange={setAsset} /></div>
        <div className="t2-calc-row"><span>거래</span><Seg opts={TRADES} value={trade} onChange={setTrade} /></div>
        <div className="t2-safe-inputs">
          <label>희망 면적 <small>선택</small><input value={areaTxt} onChange={(e) => setAreaTxt(e.target.value)} placeholder="예: 30평대" /></label>
          <label>예산 <small>선택</small><input value={budgetTxt} onChange={(e) => setBudgetTxt(e.target.value)} placeholder="예: 12억 이하" /></label>
        </div>
        <label className="t2-fld">더 하고 싶은 말 <textarea value={memo} onChange={(e) => setMemo(e.target.value)} rows={3} maxLength={1000} placeholder="예: 초등학교 가까운 곳, 6개월 뒤 입주 예정" /></label>
      </div>

      <div className="t2-ask-sec">
        <h3><i>3</i>어디로 보낼까요? {r.sgg && !candsLoading && <small>{regionName}에서 이 조건 매물을 가진 사무소 {cands.length}곳</small>}</h3>
        {!r.sgg ? <p className="t2-sempty">지역을 먼저 골라 주세요.</p> : (
          <>
            <div className="t2-calc-row"><span>방식</span><Seg opts={[{ k: "recommend", l: "콕집 추천" }, { k: "choose", l: "직접 고르기" }]} value={mode} onChange={setMode} />
              {mode === "recommend" && <Seg opts={[{ k: 30, l: "30곳" }, { k: 40, l: "40곳" }, { k: 50, l: "50곳" }]} value={count} onChange={setCount} />}</div>
            {mode === "recommend" && <p className="t2-snote">이 조건의 매물을 가진 사무소부터 자동으로 골라요. 그 동네 사무소를 한 번에 훑어야 답이 빨리 와요. 답이 없으면 30분마다 10곳씩 세 번 더 넓혀요.</p>}
            {candsLoading ? <div className="t2-sload"><i /><i /><i /></div>
              : cands.length === 0 ? <p className="t2-sempty">이 조건의 매물을 가진 사무소를 찾지 못했어요. 동을 넓히거나 유형을 바꿔 보세요.</p>
              : (
                <table className="t2-tbl t2-ask-cands">
                  <thead><tr>{mode === "choose" && <th />}<th>사무소</th><th className="num">매물</th><th>주소</th></tr></thead>
                  <tbody>
                    {(mode === "choose" ? cands : cands.slice(0, count)).map((c) => {
                      const on = picked.includes(c.realtor_id);
                      const tog = () => setPicked((v) => (on ? v.filter((x) => x !== c.realtor_id) : [...v, c.realtor_id].slice(0, 10)));
                      return (
                        <tr key={c.realtor_id} className={mode === "choose" ? (on ? "on pick" : "pick") : ""} onClick={mode === "choose" ? tog : undefined}>
                          {mode === "choose" && <td className="chk"><input type="checkbox" checked={on} onChange={tog} onClick={(e) => e.stopPropagation()} /></td>}
                          <td><b>{c.name}</b>{c.representative && <small className="blk">{c.representative}</small>}</td>
                          <td className="num">{c.listings.toLocaleString()}{c.matched && <small className="blk">이 조건</small>}</td>
                          <td className="mut">{c.address || ""}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            {mode === "choose" && cands.length > 0 && <p className="t2-snote">{picked.length}곳 골랐어요(최대 10곳).</p>}
          </>
        )}
      </div>

      <div className="t2-ask-sec">
        <h3><i>4</i>이렇게 보낼게요</h3>
        <table className="t2-tbl t2-ask-sum"><tbody>
          <tr><th>지역</th><td>{regionName || "-"}</td></tr>
          <tr><th>유형·거래</th><td>{lbl(ASSETS, asset)} · {lbl(TRADES, trade)}</td></tr>
          {areaTxt && <tr><th>면적</th><td>{areaTxt}</td></tr>}
          {budgetTxt && <tr><th>예산</th><td>{budgetTxt}</td></tr>}
          {memo && <tr><th>메모</th><td style={{ whiteSpace: "normal" }}>{memo}</td></tr>}
          <tr><th>받는 곳</th><td style={{ whiteSpace: "normal" }}>{targets.length ? `${targets.length}곳 · ${targets.slice(0, 6).map((t) => t.name).join(", ")}${targets.length > 6 ? " 외" : ""}` : "-"}</td></tr>
        </tbody></table>
        {!session ? (
          <div className="t2-login" onClickCapture={saveDraft}>
            <p>중개사무소가 연락할 번호를 확인해야 해서 여기서만 로그인이 필요해요. 적어 둔 조건은 그대로 남아요.</p>
            <button className="kakao" onClick={() => login("kakao")}>카카오로 계속하기</button>
            <button className="google" onClick={() => login("google")}>구글로 계속하기</button>
          </div>
        ) : me && !phoneOK ? <PhoneBlock session={session} onDone={() => setMe({ ...me, phone_verified: true })} />
          : phoneOK ? <p className="t2-ask-ok">{sessionName(session)} · 휴대폰 인증 완료</p> : null}
        <label className="t2-agree">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span>지역·유형·거래·면적·예산·메모가 위 중개사무소에 전달되는 데 동의해요. 이름·전화번호는 가지 않아요. 인증한 번호는 콕집이 보관하고 제안 도착 알림에만 써요.</span>
        </label>
        {err && <p className="t2-err">{err}</p>}
        <button className="t2-cta1" disabled={!canSend} onClick={submit}>
          {busy ? "보내는 중…" : !r.sgg ? "지역을 골라 주세요" : targets.length === 0 ? "받는 곳이 없어요" : !session ? "로그인 뒤 보낼 수 있어요" : !phoneOK ? "휴대폰 인증이 필요해요" : !consent ? "동의에 체크해 주세요" : `${targets.length}곳에 요청 보내기`}
        </button>
        <p className="t2-snote" style={{ marginTop: 10 }}>콕집은 중개 계약의 당사자가 아니고 조건에 맞는 중개사무소를 연결만 해요. 실제 거래 조건과 매물 상태는 해당 중개사무소에서 직접 확인하세요. 요청은 언제든 삭제할 수 있어요.</p>
      </div>
    </div>
  );
}

// ── AI 상담사 ────────────────────────────────────────
type Turn = { q: string; answer?: string; error?: string; loading?: boolean; status?: string; tools?: { tool: string }[] };
const KEEP = 10;
const EXAMPLES = ["최근 신고가 단지 보여줘", "요즘 거래 활발한 지역 알려줘", "이번 달 취소된 거래 보여줘", "전세가율 높은 단지 알려줘"];
const HINTS = ["전국 실거래·매물 자료를 살펴보는 중", "조건에 맞는 단지를 추리는 중", "여러 단지를 비교하는 중", "최신 시세·신고가와 대조하는 중", "답을 정리하는 중"];
function wantsListing(q: string) {
  const t = q.replace(/\s/g, "");
  return /(매물|집|아파트|오피스텔|빌라|원룸|단독|상가|사무실|전세|월세|매매|급매|시세|가격|호가|얼마|평형|평대|추천|찾아|구해|알아보|보고싶|살까|사고싶)/.test(t)
    && !/(취득세|양도세|보유세|종부세|재산세|세금|계산기|얼마나오|뜻이|이란무엇|의미가|거래량|통계|추이가)/.test(t);
}
const shortQ = (q: string) => { const t = q.trim().replace(/[?？!.]+$/g, "").replace(/(알려줘|알려주세요|찾아줘|찾아주세요|추천해줘|추천해주세요|보여줘|보여주세요|어때|얼마야|얼마인가요|있나요|있어)\s*$/g, "").trim(); return t.length > 24 ? `${t.slice(0, 24)}…` : t; };

function inline(s: string, go: (path: string, text?: string) => void): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*)|(\[[^\]]+\]\([^)]+\))/g;
  let last = 0, k = 0, m: RegExpExecArray | null;
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) out.push(<span key={k++}>{s.slice(last, m.index)}</span>);
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={k++}>{tok.slice(2, -2)}</strong>);
    else {
      const mm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok);
      const text = mm ? mm[1] : tok, url = mm ? mm[2] : "#";
      if (url.startsWith("/")) out.push(<a key={k++} className="t2-lnk" href={SITE + url} onClick={(e) => { e.preventDefault(); go(url, text); }}>{text}</a>);
      else out.push(<a key={k++} className="t2-lnk" href={url} target="_blank" rel="noreferrer">{text}</a>);
    }
    last = re.lastIndex;
  }
  if (last < s.length) out.push(<span key={k++}>{s.slice(last)}</span>);
  return out;
}
function Md({ text, go }: { text: string; go: (p: string, t?: string) => void }) {
  const out: ReactNode[] = []; let bullets: string[] = [];
  const flush = () => { if (bullets.length) { out.push(<ul key={`u${out.length}`}>{bullets.map((b, i) => <li key={i}>{inline(b, go)}</li>)}</ul>); bullets = []; } };
  text.split("\n").forEach((ln, i) => { const t = ln.trim(); if (/^[*-]\s+/.test(t)) bullets.push(t.replace(/^[*-]\s+/, "")); else { flush(); if (t) out.push(<p key={`p${i}`}>{inline(t, go)}</p>); } });
  flush();
  return <>{out}</>;
}
function Loading({ status }: { status?: string }) {
  const [s, setS] = useState(0);
  useEffect(() => { const id = window.setInterval(() => setS((x) => x + 1), 1000); return () => window.clearInterval(id); }, []);
  return <p className="t2-ai-wait">{status || "처리 중…"}{s >= 3 && <small> · {HINTS[Math.min(HINTS.length - 1, Math.floor(s / 3))]} · {s}초</small>}</p>;
}

function AiTab({ session, onGo, onAsk }: { session: Session | null; onGo: (path: string, text?: string) => void; onAsk: (q: string) => void }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [region, setRegion] = useState<string | null>(null);
  const [examples, setExamples] = useState<string[]>(EXAMPLES);
  const [quota, setQuota] = useState<{ used: number; limit: number; remaining: number } | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const key = `t2_ai_turns:${session?.user?.id || "anon"}`;
  const H = (): Record<string, string> => ({ ...visitorHeader(), ...authHeaders(session) });

  useEffect(() => { getJson("/ai/region").then((d) => { if (d.region) setRegion(d.region); if (d.examples?.length) setExamples(d.examples); }).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/ai/quota`, { headers: H() }).then((r) => r.json()).then((d) => { if (typeof d?.remaining === "number") setQuota(d); }).catch(() => {}); }, [session]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    try { const a = JSON.parse(localStorage.getItem(key) || "null"); setTurns(Array.isArray(a) ? a.slice(-KEEP) : []); } catch { setTurns([]); }
    if (session) fetch(`${API}/ai/history?limit=${KEEP}`, { headers: authHeaders(session) }).then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => { if (d.items?.length) setTurns((cur) => (cur.length ? cur : d.items.slice(-KEEP))); }).catch(() => {});
  }, [key]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const done = turns.filter((t) => !t.loading && (t.answer || t.error)).slice(-KEEP);
    try { if (done.length) localStorage.setItem(key, JSON.stringify(done)); } catch { /* */ }
    requestAnimationFrame(() => logRef.current?.scrollTo({ top: 1e9 }));
  }, [turns, key]);

  const ask = async (question: string) => {
    const q = question.trim(); if (!q || busy) return;
    const history = turns.flatMap((t) => (t.answer ? [{ role: "user", text: t.q }, { role: "model", text: t.answer }] : []));
    setInput(""); setBusy(true);
    setTurns((t) => [...t, { q, loading: true, status: "질문 분석 중…" }].slice(-KEEP));
    const patch = (p: Partial<Turn>) => setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, ...p } : x)));
    try {
      const r = await fetch(`${API}/ai/ask-stream`, { method: "POST", headers: { "Content-Type": "application/json", ...H() }, body: JSON.stringify({ q, history }) });
      if ([429, 401, 402, 403].includes(r.status)) {
        const dj = await r.json().catch(() => ({}));
        patch({ loading: false, status: undefined, error: (typeof dj?.detail === "object" ? dj.detail?.message : null) || (r.status === 429 ? "잠시 뒤 다시 물어 주세요." : "이용할 수 없어요.") });
        if (r.status === 429 && dj?.detail?.code === "ai_daily_limit") setQuota((p) => (p ? { ...p, used: p.limit, remaining: 0 } : p));
        return;
      }
      if (!r.ok || !r.body) throw new Error(`${r.status}`);
      const reader = r.body.getReader(); const dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await reader.read(); if (done) break;
        buf += dec.decode(value, { stream: true });
        const chunks = buf.split("\n\n"); buf = chunks.pop() ?? "";
        for (const c of chunks) {
          const line = c.trim(); if (!line.startsWith("data:")) continue;
          let ev: any; try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
          if (ev.type === "status") patch({ status: ev.label });
          else if (ev.type === "done") { patch({ loading: false, status: undefined, answer: ev.answer, tools: ev.tools_used }); if (typeof ev.remaining === "number") setQuota((p) => (p ? { ...p, remaining: ev.remaining, used: p.limit - ev.remaining } : p)); }
          else if (ev.type === "error") patch({ loading: false, status: undefined, error: ev.error });
        }
      }
    } catch (e: any) { patch({ loading: false, status: undefined, error: String(e?.message || e) }); }
    finally { setBusy(false); }
  };

  return (
    <div className="t2-ai">
      <div className="t2-ai-log" ref={logRef}>
        <div className="t2-win-in narrow">
          {turns.length === 0 && (
            <div className="t2-ai-hello">
              <h3 className="t2-win-ttl">무엇이든 물어보세요</h3>
              <p className="t2-safe-lead">매일 갱신되는 전국 매물·실거래·중개사 자료를 바로 찾아 답해요. {region && <>지금 <b>{region}</b>에서 보고 있네요. 이 지역부터 물어보세요.</>}</p>
              <div className="t2-ai-ex">{examples.map((ex) => <button key={ex} onClick={() => ask(ex)}>{ex}</button>)}</div>
            </div>
          )}
          {turns.map((t, i) => (
            <div className="t2-ai-turn" key={i}>
              <p className="t2-ai-q">{t.q}</p>
              <div className="t2-ai-a">
                <span className="who">콕집</span>
                {t.loading && <Loading status={t.status} />}
                {t.error && <p className="t2-err">{t.error}</p>}
                {t.answer && <Md text={t.answer} go={onGo} />}
                {t.answer && wantsListing(t.q) && !t.answer.includes("/request") && (
                  <p className="t2-ai-req">「{shortQ(t.q)}」 조건 그대로 그 동네 중개사무소에 보낼 수 있어요. <button className="t2-lnk" onClick={() => onAsk(t.q)}>중개사에게 매물의뢰</button></p>
                )}
                {t.answer && (!t.tools || t.tools.length === 0) && <div className="t2-ai-ex small">{examples.map((ex) => <button key={ex} onClick={() => ask(ex)}>{ex}</button>)}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="t2-ai-in">
        <div className="t2-win-in narrow">
          <div className="row">
            <input value={input} maxLength={500} disabled={busy} placeholder={`예: ${region ? `${region} 급매 찾아줘` : "관심 지역 급매 찾아줘"}`}
              onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") ask(input); }} />
            <button disabled={busy || !input.trim()} onClick={() => ask(input)}>{busy ? "…" : "보내기"}</button>
          </div>
          <p className="t2-snote">{quota ? `오늘 남은 질문 ${quota.remaining}회 · 하루 ${quota.limit}회 무료` : "로그인 없이 바로 물어보세요"} · AI도 틀릴 수 있어요. 거래 전엔 꼭 현장에서 확인하세요.</p>
        </div>
      </div>
    </div>
  );
}

// ── 내 요청 ─────────────────────────────────────────
type OfferListing = { article_no: string; complex: string | null; area_m2: number | null; price: string | null; rent: string | null; floor: string | null; trade: string };
type Offer = { name: string; message: string; contact: string; listings: OfferListing[]; at: string };
type Req = { id: number; region: string; asset: string; trade: string; area: string; budget: string; memo: string; status: string; at: string; target_count: number; offices: { name: string; status: string; at: string | null }[]; offers: Offer[] };
const PY = 3.305785;

function MineTab({ session, onNew, onGo, token }: { session: Session | null; onNew: () => void; onGo: (p: string) => void; token?: string }) {
  const [items, setItems] = useState<Req[] | null>(null);
  const [err, setErr] = useState("");
  const load = () => {
    // 문자로 받은 링크(?proposals=토큰): 로그인 없이 그 요청 하나의 접수내역과 제안을 본다
    if (token) {
      setErr("");
      getJson(`/proposals/${encodeURIComponent(token)}`).then((d) => setItems([{ id: d.id, region: d.region, asset: d.asset, trade: d.trade, area: d.area, budget: d.budget, memo: d.memo,
        status: "", at: d.at, target_count: d.sent_to, offices: Array.from({ length: d.sent_to || 0 }, () => ({ name: "", status: "", at: null })), offers: d.offers || [] }]))
        .catch(() => { setItems([]); setErr("링크를 찾을 수 없어요. 문자의 주소를 그대로 열어 주세요."); });
      return;
    }
    if (!session) return;
    setErr("");
    fetch(`${API}/me/requests`, { headers: authHeaders(session) }).then((r) => { if (!r.ok) throw new Error(r.status === 401 ? "세션이 끝났어요. 다시 로그인해 주세요." : `불러오지 못했어요 (${r.status})`); return r.json(); })
      .then((d) => setItems(d.items || [])).catch((e: Error) => { setItems([]); setErr(e.message); });
  };
  useEffect(load, [session, token]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (!session && !token) return <LoginBox why="로그인하면 보낸 요청과 중개사무소 제안을 볼 수 있어요." />;
  if (err) return <><p className="t2-sempty">{err}</p><button className="t2-cta1" onClick={load}>다시 시도</button></>;
  if (!items) return <div className="t2-sload"><i /><i /><i /></div>;
  if (items.length === 0) return (
    <div className="t2-sgo"><p>아직 보낸 요청이 없어요. 원하는 조건을 남기면 그 동네 중개사무소가 매물을 찾아 제안해요. 이용료는 없어요.</p><button onClick={onNew}>중개사에게 매물의뢰</button></div>
  );
  return (
    <div className="t2-ask">
      {token && <p className="t2-snote">문자로 받은 링크로 보는 접수내역이에요. 로그인하면 보낸 요청 전체를 볼 수 있어요.</p>}
      {items.map((r) => (
        <div className="t2-myreq" key={r.id}>
          <div className="t2-sh"><h3>{r.region || "지역 미지정"} <small>{r.asset} · {r.trade} · {(r.at || "").slice(0, 10).replace(/-/g, ".")}</small></h3>
            <span className="t2-snote" style={{ margin: 0 }}>{[r.area, r.budget].filter(Boolean).join(" · ")}</span></div>
          {r.memo && <p className="t2-myreq-memo">{r.memo}</p>}
          {r.offers.length > 0 ? (
            <table className="t2-tbl t2-offers">
              <thead><tr><th>제안한 사무소</th><th>매물</th><th>메시지</th><th>연락</th></tr></thead>
              <tbody>
                {r.offers.map((o, i) => (
                  <tr key={i}>
                    <td><b>{o.name || "중개사무소"}</b><small className="blk">{(o.at || "").slice(5, 16)}</small></td>
                    <td style={{ whiteSpace: "normal" }}>{o.listings.length === 0 ? <small>-</small> : o.listings.map((x) => (
                      <div key={x.article_no} className="t2-offer-l">
                        <b>{x.complex || "단지 미상"}</b> <small>{[x.area_m2 ? `${Math.round(x.area_m2 / PY)}평(${Math.round(x.area_m2)}㎡)` : "", x.floor ? `${x.floor}층` : "", x.trade].filter(Boolean).join(" · ")}</small> <em>{x.price || x.rent || "-"}</em>
                      </div>
                    ))}</td>
                    <td style={{ whiteSpace: "normal" }}>{o.message}</td>
                    <td>{o.contact && <a className="t2-lnk" href={`tel:${o.contact.replace(/[^0-9+]/g, "")}`}>{o.contact}</a>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="t2-snote">{r.offices.length}곳에 전달했어요. 제안이 오면 알려 드려요. 보통 하루 안에 와요.</p>}
          <p className="t2-snote">내 연락처는 중개사무소에 가지 않았어요. 위 번호로 직접 걸 때만 알려져요.</p>
        </div>
      ))}
      <div className="t2-calc-row" style={{ marginTop: 8, gap: 12 }}>
        <button className="t2-lnk" onClick={onNew}>다른 조건으로 새 요청</button>
        <button className="t2-lnk" onClick={() => onGo("/settings")}>내 정보</button>
      </div>
    </div>
  );
}

// ── 창 ─────────────────────────────────────────────
export function AskWindow({ tab, onTab, onClose, phone, session, region, onGo, token, onLogin, onComplex }: {
  tab: AskTab; onTab: (t: AskTab) => void; onClose: () => void; phone: boolean; session: Session | null; region: RegionSel; token?: string; onLogin: () => void; onComplex: (no: string, name: string) => void;
  onGo: (path: string, text?: string) => void;   // 답변 속 내부 링크(/complex/…)는 지도에서 열고, 나머지는 운영 새 탭
}) {
  const [prefillQ, setPrefillQ] = useState("");
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h); return () => document.removeEventListener("keydown", h);
  }, [onClose]);
  const go = (path: string, text?: string) => {
    if (path.startsWith("/request")) { const q = new URLSearchParams(path.split("?")[1] || "").get("q") || ""; setPrefillQ(q); onTab("req"); return; }
    if (path.startsWith("/me/requests")) { onTab("mine"); return; }
    onGo(path, text);
  };
  return (
    <section className={"t2-win" + (phone ? " phone" : "")} role="dialog" aria-label="매물의뢰">
      <header className="t2-win-h">
        <button className="t2-win-x" onClick={onClose} aria-label="지도로 돌아가기"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>지도</button>
        <h2>매물의뢰</h2>
        <nav className="t2-win-tabs" role="tablist">
          {ASK_TABS.map((t) => <button key={t.k} role="tab" aria-selected={t.k === tab} className={t.k === tab ? "on" : ""} onClick={() => onTab(t.k)}>{phone && t.k === "req" ? "매물의뢰" : t.l}</button>)}
        </nav>
      </header>
      {tab === "ai" ? <div className="t2-win-b flex"><AiTab session={session} onGo={go} onAsk={(q) => { setPrefillQ(q); onTab("req"); }} /></div> : (
        <div className="t2-win-b">
          <div className="t2-win-in narrow">
            <h3 className="t2-win-ttl">{ASK_TABS.find((t) => t.k === tab)?.l}</h3>
            {tab === "req" && <ReqTab session={session} region={region} prefillQ={prefillQ} onSent={() => onTab("mine")} />}
            {tab === "mine" && <MineTab session={session} onNew={() => onTab("req")} onGo={go} token={token} />}
            {tab === "owner" && <OwnerTab session={session} onLogin={onLogin} onGo={onComplex} />}
          </div>
        </div>
      )}
    </section>
  );
}
