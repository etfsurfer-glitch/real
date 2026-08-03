import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Building2, Check, Info, Phone, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth, loginKakao, loginGoogle } from "../auth";
import { PhoneModal } from "../components/PhoneVerify";
import { RegionSelect, useRegionFilter } from "../components/RegionSelect";

const API = import.meta.env.VITE_API_BASE;

type Cand = { realtor_id: string; name: string; address: string | null;
              representative: string | null; listings: number };

const ASSETS = [["apt", "아파트"], ["offi", "오피스텔"], ["villa", "빌라·연립"],
                ["house", "단독·다가구"], ["comm", "상가·사무실"]] as const;
const TRADES = [["A1", "매매"], ["B1", "전세"], ["B2", "월세"]] as const;

/** 콕집요청 — 손님이 조건을 남기면 그 동네 중개사무소로 전달한다.
 *  개인정보(이름·전화)가 제3자에게 넘어가므로, 받는 곳을 화면에 그대로 보여주고
 *  동의를 받은 뒤에만 보낸다. */
export default function KoczipRequest() {
  const { token } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();

  const reg = useRegionFilter();                 // 사이트 공통 지역 선택(기억됨)
  const { sido, sigungu, dong } = reg;
  const regionName = useMemo(() => [
    reg.sidos.find((x) => x.code === sido)?.name,
    reg.sigungus.find((x) => x.code === sigungu)?.name,
    reg.dongs.find((x) => x.code === dong)?.name,
  ].filter(Boolean).join(" "), [reg.sidos, reg.sigungus, reg.dongs, sido, sigungu, dong]);

  const [asset, setAsset] = useState(sp.get("asset") || "apt");
  const [trade, setTrade] = useState(sp.get("trade") || "A1");
  const [areaTxt, setAreaTxt] = useState(sp.get("area") || "");
  const [budgetTxt, setBudgetTxt] = useState("");
  const [prefill, setPrefill] = useState("");        // 무엇이 자동으로 채워졌는지 안내
  const [memo, setMemo] = useState("");
  const aiQuery = sp.get("q") || "";

  const [mode, setMode] = useState<"recommend" | "choose">("recommend");
  const [count, setCount] = useState(3);
  const [picked, setPicked] = useState<string[]>([]);
  const [cands, setCands] = useState<Cand[]>([]);
  const [phoneOK, setPhoneOK] = useState(false);
  const [phoneOpen, setPhoneOpen] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ sent_to: number; offices: { name: string }[] } | null>(null);
  const [err, setErr] = useState("");

  const authH = useCallback((): Record<string, string> =>
    (token ? { Authorization: `Bearer ${token}` } : {}), [token]);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/me`, { headers: authH() }).then((r) => r.json())
      .then((d) => setPhoneOK(!!d?.phone_verified)).catch(() => {});
  }, [token, authH]);

  // AI에 물어본 문장을 조건으로 풀어 채워 둔다 — 같은 내용을 두 번 입력하지 않게.
  useEffect(() => {
    if (!aiQuery) return;
    fetch(`${API}/requests/parse?q=${encodeURIComponent(aiQuery)}`)
      .then((r) => r.json())
      .then((d) => {
        const got: string[] = [];
        if (d.sido) { reg.setSido(d.sido.slice(0, 2)); got.push(d.region_name || "지역"); }
        if (d.sigungu) reg.setSigungu(d.sigungu.slice(0, 5));
        if (d.cortar) reg.setDong(d.cortar.slice(0, 10));
        if (d.asset) { setAsset(d.asset); got.push("유형"); }
        if (d.trade) { setTrade(d.trade); got.push("거래"); }
        if (d.area_txt) { setAreaTxt(d.area_txt); got.push(d.area_txt); }
        if (d.budget_txt) { setBudgetTxt(d.budget_txt); got.push(d.budget_txt); }
        if (got.length) setPrefill(got.join(" · "));
      })
      .catch(() => {});
  }, [aiQuery]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!sigungu) { setCands([]); return; }
    const q = dong ? `cortar=${dong.slice(0, 10)}&` : "";
    fetch(`${API}/requests/candidates?${q}sigungu=${sigungu.slice(0, 5)}&limit=20`)
      .then((r) => r.json()).then((d) => setCands(d.items || [])).catch(() => setCands([]));
  }, [sigungu, dong]);

  const targets = useMemo(() => (
    mode === "choose"
      ? cands.filter((c) => picked.includes(c.realtor_id))
      : cands.slice(0, count)
  ), [mode, picked, cands, count]);

  const ready = !!sigungu && targets.length > 0 && phoneOK && consent && !busy;

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API}/requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authH() },
        body: JSON.stringify({
          sido, sigungu, cortar: dong, region_name: regionName,
          asset, trade, area_txt: areaTxt, budget_txt: budgetTxt, memo, ai_query: aiQuery,
          pick_mode: mode, target_count: count,
          realtor_ids: mode === "choose" ? picked : [],
          consent: true,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail?.message || d?.detail || "요청을 보내지 못했어요");
      setDone(d);
    } catch (e: any) { setErr(e?.message || "요청을 보내지 못했어요"); }
    finally { setBusy(false); }
  };

  if (!token) {
    return (
      <div className="kreq">
        <h2><Sparkles size={20} strokeWidth={2.3} /> 콕집요청</h2>
        <div className="kreq-card kreq-center">
          <p className="kreq-lead">원하는 조건을 남기시면 그 동네 중개사무소에서 매물을 찾아 연락드려요.</p>
          <p className="muted">먼저 로그인해 주세요. 카카오·구글 계정으로 바로 시작할 수 있어요.</p>
          <div className="kreq-row" style={{ justifyContent: "center" }}>
            <button className="kreq-primary" onClick={loginKakao}>카카오로 시작하기</button>
            <button className="kreq-ghost" onClick={loginGoogle}>구글로 시작하기</button>
          </div>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="kreq">
        <h2><Check size={20} strokeWidth={2.6} /> 요청이 전달됐어요</h2>
        <div className="kreq-card">
          <p className="kreq-lead"><b>{done.sent_to}곳</b>의 중개사무소로 요청을 보냈어요.</p>
          <ul className="kreq-offices">
            {done.offices.map((o, i) => <li key={i}><Building2 size={15} /> {o.name}</li>)}
          </ul>
          <p className="muted" style={{ marginTop: 10 }}>
            조건에 맞는 매물이 있으면 인증하신 번호로 연락이 옵니다. 보통 하루 안에 연락이 와요.
          </p>
          <div className="kreq-row" style={{ marginTop: 14 }}>
            <button className="kreq-primary" onClick={() => nav("/me/requests")}>내 요청 보기</button>
            <button className="kreq-ghost" onClick={() => nav("/")}>홈으로</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="kreq">
      <h2><Sparkles size={20} strokeWidth={2.3} /> 콕집요청</h2>
      <p className="kreq-lead">
        원하는 조건을 남기시면 <b>그 동네 중개사무소</b>가 조건에 맞는 매물을 찾아 연락드려요.
        직접 발품 팔지 않아도 됩니다.
      </p>
      {aiQuery && (
        <div className="kreq-q">
          <Info size={14} />
          <div>
            AI에 물어보신 <b>「{aiQuery}」</b>
            {prefill && <div className="kreq-q-sub">{prefill} 을(를) 아래에 채워 뒀어요. 바꾸셔도 됩니다.</div>}
          </div>
        </div>
      )}

      {/* 1. 조건 */}
      <div className="kreq-card">
        <div className="kreq-step">1. 어떤 집을 찾으세요?</div>
        <div className="kreq-region"><RegionSelect {...reg} /></div>
        <div className="kreq-chips">
          {ASSETS.map(([k, l]) => (
            <button key={k} className={`kreq-chip ${asset === k ? "on" : ""}`}
              onClick={() => setAsset(k)}>{l}</button>
          ))}
        </div>
        <div className="kreq-chips">
          {TRADES.map(([k, l]) => (
            <button key={k} className={`kreq-chip ${trade === k ? "on" : ""}`}
              onClick={() => setTrade(k)}>{l}</button>
          ))}
        </div>
        <div className="kreq-grid2">
          <label>희망 면적
            <input value={areaTxt} onChange={(e) => setAreaTxt(e.target.value)}
              placeholder="예: 30평대" />
          </label>
          <label>예산
            <input value={budgetTxt} onChange={(e) => setBudgetTxt(e.target.value)}
              placeholder="예: 12억 이하 / 보증금 1억·월세 100" />
          </label>
        </div>
        <label className="kreq-full">더 하고 싶은 말 (선택)
          <textarea value={memo} onChange={(e) => setMemo(e.target.value)} rows={3}
            placeholder="예: 초등학교 가까운 곳, 6개월 뒤 입주 예정, 반려동물 있어요" />
        </label>
      </div>

      {/* 2. 받는 곳 */}
      <div className="kreq-card">
        <div className="kreq-step">2. 어디로 보낼까요?</div>
        <div className="kreq-modes">
          <button className={`kreq-mode ${mode === "recommend" ? "on" : ""}`}
            onClick={() => setMode("recommend")}>
            <b>콕집에게 추천받기</b>
            <span>그 동네에서 활발히 활동하는 곳으로 자동 선택</span>
          </button>
          <button className={`kreq-mode ${mode === "choose" ? "on" : ""}`}
            onClick={() => setMode("choose")}>
            <b>직접 고르기</b>
            <span>목록에서 원하는 곳만 선택</span>
          </button>
        </div>

        {mode === "recommend" && (
          <div className="kreq-count">
            <span>몇 곳에 보낼까요?</span>
            <div className="kreq-chips" style={{ margin: 0 }}>
              {[3, 5, 7, 10].map((n) => (
                <button key={n} className={`kreq-chip ${count === n ? "on" : ""}`}
                  onClick={() => setCount(n)}>{n}곳</button>
              ))}
            </div>
            <div className="muted" style={{ fontSize: 12.5 }}>
              정하지 않으시면 3곳으로 보냅니다. 많이 보낼수록 연락도 많이 옵니다.
            </div>
          </div>
        )}

        {!sigungu && <p className="muted">지역을 먼저 선택해 주세요.</p>}
        {sigungu && cands.length === 0 && <p className="muted">이 지역에서 연결할 중개사무소를 찾지 못했어요.</p>}

        {mode === "choose" ? (
          <ul className="kreq-cands">
            {cands.map((c) => (
              <li key={c.realtor_id}>
                <label>
                  <input type="checkbox" checked={picked.includes(c.realtor_id)}
                    onChange={(e) => setPicked((v) => (
                      e.target.checked ? [...v, c.realtor_id].slice(0, 10)
                                       : v.filter((x) => x !== c.realtor_id)))} />
                  <div>
                    <b>{c.name}</b>
                    <div className="muted">{c.address || ""}{c.listings ? ` · 매물 ${c.listings.toLocaleString()}건` : ""}</div>
                  </div>
                </label>
              </li>
            ))}
          </ul>
        ) : (
          <ul className="kreq-offices">
            {targets.map((c) => <li key={c.realtor_id}><Building2 size={15} /> {c.name}</li>)}
          </ul>
        )}
      </div>

      {/* 3. 본인 확인 + 동의 */}
      <div className="kreq-card">
        <div className="kreq-step">3. 연락받을 번호를 확인해 주세요</div>
        {phoneOK ? (
          <p className="kreq-ok"><Check size={16} strokeWidth={2.6} /> 휴대폰 인증이 끝났습니다.</p>
        ) : (
          <>
            <p className="muted">
              중개사무소가 연락드릴 번호입니다. 본인 명의 휴대폰으로 인증해 주세요.
            </p>
            <button className="kreq-primary" onClick={() => setPhoneOpen(true)}>
              <Phone size={15} strokeWidth={2.4} /> 휴대폰 인증하기
            </button>
          </>
        )}

        <div className="kreq-consent">
          <div className="kreq-consent-h"><ShieldCheck size={16} strokeWidth={2.4} /> 개인정보 제3자 제공 동의 <span>(필수)</span></div>
          <div className="kreq-consent-b">
            <div><b>제공받는 곳</b> — {targets.length ? targets.map((t) => t.name).join(", ") : "선택한 중개사무소"}</div>
            <div><b>제공 항목</b> — 이름, 휴대전화번호, 위에 적으신 조건</div>
            <div><b>이용 목적</b> — 조건에 맞는 매물 안내 및 상담 연락</div>
            <div><b>보유 기간</b> — 상담 종료 후 3개월 (삭제 요청 시 즉시 파기)</div>
            <div className="kreq-consent-note">
              <b>전달된 중개사무소와 콕집 관리자 외에는 연락처를 볼 수 없습니다.</b>
              동의를 거부하실 수 있으며, 거부하시면 중개사 연결만 되지 않습니다.
            </div>
          </div>
          <label className="kreq-agree">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            위 내용을 확인했고, 제 정보가 <b>선택한 중개사무소에만</b> 전달되는 것에 동의합니다.
          </label>
        </div>
      </div>

      {err && <div className="kreq-err">{err}</div>}
      <button className="kreq-submit" disabled={!ready} onClick={submit}>
        {busy ? "보내는 중…" : `${targets.length || 0}곳에 요청 보내기`}
      </button>
      {!ready && !busy && (
        <div className="muted" style={{ textAlign: "center", fontSize: 12.5, marginTop: 6 }}>
          {!sigungu ? "지역을 선택해 주세요"
            : targets.length === 0 ? "보낼 중개사무소를 선택해 주세요"
            : !phoneOK ? "휴대폰 인증이 필요해요" : "동의에 체크해 주세요"}
        </div>
      )}

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
