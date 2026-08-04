import { useEffect, useRef, useState, ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MapPin, SendHorizonal, ShieldCheck } from "lucide-react";
import { useAuth } from "../auth";
import { PhoneModal } from "../components/PhoneVerify";
import { LevelBadge } from "../components/LevelBadge";
import ShareInline from "../components/ShareInline";
import { visitorHeader } from "../lib/visitor";

const API_BASE = import.meta.env.VITE_API_BASE;

// 화면에 남겨 두는 최근 문답 수. 답변 하나가 길어서 이보다 많으면 들어오자마자
// 과거 대화가 화면을 가득 채운다 — 저장·복원·서버시드 모두 같은 값을 쓴다.
const KEEP_TURNS = 10;

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

/** 매물을 찾는 질문일 때만 콕집요청을 권한다(통계·용어 질문엔 붙이지 않는다). */
function wantsListing(q: string): boolean {
  const t = (q || "").replace(/\s/g, "");
  if (!t) return false;
  // 집을 찾는 이야기면 권한다. 예전엔 '평균·시세'까지 막았는데
  // "서초동 아파트 평균가" 같은 정상 질문까지 빠져서 세금·용어 질문만 걸러내도록 좁혔다.
  // '가격·얼마·호가'가 빠져 있어 "잠실 파크리오 가격 알려줘"에 안내가 안 붙었다(실측).
  const want = /(매물|집|아파트|오피스텔|빌라|원룸|단독|상가|사무실|전세|월세|매매|급매|시세|가격|호가|얼마|평형|평대|추천|찾아|구해|알아보|보고싶|살까|사고싶)/;
  const block = /(취득세|양도세|보유세|종부세|재산세|세금|계산기|얼마나오|뜻이|이란무엇|의미가|거래량|통계|추이가)/;
  return want.test(t) && !block.test(t);
}

/** 물음표·군말을 걷어낸 짧은 조건 문구 — 버튼 문구에 그대로 인용한다. */
function shortQ(q: string): string {
  const t = (q || "").trim()
    .replace(/[?？!.]+$/g, "")
    .replace(/(알려줘|알려주세요|찾아줘|찾아주세요|추천해줘|추천해주세요|보여줘|보여주세요|어때|어떄|얼마야|얼마인가요|있나요|있어)\s*$/g, "")
    .trim();
  return t.length > 24 ? `${t.slice(0, 24)}…` : t;
}

// 카카오톡처럼 '누가 말했는지'를 프로필로 보여준다 — 데이터만 나열하면 딱딱해서,
// 얼굴을 붙여 두면 같은 답도 훨씬 친근하게 읽힌다.
const AI_NAME = "콕집이";

function AiSaid({ children }: { children: ReactNode }) {
  return (
    <div className="ai-said">
      <img className="ai-avatar" src="/ai-avatar.png" alt="" width={40} height={40} loading="lazy" />
      <div className="ai-said-body">
        <div className="ai-said-name">{AI_NAME}</div>
        {children}
      </div>
    </div>
  );
}

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
          <AiSaid>
            <div className="ai-a ai-loading">
              <span className="ai-spin" />
              <span className="ai-loading-text">
                {t.status || "처리 중…"}
                {secs >= 3 && (
                  <span className="ai-loading-hint">{hint} · {secs}초</span>
                )}
              </span>
            </div>
          </AiSaid>
        )}
        {t.error && <AiSaid><div className="ai-a ai-err">오류: {t.error}</div></AiSaid>}
        {t.answer && (
          <AiSaid>
          <div className="ai-a">
            {renderMd(t.answer)}
            {isAdmin && t.tools && t.tools.length > 0 && (
              <div className="ai-meta">
                조회: {t.tools.map((x) => x.tool).join(", ")}
                {t.usage?.total_tokens ? ` · ${t.usage.total_tokens} tokens` : ""}
              </div>
            )}
          </div>
          </AiSaid>
        )}
      </div>
      {t.answer && wantsListing(t.q) && !t.answer.includes("/request") && (
        <div className="ai-req no-capture">
          <div>
            <b>「{shortQ(t.q)}」 조건으로 콕집요청 보내보시겠어요?</b>
            <span>이 조건 그대로 그 동네 중개사무소에 전달돼요. 맞는 매물이 있으면 연락이 옵니다.</span>
          </div>
          <a className="ai-req-btn" href={`/request?q=${encodeURIComponent(t.q)}`}>콕집요청 보내기</a>
        </div>
      )}
      {t.answer && (
        <div className="ai-share no-capture">
          <ShareInline targetRef={ref} title={t.q} fileName="콕집_AI답변" />
        </div>
      )}
      {children}
    </div>
  );
}

