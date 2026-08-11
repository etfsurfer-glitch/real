// ══════════════════════════════════════════════════════════════════════════
// 카드뉴스 v2 — 원하는 카드 한 장을 골라 만든다
//
//   v1(/admin/cardnews)은 브라우저에서 html2canvas 로 그린다.
//   v2 는 nfind 박스의 헤드리스 크롬이 콕집 API·청약홈·LH·뉴스에서 재료를 모아
//   Gemini 로 카피를 쓰고 1080×1350 PNG 로 뽑는다.
//
//   선택지는 생성기의 카탈로그(lib/catalog.js)를 그대로 받아 그린다 —
//   카드 종류를 늘려도 이 파일은 손댈 필요가 없다.
//
//   스타일은 프로젝트 관례대로 컴포넌트 하단 css 블록 + styles.css 토큰을 쓴다
//   (이 프로젝트에 Tailwind 는 없다).
// ══════════════════════════════════════════════════════════════════════════
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle, Building2, CalendarDays, Check, Copy, Download, FileImage,
  Flame, Gift, Home, Images, Loader2, Newspaper, Play, RefreshCw, Ruler,
  ScrollText, TrendingUp,
} from "lucide-react";
import { useAuth } from "../auth";
import { useRegionFilter } from "../components/RegionSelect";

const API_BASE = import.meta.env.VITE_API_BASE;

type Choice = { value: string; label: string };
type Option = {
  key: string;
  type: "region" | "select" | "number";
  label: string;
  hint?: string;
  default?: string | number;
  min?: number;
  max?: number;
  choices?: Choice[];
};
type CardSpec = { key: string; label: string; desc: string; format: string; options: Option[] };
type Run = { folder: string; createdAt: string; headline: string; status: string; slideCount: number };
type CardFile = { index: number; type?: string; title?: string; file: string };
type Manifest = {
  slides?: CardFile[];
  files?: CardFile[];
  caption?: string;
  hashtags?: string[];
  headline?: string;
  cardLabel?: string;
};

const cardsOf = (m: Manifest | null): CardFile[] => m?.slides ?? m?.files ?? [];
// 해시태그는 이미 # 가 붙어 온다 — 중복해서 붙이지 않는다
const tag = (h: string) => (h.startsWith("#") ? h : `#${h}`);

// 카드 종류마다 아이콘 하나. 카탈로그가 늘면 기본값(FileImage)으로 떨어진다.
const ICON: Record<string, typeof Flame> = {
  deal: Flame, record: TrendingUp, market: Ruler, volume: Building2,
  apply: ScrollText, remndr: Gift, calendar: CalendarDays, gap: Ruler,
  lh: Home, news: Newspaper, newsTop: Newspaper,
};

function folderLabel(f: string): string {
  const m = /^(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})$/.exec(f);
  if (!m) return f;
  return `${+m[2]}.${+m[3]} ${m[4]}:${m[5]}`;
}

