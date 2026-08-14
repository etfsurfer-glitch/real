import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Bell } from "lucide-react";
import { useAuth } from "../auth";
import { currentEndpoint } from "../lib/push";

const API = import.meta.env.VITE_API_BASE;

// 헤더 종 아이콘 + 안읽음 배지. /me/alerts 의 unread 만 가볍게 폴링한다.
// endpoint 기준이라 로그인 안 해도 이 기기가 받은 알림의 안읽음 수를 보여준다.
export default function AlertBell() {
  const { token } = useAuth();
  const [unread, setUnread] = useState(0);

  const poll = useCallback(async () => {
    if (!API) return;
    const ep = await currentEndpoint();
    if (!ep && !token) { setUnread(0); return; }   // 구독도 로그인도 없으면 알림 자체가 없음
    const qs = new URLSearchParams({ limit: "1" });
    if (ep) qs.set("endpoint", ep);
    try {
      const r = await fetch(`${API}/me/alerts?${qs}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const d = await r.json();
      setUnread(d.unread || 0);
    } catch { /* 무시 */ }
  }, [token]);

  useEffect(() => {
    poll();
    // 앱으로 돌아왔을 때(알림 눌러 진입 포함) 즉시 갱신 + 완만한 폴링.
    const onVis = () => { if (document.visibilityState === "visible") poll(); };
    document.addEventListener("visibilitychange", onVis);
    const t = setInterval(poll, 90_000);
    return () => { document.removeEventListener("visibilitychange", onVis); clearInterval(t); };
  }, [poll]);

  return (
    <Link to="/alerts" className="alert-bell" aria-label={`알림${unread ? ` ${unread}건 안읽음` : ""}`}>
      <Bell size={19} strokeWidth={2.2} />
      {unread > 0 && <span className="alert-bell-badge">{unread > 99 ? "99+" : unread}</span>}
      <style>{`
.alert-bell{position:relative;display:inline-flex;align-items:center;justify-content:center;
  width:38px;height:38px;border-radius:10px;color:var(--c-text,#33425a);text-decoration:none}
.alert-bell:hover{background:var(--c-surface-soft,#f2f6fc);color:var(--c-primary,#1268d3)}
.alert-bell-badge{position:absolute;top:4px;right:3px;min-width:16px;height:16px;padding:0 4px;
  display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;line-height:1;
  color:#fff;background:#e6376e;border-radius:999px;box-shadow:0 0 0 2px var(--c-surface,#fff)}
      `}</style>
    </Link>
  );
}