export default function AiChat() {
  const { user, token, refreshMe, isAdmin } = useAuth();
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
  const jumpedRef = useRef(false);   // 최신 대화로 한 번만 내려가게(이후엔 사용자 스크롤 존중)

  // AI는 로그인 없이 누구나 이용 가능하고 포인트도 들지 않는다.
  // 제한은 서버가 방문자별 하루 50건으로 건다(폭주 방지는 별도 연타·동시 상한).
  const needLogin = false;
  const needVerify = false;  // 전화인증 게이트 해제
  const gated = false;
  const [quota, setQuota] = useState<{ used: number; limit: number; remaining: number } | null>(null);

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

  // 오늘 남은 질문 수 — 로그인 상태가 바뀌면 기준(계정↔방문자ID)이 달라져 다시 읽는다
  useEffect(() => {
    if (!API_BASE) return;
    let alive = true;
    fetch(`${API_BASE}/ai/quota`, {
      headers: { ...visitorHeader(), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    })
      .then((r) => r.json())
      .then((d) => { if (alive && typeof d?.remaining === "number") setQuota(d); })
      .catch(() => {});
    return () => { alive = false; };
  }, [token]);

  // (1) 복원: localStorage 우선(즉시) — 페이지 이동 후 돌아오거나 앱 재실행 시 대화 유지
  useEffect(() => {
    if (!histKey || restoredKeyRef.current === histKey) return;
    restoredKeyRef.current = histKey;
    try {
      const raw = localStorage.getItem(histKey);
      const arr = raw ? JSON.parse(raw) : null;
      setTurns(Array.isArray(arr) ? arr.slice(-KEEP_TURNS) : []);
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
    fetch(`${API_BASE}/ai/history?limit=${KEEP_TURNS}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d: { items?: Turn[] }) => {
        if (d.items && d.items.length) {
          const recent = d.items.slice(-KEEP_TURNS);
          setTurns(recent);
          try { localStorage.setItem(histKey, JSON.stringify(recent)); } catch { /* */ }
        }
      })
      .catch(() => {});
  }, [histKey, token]);

  // 저장: 완료된 턴만(로딩/스트리밍 중 제외), 최근 10개
  useEffect(() => {
    if (!histKey) return;
    const done = turns.filter((t) => !t.loading && (t.answer || t.error)).slice(-KEEP_TURNS);
    try {
      if (done.length) localStorage.setItem(histKey, JSON.stringify(done));
    } catch { /* 용량초과 등 무시 */ }
  }, [turns, histKey]);

  // 들어오자마자 '가장 최근 대화'가 보이게 맨 아래로. 복원된 첫 렌더에서 한 번만,
  // 애니메이션 없이(auto) 내려야 과거 대화가 스쳐 지나가는 느낌이 안 난다.
  useEffect(() => {
    if (jumpedRef.current || !turns.length) return;
    jumpedRef.current = true;
    // 답변 본문·이미지가 자리를 잡은 뒤라야 실제 바닥이 계산된다
    requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: 1e9, behavior: "auto" }));
  }, [turns.length]);

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
    // 새 문답을 붙이면서 오래된 것은 떨군다 — 화면엔 항상 최근 10개만 남는다
    setTurns((t) => [...t, { q, loading: true, status: "질문 분석 중…" }].slice(-KEEP_TURNS));
    const patchLast = (patch: Partial<Turn>) =>
      setTurns((t) => t.map((x, i) => i === t.length - 1 ? { ...x, ...patch } : x));
    try {
      const r = await fetch(`${API_BASE}/ai/ask-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...visitorHeader(),
                   ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ q, history }),
      });
      // 429 = 이용 제한(하루 50건·연타·동시). 서버 메시지를 그대로 보여준다.
      if (r.status === 429 || r.status === 401 || r.status === 403 || r.status === 402) {
        const dj = await r.json().catch(() => ({}));
        const detailMsg = typeof dj?.detail === "object" ? dj.detail?.message : null;
        patchLast({ loading: false, status: undefined,
          error: detailMsg || (r.status === 429 ? "잠시 후 다시 시도해 주세요." : "이용할 수 없어요.") });
        if (r.status === 429 && typeof dj?.detail === "object" && dj.detail?.code === "ai_daily_limit") {
          setQuota((p) => p ? { ...p, used: p.limit, remaining: 0 } : p);
        }
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
          let ev: { type: string; label?: string; answer?: string; tools_used?: Turn["tools"]; usage?: Turn["usage"]; error?: string; remaining?: number };
          try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
          if (ev.type === "status") patchLast({ status: ev.label });
          else if (ev.type === "done") {
            patchLast({ loading: false, status: undefined, answer: ev.answer, tools: ev.tools_used, usage: ev.usage });
            if (typeof ev.remaining === "number") {
              const rem = ev.remaining;
              setQuota((p) => p ? { ...p, remaining: rem, used: p.limit - rem } : p);
            }
            refreshMe();
          }
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
            <img className="ai-hero-char" src="/ai-character.png" alt="콕집이" width={132} height={186} />
            <h2 className="ai-hero-title">안녕하세요, {AI_NAME}예요</h2>
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
          <div className="ai-points-row">
            <span style={{ display: "inline-flex", alignItems: "center" }}>
              {user
                ? (isAdmin
                    ? <span className="admin-badge">관리자</span>
                    : <LevelBadge level={user.level ?? 0} rank={user.rank} />)
                : null}
              {quota
                ? <>오늘 남은 질문 <b style={{ marginLeft: 4 }}>{quota.remaining}회</b></>
                : <>로그인 없이 바로 물어보세요</>}
            </span>
            <span className="muted">
              {quota ? `하루 ${quota.limit}회 · 무료` : "무료"}
            </span>
          </div>
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
