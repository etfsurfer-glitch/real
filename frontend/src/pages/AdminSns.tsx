import { useCallback, useEffect, useState } from "react";
import { authClient } from "../auth";

const API = import.meta.env.VITE_API_BASE;
const PLATFORMS = [
  { key: "threads", label: "Threads" },
  { key: "instagram", label: "Instagram" },
  { key: "x", label: "X" },
] as const;
type Plat = typeof PLATFORMS[number]["key"];

type Region = { code: string; name: string };
type RegionSel = { sido: string; sigungu: string; dong: string | null; label?: string };
type Routine = {
  id: number; name: string; post_time: string; platforms: string[]; enabled: boolean;
  weekdays: number[]; regions: RegionSel[];
};
const WD = ["월", "화", "수", "목", "금", "토", "일"];
function wdText(w: number[]): string {
  if (!w || w.length === 0) return "매일";
  if (w.length === 5 && [0, 1, 2, 3, 4].every((x) => w.includes(x))) return "평일";
  if (w.length === 2 && w.includes(5) && w.includes(6)) return "주말";
  return w.slice().sort((a, b) => a - b).map((x) => WD[x]).join("·");
}
type QItem = {
  id: number; routine: string; platform: string; run_at: string; status: string;
  caption: string; result: string; created_at: string; sent_at: string | null;
};

async function authFetch(path: string, init?: RequestInit) {
  const s = await authClient?.auth.getSession();
  const tok = s?.data?.session?.access_token;
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

export default function AdminSns() {
  const [tab, setTab] = useState<"routine" | "account" | "queue" | "engage">("routine");
  const [accounts, setAccounts] = useState<Record<string, Record<string, string>>>({});
  const [checks, setChecks] = useState<Record<string, { status: string; result: string; checked_at: string | null }>>({});
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [queue, setQueue] = useState<QItem[]>([]);
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    authFetch("/admin/sns/accounts").then((j) => { setAccounts(j.accounts || {}); setChecks(j.checks || {}); }).catch(() => {});
    authFetch("/admin/sns/routines").then((j) => setRoutines(j.items || [])).catch(() => {});
    authFetch("/admin/sns/queue?limit=40").then((j) => setQueue(j.items || [])).catch(() => {});
  }, []);
  useEffect(load, [load]);

  return (
    <div className="sns-page">
      <h2 style={{ margin: "4px 0 6px" }}>SNS 자동포스팅</h2>
      <p className="muted" style={{ margin: "0 0 14px", fontSize: 13 }}>
        루틴에 등록한 지역·시각마다 뉴스레터를 만들어 Threads·Instagram·X 에 10~30분 랜덤 간격으로 올립니다.
        발행은 별도 워커 서버(브라우저 자동화)가 수행합니다.
      </p>
      <div className="sns-tabs">
        {([["routine", "발행 루틴"], ["engage", "반응 마케팅"], ["account", "계정"],
           ["queue", "발행 현황"]] as const).map(([k, l]) => (
          <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
        ))}
        <button className="sns-reload" onClick={load}>새로고침</button>
      </div>
      {msg && <div className="sns-msg">{msg}</div>}

      {tab === "routine" && <RoutineTab routines={routines} accounts={accounts} reload={load} setMsg={setMsg} />}
      {tab === "account" && <AccountTab accounts={accounts} checks={checks} reload={load} setMsg={setMsg} />}
      {tab === "queue" && <QueueTab queue={queue} reload={load} />}
      {tab === "engage" && <EngageTab setMsg={setMsg} />}
    </div>
  );
}

