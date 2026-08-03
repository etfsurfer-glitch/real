import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Building2, Check, ChevronLeft, Phone, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth, loginKakao, loginGoogle } from "../auth";
import { PhoneModal } from "../components/PhoneVerify";
import { RegionSelect, useRegionFilter } from "../components/RegionSelect";

const API = import.meta.env.VITE_API_BASE;

type Cand = { realtor_id: string; name: string; address: string | null;
              representative: string | null; listings: number; matched: boolean };

const ASSETS = [["apt", "아파트"], ["offi", "오피스텔"], ["villa", "빌라·연립"],
                ["house", "단독·다가구"], ["comm", "상가·사무실"]] as const;
const TRADES = [["A1", "매매"], ["B1", "전세"], ["B2", "월세"]] as const;
const STEPS = ["지역", "조건", "받는 곳", "보내기"];

const label = (arr: readonly (readonly [string, string])[], k: string) =>
  arr.find(([v]) => v === k)?.[1] || "";

/** 콕집요청 — 한 화면에 하나씩만 묻는 단계형.
 *  중개사무소에는 '조건만' 전달된다(이름·전화 아님). 중개사가 매물과 자기 연락처를
 *  제안으로 남기면 손님이 보고 직접 전화하는 구조다. */
export default function KoczipRequest() {
  const { token } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();

  const reg = useRegionFilter();
  const { sido, sigungu, dong } = reg;
  const regionName = useMemo(() => [
    reg.sidos.find((x) => x.code === sido)?.name,
    reg.sigungus.find((x) => x.code === sigungu)?.name,
    reg.dongs.find((x) => x.code === dong)?.name,
  ].filter(Boolean).join(" "), [reg.sidos, reg.sigungus, reg.dongs, sido, sigungu, dong]);

  const [step, setStep] = useState(0);
  const [asset, setAsset] = useState(sp.get("asset") || "apt");
  const [trade, setTrade] = useState(sp.get("trade") || "A1");
  const [areaTxt, setAreaTxt] = useState(sp.get("area") || "");
  const [budgetTxt, setBudgetTxt] = useState("");
  const [memo, setMemo] = useState("");
  const aiQuery = sp.get("q") || "";
  const [prefill, setPrefill] = useState("");

  const [mode, setMode] = useState<"recommend" | "choose">("recommend");
  const [count, setCount] = useState(3);
  const [picked, setPicked] = useState<string[]>([]);
  const [cands, setCands] = useState<Cand[]>([]);
  const [phoneOK, setPhoneOK] = useState(false);
  const [phoneOpen, setPhoneOpen] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ sent_to: number; offices: { name: string }[];
                                    proposals_url?: string } | null>(null);
  const [err, setErr] = useState("");

  const authH = useCallback((): Record<string, string> =>
    (token ? { Authorization: `Bearer ${token}` } : {}), [token]);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/me`, { headers: authH() }).then((r) => r.json())
      .then((d) => setPhoneOK(!!d?.phone_verified)).catch(() => {});
  }, [token, authH]);

  // AI에 물어본 문장을 조건으로 풀어 채운다.
  // 지역 드롭다운은 10자리 코드를 쓴다 — 2·5자리를 넣으면 아무것도 안 골라진다(실측).
  useEffect(() => {
    if (!aiQuery) return;
    fetch(`${API}/requests/parse?q=${encodeURIComponent(aiQuery)}`)
      .then((r) => r.json())
      .then((d) => {
        const got: string[] = [];
        if (d.sido_cortar) { reg.setSido(d.sido_cortar); got.push(d.region_name || "지역"); }
        if (d.sigungu_cortar) reg.setSigungu(d.sigungu_cortar);
        if (d.cortar) reg.setDong(d.cortar);
        if (d.asset) { setAsset(d.asset); got.push(label(ASSETS, d.asset)); }
        if (d.trade) { setTrade(d.trade); got.push(label(TRADES, d.trade)); }
        if (d.area_txt) { setAreaTxt(d.area_txt); got.push(d.area_txt); }
        if (d.budget_txt) { setBudgetTxt(d.budget_txt); got.push(d.budget_txt); }
        if (got.length) setPrefill(got.filter(Boolean).join(" · "));
      })
      .catch(() => {});
  }, [aiQuery]);   // eslint-disable-line react-hooks/exhaustive-deps

  // 받는 곳 후보 — 조건이 정해진 뒤에 불러야 '그 조건 매물을 가진 곳'이 나온다
  useEffect(() => {
    if (step < 2 || !sigungu) return;
    const q = new URLSearchParams({ sigungu: sigungu.slice(0, 5), asset, trade, limit: "20" });
    if (dong) q.set("cortar", dong.slice(0, 10));
    fetch(`${API}/requests/candidates?${q}`)
      .then((r) => r.json()).then((d) => setCands(d.items || [])).catch(() => setCands([]));
  }, [step, sigungu, dong, asset, trade]);

  const targets = useMemo(() => (
    mode === "choose" ? cands.filter((c) => picked.includes(c.realtor_id)) : cands.slice(0, count)
  ), [mode, picked, cands, count]);

  const canNext = [!!sigungu, true, targets.length > 0, false][step];
  const canSend = !!token && targets.length > 0 && phoneOK && consent && !busy;

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API}/requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authH() },
        body: JSON.stringify({
          sido: sido.slice(0, 2), sigungu: sigungu.slice(0, 5), cortar: dong,
          region_name: regionName, asset, trade,
          area_txt: areaTxt, budget_txt: budgetTxt, memo, ai_query: aiQuery,
          pick_mode: mode, target_count: count,
          realtor_ids: mode === "choose" ? picked : [], consent: true,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail?.message || d?.detail || "요청을 보내지 못했어요");
      setDone(d);
    } catch (e: any) { setErr(e?.message || "요청을 보내지 못했어요"); }
    finally { setBusy(false); }
  };

  if (done) {
    return (
      <div className="kreq">
        <h2><Check size={20} strokeWidth={2.6} /> 요청이 전달됐어요</h2>
        <div className="kreq-card">
          <p className="kreq-lead"><b>{done.sent_to}곳</b>의 중개사무소로 요청을 보냈어요.</p>
          <ul className="kreq-offices">
            {done.offices.map((o, i) => <li key={i}><Building2 size={15} /> {o.name}</li>)}
          </ul>
          <div className="kreq-safe" style={{ marginTop: 10 }}>
            <b>연락처는 전달되지 않았습니다.</b> 조건만 갔어요.
          </div>
          <p className="muted" style={{ marginTop: 10 }}>
            중개사무소가 매물과 연락처를 제안으로 남기면 알려드릴게요. 보통 하루 안에 옵니다.
            확인하시고 <b>마음에 드는 곳에만</b> 전화하시면 됩니다.
          </p>
          {done.proposals_url && (
            <div className="kreq-q" style={{ marginTop: 12 }}>
              <div>제안이 오면 문자로 알려드려요. 이 주소로 <b>로그인 없이</b> 다시 보실 수 있습니다.
                <div className="kreq-q-sub">{done.proposals_url}</div>
              </div>
            </div>
          )}
          <div className="kreq-row" style={{ marginTop: 14 }}>
            <button className="kreq-primary"
              onClick={() => nav(done.proposals_url
                ? new URL(done.proposals_url).pathname : "/me/requests")}>
              받은 제안 보기
            </button>
            <button className="kreq-ghost" onClick={() => nav("/")}>홈으로</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="kreq">
      <h2><Sparkles size={20} strokeWidth={2.3} /> 콕집요청</h2>

      <ol className="kstep">
        {STEPS.map((s, i) => (
          <li key={s} className={i === step ? "on" : i < step ? "ok" : ""}>
            <i>{i < step ? <Check size={12} strokeWidth={3} /> : i + 1}</i>{s}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div className="kreq-card">
          <div className="kreq-step">어느 지역에서 찾으세요?</div>
          <p className="muted" style={{ marginBottom: 12 }}>
            동까지 고르시면 그 동네에서 실제로 매물을 가진 사무소로 전달됩니다.
          </p>
          <div className="kreq-region"><RegionSelect {...reg} /></div>
          {prefill && (
            <div className="kreq-q">
              <div>AI에 물어보신 <b>「{aiQuery}」</b>
                <div className="kreq-q-sub">{prefill} 을(를) 채워 뒀어요. 바꾸셔도 됩니다.</div>
              </div>
            </div>
          )}
          {regionName && <div className="kreq-pick">선택한 지역 — <b>{regionName}</b></div>}
        </div>
      )}

      {step === 1 && (
        <div className="kreq-card">
          <div className="kreq-step">어떤 집을 찾으세요?</div>
          <div className="kreq-lbl">유형</div>
          <div className="kreq-chips">
            {ASSETS.map(([k, l]) => (
              <button key={k} className={`kreq-chip ${asset === k ? "on" : ""}`}
                onClick={() => setAsset(k)}>{l}</button>
            ))}
          </div>
          <div className="kreq-lbl">거래</div>
          <div className="kreq-chips">
            {TRADES.map(([k, l]) => (
              <button key={k} className={`kreq-chip ${trade === k ? "on" : ""}`}
                onClick={() => setTrade(k)}>{l}</button>
            ))}
          </div>
          <div className="kreq-grid2">
            <label>희망 면적 <span>선택</span>
              <input value={areaTxt} onChange={(e) => setAreaTxt(e.target.value)} placeholder="예: 30평대" />
            </label>
            <label>예산 <span>선택</span>
              <input value={budgetTxt} onChange={(e) => setBudgetTxt(e.target.value)}
                placeholder="예: 12억 이하" />
            </label>
          </div>
          <label className="kreq-full">더 하고 싶은 말 <span>선택</span>
            <textarea value={memo} onChange={(e) => setMemo(e.target.value)} rows={3}
              placeholder="예: 초등학교 가까운 곳, 6개월 뒤 입주 예정" />
          </label>
        </div>
      )}

      {step === 2 && (
        <div className="kreq-card">
          <div className="kreq-step">어디로 보낼까요?</div>
          <div className="kreq-modes">
            <button className={`kreq-mode ${mode === "recommend" ? "on" : ""}`}
              onClick={() => setMode("recommend")}>
              <b>콕집에게 추천받기</b>
              <span>이 조건의 매물을 가진 사무소로 자동 선택</span>
            </button>
            <button className={`kreq-mode ${mode === "choose" ? "on" : ""}`}
              onClick={() => setMode("choose")}>
              <b>직접 고르기</b>
              <span>목록에서 원하는 곳만 선택</span>
            </button>
          </div>

          {mode === "recommend" ? (
            <>
              <div className="kreq-lbl">몇 곳에 보낼까요?</div>
              <div className="kreq-chips">
                {[3, 5, 7, 10].map((n) => (
                  <button key={n} className={`kreq-chip ${count === n ? "on" : ""}`}
                    onClick={() => setCount(n)}>{n}곳</button>
                ))}
              </div>
              <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
                정하지 않으시면 3곳입니다. 많이 보낼수록 연락도 많이 옵니다.
                <b> 받는 곳은 다음 화면에서 확인하실 수 있어요.</b>
              </p>
            </>
          ) : cands.length === 0 ? (
            <p className="muted">이 조건의 매물을 가진 사무소를 찾지 못했어요. 추천받기를 이용해 보세요.</p>
          ) : (
            <>
              <ul className="kreq-cands">
                {cands.map((c) => {
                  const on = picked.includes(c.realtor_id);
                  return (
                    <li key={c.realtor_id}>
                      <button type="button" className={`kreq-cand ${on ? "on" : ""}`}
                        onClick={() => setPicked((v) => (
                          on ? v.filter((x) => x !== c.realtor_id) : [...v, c.realtor_id].slice(0, 10)))}>
                        <span className={`kreq-box ${on ? "on" : ""}`}>
                          {on && <Check size={13} strokeWidth={3.2} />}
                        </span>
                        <span className="kreq-cand-b">
                          <b>{c.name}</b>
                          <em>{c.matched
                            ? `이 조건 매물 ${c.listings.toLocaleString()}건 보유`
                            : `매물 ${c.listings.toLocaleString()}건`}</em>
                          {c.address && <i>{c.address}</i>}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
                {picked.length}곳 선택됨 (최대 10곳)
              </div>
            </>
          )}
        </div>
      )}

      {step === 3 && (
        <>
          <div className="kreq-card">
            <div className="kreq-step">이렇게 보낼게요</div>
            <div className="kreq-sum">
              <div><span>지역</span><b>{regionName || "-"}</b></div>
              <div><span>유형·거래</span><b>{label(ASSETS, asset)} · {label(TRADES, trade)}</b></div>
              {areaTxt && <div><span>면적</span><b>{areaTxt}</b></div>}
              {budgetTxt && <div><span>예산</span><b>{budgetTxt}</b></div>}
              {memo && <div><span>메모</span><b>{memo}</b></div>}
            </div>
            <div className="kreq-lbl">받는 곳 {targets.length}곳</div>
            <ul className="kreq-offices">
              {targets.map((c) => (
                <li key={c.realtor_id}>
                  <Building2 size={15} />
                  <span>{c.name}{c.matched ? ` · 이 조건 매물 ${c.listings.toLocaleString()}건` : ""}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="kreq-card">
            <div className="kreq-step">연락받을 번호를 확인해 주세요</div>
            {!token ? (
              <>
                <p className="muted">
                  중개사무소가 연락드릴 번호를 확인해야 해서 여기서만 로그인이 필요합니다.
                  적어 두신 조건은 그대로 유지됩니다.
                </p>
                <div className="kreq-row">
                  <button className="kreq-primary" onClick={loginKakao}>카카오로 계속하기</button>
                  <button className="kreq-ghost" onClick={loginGoogle}>구글로 계속하기</button>
                </div>
              </>
            ) : phoneOK ? (
              <p className="kreq-ok"><Check size={16} strokeWidth={2.6} /> 휴대폰 인증이 끝났습니다.</p>
            ) : (
              <>
                <p className="muted">중개사무소가 연락드릴 번호입니다. 본인 명의 휴대폰으로 인증해 주세요.</p>
                <button className="kreq-primary" onClick={() => setPhoneOpen(true)}>
                  <Phone size={15} strokeWidth={2.4} /> 휴대폰 인증하기
                </button>
              </>
            )}

            <div className="kreq-consent">
              <div className="kreq-consent-h">
                <ShieldCheck size={16} strokeWidth={2.4} /> 무엇이 전달되나요 <span>(확인 필요)</span>
              </div>
              <div className="kreq-consent-b">
                <div className="kreq-safe">
                  <b>내 이름과 전화번호는 전달되지 않습니다.</b>
                  중개사무소에는 <b>조건만</b> 갑니다.
                </div>
                <div><b>전달되는 곳</b> — {targets.length ? targets.map((t) => t.name).join(", ") : "선택한 중개사무소"}</div>
                <div><b>전달 내용</b> — 지역 · 유형 · 거래 · 면적 · 예산 · 요청 메모</div>
                <div><b>그다음</b> — 중개사무소가 매물과 자기 연락처를 제안으로 남기면,
                  확인하시고 <b>마음에 드는 곳에 직접 전화</b>하시면 됩니다.</div>
                <div className="kreq-consent-note">
                  인증하신 번호는 콕집이 보관하며 <b>제안 도착 알림에만</b> 씁니다.
                  요청은 언제든 삭제 요청하실 수 있습니다.
                </div>
              </div>
              <label className="kreq-agree">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                <span>위 내용을 확인했고, <b>조건이 전달되는 것</b>에 동의합니다.</span>
              </label>
            </div>
          </div>
          {err && <div className="kreq-err">{err}</div>}
        </>
      )}

      <div className="kreq-nav">
        {step > 0 && (
          <button className="kreq-ghost" onClick={() => setStep((s) => s - 1)}>
            <ChevronLeft size={15} /> 이전
          </button>
        )}
        {step < 3 ? (
          <button className="kreq-submit" disabled={!canNext} onClick={() => setStep((s) => s + 1)}>
            {step === 0 && !sigungu ? "지역을 선택해 주세요"
              : step === 2 && targets.length === 0 ? "받는 곳을 선택해 주세요" : "다음"}
          </button>
        ) : (
          <button className="kreq-submit" disabled={!canSend} onClick={submit}>
            {busy ? "보내는 중…"
              : !token ? "로그인 후 보낼 수 있어요"
              : !phoneOK ? "휴대폰 인증이 필요해요"
              : !consent ? "동의에 체크해 주세요"
              : `${targets.length}곳에 요청 보내기`}
          </button>
        )}
      </div>

      {phoneOpen && token && (
        <PhoneModal token={token} onClose={() => setPhoneOpen(false)}
          onDone={() => { setPhoneOK(true); setPhoneOpen(false); }} />
      )}
      <p className="muted" style={{ fontSize: 12, marginTop: 14, lineHeight: 1.6 }}>
        콕집은 중개 계약의 당사자가 아니며, 조건에 맞는 중개사무소를 연결해 드리는 역할만 합니다.
        실제 거래 조건과 매물 상태는 해당 중개사무소에서 직접 확인하세요. 이용료는 없습니다.
      </p>
    </div>
  );
}
