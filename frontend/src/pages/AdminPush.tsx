import { useEffect, useState, useCallback } from "react";
import { Bell, Send, Users } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

export default function AdminPush() {
  const { token } = useAuth();
  const [stats, setStats] = useState<{ subscriptions: number; users: number; configured: boolean } | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [url, setUrl] = useState("/");
  const [target, setTarget] = useState("all");
  const [uid, setUid] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");

  const load = useCallback(() => {
    if (!token || !API) return;
    fetch(`${API}/admin/push/stats`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then(setStats).catch(() => {});
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const send = async () => {
    if (!title.trim() || !body.trim()) { setResult("제목·내용을 입력하세요."); return; }
    setBusy(true); setResult("");
    const tgt = target === "user" ? `user:${uid.trim()}` : "all";
    try {
      const r = await fetch(`${API}/admin/push/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: title.trim(), body: body.trim(), url: url.trim() || "/", target: tgt }),
      });
      const d = await r.json();
      setResult(r.ok ? `발송 완료 — 대상 ${d.targets}명 / 성공 ${d.sent} / 실패 ${d.failed ?? 0} / 정리 ${d.pruned ?? 0}` : `실패: ${d.detail || r.status}`);
    } catch (e) { setResult("발송 오류"); }
    setBusy(false);
  };

  return (
    <div className="apush">
      <h2><Bell size={20} strokeWidth={2.3} aria-hidden /> 푸시 알림 발송</h2>
      <div className="apush-stat">
        <span><Users size={14} /> 구독자 <b>{stats?.users ?? "—"}</b>명 · 기기 <b>{stats?.subscriptions ?? "—"}</b>대</span>
        {stats && !stats.configured && <span style={{ color: "#b91c1c" }}> · ⚠ VAPID 미설정</span>}
      </div>

      <label className="apush-l">제목</label>
      <input className="apush-in" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="예: 콕집 새 기능 안내" maxLength={60} />
      <label className="apush-l">내용</label>
      <textarea className="apush-ta" value={body} onChange={(e) => setBody(e.target.value)} placeholder="알림 본문" maxLength={180} rows={3} />
      <label className="apush-l">클릭 시 이동 URL</label>
      <input className="apush-in" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="/ (예: /complex/12345)" />

      <label className="apush-l">대상</label>
      <div className="apush-target">
        <label><input type="radio" checked={target === "all"} onChange={() => setTarget("all")} /> 전체 구독자</label>
        <label><input type="radio" checked={target === "user"} onChange={() => setTarget("user")} /> 특정 사용자(uid)</label>
      </div>
      {target === "user" && <input className="apush-in" value={uid} onChange={(e) => setUid(e.target.value)} placeholder="Supabase user_id" />}

      <button className="apush-send" onClick={send} disabled={busy}>
        <Send size={15} strokeWidth={2.3} /> {busy ? "발송 중…" : "발송"}
      </button>
      {result && <div className="apush-result">{result}</div>}
      <p className="apush-note">발송 즉시 켜진 기기로 도착합니다. 만료된 구독은 자동 정리됩니다.</p>
    </div>
  );
}
