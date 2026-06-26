import { useEffect, useRef, useState, ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles, MapPin, SendHorizonal, Lock, ShieldCheck } from "lucide-react";
import { useAuth, loginKakao, loginGoogle } from "../auth";
import { PhoneModal } from "../components/PhoneVerify";
import { LevelBadge } from "../components/LevelBadge";
import ShareBar from "../components/ShareBar";

const API_BASE = import.meta.env.VITE_API_BASE;

type Turn = {
  q: string;
  answer?: string;
  tools?: { tool: string; args: Record<string, unknown> }[];
  usage?: { total_tokens?: number };
  error?: string;
  loading?: boolean;
  status?: string;   // 진행 단계 라벨 (스트리밍 중)
};

// 지역 미탐지 시 fallback — 특정 도시를 박지 않은 전국 단위 예시.
// 접속 지역이 잡히면 /ai/region 의 지역화 예시(geoExamples)가 우선 사용된다.
const EXAMPLES = [
  "최근 신고가 단지 보여줘",
  "요즘 거래 활발한 지역 알려줘",
  "이번 달 취소된 거래 보여줘",
  "전세가율 높은 단지 알려줘",
];

// 가벼운 마크다운 렌더 (굵게 + 링크 + 불릿 + 문단). 외부 라이브러리 없음.
// [텍스트](/경로) → SPA 내부 링크(Link), [텍스트](http..) → 새 탭.
function inline(s: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*)|(\[[^\]]+\]\([^)]+\))/g;
  let last = 0, k = 0;
  let mt: RegExpExecArray | null;
  while ((mt = re.exec(s)) !== null) {
    if (mt.index > last) out.push(<span key={k++}>{s.slice(last, mt.index)}</span>);
    const tok = mt[0];
    if (tok.startsWith("**")) {
      out.push(<strong key={k++}>{tok.slice(2, -2)}</strong>);
    } else {
      const m = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok);
      const text = m ? m[1] : tok, url = m ? m[2] : "#";
      // 행 전체 클릭(Bullet)과 겹치지 않게 stopPropagation — 보조 링크(예: 중개사)는 자기 경로로.
      const stop = (e: React.MouseEvent) => e.stopPropagation();
      if (url.startsWith("/")) out.push(<Link key={k++} to={url} className="ai-link" onClick={stop}>{text}</Link>);
      else out.push(<a key={k++} href={url} target="_blank" rel="noreferrer" className="ai-link" onClick={stop}>{text}</a>);
    }
    last = re.lastIndex;
  }
  if (last < s.length) out.push(<span key={k++}>{s.slice(last)}</span>);
  return out;
}
// 목록 한 줄에 들어있는 첫 내부 경로(단지/중개사 등) — 그 줄 전체를 탭하면 여기로 이동.
function firstInternalLink(s: string): string | null {
  const m = /\]\((\/[^)]+)\)/.exec(s);
  return m ? m[1] : null;
}
// 목록 항목: 단지/중개사 링크가 있으면 줄 전체를 클릭 가능하게(이름을 눌러도 이동). 모바일 탭 타깃 확대.
function Bullet({ text }: { text: string }) {
  const navigate = useNavigate();
  const path = firstInternalLink(text);
  return (
    <li
      className={path ? "ai-li-go" : undefined}
      onClick={path ? () => navigate(path) : undefined}
      role={path ? "link" : undefined}
    >
      {inline(text)}
    </li>
  );
}
function renderMd(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      out.push(<ul key={`u${out.length}`} className="ai-ul">{bullets.map((b, i) => <Bullet key={i} text={b} />)}</ul>);
      bullets = [];
    }
  };
  text.split("\n").forEach((ln, idx) => {
    const t = ln.trim();
    if (/^[*-]\s+/.test(t)) bullets.push(t.replace(/^[*-]\s+/, ""));
    else { flush(); if (t) out.push(<p key={`p${idx}`} className="ai-p">{inline(t)}</p>); }
  });
  flush();
  return out;
}

// 느린 응답에도 '충분히 알아보는 중'이 느껴지도록 순환 안내문(경과에 따라 진행).
const LOADING_HINTS = [
  "전국 실거래·매물 데이터를 살펴보는 중이에요",
  "조건에 맞는 단지를 하나씩 추리는 중이에요",
  "여러 단지를 비교하고 정렬하는 중이에요",
  "최신 시세·신고가와 대조하는 중이에요",
  "거의 다 됐어요. 답변을 정리하는 중이에요",
];

