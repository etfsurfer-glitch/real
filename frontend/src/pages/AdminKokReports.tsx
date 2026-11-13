import { useCallback, useEffect, useState } from "react";
import { Flag, CheckCircle2 } from "lucide-react";
import { useAuth } from "../auth";
import { Loading } from "../components/Loading";

const API = import.meta.env.VITE_API_BASE;

// 콕집매물 허위매물 신고 — 매물별로 묶어 보고, 매물 보류(소비자 화면에서 내림)·보류 풀기·신고 처리/기각.
// 중개사에게 따로 연락하지 않는다(시험 중). 보류하면 등록자 라운지에 '신고 확인 중'으로 보인다.
type Rep = { id: number; lid: string; reason: string; reason_label: string; detail: string | null; member: number; status: string; created_at: string };
type Target = { found: boolean; src?: string; name?: string; complex_no?: string; office?: string; price_text?: string; status?: string;
  publish_state?: string; held?: boolean; dong?: string; floor?: number | null; addr?: string };
type Group = { lid: string; reports: Rep[]; last_at: string; target: Target; n_total: number };
type Resp = { groups: Group[]; counts: Record<string, number> };

const ST_L: Record<string, string> = { open: "미처리", done: "처리함", rejected: "기각" };
const LST_L: Record<string, string> = { active: "게시 중", closed: "내림", sold: "거래완료", expired: "만료", blocked: "차단", deleted: "삭제" };

export default function AdminKokReports() {
  const { token } = useAuth();
  const [status, setStatus] = useState("open");
  const [data, setData] = useState<Resp | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const H = { Authorization: `Bearer ${token}` };

  const load = useCallback(() => {
    if (!API || !token) return;
    setErr("");
    fetch(`${API}/admin/kok/reports?status=${status}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setData).catch((e) => setErr(String(e)));
  }, [token, status]);
  useEffect(() => { load(); }, [load]);

  const post = async (key: string, url: string, body: object) => {
    setBusy(key);
    try {
      const r = await fetch(`${API}${url}`, { method: "POST", headers: { "Content-Type": "application/json", ...H }, body: JSON.stringify(body) });
      if (!r.ok) throw new Error(await r.text());
      load();
    } catch (e) { setErr("실패: " + String(e).slice(0, 140)); } finally { setBusy(""); }
  };
  const setRep = (id: number, st: string) => post(`r${id}`, `/admin/kok/reports/${id}/status`, { status: st });
  const hold = (lid: string, action: "hold" | "release") => post(`h${lid}`, `/admin/kok/listing/${lid}/hold`, { action });

  if (!API) return <div className="muted">로컬 API 미설정</div>;
  if (err && !data) return <div style={{ color: "crimson", padding: 20 }}>오류: {err}</div>;
  if (!data) return <Loading />;

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "18px 16px 60px" }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, margin: "4px 0 4px", display: "flex", alignItems: "center", gap: 7 }}>
        <Flag size={20} /> 허위매물 신고
      </h1>
      <p style={{ color: "var(--c-muted)", fontSize: 13.5, margin: "0 0 12px" }}>
        콕집매물 상세의 '허위매물 신고'로 들어온 것. 매물을 보류하면 소비자 화면에서 바로 내려가고, 등록자 라운지에는 '신고 확인 중'으로 보여요.
        보류는 매일 다시 계산해도 풀리지 않고 여기서 '보류 풀기'로만 풀려요. 중개사에게 따로 연락하지 않아요.
      </p>
      <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        {(["open", "done", "rejected", "all"] as const).map((s) => (
          <button key={s} className={`nv-btn${status === s ? " on" : ""}`} style={status === s ? { fontWeight: 700 } : undefined} onClick={() => setStatus(s)}>
            {s === "all" ? "전체" : ST_L[s]} {s === "all" ? "" : `${data.counts[s] ?? 0}`}
          </button>
        ))}
        {err && <span style={{ color: "crimson", fontSize: 13 }}>{err}</span>}
      </div>

      {data.groups.length === 0 && (
        <div className="muted" style={{ padding: 16, display: "flex", alignItems: "center", gap: 6 }}>
          <CheckCircle2 size={14} style={{ color: "#1a7f4b" }} aria-hidden /> 해당 신고 없음
        </div>
      )}

      {data.groups.map((g) => {
        const t = g.target;
        return (
          <div key={g.lid} className="vw-card" style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
              <div>
                <b>{t.found ? t.name || "(이름 없음)" : "매물 없음(지워짐)"}</b>{" "}
                <span className="muted" style={{ fontSize: 12 }}>{g.lid}{t.src ? ` · ${t.src}` : ""}</span>
                {t.found && (
                  <div className="muted" style={{ fontSize: 13 }}>
                    {[t.price_text, t.dong ? `${t.dong}동` : "", t.floor ? `${t.floor}층` : "", t.addr, t.office].filter(Boolean).join(" · ")}
                  </div>
                )}
                {t.found && (
                  <div style={{ fontSize: 12, marginTop: 2 }}>
                    <span className="ctx-badge">{LST_L[t.status || ""] || t.status}</span>{" "}
                    {t.held ? <span className="ctx-badge" style={{ background: "#fde8e8", color: "#c0392b" }}>운영자 보류</span>
                      : t.publish_state === "hold" ? <span className="ctx-badge">게시 전(필수 항목)</span>
                      : <span className="ctx-badge" style={{ background: "#e8f6ee", color: "#1a7f4b" }}>소비자 노출</span>}
                    {" "}<span className="muted">신고 누적 {g.n_total}건</span>
                  </div>
                )}
              </div>
              {t.found && (
                <div style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                  {t.complex_no && <a className="nv-btn" href={`/complex/${t.complex_no}`} target="_blank" rel="noreferrer">단지 보기</a>}
                  {t.held
                    ? <button className="nv-btn" disabled={!!busy} onClick={() => hold(g.lid, "release")}>보류 풀기</button>
                    : <button className="nv-btn" style={{ color: "#c0392b" }} disabled={!!busy} onClick={() => hold(g.lid, "hold")}>매물 보류(내리기)</button>}
                </div>
              )}
            </div>
            <div style={{ marginTop: 8, borderTop: "1px solid var(--c-border)" }}>
              {g.reports.map((r) => (
                <div key={r.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "6px 0", fontSize: 13, flexWrap: "wrap" }}>
                  <span style={{ minWidth: 92 }} className="muted">{r.created_at.slice(5, 16)}</span>
                  <b style={{ minWidth: 150 }}>{r.reason_label}</b>
                  <span style={{ flex: 1, minWidth: 160 }}>{r.detail || <span className="muted">내용 없음</span>}</span>
                  <span className="muted" style={{ fontSize: 12 }}>{r.member ? "회원" : "비회원"} · {ST_L[r.status] || r.status}</span>
                  {r.status === "open" ? (
                    <>
                      <button className="nv-btn" disabled={!!busy} onClick={() => setRep(r.id, "done")}>처리함</button>
                      <button className="nv-btn" disabled={!!busy} onClick={() => setRep(r.id, "rejected")}>기각</button>
                    </>
                  ) : (
                    <button className="nv-btn" disabled={!!busy} onClick={() => setRep(r.id, "open")}>미처리로</button>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