export default function CardNewsV2() {
  const { token } = useAuth();

  const [catalog, setCatalog] = useState<CardSpec[] | null>(null);
  const [pick, setPick] = useState<string>("deal");
  const [vals, setVals] = useState<Record<string, string | number>>({});

  const [runs, setRuns] = useState<Run[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  // 지역 선택기는 사이트 전역에서 쓰는 것을 그대로 쓴다(시도 → 시군구 종속)
  const rf = useRegionFilter();

  const api = useCallback(
    async (path: string, init?: RequestInit) => {
      const r = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: { ...(init?.headers || {}), Authorization: `Bearer ${token}` },
      });
      if (!r.ok) {
        // 생성기가 준 메시지를 그대로 보여준다("급매가 2건도 없습니다" 같은 것)
        let msg = `${r.status}`;
        try {
          const j = JSON.parse(await r.text());
          msg = j.detail || j.error || msg;
        } catch {
          /* 본문이 JSON 이 아니면 상태코드만 */
        }
        throw new Error(msg);
      }
      return r.json();
    },
    [token],
  );

  const spec = useMemo(() => catalog?.find((c) => c.key === pick) ?? null, [catalog, pick]);

  // 카드를 바꾸면 그 카드의 기본값으로 초기화한다
  useEffect(() => {
    if (!spec) return;
    const next: Record<string, string | number> = {};
    for (const o of spec.options) if (o.type !== "region" && o.default != null) next[o.key] = o.default;
    setVals(next);
  }, [spec]);

  useEffect(() => {
    if (!token || !API_BASE) return;
    api("/admin/cardnews2/catalog")
      .then((d) => setCatalog(d.cards ?? []))
      .catch((e) => setErr(String(e)));
  }, [token, api]);

  const loadRuns = useCallback(async () => {
    try {
      const d = await api("/admin/cardnews2/runs");
      setRuns(d.runs ?? []);
      setSel((cur) => cur ?? (d.runs?.[0]?.folder ?? null));
    } catch (e) {
      setErr(String(e));
    }
  }, [api]);

  useEffect(() => {
    if (token && API_BASE) loadRuns();
  }, [token, loadRuns]);

  useEffect(() => {
    if (!sel || !token) return;
    setManifest(null);
    api(`/admin/cardnews2/runs/${sel}`)
      .then((d) => setManifest(d.manifest ?? null))
      .catch((e) => setErr(String(e)));
  }, [sel, token, api]);

  // 진행 로그 폴링 — 한 장이면 대개 10~30초다
  useEffect(() => {
    if (!jobId) return;
    let alive = true;
    const tick = async () => {
      try {
        const d = await api(`/admin/cardnews2/jobs/${jobId}`);
        if (!alive) return;
        setLines(d.lines ?? []);
        if (d.done) {
          setRunning(false);
          setJobId(null);
          if (d.error) setErr(d.error);
          else if (d.folder) {
            await loadRuns();
            setSel(d.folder);
          }
          return;
        }
      } catch (e) {
        if (!alive) return;
        setErr(String(e));
        setRunning(false);
        setJobId(null);
        return;
      }
      if (alive) setTimeout(tick, 2000);
    };
    tick();
    return () => {
      alive = false;
    };
  }, [jobId, api, loadRuns]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [lines]);

  const hasRegion = !!spec?.options.some((o) => o.type === "region");

  // 지금 고른 조건을 한 줄로 — 버튼 옆에 붙여 무엇이 나올지 미리 읽히게 한다
  const summary = useMemo(() => {
    if (!spec) return "";
    const parts: string[] = [];
    if (hasRegion) {
      const nm =
        rf.sigungus.find((x) => x.code === rf.sigungu)?.name ||
        rf.sidos.find((x) => x.code === rf.sido)?.name;
      parts.push(nm || "전국");
    }
    for (const o of spec.options) {
      if (o.type === "region") continue;
      const v = String(vals[o.key] ?? o.default ?? "");
      if (o.type === "select") {
        const c = o.choices?.find((x) => x.value === v);
        if (c) parts.push(c.label);
      } else if (o.type === "number") parts.push(`${v}건`);
    }
    return parts.join(" · ");
  }, [spec, vals, hasRegion, rf.sido, rf.sigungu, rf.sidos, rf.sigungus]);

  const start = async () => {
    setErr("");
    setLines([]);
    setRunning(true);
    try {
      const options: Record<string, string | number> = { ...vals };
      if (hasRegion) {
        // 좁은 것 하나만 보낸다 — 서버 쿼리도 같은 규칙이다
        if (rf.sigungu) options.sigungu = rf.sigungu;
        else if (rf.sido) options.sido = rf.sido;
        // 청약·LH 공고에는 지역코드가 없어 이름으로 거른다
        const nm =
          rf.sigungus.find((x) => x.code === rf.sigungu)?.name ||
          rf.sidos.find((x) => x.code === rf.sido)?.name;
        if (nm) options._regionName = nm;
      }
      const d = await api("/admin/cardnews2/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card: pick, options }),
      });
      setJobId(String(d.jobId));
    } catch (e) {
      setErr(String(e));
      setRunning(false);
    }
  };

  const save = async (folder: string, name: string) => {
    try {
      const r = await fetch(`${API_BASE}/admin/cardnews2/file/${folder}/${name}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `koczip_${folder}_${name}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(`내려받기 실패: ${e}`);
    }
  };

  const copyCaption = () => {
    if (!manifest?.caption) return;
    navigator.clipboard.writeText(
      `${manifest.caption}\n\n${(manifest.hashtags ?? []).map(tag).join(" ")}`,
    );
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="cn2">
      <style>{css}</style>

      <div className="section-title" style={{ marginTop: 4 }}>
        <Images size={16} strokeWidth={2.2} /> 카드뉴스 v2{" "}
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>
          한 장씩 골라 만들기 · 관리자
        </span>
      </div>
      <p className="cn2-lead">
        만들 카드를 하나 고르고 조건을 정하면 인스타 카드(1080×1350) 한 장이 나온다.
        숫자는 콕집 데이터에서 그대로 오고 문구만 AI 가 쓴다.
      </p>

      {err && (
        <div className="cn2-err">
          <AlertCircle size={15} strokeWidth={2.3} />
          <span>{err}</span>
        </div>
      )}

      {/* ── ① 무엇을 만들까 ─────────────────────────────────────────── */}
      <div className="cn2-step">
        <span className="cn2-num">1</span> 무엇을 만들까
      </div>
      {catalog === null ? (
        <div className="cn2-skel-grid">
          {Array.from({ length: 8 }, (_, i) => <div key={i} className="cn2-skel" />)}
        </div>
      ) : (
        <div className="cn2-cards">
          {catalog.map((c) => {
            const Ic = ICON[c.key] || FileImage;
            const on = pick === c.key;
            return (
              <button
                key={c.key}
                className={`cn2-card${on ? " on" : ""}`}
                onClick={() => setPick(c.key)}
                disabled={running}
              >
                <span className="cn2-card-ic"><Ic size={17} strokeWidth={2.2} /></span>
                <b>{c.label}</b>
                <span className="cn2-card-desc">{c.desc}</span>
                {on && <span className="cn2-card-tick"><Check size={13} strokeWidth={3} /></span>}
              </button>
            );
          })}
        </div>
      )}

      {/* ── ② 조건 ──────────────────────────────────────────────────── */}
      {spec && (
        <>
          <div className="cn2-step">
            <span className="cn2-num">2</span> 조건
            {spec.options.length === 0 && (
              <span className="cn2-step-note">이 카드는 따로 고를 것이 없다</span>
            )}
          </div>

          <div className="cn2-panel">
            {spec.options.length > 0 && (
              <div className="cn2-opts">
                {spec.options.map((o) =>
                  o.type === "region" ? (
                    <div className="cn2-opt" key={o.key}>
                      <label>{o.label}</label>
                      <div className="cn2-row">
                        <select
                          value={rf.sido}
                          disabled={running}
                          onChange={(e) => rf.setSido(e.target.value)}
                        >
                          <option value="">전국</option>
                          {rf.sidos.map((r) => (
                            <option key={r.code} value={r.code}>{r.name}</option>
                          ))}
                        </select>
                        <select
                          value={rf.sigungu}
                          disabled={running || !rf.sido}
                          onChange={(e) => rf.setSigungu(e.target.value)}
                        >
                          <option value="">전체</option>
                          {rf.sigungus.map((r) => (
                            <option key={r.code} value={r.code}>{r.name}</option>
                          ))}
                        </select>
                      </div>
                      {o.hint && <small>{o.hint}</small>}
                    </div>
                  ) : o.type === "select" ? (
                    <div className="cn2-opt" key={o.key}>
                      <label>{o.label}</label>
                      <div className="cn2-chips">
                        {o.choices?.map((c) => (
                          <button
                            key={c.value}
                            className={String(vals[o.key] ?? o.default) === c.value ? "on" : ""}
                            disabled={running}
                            onClick={() => setVals((v) => ({ ...v, [o.key]: c.value }))}
                          >
                            {c.label}
                          </button>
                        ))}
                      </div>
                      {o.hint && <small>{o.hint}</small>}
                    </div>
                  ) : (
                    <div className="cn2-opt" key={o.key}>
                      <label>{o.label}</label>
                      <div className="cn2-chips">
                        {Array.from(
                          { length: (o.max ?? 8) - (o.min ?? 4) + 1 },
                          (_, i) => (o.min ?? 4) + i,
                        ).map((n) => (
                          <button
                            key={n}
                            className={Number(vals[o.key] ?? o.default) === n ? "on" : ""}
                            disabled={running}
                            onClick={() => setVals((v) => ({ ...v, [o.key]: n }))}
                          >
                            {n}
                          </button>
                        ))}
                      </div>
                      {o.hint && <small>{o.hint}</small>}
                    </div>
                  ),
                )}
              </div>
            )}

            <div className="cn2-go">
              <div className="cn2-go-sum">
                <b>{spec.label}</b>
                {summary && <span>{summary}</span>}
              </div>
              <button className="cn2-run" onClick={start} disabled={running || !catalog}>
                {running
                  ? <><Loader2 size={16} className="cn2-spin" /> 만드는 중…</>
                  : <><Play size={15} strokeWidth={2.6} /> 이 카드 만들기</>}
              </button>
            </div>

            {(running || lines.length > 0) && (
              <pre className="cn2-log" ref={logRef}>{lines.join("\n")}</pre>
            )}
          </div>
        </>
      )}

      {/* ── ③ 결과 ──────────────────────────────────────────────────── */}
      <div className="cn2-step">
        <span className="cn2-num">3</span> 만든 카드
        <button className="cn2-refresh" onClick={loadRuns}>
          <RefreshCw size={12} strokeWidth={2.4} /> 새로고침
        </button>
      </div>

      {runs && runs.length > 0 && (
        <div className="cn2-runs">
          {runs.slice(0, 14).map((r) => (
            <button
              key={r.folder}
              className={`cn2-run-chip${sel === r.folder ? " on" : ""}`}
              onClick={() => setSel(r.folder)}
              title={r.headline}
            >
              {folderLabel(r.folder)}
              {r.slideCount > 1 && <i>{r.slideCount}장</i>}
            </button>
          ))}
        </div>
      )}

      {runs?.length === 0 && <p className="cn2-empty">아직 만든 카드가 없다.</p>}

      {sel && (
        <div className="cn2-result">
          <div className="cn2-shot">
            {manifest === null ? (
              <div className="cn2-shot-skel" />
            ) : (
              cardsOf(manifest).map((f) => (
                <figure key={f.file}>
                  <CardImg folder={sel} name={f.file} token={token!} />
                  <figcaption>
                    <span title={f.title}>{f.title || f.type}</span>
                    <button onClick={() => save(sel, f.file)}>
                      <Download size={13} strokeWidth={2.4} /> 저장
                    </button>
                  </figcaption>
                </figure>
              ))
            )}
          </div>

          {manifest?.caption && (
            <div className="cn2-cap">
              <h3>
                캡션
                <button onClick={copyCaption} className={copied ? "done" : ""}>
                  {copied
                    ? <><Check size={12} strokeWidth={3} /> 복사됨</>
                    : <><Copy size={12} strokeWidth={2.4} /> 복사</>}
                </button>
              </h3>
              <p>{manifest.caption}</p>
              {!!manifest.hashtags?.length && (
                <div className="cn2-tags">
                  {manifest.hashtags.map((h) => <span key={h}>{tag(h)}</span>)}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** 카드 이미지 — 관리자 토큰이 필요해 blob 으로 받아 건다. */
function CardImg({ folder, name, token }: { folder: string; name: string; token: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    fetch(`${API_BASE}/admin/cardnews2/file/${folder}/${name}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(String(r.status)))))
      .then((b) => {
        if (!alive) return;
        url = URL.createObjectURL(b);
        setSrc(url);
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [folder, name, token]);

  if (!src) return <div className="cn2-shot-skel" />;
  return <img src={src} alt={name} loading="lazy" />;
}

const css = `
.cn2{max-width:1080px}
.cn2-lead{margin:6px 0 18px;font-size:13.5px;line-height:1.6;color:var(--c-muted);max-width:62ch}

/* 단계 머리 */
.cn2-step{display:flex;align-items:center;gap:8px;margin:22px 0 10px;
  font-size:14.5px;font-weight:800;color:var(--c-text)}
.cn2-num{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;
  border-radius:50%;background:var(--c-primary);color:#fff;font-size:11.5px;font-weight:800}
.cn2-step-note{font-size:12.5px;font-weight:400;color:var(--c-faint)}
.cn2-refresh{margin-left:auto;display:inline-flex;align-items:center;gap:5px;border:1px solid var(--c-border);
  background:var(--c-card);border-radius:var(--r-pill);padding:4px 11px;font-size:11.5px;font-weight:700;
  color:var(--c-muted);cursor:pointer}
.cn2-refresh:hover{border-color:var(--c-primary);color:var(--c-primary)}

/* 오류 */
.cn2-err{display:flex;align-items:flex-start;gap:8px;margin:10px 0;padding:10px 13px;
  border:1px solid #f3c9c9;background:#fdf3f3;border-radius:var(--r-md);
  font-size:13px;line-height:1.5;color:#a52a2a}
.cn2-err svg{flex:none;margin-top:1px}

/* ① 카드 고르기 */
.cn2-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));gap:9px}
.cn2-card{position:relative;display:flex;flex-direction:column;gap:3px;padding:13px 13px 12px;
  border:1px solid var(--c-border);background:var(--c-card);border-radius:var(--r-md);
  text-align:left;cursor:pointer;box-shadow:var(--sh-xs);
  transition:border-color .16s ease,box-shadow .16s ease,transform .16s ease}
.cn2-card:hover:not(:disabled){border-color:#b9d0ee;box-shadow:var(--sh-md);transform:translateY(-1px)}
.cn2-card:disabled{opacity:.55;cursor:default}
.cn2-card.on{border-color:var(--c-primary);background:var(--c-primary-tint);
  box-shadow:0 0 0 2px rgba(18,104,211,.16),var(--sh-sm)}
.cn2-card-ic{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
  margin-bottom:3px;border-radius:9px;background:var(--c-primary-soft);color:var(--c-primary)}
.cn2-card.on .cn2-card-ic{background:var(--c-primary);color:#fff}
.cn2-card b{font-size:13.5px;font-weight:800;color:var(--c-text);letter-spacing:-.01em}
.cn2-card-desc{font-size:11.5px;line-height:1.45;color:var(--c-muted);word-break:keep-all}
.cn2-card-tick{position:absolute;top:9px;right:9px;display:inline-flex;align-items:center;
  justify-content:center;width:17px;height:17px;border-radius:50%;background:var(--c-primary);color:#fff}
.cn2-skel-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));gap:9px}
.cn2-skel{height:92px;border-radius:var(--r-md);background:linear-gradient(90deg,#eef1f5,#f7f9fb,#eef1f5);
  background-size:200% 100%;animation:cn2sh 1.3s linear infinite}
@keyframes cn2sh{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* ② 조건 */
.cn2-panel{border:1px solid var(--c-border);background:var(--c-card);border-radius:var(--r-lg);
  padding:16px 17px;box-shadow:var(--sh-sm)}
.cn2-opts{display:flex;flex-wrap:wrap;gap:18px 26px}
.cn2-opt{display:flex;flex-direction:column;gap:6px}
.cn2-opt>label{font-size:12px;font-weight:800;color:#5a6b80;letter-spacing:.01em}
.cn2-opt small{font-size:11px;line-height:1.4;color:var(--c-faint);max-width:22ch}
.cn2-row{display:flex;gap:6px}
.cn2-opt select{min-width:104px;padding:7px 10px;border:1px solid #d9e2ef;border-radius:9px;font:inherit;
  font-size:13px;font-weight:600;color:var(--c-text);background:#fff;cursor:pointer}
.cn2-opt select:disabled{background:#f6f8fa;color:var(--c-faint);cursor:default}
.cn2-opt select:focus{outline:none;border-color:var(--c-primary);box-shadow:0 0 0 3px rgba(18,104,211,.1)}
.cn2-chips{display:flex;flex-wrap:wrap;gap:5px}
.cn2-chips button{border:1px solid #d9e2ef;background:#fff;border-radius:var(--r-pill);
  padding:6px 12px;font:inherit;font-size:12.5px;font-weight:700;color:#3c4a60;cursor:pointer;
  transition:border-color .14s ease,background .14s ease,color .14s ease}
.cn2-chips button:hover:not(:disabled){border-color:#b9d0ee}
.cn2-chips button.on{border-color:var(--c-primary);background:var(--c-primary-soft);color:#0b4ea2}
.cn2-chips button:disabled{opacity:.5;cursor:default}

/* 실행 줄 */
.cn2-go{display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  margin-top:16px;padding-top:14px;border-top:1px dashed var(--c-border)}
.cn2-go-sum{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;min-width:0}
.cn2-go-sum b{font-size:14px;font-weight:800;color:var(--c-text)}
.cn2-go-sum span{font-size:12.5px;color:var(--c-muted)}
.cn2-run{margin-left:auto;display:inline-flex;align-items:center;gap:7px;border:none;
  background:var(--c-primary);color:#fff;border-radius:11px;padding:11px 20px;
  font:inherit;font-size:14px;font-weight:800;cursor:pointer;
  box-shadow:0 2px 10px rgba(18,104,211,.28);transition:background .15s ease,box-shadow .15s ease}
.cn2-run:hover:not(:disabled){background:var(--c-primary-strong);box-shadow:0 4px 14px rgba(18,104,211,.34)}
.cn2-run:disabled{background:#9db8dc;box-shadow:none;cursor:default}
.cn2-spin{animation:cn2spin .9s linear infinite}
@keyframes cn2spin{to{transform:rotate(360deg)}}

/* 진행 로그 */
.cn2-log{margin:13px 0 0;max-height:154px;overflow:auto;border-radius:var(--r-md);
  background:#101828;color:#d7e2f0;padding:11px 13px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;line-height:1.65;
  white-space:pre-wrap;word-break:break-all}

/* ③ 결과 */
.cn2-runs{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px}
.cn2-run-chip{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--c-border);
  background:var(--c-card);border-radius:var(--r-pill);padding:5px 12px;
  font:inherit;font-size:12px;font-weight:700;color:#42506a;cursor:pointer}
.cn2-run-chip:hover{border-color:#b9d0ee}
.cn2-run-chip.on{border-color:var(--c-primary);background:var(--c-primary-soft);color:#0b4ea2}
.cn2-run-chip i{font-style:normal;font-size:10.5px;font-weight:700;color:var(--c-faint)}
.cn2-empty{font-size:13px;color:var(--c-muted)}

.cn2-result{margin-top:2px;display:grid;grid-template-columns:minmax(0,320px) minmax(0,1fr);gap:18px;align-items:start}
@media (max-width:760px){.cn2-result{grid-template-columns:1fr}}
.cn2-shot figure{margin:0;border:1px solid var(--c-border);border-radius:var(--r-lg);
  overflow:hidden;background:var(--c-card);box-shadow:var(--sh-md)}
.cn2-shot img{display:block;width:100%}
.cn2-shot figcaption{display:flex;align-items:center;justify-content:space-between;gap:8px;
  padding:9px 11px;border-top:1px solid var(--c-border-soft);background:#fbfcfd}
.cn2-shot figcaption span{font-size:12px;font-weight:700;color:var(--c-text-soft);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cn2-shot figcaption button{flex:none;display:inline-flex;align-items:center;gap:5px;
  border:1px solid var(--c-border);background:#fff;border-radius:8px;padding:5px 10px;
  font:inherit;font-size:11.5px;font-weight:700;color:#42506a;cursor:pointer}
.cn2-shot figcaption button:hover{border-color:var(--c-primary);color:var(--c-primary)}
.cn2-shot-skel{width:100%;aspect-ratio:4/5;border-radius:var(--r-lg);
  background:linear-gradient(90deg,#eef1f5,#f7f9fb,#eef1f5);background-size:200% 100%;
  animation:cn2sh 1.3s linear infinite}

.cn2-cap{border:1px solid var(--c-border);background:var(--c-card);border-radius:var(--r-lg);
  padding:15px 17px;box-shadow:var(--sh-sm)}
.cn2-cap h3{display:flex;align-items:center;gap:10px;margin:0 0 9px;font-size:13px;font-weight:800;
  color:var(--c-text)}
.cn2-cap h3 button{margin-left:auto;display:inline-flex;align-items:center;gap:5px;
  border:1px solid var(--c-border);background:#fff;border-radius:8px;padding:5px 11px;
  font:inherit;font-size:11.5px;font-weight:700;color:#42506a;cursor:pointer}
.cn2-cap h3 button:hover{border-color:var(--c-primary);color:var(--c-primary)}
.cn2-cap h3 button.done{border-color:var(--c-wolse);color:var(--c-wolse)}
.cn2-cap p{margin:0;font-size:13.5px;line-height:1.75;color:var(--c-text-soft);white-space:pre-wrap}
.cn2-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:11px;padding-top:11px;
  border-top:1px solid var(--c-border-soft)}
.cn2-tags span{font-size:12px;font-weight:600;color:var(--c-primary);
  background:var(--c-primary-tint);border-radius:var(--r-pill);padding:3px 9px}
`;
