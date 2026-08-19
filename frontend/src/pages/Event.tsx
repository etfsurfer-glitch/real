import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Coffee, Candy, Check, ChevronRight, ShieldCheck } from "lucide-react";
import { useAuth, loginKakao } from "../auth";
import { isInstalledApp } from "../lib/appmode";
import AppOnlyGate from "../components/AppOnlyGate";
import { PhoneModal } from "../components/PhoneVerify";

const API = import.meta.env.VITE_API_BASE;

type Check = { label: string; done: boolean };
type Progress = { cur: number; goal: number } | { checks: Check[] };
type Mission = {
  key: string; title: string; desc: string;
  reward: "coffee" | "lollipop"; reward_label: string;
  done: boolean; claimed: boolean;
  progress: Progress | null;
};
type Status = { audience: "user" | "realtor"; missions: Mission[]; coupon_count: number };

// 도장(스탬프) 안에 찍히는 마크 — 보상 그대로. 커피 미션은 커피컵, 가입은 사탕.
function RewardMark({ reward, size = 20 }: { reward: string; size?: number }) {
  return reward === "coffee"
    ? <Coffee size={size} strokeWidth={2.2} aria-hidden />
    : <Candy size={size} strokeWidth={2.2} aria-hidden />;
}

export default function Event() {
  const { token, user, refreshMe } = useAuth();
  const [st, setSt] = useState<Status | null>(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [phoneOpen, setPhoneOpen] = useState(false);
  const phoneVerified = !!user?.phoneVerified;

  const load = useCallback(() => {
    if (!token || !isInstalledApp()) return;   // 앱 밖에서는 데이터 요청도 하지 않는다.
    fetch(`${API}/event/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then(setSt).catch(() => {});
    fetch(`${API}/event/attendance`, { method: "POST", headers: { Authorization: `Bearer ${token}` } })
      .catch(() => {});
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const claim = async (m: Mission) => {
    if (!token || busy) return;
    setBusy(m.key); setMsg("");
    try {
      const r = await fetch(`${API}/event/claim`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ mission_key: m.key }),
      });
      const d = await r.json();
      if (r.ok) { setMsg(`도장 완료 — ${m.reward_label} 쿠폰이 쿠폰함에 담겼어요`); load(); }
      else setMsg(d.detail || "잠시 후 다시 시도해주세요.");
    } finally { setBusy(""); }
  };

  const stampedCount = st ? st.missions.filter((m) => m.claimed).length : 0;

  return (
    <AppOnlyGate title="이벤트는 앱에서 참여해요"
      desc={<>커피·추파춥스 보상 이벤트는 <b>콕집 안드로이드 앱</b>에서만 참여할 수 있어요.<br />앱을 설치하고 다시 열어주세요.</>}>
    <div className="ev2">
      <div className="ev2-ticket">
        <div className="ev2-head">
          <span className="ev2-kicker">콕집 안드로이드 오픈 기념</span>
          <h1>미션 스탬프<br />커피 쿠폰</h1>
          <p className="ev2-lede">
            미션을 깨서 도장을 모으세요. <b>커피 최대 2잔</b>과 <b>추파춥스</b>가
            쿠폰함에 담겨요.
          </p>
          {st && (
            <div className="ev2-meta">
              <span className="ev2-aud">{st.audience === "realtor" ? "중개사 회원" : "일반 회원"}</span>
              <span className="ev2-count">도장 <b>{stampedCount}</b> / {st.missions.length}</span>
            </div>
          )}
        </div>

        <div className="ev2-perf" aria-hidden />

        {!token ? (
          <div className="ev2-login">
            <p>도장은 <b>로그인 후</b> 찍을 수 있어요.</p>
            <button className="ev2-kakao" onClick={loginKakao}>카카오로 로그인하고 시작</button>
          </div>
        ) : (
          <>
            {msg && <div className="ev2-msg">{msg}</div>}
            <ol className="ev2-stamps">
              {st?.missions.map((m, i) => {
                const state = m.claimed ? "done" : m.done ? "ready" : "todo";
                const bar = m.progress && "cur" in m.progress ? m.progress : null;    // {cur,goal}
                const checks = m.progress && "checks" in m.progress ? m.progress.checks : null;
                return (
                  <li key={m.key} className={`ev2-row ${state}`}>
                    <div className={`ev2-stamp ${m.reward}`}>
                      {m.claimed
                        ? <span className="ev2-inked"><RewardMark reward={m.reward} size={22} /></span>
                        : m.done
                          ? <RewardMark reward={m.reward} size={20} />
                          : <span className="ev2-no">{i + 1}</span>}
                    </div>
                    <div className="ev2-info">
                      <div className="ev2-mtitle">{m.title}</div>
                      <div className="ev2-mdesc">{m.desc}</div>
                      {m.key === "attend7" && state !== "done" && bar && (
                        <div className="ev2-days" aria-label={`7일 중 ${bar.cur}일 출석`}>
                          {Array.from({ length: bar.goal }, (_, d) => (
                            <span key={d} className={`ev2-day${d < bar.cur ? " on" : ""}`}>
                              {d < bar.cur ? <Check size={11} strokeWidth={3.4} /> : d + 1}
                            </span>
                          ))}
                        </div>
                      )}
                      {m.key !== "attend7" && bar && state === "todo" && (
                        <div className="ev2-prog">
                          <span className="ev2-prog-bar"><i style={{ width: `${(bar.cur / bar.goal) * 100}%` }} /></span>
                          <em>{bar.cur} / {bar.goal}</em>
                        </div>
                      )}
                      {checks && state !== "done" && (
                        <ul className="ev2-checks">
                          {checks.map((ch) => (
                            <li key={ch.label} className={ch.done ? "on" : ""}>
                              {ch.done
                                ? <Check size={12} strokeWidth={3.4} aria-hidden />
                                : <span className="ev2-check-o" aria-hidden />}
                              {ch.label}
                            </li>
                          ))}
                        </ul>
                      )}
                      {m.key === "signup" && state === "todo" && !phoneVerified && (
                        <div className="ev2-verify-note">
                          추파춥스는 <b>번호 인증</b>까지 완료해야 받을 수 있어요.
                        </div>
                      )}
                      <div className={`ev2-reward ${m.reward}`}>
                        <RewardMark reward={m.reward} size={12} /> {m.reward_label}
                      </div>
                    </div>
                    <div className="ev2-act">
                      {state === "done" && <span className="ev2-got"><Check size={13} strokeWidth={3} /> 완료</span>}
                      {state === "ready" && (
                        <button className="ev2-claim" disabled={busy === m.key} onClick={() => claim(m)}>
                          {busy === m.key ? "…" : "도장 받기"}
                        </button>
                      )}
                      {state === "todo" && (m.key === "signup" && !phoneVerified
                        ? <button className="ev2-verify-btn" onClick={() => setPhoneOpen(true)}>
                            <ShieldCheck size={13} strokeWidth={2.6} /> 번호 인증
                          </button>
                        : <span className="ev2-todo">진행 중</span>)}
                    </div>
                  </li>
                );
              })}
            </ol>

            <Link to="/me/coupons" className="ev2-coupon">
              내 쿠폰함{st?.coupon_count ? ` (${st.coupon_count})` : ""} 보기 <ChevronRight size={15} />
            </Link>
          </>
        )}
        {phoneOpen && token && (
          <PhoneModal
            token={token}
            onClose={() => setPhoneOpen(false)}
            onDone={async () => { await refreshMe(); setPhoneOpen(false); load(); }}
          />
        )}
      </div>

      <p className="ev2-note">
        · 추파춥스는 실물 상품으로, 앱 안내에 따라 별도 지급돼요.<br />
        · 커피 기프티콘은 미션 달성 시 쿠폰함에 담겨요 · 유효기간 30일.<br />
        · 본 이벤트는 콕집 앱 회원에게만 적용됩니다.
      </p>

      <style>{`
.ev2{max-width:520px;margin:0 auto;padding:14px 14px 90px}
.ev2-ticket{background:#fffdf8;border:1px solid #ece3d4;border-radius:20px;
  box-shadow:0 10px 34px rgba(60,42,20,.10);overflow:hidden}
.ev2-head{padding:24px 22px 20px;background:
  radial-gradient(140% 90% at 100% 0%, #fbf3e4 0%, #fffdf8 55%)}
.ev2-kicker{display:inline-block;font-size:11px;font-weight:800;letter-spacing:.04em;
  color:#b0741f;border:1px solid #e7c98f;border-radius:6px;padding:3px 8px;background:#fff7ea}
.ev2-head h1{font-size:27px;line-height:1.18;font-weight:900;letter-spacing:-.6px;
  color:#241d13;margin:13px 0 0}
.ev2-lede{font-size:12.8px;line-height:1.65;color:#6b5e49;margin:10px 0 0}
.ev2-lede b{color:#8a5320}
.ev2-meta{display:flex;align-items:center;gap:9px;margin-top:16px}
.ev2-aud{font-size:11.5px;font-weight:800;color:#1268d3;background:#eaf2fd;border-radius:999px;padding:5px 11px}
.ev2-count{font-size:12px;font-weight:700;color:#8a7a5f}
.ev2-count b{color:#241d13;font-weight:900}
/* 티켓 절취선 — 양옆 반원 노치 + 점선 */
.ev2-perf{position:relative;height:1px;margin:0 0;background:transparent}
.ev2-perf::before{content:"";position:absolute;top:-11px;left:0;bottom:auto;height:0;width:100%;
  border-top:2px dashed #e6dcc8}
.ev2-perf::after{content:"";position:absolute;left:-11px;right:-11px;top:-22px;height:22px;
  background:radial-gradient(circle at 0 11px,#f5eee0 11px,transparent 11px),
             radial-gradient(circle at 100% 11px,#f5eee0 11px,transparent 11px)}
.ev2-stamps{list-style:none;margin:0;padding:8px 16px 6px;display:flex;flex-direction:column}
.ev2-row{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:14px;
  padding:16px 4px;border-bottom:1px dashed #efe7d6}
.ev2-row:last-child{border-bottom:none}
/* 도장 자리 */
.ev2-stamp{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  flex:none;border:2px dashed #d9cdb4;color:#c3b590;background:#fffefb}
.ev2-row.ready .ev2-stamp{border:2px solid #1268d3;color:#1268d3;background:#f4f9ff;
  box-shadow:0 0 0 4px rgba(18,104,211,.10);animation:ev2pulse 1.6s ease-in-out infinite}
.ev2-row.done .ev2-stamp{border:none}
.ev2-no{font-size:17px;font-weight:900;color:#c3b590}
/* 찍힌 도장 — 잉크 링 + 살짝 기울어진 마크 */
.ev2-inked{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  color:#fff;background:#12508f;box-shadow:inset 0 0 0 3px rgba(255,255,255,.35);
  transform:rotate(-9deg);opacity:.94}
.ev2-info{min-width:0}
.ev2-mtitle{font-size:15px;font-weight:800;color:#241d13}
.ev2-row.done .ev2-mtitle{color:#8a7a5f}
.ev2-mdesc{font-size:12px;color:#8a7a5f;margin-top:2px}
.ev2-prog{display:flex;align-items:center;gap:8px;margin-top:9px}
.ev2-prog-bar{flex:1;max-width:140px;height:7px;border-radius:999px;background:#efe7d6;overflow:hidden}
.ev2-prog-bar i{display:block;height:100%;background:#1268d3;border-radius:999px;transition:width .3s}
.ev2-prog em{font-style:normal;font-size:11.5px;font-weight:800;color:#1268d3}
/* 7일 출석 도장 칸 */
.ev2-days{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.ev2-day{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:800;color:#c3b590;border:1.5px dashed #d9cdb4;background:#fffefb}
.ev2-day.on{color:#fff;border:1.5px solid #12508f;background:#12508f;transform:rotate(-8deg);
  box-shadow:inset 0 0 0 2px rgba(255,255,255,.35)}
/* 복합 미션 하위 달성 체크(중개사: 홈페이지·매물점검) */
.ev2-checks{list-style:none;margin:9px 0 0;padding:0;display:flex;flex-direction:column;gap:5px}
.ev2-checks li{display:flex;align-items:center;gap:7px;font-size:12.5px;font-weight:700;color:#a89a80}
.ev2-checks li.on{color:#1f7a4d}
.ev2-checks li svg{color:#1f7a4d}
.ev2-check-o{width:12px;height:12px;border-radius:50%;border:1.6px solid #d3c6ab;display:inline-block;flex:none}
.ev2-reward{display:inline-flex;align-items:center;gap:4px;margin-top:9px;font-size:11.5px;font-weight:800}
.ev2-reward.coffee{color:#8a5320}
.ev2-reward.lollipop{color:#c0396f}
.ev2-act{flex:none;text-align:right}
.ev2-claim{background:#1268d3;color:#fff;border:none;font-size:12.5px;font-weight:800;
  padding:9px 15px;border-radius:9px;cursor:pointer}
.ev2-claim:disabled{opacity:.5}
.ev2-got{display:inline-flex;align-items:center;gap:3px;font-size:12px;font-weight:800;color:#1f7a4d}
.ev2-todo{font-size:12px;font-weight:700;color:#b3a684}
.ev2-verify-btn{display:inline-flex;align-items:center;gap:4px;background:#12508f;color:#fff;border:none;
  font-size:12px;font-weight:800;padding:9px 13px;border-radius:9px;cursor:pointer;white-space:nowrap}
.ev2-verify-note{margin-top:8px;font-size:12px;font-weight:700;color:#b06a1f;
  background:#fbf1e0;border:1px solid #f0dcbb;border-radius:9px;padding:7px 11px;line-height:1.5}
.ev2-verify-note b{color:#8a5320}
.ev2-coupon{display:flex;align-items:center;justify-content:center;gap:3px;margin:6px 16px 18px;
  padding:12px;font-size:13px;font-weight:800;color:#1268d3;text-decoration:none;
  border-top:1px dashed #efe7d6}
.ev2-login{padding:26px 20px 24px;text-align:center}
.ev2-login p{font-size:14px;color:#4a4030;margin:0 0 14px}
.ev2-kakao{background:#FEE500;color:#181600;border:none;font-size:14px;font-weight:800;
  padding:12px 20px;border-radius:11px;cursor:pointer}
.ev2-appnote{font-size:12px;color:#9a8c72;margin-top:13px}
.ev2-msg{margin:12px 16px 0;background:#eef7f0;border:1px solid #bfe3c9;color:#1f7a4d;
  font-size:12.5px;font-weight:700;padding:10px 13px;border-radius:11px}
.ev2-note{font-size:11px;line-height:1.7;color:#9a8c72;margin:14px 6px 0}
@keyframes ev2pulse{0%,100%{box-shadow:0 0 0 4px rgba(18,104,211,.10)}50%{box-shadow:0 0 0 7px rgba(18,104,211,.04)}}
@media (prefers-reduced-motion:reduce){.ev2-row.ready .ev2-stamp{animation:none}}
      `}</style>
    </div>
    </AppOnlyGate>
  );
}