// 한 문답(질문+답변) 블록 — 자체 ref로 감싸 공유(이미지/카카오/URL) 가능. 추천칩 등은 children.
function AiTurn({ t, children }: { t: Turn; children?: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const { isAdmin } = useAuth();
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    if (!t.loading) { setSecs(0); return; }
    const id = window.setInterval(() => setSecs((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [t.loading]);
  const hint = LOADING_HINTS[Math.min(LOADING_HINTS.length - 1, Math.floor(secs / 3))];
  return (
    <div className="ai-turn">
      <div ref={ref} className="share-target">
        <div className="ai-q">{t.q}</div>
        {t.loading && (
          <div className="ai-a ai-loading">
            <span className="ai-spin" />
            <span className="ai-loading-text">
              {t.status || "처리 중…"}
              {secs >= 3 && (
                <span className="ai-loading-hint">{hint} · {secs}초</span>
              )}
            </span>
          </div>
        )}
        {t.error && <div className="ai-a ai-err">오류: {t.error}</div>}
        {t.answer && (
          <div className="ai-a">
            {renderMd(t.answer)}
            {isAdmin && t.tools && t.tools.length > 0 && (
              <div className="ai-meta">
                조회: {t.tools.map((x) => x.tool).join(", ")}
                {t.usage?.total_tokens ? ` · ${t.usage.total_tokens} tokens` : ""}
              </div>
            )}
          </div>
        )}
      </div>
      {t.answer && (
        <div className="ai-share no-capture">
          <ShareBar targetRef={ref} title={t.q} fileName="콕집_AI답변" />
        </div>
      )}
      {children}
    </div>
  );
}

export default function AiChat() {
  const { user, token, ready, configured, refreshMe, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [region, setRegion] = useState<string | null>(null);
  const [geoExamples, setGeoExamples] = useState<string[] | null>(null);
  const [verifyOpen, setVerifyOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // 대화 복원/저장 — 사용자별 키(공용 기기에서 타인 대화 노출 방지)
  const histKey = user ? `koczip_ai_turns:${user.id}` : null;
  const restoredKeyRef = useRef<string | null>(null);
  const seededKeyRef = useRef<string | null>(null);

  // AI는 로그인만 하면 이용 가능(전화인증 불필요). 포인트로 사용 제한.
  const needLogin = configured && ready && !user;
  const needVerify = false;  // 전화인증 게이트 해제 — 누구나 로그인 후 체험 가능
  const gated = needLogin;

  // 접속 IP 지역 → 지역 맞춤 추천질문 (geo-IP, LLM 호출 없음)
  useEffect(() => {
    if (!API_BASE) return;
    let alive = true;
    fetch(`${API_BASE}/ai/region`)
      .then((r) => r.json())
      .then((d: { region: string | null; examples: string[] | null }) => {
        if (!alive) return;
        if (d.region) setRegion(d.region);
        if (d.examples && d.examples.length) setGeoExamples(d.examples);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  // (1) 복원: localStorage 우선(즉시) — 페이지 이동 후 돌아오거나 앱 재실행 시 대화 유지
  useEffect(() => {
    if (!histKey || restoredKeyRef.current === histKey) return;
    restoredKeyRef.current = histKey;
    try {
      const raw = localStorage.getItem(histKey);
      const arr = raw ? JSON.parse(raw) : null;
      setTurns(Array.isArray(arr) ? arr : []);
    } catch { setTurns([]); }
  }, [histKey]);

  // (2) 서버 시드: 로컬에 없을 때만(/ai/history) — 재로그인·다른 기기에서도 과거 답 복원
  useEffect(() => {
    if (!histKey || !token || !API_BASE) return;
    if (seededKeyRef.current === histKey) return;
    seededKeyRef.current = histKey;
    let hasLocal = false;
    try { hasLocal = !!localStorage.getItem(histKey); } catch { /* */ }
    if (hasLocal) return;
    fetch(`${API_BASE}/ai/history?limit=30`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d: { items?: Turn[] }) => {
        if (d.items && d.items.length) {
          setTurns(d.items);
          try { localStorage.setItem(histKey, JSON.stringify(d.items)); } catch { /* */ }
        }
      })
      .catch(() => {});
  }, [histKey, token]);

  // 저장: 완료된 턴만(로딩/스트리밍 중 제외), 최근 30개
  useEffect(() => {
    if (!histKey) return;
    const done = turns.filter((t) => !t.loading && (t.answer || t.error)).slice(-30);
    try {
      if (done.length) localStorage.setItem(histKey, JSON.stringify(done));
    } catch { /* 용량초과 등 무시 */ }
  }, [turns, histKey]);

  const examples = geoExamples ?? EXAMPLES;

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    if (!API_BASE) { setTurns((t) => [...t, { q, error: "로컬 API 미설정 — 이 기능은 로컬에서만 동작합니다." }]); return; }
    // 게이트: 미로그인/미인증이면 질의 대신 인증 유도
    if (needVerify) { setVerifyOpen(true); return; }
    if (needLogin) return;  // 로그인 카드가 노출되어 있음
    // 직전까지 완료된 턴을 멀티턴 맥락으로 전달
    const history = turns.flatMap((t) =>
      t.answer ? [{ role: "user", text: t.q }, { role: "model", text: t.answer }] : []);
    setInput("");
    setBusy(true);
    setTurns((t) => [...t, { q, loading: true, status: "질문 분석 중…" }]);
    const patchLast = (patch: Partial<Turn>) =>
      setTurns((t) => t.map((x, i) => i === t.length - 1 ? { ...x, ...patch } : x));
    try {
      const r = await fetch(`${API_BASE}/ai/ask-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ q, history }),
      });
      if (r.status === 401 || r.status === 403 || r.status === 402) {
        const dj = await r.json().catch(() => ({}));
        const detailMsg = typeof dj?.detail === "object" ? dj.detail?.message : null;
        patchLast({ loading: false, status: undefined,
          error: r.status === 402 ? (detailMsg || "포인트가 부족해요.")
            : r.status === 401 ? "로그인이 필요합니다." : "전화번호 인증 후 이용할 수 있어요." });
        if (r.status === 403) setVerifyOpen(true);
        return;
      }
      if (!r.ok || !r.body) {
        const txt = r.body ? await r.text() : "";
        throw new Error(`${r.status} ${txt.slice(0, 200)}`);
      }
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      // SSE 파싱: "data: {...}\n\n"
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const chunks = buf.split("\n\n");
        buf = chunks.pop() ?? "";
        for (const c of chunks) {
          const line = c.trim();
          if (!line.startsWith("data:")) continue;
          let ev: { type: string; label?: string; answer?: string; tools_used?: Turn["tools"]; usage?: Turn["usage"]; error?: string; points?: number };
          try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
          if (ev.type === "status") patchLast({ status: ev.label });
          else if (ev.type === "done") { patchLast({ loading: false, status: undefined, answer: ev.answer, tools: ev.tools_used, usage: ev.usage }); refreshMe(); }
          else if (ev.type === "error") patchLast({ loading: false, status: undefined, error: ev.error });
          setTimeout(() => scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }), 20);
        }
      }
    } catch (e) {
      patchLast({ loading: false, status: undefined, error: String(e) });
    } finally {
      setBusy(false);
      setTimeout(() => scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }), 50);
    }
  };

  return (
    <>
      <div className="ai-wrap" ref={scrollRef}>
        {turns.length === 0 && (
          <div className="ai-hero">
            <div className="ai-hero-badge"><Sparkles size={20} strokeWidth={2.2} /></div>
            <h2 className="ai-hero-title">콕집 AI에게 물어보세요</h2>
            <p className="ai-hero-sub">
              매일 갱신되는 전국 매물 · 실거래 · 중개사 데이터를 분석해 바로 답해드려요
            </p>
            {region && (
              <p className="ai-region-greet">
                <MapPin size={14} strokeWidth={2.4} aria-hidden /> <b>{region}</b>에서 접속하셨군요? 이 지역 부동산부터 알아보세요
              </p>
            )}
            <div className="ai-chips">
              {examples.map((ex) => (
                <button key={ex} className="ai-chip" onClick={() => ask(ex)}>{ex}</button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <AiTurn key={i} t={t}>
            {/* 도구를 안 쓴 답변(엉뚱한 질문·거절 등)엔 클릭형 추천 질문 제공 */}
            {t.answer && (!t.tools || t.tools.length === 0) && (
              <div className="ai-suggest no-capture">
                <span className="muted" style={{ fontSize: 12, display: "inline-flex", alignItems: "center", gap: 4 }}>
                  {region ? <><MapPin size={11} strokeWidth={2.4} /> {region}에서 접속하셨네요 — 이렇게 물어보세요</> : "이런 걸 물어보세요"}
                </span>
                <div className="ai-chips" style={{ justifyContent: "flex-start" }}>
                  {examples.map((ex) => (
                    <button key={ex} className="ai-chip" onClick={() => ask(ex)}>{ex}</button>
                  ))}
                </div>
              </div>
            )}
          </AiTurn>
        ))}
      </div>

      {needLogin && (
        <div className="ai-gate">
          <div className="ai-gate-ic"><Lock size={20} strokeWidth={2.2} /></div>
          <div className="ai-gate-t">AI 질문은 로그인이 필요해요</div>
          <div className="ai-gate-sub">실거래·급매 조회는 로그인 없이 이용할 수 있어요. AI 질문만 가입이 필요해요.</div>
          <div className="ai-gate-btns">
            <button className="auth-btn kakao" onClick={() => loginKakao()}>
              <svg className="kakao-icon" aria-hidden width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 3C6.48 3 2 6.36 2 10.5c0 2.66 1.8 5 4.51 6.32-.15.52-.97 3.36-1 3.59 0 0-.02.17.09.24.11.07.24.02.24.02.32-.05 3.74-2.45 4.33-2.87.59.08 1.2.13 1.83.13 5.52 0 10-3.36 10-7.5S17.52 3 12 3z" />
              </svg>
              카카오로 시작
            </button>
            <button className="auth-btn google" onClick={() => loginGoogle()}>
              <svg className="google-icon" aria-hidden width="14" height="14" viewBox="0 0 48 48">
                <path fill="#4285F4" d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z"/>
                <path fill="#34A853" d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z"/>
                <path fill="#FBBC05" d="M11.69 28.18C11.25 26.86 11 25.45 11 24s.25-2.86.69-4.18v-5.7H4.34A21.99 21.99 0 0 0 2 24c0 3.55.85 6.91 2.34 9.88l7.35-5.7z"/>
                <path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z"/>
              </svg>
              구글로 시작
            </button>
          </div>
          <button className="ai-gate-skip" onClick={() => navigate("/")}>로그인 없이 둘러보기 →</button>
        </div>
      )}
      {needVerify && (
        <div className="ai-gate">
          <div className="ai-gate-ic verify"><ShieldCheck size={20} strokeWidth={2.2} /></div>
          <div className="ai-gate-t">전화번호 인증이 필요해요</div>
          <div className="ai-gate-sub">AI 서비스는 전화번호 인증 후 이용할 수 있어요. 1분이면 끝나요.</div>
          <div className="ai-gate-btns">
            <button className="auth-btn kakao" onClick={() => setVerifyOpen(true)}>전화번호 인증하기</button>
          </div>
        </div>
      )}

      {!gated && (
        <>
          {user && (
            <div className="ai-points-row">
              <span style={{ display: "inline-flex", alignItems: "center" }}>
                {isAdmin
                  ? <span className="admin-badge">관리자</span>
                  : <LevelBadge level={user.level ?? 0} rank={user.rank} />}
                보유 <b style={{ marginLeft: 4 }}>{(user.points ?? 0).toLocaleString()}P</b>
              </span>
              <span className="muted">질문 1회 {user.aiCost ?? 10}P</span>
            </div>
          )}
          <div className="ai-input-row">
            <input
              className="ai-input"
              value={input}
              placeholder={`예: ${region ? `${region} 급매 찾아줘` : "관심 지역 급매 찾아줘"}`}
              maxLength={500}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") ask(input); }}
              disabled={busy}
            />
            <button className="ai-send" onClick={() => ask(input)} disabled={busy || !input.trim()}>
              {busy ? "…" : <><SendHorizonal size={15} strokeWidth={2.2} /> 보내기</>}
            </button>
          </div>
          <p className="muted" style={{ fontSize: 11, marginTop: 6 }}>
            AI도 실수할 수 있습니다. 해당 답변은 참고용입니다. 거래 전 현장 확인 필수입니다.
          </p>
        </>
      )}

      {verifyOpen && token && (
        <PhoneModal
          token={token}
          onClose={() => setVerifyOpen(false)}
          onDone={async () => { await refreshMe(); setVerifyOpen(false); }}
        />
      )}
    </>
  );
}
