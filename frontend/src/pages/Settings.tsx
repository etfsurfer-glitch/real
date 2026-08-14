import { useEffect, useState } from "react";
import { Bell, BellOff, Info, ExternalLink } from "lucide-react";
import { useAuth } from "../auth";
import {
  pushSupported, pushPermission, isPushSubscribed,
  acceptPush, disablePush,
} from "../lib/push";

// 앱 설정 — 지금은 알림 on/off 가 핵심. 계정 메뉴(로그인 필요)와 달리
// 비회원도 여기서 알림을 켜고 끌 수 있다(익명 구독 지원). 앱에서만 노출(App.tsx 가드).
export default function Settings() {
  const { token, user } = useAuth();
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const supported = pushSupported();
  const perm = pushPermission();

  useEffect(() => { isPushSubscribed().then(setOn); }, []);

  const toggle = async () => {
    setBusy(true); setMsg("");
    try {
      if (on) {
        await disablePush(token || "");
        setOn(false); setMsg("알림을 껐어요.");
      } else {
        const r = await acceptPush(token);           // 미로그인이면 익명 구독
        if (r.ok) { setOn(true); setMsg("알림을 켰어요. 신고가·급매 소식을 보내드려요."); }
        else setMsg(r.reason || "알림을 켜지 못했어요.");
      }
    } finally { setBusy(false); }
  };

  return (
    <div className="set-wrap">
      <h1>설정</h1>

      <section className="set-card">
        <h2>알림</h2>

        {!supported ? (
          <p className="set-note"><Info size={14} /> 이 기기에서는 알림을 지원하지 않아요.</p>
        ) : perm === "denied" ? (
          <p className="set-note">
            <Info size={14} /> 알림이 브라우저/시스템에서 차단돼 있어요.
            기기 설정 &gt; 앱 &gt; 콕집 &gt; 알림에서 허용해 주세요.
          </p>
        ) : (
          <button className={"set-toggle" + (on ? " on" : "")} onClick={toggle} disabled={busy}>
            <span className="set-toggle-ic">{on ? <Bell size={18} /> : <BellOff size={18} />}</span>
            <span className="set-toggle-body">
              <b>{on ? "알림 받는 중" : "알림 받기"}</b>
              <em>{on ? "누르면 알림을 끕니다" : "신고가·급매·관심단지 소식"}</em>
            </span>
            <span className={"set-switch" + (on ? " on" : "")}><i /></span>
          </button>
        )}

        {msg && <p className="set-msg">{msg}</p>}

        <p className="set-sub">
          {user
            ? "관심 단지를 찜하면 그 단지의 신고가·매물 변동을 매일 오전 10시·오후 4시에 알려드려요."
            : "로그인하지 않아도 오늘의 급매·신고가 소식을 받을 수 있어요. 로그인하면 관심 단지 알림까지 받아요."}
        </p>
      </section>

      <section className="set-card">
        <h2>정보</h2>
        <a className="set-link" href="/terms"><span>이용약관</span><ExternalLink size={15} /></a>
        <a className="set-link" href="/privacy"><span>개인정보처리방침</span><ExternalLink size={15} /></a>
      </section>

      <style>{`
.set-wrap{max-width:560px;margin:0 auto;padding:18px 14px 80px}
.set-wrap h1{font-size:21px;font-weight:800;color:var(--c-text,#18233a);margin:0 0 16px}
.set-card{background:var(--c-surface,#fff);border:1px solid var(--c-border,#e3e8ef);
  border-radius:16px;padding:16px;margin-bottom:14px}
.set-card h2{font-size:13px;font-weight:800;color:var(--c-text-soft,#8b95a5);margin:0 0 12px;
  letter-spacing:.02em}
.set-toggle{display:flex;align-items:center;gap:12px;width:100%;padding:12px;background:none;
  border:1.5px solid var(--c-border,#e3e8ef);border-radius:12px;cursor:pointer;text-align:left;
  transition:border-color .12s,background .12s}
.set-toggle.on{border-color:var(--c-primary,#1268d3);background:var(--c-primary-soft,#f4f9ff)}
.set-toggle:disabled{opacity:.6}
.set-toggle-ic{flex:none;display:flex;align-items:center;justify-content:center;width:40px;height:40px;
  border-radius:10px;background:var(--c-primary-soft,#eaf2fd);color:var(--c-primary,#1268d3)}
.set-toggle-body{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.set-toggle-body b{font-size:15px;font-weight:800;color:var(--c-text,#18233a)}
.set-toggle-body em{font-style:normal;font-size:12.5px;color:var(--c-text-soft,#5a6b80)}
.set-switch{flex:none;width:44px;height:26px;border-radius:999px;background:#cfd6e0;position:relative;
  transition:background .15s}
.set-switch.on{background:var(--c-primary,#1268d3)}
.set-switch i{position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;
  transition:left .15s;box-shadow:0 1px 3px rgba(0,0,0,.25)}
.set-switch.on i{left:21px}
.set-msg{margin:10px 2px 0;font-size:13px;color:var(--c-primary-strong,#0c4ea0);font-weight:600}
.set-note{display:flex;align-items:flex-start;gap:6px;margin:0;font-size:13px;line-height:1.5;
  color:var(--c-text-soft,#5a6b80)}
.set-sub{margin:12px 2px 0;font-size:12.5px;line-height:1.6;color:var(--c-text-soft,#8b95a5)}
.set-link{display:flex;align-items:center;justify-content:space-between;padding:12px 4px;
  font-size:14.5px;font-weight:600;color:var(--c-text,#33425a);text-decoration:none;
  border-bottom:1px solid var(--c-border,#eef2f7)}
.set-link:last-child{border-bottom:none}
.set-link:hover{color:var(--c-primary,#1268d3)}
.set-link svg{color:var(--c-text-soft,#a9b3c1)}
      `}</style>
    </div>
  );
}