function RoutineTab({ routines, accounts, reload, setMsg }: {
  routines: Routine[]; accounts: Record<string, Record<string, string>>;
  reload: () => void; setMsg: (s: string) => void;
}) {
  const connected = (k: string) => {
    const a = accounts[k] || {};
    return !!(a.cookies || a.username);
  };
  const [sidos, setSidos] = useState<Region[]>([]);
  const [sggs, setSggs] = useState<Region[]>([]);
  const [dongs, setDongs] = useState<Region[]>([]);
  const [pick, setPick] = useState({ sido: "1100000000", sigungu: "", dong: "" });
  const [regions, setRegions] = useState<RegionSel[]>([]);
  const [name, setName] = useState("");
  const [postTime, setPostTime] = useState("09:00");
  const [weekdays, setWeekdays] = useState<number[]>([]);
  const [plats, setPlats] = useState<Plat[]>([]);
  const [platsTouched, setPlatsTouched] = useState(false);

  // 계정이 연결된 플랫폼만 기본 선택 — 미연결을 기본 체크하면 발행 건수가 튀어 혼란스럽다.
  useEffect(() => {
    if (platsTouched) return;
    const ok = PLATFORMS.map((p) => p.key).filter((k) => connected(k)) as Plat[];
    setPlats(ok);
  }, [accounts, platsTouched]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetch(`${API}/stats/changes/sido-list`).then((r) => r.json()).then((j) => setSidos(j.items || [])).catch(() => {}); }, []);
  useEffect(() => {
    if (!pick.sido) return;
    fetch(`${API}/stats/sigungu-list?sido=${pick.sido.slice(0, 2)}`).then((r) => r.json())
      .then((j) => setSggs(j.items || [])).catch(() => {});
  }, [pick.sido]);
  useEffect(() => {
    if (!pick.sigungu) { setDongs([]); return; }
    fetch(`${API}/stats/dong-list?sigungu=${pick.sigungu.slice(0, 5)}`).then((r) => r.json())
      .then((j) => setDongs(j.items || [])).catch(() => {});
  }, [pick.sigungu]);

  const addRegion = () => {
    if (!pick.sigungu) { setMsg("시·군·구를 선택하세요."); return; }
    const label = [sidos.find((s) => s.code === pick.sido)?.name,
      sggs.find((s) => s.code === pick.sigungu)?.name,
      dongs.find((s) => s.code === pick.dong)?.name].filter(Boolean).join(" ");
    if (regions.some((r) => r.sigungu === pick.sigungu && (r.dong || "") === (pick.dong || ""))) {
      setMsg("이미 추가된 지역입니다."); return;
    }
    setRegions([...regions, { sido: pick.sido, sigungu: pick.sigungu, dong: pick.dong || null, label }]);
    setPick({ ...pick, sigungu: "", dong: "" });
  };

  const add = async () => {
    if (!name || regions.length === 0) { setMsg("이름과 지역(1개 이상)이 필요합니다."); return; }
    try {
      await authFetch("/admin/sns/routines", {
        method: "POST",
        body: JSON.stringify({ name, post_time: postTime, platforms: plats, weekdays, regions }),
      });
      setMsg(`루틴 추가 완료 — 발행 ${regions.length * plats.length}건이 ${postTime}부터 10~30분 간격으로 나갑니다.`);
      setName(""); setRegions([]);
      reload();
    } catch { setMsg("추가 실패"); }
  };

  const preset = (kind: string) => {
    if (kind === "daily") setWeekdays([]);
    else if (kind === "weekday") setWeekdays([0, 1, 2, 3, 4]);
    else if (kind === "weekend") setWeekdays([5, 6]);
  };

  return (
    <>
      <div className="sns-card">
        <h3>새 루틴</h3>
        <div className="sns-form" style={{ marginBottom: 10 }}>
          <input placeholder="루틴 이름 — 관리용 (예: 강남권 아침 발행)" value={name}
            onChange={(e) => setName(e.target.value)} style={{ minWidth: 260 }} />
        </div>

        <div className="sns-sub">1단계 · 지역 고르기 <span className="muted">여러 개 담으면 지역마다 카드가 따로 만들어집니다</span></div>
        <div className="sns-form">
          <select value={pick.sido} onChange={(e) => setPick({ sido: e.target.value, sigungu: "", dong: "" })}>
            {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          <select value={pick.sigungu} onChange={(e) => setPick({ ...pick, sigungu: e.target.value, dong: "" })}>
            <option value="">시·군·구</option>
            {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          <select value={pick.dong} onChange={(e) => setPick({ ...pick, dong: e.target.value })} disabled={!pick.sigungu}>
            <option value="">동 전체</option>
            {dongs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          <button onClick={addRegion}>+ 지역 담기</button>
        </div>
        {regions.length > 0 && (
          <div className="sns-chips">
            {regions.map((r, i) => (
              <span className="sns-chip" key={i}>{r.label}
                <button onClick={() => setRegions(regions.filter((_, j) => j !== i))}>×</button>
              </span>
            ))}
          </div>
        )}

        <div className="sns-sub">2단계 · 언제 올릴지 <span className="muted">첫 글이 나가는 시각과 반복 요일</span></div>
        <div className="sns-form">
          <input type="time" value={postTime} onChange={(e) => setPostTime(e.target.value)} />
          <div className="sns-presets">
            <button className={weekdays.length === 0 ? "on" : ""} onClick={() => preset("daily")}>매일</button>
            <button className={wdText(weekdays) === "평일" ? "on" : ""} onClick={() => preset("weekday")}>평일</button>
            <button className={wdText(weekdays) === "주말" ? "on" : ""} onClick={() => preset("weekend")}>주말</button>
          </div>
          <div className="sns-wd">
            {WD.map((d, i) => (
              <button key={d} className={weekdays.includes(i) ? "on" : ""}
                onClick={() => setWeekdays(weekdays.includes(i) ? weekdays.filter((x) => x !== i) : [...weekdays, i])}>{d}</button>
            ))}
          </div>
        </div>

        <div className="sns-sub">3단계 · 어디에 올릴지 <span className="muted">고른 플랫폼마다 글이 하나씩 나갑니다</span></div>
        <div className="sns-form">
          <div className="sns-plats">
            {PLATFORMS.map((p) => (
              <label key={p.key} className={connected(p.key) ? "" : "sns-noconn"}
                title={connected(p.key) ? "" : "계정 탭에서 쿠키를 넣고 '연결 확인'을 먼저 하세요"}>
                <input type="checkbox" disabled={!connected(p.key)}
                  checked={plats.includes(p.key)}
                  onChange={(e) => {
                    setPlatsTouched(true);
                    setPlats(e.target.checked ? [...plats, p.key] : plats.filter((x) => x !== p.key));
                  }} />
                {p.label}{connected(p.key) ? "" : " · 계정 연결 필요"}
              </label>
            ))}
          </div>
          <button className="sns-primary" onClick={add}
            disabled={!name || regions.length === 0 || plats.length === 0}>루틴 추가</button>
        </div>
        {plats.length === 0 && (
          <div className="sns-warn">
            올릴 곳이 없습니다. <b>계정 탭</b>에서 쿠키를 넣고 <b>연결 확인</b>을 마친 플랫폼만 선택할 수 있습니다.
          </div>
        )}
        {regions.length > 0 && plats.length > 0 && (
          <>
            <div className="sns-est">
              <b>{wdText(weekdays)} {postTime}</b>부터 글이 나갑니다.
              지역 {regions.length}곳 × 올릴 곳 {plats.length}군데 = <b>하루 {regions.length * plats.length}건</b>,
              10~30분 간격으로 순서대로 올라가며 마지막 글은 약{" "}
              {Math.round((regions.length * plats.length - 1) * 20 / 60 * 10) / 10}시간 뒤입니다.
            </div>
            {plats.some((k) => !connected(k)) && (
              <div className="sns-warn">
                {plats.filter((k) => !connected(k)).map((k) => PLATFORMS.find((p) => p.key === k)?.label).join(", ")}
                {" "}계정이 아직 연결되지 않았습니다. 이대로 등록하면 그 플랫폼 발행은 <b>실패로 기록</b>됩니다.
                계정 탭에서 쿠키를 넣고 <b>연결 확인</b>을 먼저 하시거나, 체크를 해제하세요.
              </div>
            )}
          </>
        )}
      </div>

      <div className="sns-card">
        <h3>등록된 루틴 <span className="muted">{routines.length}개</span></h3>
        {routines.length === 0 ? <div className="muted">아직 없습니다.</div> : (
          <table className="sns-tbl">
            <thead><tr><th>이름 / 지역</th><th>시각</th><th>주기</th><th>플랫폼</th><th>상태</th><th></th></tr></thead>
            <tbody>
              {routines.map((r) => (
                <tr key={r.id}>
                  <td><b>{r.name}</b>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {(r.regions || []).map((g) => g.label).join(", ") || "-"}
                    </div>
                  </td>
                  <td>{r.post_time}</td>
                  <td>{wdText(r.weekdays)}</td>
                  <td className="muted">{r.platforms.join(" · ")}</td>
                  <td>{r.enabled ? <span className="sns-on">사용</span> : <span className="sns-off">중지</span>}</td>
                  <td className="sns-acts">
                    <button onClick={async () => { await authFetch(`/admin/sns/routines/${r.id}/run-now`, { method: "POST" }); setMsg("발행 큐에 넣었습니다."); reload(); }}>지금 발행</button>
                    <button onClick={async () => { await authFetch(`/admin/sns/routines/${r.id}/toggle`, { method: "POST" }); reload(); }}>{r.enabled ? "중지" : "사용"}</button>
                    <button className="sns-del" onClick={async () => { if (confirm("삭제할까요?")) { await authFetch(`/admin/sns/routines/${r.id}`, { method: "DELETE" }); reload(); } }}>삭제</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function AccountTab({ accounts, checks, reload, setMsg }: {
  accounts: Record<string, Record<string, string>>;
  checks: Record<string, { status: string; result: string; checked_at: string | null }>;
  reload: () => void; setMsg: (s: string) => void;
}) {
  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});
  const [busy, setBusy] = useState("");
  const set = (p: string, k: string, v: string) =>
    setDraft({ ...draft, [p]: { ...(draft[p] || {}), [k]: v } });

  const save = async (p: string) => {
    try {
      await authFetch(`/admin/sns/accounts/${p}`, { method: "PUT", body: JSON.stringify(draft[p] || {}) });
      setMsg(`${p} 계정을 저장했습니다.`);
      setDraft({ ...draft, [p]: {} });
      reload();
    } catch { setMsg("저장 실패"); }
  };

  /** 연결 확인 — 워커가 세션을 점검하고, 로그아웃 상태면 저장된 계정으로 로그인까지 시도한다. */
  const test = async (p: string) => {
    setBusy(p);
    try {
      await authFetch(`/admin/sns/accounts/${p}/test`, { method: "POST" });
      setMsg(`${p} 연결 확인을 요청했습니다. 워커가 1분 안에 점검하고 결과가 아래에 표시됩니다.`);
      let n = 0;
      const timer = setInterval(() => {           // 결과 나올 때까지 잠깐 폴링
        n += 1; reload();
        if (n >= 12) { clearInterval(timer); setBusy(""); }
      }, 10000);
    } catch (e) {
      setMsg("연결 확인 요청 실패 — 아이디·비밀번호를 먼저 저장하세요.");
      setBusy("");
    }
  };

  const stateOf = (p: string) => {
    const c = checks[p];
    if (!c) return { cls: "none", txt: "확인한 적 없음" };
    if (c.status === "done") return { cls: "ok", txt: `정상 · ${c.result}` };
    if (c.status === "error") return { cls: "bad", txt: `문제 · ${c.result}` };
    return { cls: "wait", txt: "점검 중… (최대 1분)" };
  };

  return (
    <>
      <div className="sns-note">
        <b>쿠키 방식을 권장합니다.</b> 서버에서 아이디·비밀번호로 로그인하면 메타·X가
        “데이터센터 접속”으로 보고 <b>본인확인 화면</b>을 띄워 자동 로그인이 막힙니다(실제로 확인됨).
        내 PC 브라우저에서 이미 로그인한 <b>쿠키를 복사해 넣으면</b> 그 세션을 그대로 써서 이 절차를 건너뜁니다.
        <div style={{ marginTop: 8 }}>
          <b>쿠키 복사 방법</b> — 크롬에서 해당 사이트(인스타그램·스레드·X)에 로그인 →
          확장프로그램 <i>Cookie-Editor</i> 설치 → 사이트에서 확장 실행 → <b>Export → JSON</b> 복사 →
          아래 칸에 붙여넣기. (개발자도구 Network 탭의 <i>Cookie</i> 헤더 문자열도 그대로 붙여넣을 수 있습니다.)
        </div>
        비밀번호·쿠키는 서버 파일(권한 600)에만 저장되고 화면엔 마스킹으로만 보입니다. 빈칸은 기존 값 유지.
      </div>
      {PLATFORMS.map((p) => {
        const st = stateOf(p.key);
        return (
          <div className="sns-card" key={p.key}>
            <h3>{p.label}
              <span className={`sns-chk sns-chk-${st.cls}`}>{st.txt}</span>
            </h3>
            <div className="sns-saved">
              저장됨: {Object.keys(accounts[p.key] || {}).length
                ? Object.entries(accounts[p.key]).map(([k, v]) => `${k}=${v}`).join("  ")
                : "없음"}
              {checks[p.key]?.checked_at ? `   (마지막 확인 ${checks[p.key].checked_at?.slice(5, 16)})` : ""}
            </div>
            <div className="sns-form">
              <input placeholder="아이디 / 이메일" value={draft[p.key]?.username ?? ""}
                onChange={(e) => set(p.key, "username", e.target.value)} />
              <input type="password" placeholder="비밀번호" value={draft[p.key]?.password ?? ""}
                onChange={(e) => set(p.key, "password", e.target.value)} />
              <input placeholder="TOTP 시크릿 (2FA 사용 시, 선택)" value={draft[p.key]?.totp ?? ""}
                onChange={(e) => set(p.key, "totp", e.target.value)} />
              <button className="sns-primary" onClick={() => save(p.key)}>저장</button>
              <button onClick={() => test(p.key)} disabled={busy === p.key}>
                {busy === p.key ? "확인 중…" : "연결 확인"}
              </button>
              <button className="sns-del" onClick={async () => {
                if (!confirm(`${p.label} 계정 정보(아이디·비밀번호·쿠키)를 모두 지울까요?`)) return;
                await authFetch(`/admin/sns/accounts/${p.key}`, { method: "DELETE" });
                setDraft({ ...draft, [p.key]: {} });
                setMsg(`${p.label} 계정 정보를 삭제했습니다.`);
                reload();
              }}>계정 삭제</button>
            </div>
            <div className="sns-hint">
              비밀번호를 바꾸셨으면 <b>새 값을 입력하고 저장</b>하면 덮어씁니다(빈칸은 기존 값 유지).
              완전히 지우려면 <b>계정 삭제</b>를 쓰세요.
            </div>
            <textarea className="sns-cookie" rows={3}
              placeholder={`${p.label} 쿠키 붙여넣기 (권장) — Cookie-Editor의 JSON 또는 "sessionid=…; csrftoken=…" 형식`}
              value={draft[p.key]?.cookies ?? ""}
              onChange={(e) => set(p.key, "cookies", e.target.value)} />
          </div>
        );
      })}
    </>
  );
}

function QueueTab({ queue, reload }: { queue: QItem[]; reload: () => void }) {
  const badge = (s: string) => (
    <span className={`sns-st sns-st-${s}`}>
      {{ pending: "대기", sending: "발행중", done: "완료", error: "실패" }[s] || s}
    </span>
  );
  return (
    <div className="sns-card">
      <h3>발행 현황 <span className="muted">최근 {queue.length}건</span></h3>
      {queue.length === 0 ? <div className="muted">기록이 없습니다.</div> : (
        <table className="sns-tbl">
          <thead><tr><th>루틴</th><th>플랫폼</th><th>예정</th><th>상태</th><th>결과</th><th></th></tr></thead>
          <tbody>
            {queue.map((q) => (
              <tr key={q.id}>
                <td>{q.routine}</td>
                <td><b>{q.platform}</b></td>
                <td className="muted">{(q.run_at || "").slice(5, 16)}</td>
                <td>{badge(q.status)}</td>
                <td className="sns-res" title={q.caption}>{q.result || ""}</td>
                <td>{(q.status === "pending" || q.status === "error") && (
                  <button className="sns-del" onClick={async () => { await authFetch(`/admin/sns/queue/${q.id}`, { method: "DELETE" }); reload(); }}>삭제</button>
                )}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}


type EngCfg = {
  enabled: boolean; keywords: string[]; min_gap_sec: number; max_gap_sec: number;
  daily_limit: number; do_comment: boolean; today_count: number;
  do_follow: boolean; follow_limit: number; today_follow: number;
};
type EngLog = {
  id: number; keyword: string; author: string; post: string; liked: boolean;
  comment: string; status: string; detail: string; at: string; followed: boolean;
  verified: boolean; url: string;
};
type EngSummary = { total: number; liked: number; commented: number; followed: number;
                    verified: number; linked: number; mentioned: number };

/** 키워드로 최신글을 찾아 좋아요 + AI 댓글. 켜고 끄기와 기록 확인. */
function EngageTab({ setMsg }: { setMsg: (s: string) => void }) {
  const [cfg, setCfg] = useState<EngCfg | null>(null);
  const [logs, setLogs] = useState<EngLog[]>([]);
  const [sum, setSum] = useState<EngSummary | null>(null);
  const [kwText, setKwText] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    authFetch("/admin/sns/engage").then((j: EngCfg) => {
      setCfg(j); setKwText((j.keywords || []).join(", "));
    }).catch(() => {});
    authFetch("/admin/sns/engage/log?limit=40").then((j) => {
      setLogs(j.items || []); setSum(j.summary || null);
    }).catch(() => {});
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 30000);   // 동작 중 기록이 쌓이므로 주기 갱신
    return () => clearInterval(t);
  }, [load]);

  const save = async (patch: Partial<EngCfg> & { keywords?: string[] }) => {
    setBusy(true);
    try {
      const j = await authFetch("/admin/sns/engage", { method: "PUT", body: JSON.stringify(patch) });
      setCfg(j);
      setMsg(patch.enabled === true ? "반응 마케팅을 시작했습니다."
        : patch.enabled === false ? "반응 마케팅을 멈췄습니다." : "설정을 저장했습니다.");
      load();
    } catch { setMsg("저장 실패"); } finally { setBusy(false); }
  };

  if (!cfg) return <div className="sns-card">불러오는 중…</div>;
  const running = cfg.enabled;

  return (
    <>
      <div className="sns-card">
        <h3>반응 마케팅
          <span className={`sns-chk sns-chk-${running ? "ok" : "none"}`}>
            {running ? "작동 중" : "멈춤"}
          </span>
        </h3>
        <div className="sns-hint" style={{ marginTop: 0, marginBottom: 12 }}>
          키워드로 <b>최신글</b>을 찾아 좋아요를 누르고, AI가 글을 읽고 어울리는 댓글을 답니다.
          작성자 팔로우까지 할 수 있습니다(이미 팔로우 중이면 손대지 않아 <b>언팔로우는 일어나지 않습니다</b>).
          한 번에 키워드 1개·글 1건만 다루며, 아래 간격만큼 쉬었다가 다음 키워드로 넘어갑니다.
        </div>
        <div className="sns-form">
          <button className="sns-primary" disabled={busy}
            onClick={() => save({ enabled: !running })}
            style={running ? { background: "#d23b3b" } : undefined}>
            {running ? "■ 멈추기" : "▶ 시작하기"}
          </button>
          <span className="muted">
            오늘 반응 {cfg.today_count} / {cfg.daily_limit}건 · 팔로우 {cfg.today_follow} / {cfg.follow_limit}명
          </span>
        </div>
        {sum && sum.total > 0 && (
          <div className="sns-hint" style={{ marginBottom: 0 }}>
            최근 24시간 — 좋아요 <b>{sum.liked}</b> · 댓글 <b>{sum.commented}</b>
            (화면 확인 <b>{sum.verified}</b>) · 팔로우 <b>{sum.followed}</b> · 콕집 언급 <b>{sum.mentioned}</b>(주소 <b>{sum.linked}</b>)
            <span className="muted">
              {" "}· 댓글은 게시 후 글을 다시 읽어 실제로 붙었는지 확인한 것만 &lsquo;확인&rsquo;으로 셉니다.
            </span>
          </div>
        )}
      </div>

      <div className="sns-card">
        <h3>설정</h3>
        <div className="sns-sub">검색 키워드 <span className="muted">쉼표로 구분 · 순서대로 하나씩 돕니다</span></div>
        <div className="sns-form">
          <input value={kwText} onChange={(e) => setKwText(e.target.value)} style={{ minWidth: 380 }} />
          <button onClick={() => save({ keywords: kwText.split(",").map((x) => x.trim()).filter(Boolean) })}>
            키워드 저장
          </button>
        </div>

        <div className="sns-sub">반복 간격 · 하루 한도</div>
        <div className="sns-form">
          <label className="muted">최소
            <input type="number" min={60} step={30} value={cfg.min_gap_sec}
              onChange={(e) => setCfg({ ...cfg, min_gap_sec: Number(e.target.value) })}
              style={{ width: 90, marginLeft: 6 }} />초
          </label>
          <label className="muted">최대
            <input type="number" min={90} step={30} value={cfg.max_gap_sec}
              onChange={(e) => setCfg({ ...cfg, max_gap_sec: Number(e.target.value) })}
              style={{ width: 90, marginLeft: 6 }} />초
          </label>
          <label className="muted">하루 최대
            <input type="number" min={1} value={cfg.daily_limit}
              onChange={(e) => setCfg({ ...cfg, daily_limit: Number(e.target.value) })}
              style={{ width: 80, marginLeft: 6 }} />건
          </label>
          <label className="sns-plats" style={{ gap: 5 }}>
            <input type="checkbox" checked={cfg.do_comment}
              onChange={(e) => setCfg({ ...cfg, do_comment: e.target.checked })} />
            댓글까지 달기 (끄면 좋아요만)
          </label>
          <label className="sns-plats" style={{ gap: 5 }}>
            <input type="checkbox" checked={cfg.do_follow}
              onChange={(e) => setCfg({ ...cfg, do_follow: e.target.checked })} />
            작성자 팔로우
          </label>
          <label className="muted">팔로우 하루 최대
            <input type="number" min={0} value={cfg.follow_limit}
              onChange={(e) => setCfg({ ...cfg, follow_limit: Number(e.target.value) })}
              style={{ width: 70, marginLeft: 6 }} />명
          </label>
          <button onClick={() => save({
            min_gap_sec: cfg.min_gap_sec, max_gap_sec: cfg.max_gap_sec,
            daily_limit: cfg.daily_limit, do_comment: cfg.do_comment,
            do_follow: cfg.do_follow, follow_limit: cfg.follow_limit,
          })}>설정 저장</button>
        </div>
      </div>

      <div className="sns-card">
        <h3>최근 활동 <span className="muted">{logs.length}건</span></h3>
        {logs.length === 0 ? <div className="muted">아직 기록이 없습니다.</div> : (
          <table className="sns-tbl">
            <thead><tr><th>시각</th><th>키워드</th><th>상대</th><th>원글</th><th>내 댓글</th>
              <th>결과</th><th>링크</th></tr></thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id}>
                  <td className="muted">{(l.at || "").slice(5, 16)}</td>
                  <td>{l.keyword}</td>
                  <td>{l.url
                    ? <a href={l.url} target="_blank" rel="noreferrer">@{l.author}</a>
                    : `@${l.author}`}</td>
                  <td className="sns-res" title={l.post}>{l.post}</td>
                  <td className="sns-res" title={l.comment}>
                    {l.comment || "-"}
                    {l.comment && (
                      <span className={`sns-st sns-st-${l.verified ? "done" : "pending"}`}
                        style={{ marginLeft: 6 }}
                        title={l.verified ? "글을 다시 읽어 댓글이 붙은 것을 확인함" : "화면 확인이 안 된 건"}>
                        {l.verified ? "확인" : "미확인"}
                      </span>
                    )}
                  </td>
                  <td>
                    {l.liked && <span className="sns-on">♥</span>}{" "}
                    {l.followed && <span className="sns-on" title="팔로우함">＋</span>}{" "}
                    <span className={`sns-st sns-st-${l.status === "ok" ? "done" : "pending"}`}>
                      {l.status === "ok" ? "완료" : l.status === "skip" ? "건너뜀" : l.status}
                    </span>
                  </td>
                  <td>{l.url ? <a href={l.url} target="_blank" rel="noreferrer">글 열기</a>
                             : <span className="muted">-</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
