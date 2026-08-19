import { useEffect, useState, useCallback, type MouseEvent } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Bell, Home, TrendingUp, Tag, MessageSquare, Megaphone, Check, ChevronDown, ChevronRight } from "lucide-react";
import { useAuth } from "../auth";
import { currentEndpoint } from "../lib/push";

const API = import.meta.env.VITE_API_BASE;

type Alert = {
  id: number; title: string; body: string; url: string; tag: string;
  icon?: string; read: boolean; created_at: string;
};

// 알림 종류(tag)별 아이콘 — 한눈에 무슨 알림인지 알 수 있게.
function tagIcon(tag: string) {
  if (tag.startsWith("fav")) return Home;            // 관심단지
  if (tag.includes("general") || tag === "daily-general") return Megaphone;  // 오늘의 급매·신고가
  if (tag.includes("offer") || tag.includes("req")) return MessageSquare;    // 콕집요청
  if (tag.includes("high")) return TrendingUp;       // 신고가
  if (tag.includes("deal")) return Tag;              // 급매
  return Bell;
}

// "8/14 16:00" / "어제" / "3일 전" 같은 상대 표기.
function when(s: string): string {
  const t = new Date(s.replace(" ", "T"));
  if (isNaN(t.getTime())) return s.slice(5, 16);
  const now = new Date();
  const diffH = (now.getTime() - t.getTime()) / 3.6e6;
  if (diffH < 1) return "방금";
  if (diffH < 24 && now.getDate() === t.getDate()) return `오늘 ${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
  const days = Math.floor(diffH / 24);
  if (days === 1) return "어제";
  if (days < 7) return `${days}일 전`;
  return `${t.getMonth() + 1}/${t.getDate()}`;
}

export default function Alerts() {
  const { token } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [items, setItems] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [endpoint, setEndpoint] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());   // 펼쳐서 전체 내용을 보는 알림 id

  const load = useCallback(async () => {
    if (!API) { setLoading(false); return; }
    const ep = await currentEndpoint();
    setEndpoint(ep);
    const qs = new URLSearchParams();
    if (ep) qs.set("endpoint", ep);
    try {
      const r = await fetch(`${API}/me/alerts?${qs}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const d = await r.json();
      setItems(d.items || []);
    } catch { /* 무시 */ }
    setLoading(false);
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const markAllRead = async () => {
    setItems((xs) => xs.map((x) => ({ ...x, read: true })));
    try {
      await fetch(`${API}/me/alerts/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ all: true, endpoint }),
      });
      window.dispatchEvent(new Event("koczip:alerts-changed"));   // 헤더 종 배지 즉시 갱신
    } catch { /* 무시 */ }
  };

  const markRead = (a: Alert) => {
    if (a.read) return;
    try {
      fetch(`${API}/me/alerts/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ id: a.id, endpoint }),
      });
      setItems((xs) => xs.map((x) => (x.id === a.id ? { ...x, read: true } : x)));
      window.dispatchEvent(new Event("koczip:alerts-changed"));   // 헤더 종 배지 즉시 갱신
    } catch { /* 무시 */ }
  };

  // 알림을 누르면 전체 내용을 펼친다(리스트는 2줄로 잘리므로). 다시 누르면 접힘.
  // 관심단지 여러 개가 한 줄로 이어진 긴 알림도 여기서 온전히 볼 수 있다.
  const toggle = (a: Alert) => {
    markRead(a);
    setExpanded((s) => {
      const next = new Set(s);
      if (next.has(a.id)) next.delete(a.id); else next.add(a.id);
      return next;
    });
  };

  // 펼친 알림의 '바로가기' — 해당 화면으로 이동(내부는 SPA, 외부는 그대로).
  const go = (a: Alert, e: MouseEvent) => {
    e.stopPropagation();
    if (a.url.startsWith("/")) nav(a.url);
    else window.location.href = a.url;
  };

  const unread = items.filter((x) => !x.read).length;

  return (
    <div className="alerts-wrap">
      <div className="alerts-head">
        <h1><Bell size={20} strokeWidth={2.2} /> 알림</h1>
        {unread > 0 && (
          <button className="alerts-readall" onClick={markAllRead}>
            <Check size={15} /> 모두 읽음
          </button>
        )}
      </div>

      {loading ? (
        <div className="alerts-empty">불러오는 중…</div>
      ) : items.length === 0 ? (
        <div className="alerts-empty">
          <Bell size={40} strokeWidth={1.6} />
          <p>아직 받은 알림이 없어요.</p>
          <span>관심 단지를 찜하거나 알림을 켜면 신고가·급매 소식을 보내드려요.</span>
        </div>
      ) : (
        <ul className="alerts-list">
          {items.map((a) => {
            const Icon = tagIcon(a.tag);
            const isOpen = expanded.has(a.id);
            // 목적지가 없거나(빈값), 홈(기본값)이거나, 지금 보고 있는 페이지면 '바로가기'를 숨긴다
            // — 눌러도 제자리라 '반응 없는 버튼'처럼 보이는 걸 막는다.
            const dest = (a.url || "").split("?")[0].split("#")[0];
            const hasDest = !!a.url && a.url !== "/" && dest !== loc.pathname;
            return (
              <li key={a.id} className={"alert-item" + (a.read ? "" : " unread") + (isOpen ? " open" : "")}
                  onClick={() => toggle(a)}>
                <span className="alert-ic"><Icon size={18} strokeWidth={2} /></span>
                <div className="alert-body">
                  <div className="alert-title">{a.title}{!a.read && <em className="alert-dot" />}</div>
                  <div className={"alert-text" + (isOpen ? " expanded" : "")}>{a.body}</div>
                  <div className="alert-time">{when(a.created_at)}</div>
                  {isOpen && hasDest && (
                    <button className="alert-go" onClick={(e) => go(a, e)}>
                      바로가기 <ChevronRight size={14} strokeWidth={2.4} />
                    </button>
                  )}
                </div>
                <ChevronDown size={16} strokeWidth={2.2} className={"alert-caret" + (isOpen ? " up" : "")} />
              </li>
            );
          })}
        </ul>
      )}

      <style>{`
.alerts-wrap{max-width:640px;margin:0 auto;padding:16px 14px 80px}
.alerts-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.alerts-head h1{display:flex;align-items:center;gap:8px;font-size:20px;font-weight:800;color:var(--c-text,#18233a);margin:0}
.alerts-readall{display:inline-flex;align-items:center;gap:4px;font-size:13px;font-weight:700;
  color:var(--c-primary,#1268d3);background:var(--c-primary-soft,#eaf2fd);border:none;
  border-radius:999px;padding:7px 13px;cursor:pointer}
.alerts-readall:hover{background:#dcebfb}
.alerts-empty{display:flex;flex-direction:column;align-items:center;gap:8px;text-align:center;
  padding:64px 20px;color:var(--c-text-soft,#8b95a5)}
.alerts-empty p{margin:8px 0 0;font-size:15px;font-weight:700;color:var(--c-text,#5a6b80)}
.alerts-empty span{font-size:13px;line-height:1.5;max-width:280px}
.alerts-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.alert-item{display:flex;gap:12px;padding:14px;background:var(--c-surface,#fff);
  border:1px solid var(--c-border,#e3e8ef);border-radius:14px;cursor:pointer;
  transition:border-color .12s,background .12s}
.alert-item:hover{border-color:var(--c-primary,#1268d3)}
.alert-item.unread{background:var(--c-primary-soft,#f4f9ff);border-color:#cfe2fb}
.alert-item.open{border-color:var(--c-primary,#1268d3);box-shadow:0 4px 14px rgba(18,104,211,.08)}
.alert-ic{flex:none;display:flex;align-items:center;justify-content:center;width:38px;height:38px;
  border-radius:10px;background:var(--c-primary-soft,#eaf2fd);color:var(--c-primary,#1268d3)}
.alert-body{min-width:0;flex:1}
.alert-title{display:flex;align-items:center;gap:6px;font-size:14.5px;font-weight:800;color:var(--c-text,#18233a)}
.alert-dot{width:7px;height:7px;border-radius:50%;background:#e6376e;flex:none}
.alert-text{font-size:13px;line-height:1.5;color:var(--c-text-soft,#5a6b80);margin-top:3px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.alert-text.expanded{display:block;overflow:visible;-webkit-line-clamp:unset;
  white-space:pre-wrap;word-break:break-word;color:var(--c-text,#33425a)}
.alert-time{font-size:11.5px;color:var(--c-text-soft,#a9b3c1);margin-top:5px}
.alert-go{display:inline-flex;align-items:center;gap:3px;margin-top:10px;padding:7px 13px;
  font-size:13px;font-weight:800;color:#fff;background:var(--c-primary,#1268d3);
  border:none;border-radius:9px;cursor:pointer}
.alert-go:hover{background:var(--c-primary-strong,#0c4ea0)}
.alert-caret{flex:none;align-self:center;color:var(--c-text-soft,#b3bdcc);transition:transform .15s}
.alert-caret.up{transform:rotate(180deg);color:var(--c-primary,#1268d3)}
      `}</style>
    </div>
  );
}
