// ══════════════════════════════════════════════════════════════════════════
// 카드뉴스 v2 — 원하는 카드 한 장을 골라 만든다
//
//   v1(/admin/cardnews)은 브라우저에서 html2canvas 로 그린다.
//   v2 는 nfind 박스의 헤드리스 크롬이 콕집 API·청약홈·LH·뉴스에서 재료를 모아
//   Gemini 로 카피를 쓰고 1080×1350 PNG 로 뽑는다.
//
//   선택지는 생성기의 카탈로그(lib/catalog.js)를 그대로 받아 그린다 —
//   카드 종류를 늘려도 이 파일은 손댈 필요가 없다.
// ══════════════════════════════════════════════════════════════════════════
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, Images, Loader2, Play, RefreshCw } from "lucide-react";
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

function folderLabel(f: string): string {
  const m = /^(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})$/.exec(f);
  if (!m) return f;
  return `${+m[2]}. ${+m[3]}. ${m[4]}:${m[5]}`;
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

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-5">
        <h1 className="flex items-center gap-2 text-xl font-bold text-ink">
          <Images size={20} className="text-brand" /> 카드뉴스 v2
        </h1>
        <p className="mt-1 text-sm text-muted">
          만들 카드를 하나 고르고 조건을 정하면 인스타 카드(1080×1350) 한 장이 나온다.
          숫자는 콕집 데이터에서 그대로 오고, 문구만 AI 가 쓴다.
        </p>
      </header>

      {err && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      )}

      {/* ── ① 무엇을 만들까 ─────────────────────────────────────────── */}
      <section className="mb-4">
        <h2 className="mb-2 text-sm font-semibold text-ink">① 무엇을 만들까</h2>
        {catalog === null ? (
          <p className="text-sm text-muted">불러오는 중…</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {catalog.map((c) => (
              <button
                key={c.key}
                onClick={() => setPick(c.key)}
                disabled={running}
                className={`rounded-xl border p-3 text-left transition ${
                  pick === c.key
                    ? "border-brand bg-brand/5 ring-1 ring-brand"
                    : "border-line bg-white hover:border-brand/40"
                }`}
              >
                <div className="text-sm font-semibold text-ink">{c.label}</div>
                <div className="mt-0.5 text-xs leading-4 text-muted">{c.desc}</div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* ── ② 조건 ──────────────────────────────────────────────────── */}
      {spec && (
        <section className="mb-4 rounded-xl border border-line bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-ink">
            ② 조건
            {spec.options.length === 0 && (
              <span className="ml-2 font-normal text-muted">— 이 카드는 고를 것이 없다</span>
            )}
          </h2>

          <div className="flex flex-wrap items-end gap-4">
            {spec.options.map((o) =>
              o.type === "region" ? (
                <div key={o.key} className="text-sm">
                  <span className="mb-1 block text-muted">{o.label}</span>
                  <div className="flex gap-2">
                    <select
                      className="rounded-lg border border-line px-3 py-2"
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
                      className="rounded-lg border border-line px-3 py-2 disabled:opacity-40"
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
                  {o.hint && <p className="mt-1 text-xs text-muted">{o.hint}</p>}
                </div>
              ) : o.type === "select" ? (
                <label key={o.key} className="text-sm">
                  <span className="mb-1 block text-muted">{o.label}</span>
                  <select
                    className="rounded-lg border border-line px-3 py-2"
                    value={String(vals[o.key] ?? o.default ?? "")}
                    disabled={running}
                    onChange={(e) => setVals((v) => ({ ...v, [o.key]: e.target.value }))}
                  >
                    {o.choices?.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                  {o.hint && <p className="mt-1 max-w-[13rem] text-xs leading-4 text-muted">{o.hint}</p>}
                </label>
              ) : (
                <label key={o.key} className="text-sm">
                  <span className="mb-1 block text-muted">{o.label}</span>
                  <select
                    className="rounded-lg border border-line px-3 py-2"
                    value={String(vals[o.key] ?? o.default ?? "")}
                    disabled={running}
                    onChange={(e) => setVals((v) => ({ ...v, [o.key]: Number(e.target.value) }))}
                  >
                    {Array.from(
                      { length: (o.max ?? 8) - (o.min ?? 4) + 1 },
                      (_, i) => (o.min ?? 4) + i,
                    ).map((n) => (
                      <option key={n} value={n}>{n}건</option>
                    ))}
                  </select>
                  {o.hint && <p className="mt-1 max-w-[13rem] text-xs leading-4 text-muted">{o.hint}</p>}
                </label>
              ),
            )}

            <button
              onClick={start}
              disabled={running || !catalog}
              className="ml-auto inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 font-semibold text-white disabled:opacity-50"
            >
              {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              {running ? "만드는 중…" : "이 카드 만들기"}
            </button>
          </div>

          {(running || lines.length > 0) && (
            <pre
              ref={logRef}
              className="mt-3 max-h-44 overflow-auto rounded-lg bg-slate-900 px-3 py-2 text-xs leading-5 text-slate-100"
            >
              {lines.join("\n")}
            </pre>
          )}
        </section>
      )}

      {/* ── ③ 결과 ──────────────────────────────────────────────────── */}
      <section>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-ink">③ 만든 카드</h2>
          <button
            onClick={loadRuns}
            className="inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-xs text-muted"
          >
            <RefreshCw size={12} /> 새로고침
          </button>
          <div className="flex flex-wrap gap-1.5">
            {runs?.length === 0 && <span className="text-sm text-muted">아직 없다.</span>}
            {runs?.slice(0, 12).map((r) => (
              <button
                key={r.folder}
                onClick={() => setSel(r.folder)}
                className={`rounded-lg border px-2.5 py-1 text-xs ${
                  sel === r.folder
                    ? "border-brand bg-brand/10 font-semibold text-brand"
                    : "border-line text-ink"
                }`}
                title={r.headline}
              >
                {folderLabel(r.folder)}
                {r.slideCount > 1 && <span className="ml-1 text-muted">{r.slideCount}장</span>}
              </button>
            ))}
          </div>
        </div>

        {sel && manifest && (
          <div className="grid gap-4 md:grid-cols-[minmax(0,340px)_1fr]">
            <div>
              {cardsOf(manifest).map((f) => (
                <figure
                  key={f.file}
                  className="mb-3 overflow-hidden rounded-xl border border-line bg-white"
                >
                  <CardImg folder={sel} name={f.file} token={token!} />
                  <figcaption className="flex items-center justify-between gap-2 px-3 py-2">
                    <span className="truncate text-xs text-ink" title={f.title}>
                      {f.title || f.type}
                    </span>
                    <button
                      onClick={() => save(sel, f.file)}
                      className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-line px-2 py-1 text-xs"
                    >
                      <Download size={12} /> 저장
                    </button>
                  </figcaption>
                </figure>
              ))}
            </div>

            {manifest.caption && (
              <div className="rounded-xl border border-line bg-white p-4">
                <h3 className="mb-2 text-sm font-semibold text-ink">캡션</h3>
                <p className="whitespace-pre-wrap text-sm leading-6 text-ink">{manifest.caption}</p>
                {!!manifest.hashtags?.length && (
                  <p className="mt-2 text-sm text-brand">{manifest.hashtags.map(tag).join(" ")}</p>
                )}
                <button
                  onClick={() =>
                    navigator.clipboard.writeText(
                      `${manifest.caption}\n\n${(manifest.hashtags ?? []).map(tag).join(" ")}`,
                    )
                  }
                  className="mt-3 rounded-lg border border-line px-3 py-1.5 text-xs"
                >
                  캡션 복사
                </button>
              </div>
            )}
          </div>
        )}
      </section>
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

  if (!src) return <div className="aspect-[4/5] w-full animate-pulse bg-slate-100" />;
  return <img src={src} alt={name} className="block w-full" loading="lazy" />;
}
