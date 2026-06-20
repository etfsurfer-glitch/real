import { useEffect, useRef, useState } from "react";
import { ChevronDown, ShieldCheck, ShieldAlert, LogOut, BadgeCheck, Gift, ListOrdered, Bell, BellOff } from "lucide-react";
import { useAuth, logout } from "../auth";
import { PhoneModal } from "./PhoneVerify";
import { LevelBadge } from "./LevelBadge";
import { RankTableModal } from "./RankTable";
import { copyText } from "../lib/share";
import { enablePush, disablePush, isPushSubscribed, pushSupported } from "../lib/push";

// 로그인 사용자 계정 메뉴 — 회원번호·전화인증 상태 표시, 인증/취소/로그아웃.
export default function AccountMenu() {
  const { user, token, refreshMe, isAdmin } = useAuth();
  const [open, setOpen] = useState(false);
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [rankOpen, setRankOpen] = useState(false);
  const [inviteMsg, setInviteMsg] = useState("");
  const [pushOn, setPushOn] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushMsg, setPushMsg] = useState("");
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => { isPushSubscribed().then(setPushOn); }, [open]);
  const togglePush = async () => {
    setPushBusy(true); setPushMsg("");
    if (pushOn) { await disablePush(token || ""); setPushOn(false); setPushMsg("알림을 껐어요."); }
    else {
      const r = await enablePush(token || "");
      if (r.ok) { setPushOn(true); setPushMsg("알림을 켰어요. 관심단지·상담 알림을 받아요."); }
      else setPushMsg(r.reason || "켜기 실패");
    }
    setPushBusy(false);
    window.setTimeout(() => setPushMsg(""), 3500);
  };

  const copyInvite = async () => {
    const link = `${window.location.origin}/?ref=${user?.memberNo}`;
    const ok = await copyText(link);
    setInviteMsg(ok ? "복사됨!" : "복사 실패");
    window.setTimeout(() => setInviteMsg(""), 1800);
  };

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (!user || !token) return null;
  const verified = !!user.phoneVerified;

  return (
    <div className="acct" ref={wrapRef}>
      <button className="acct-trigger" onClick={() => setOpen((v) => !v)}>
        {user.avatar
          ? <img className="auth-avatar" src={user.avatar} alt="" />
          : <span className="auth-avatar acct-avatar-ph" />}
        <span className="auth-name">{user.nickname || user.name}</span>
        {verified && <BadgeCheck size={14} className="acct-verified-ic" aria-label="인증 회원" />}
        <ChevronDown size={14} strokeWidth={2.2} />
      </button>

      {open && (
        <div className="acct-pop">
          <div className="acct-head">
            <div className="acct-name">{user.nickname || user.name}</div>
            {user.nickname && <div className="acct-email">{user.name}{user.email ? ` · ${user.email}` : ""}</div>}
            {!user.nickname && user.email && <div className="acct-email">{user.email}</div>}
            {user.memberNo != null && (
              <div className="acct-member">회원번호 <b>#{user.memberNo}</b></div>
            )}
          </div>

          {(
            <div className="acct-rank">
              <div className="acct-rank-top">
                <span className="rank-lvgroup">
                  <span className="rank-badge">
                    {isAdmin
                      ? <span className="admin-badge">관리자</span>
                      : <LevelBadge level={user.level ?? 0} rank={user.rank ?? "부린이"} />}
                  </span>
                  <button className="rank-table-btn" title="계급표 보기"
                    aria-label="계급표 보기" onClick={() => setRankOpen(true)}>
                    <ListOrdered size={13} strokeWidth={2.2} />
                  </button>
                </span>
                <span className="acct-points"><b>{(user.points ?? 0).toLocaleString()}</b> P</span>
              </div>
              {!isAdmin && user.nextRank && user.nextAt != null && (
                <>
                  <div className="acct-rank-bar">
                    <span style={{ width: `${Math.min(100, Math.round(((user.earned ?? 0) / user.nextAt) * 100))}%` }} />
                  </div>
                  <div className="acct-rank-next">다음 <LevelBadge level={(user.level ?? 0) + 1} rank={user.nextRank} /> 까지 {(user.nextRemaining ?? Math.max(0, user.nextAt - (user.earned ?? 0))).toLocaleString()}P</div>
                </>
              )}
            </div>
          )}

          {verified && user.memberNo != null && (
            <button className="acct-item primary" onClick={copyInvite}>
              <Gift size={13} strokeWidth={2.2} /> 친구 초대 링크 복사 {inviteMsg && <span className="acct-flash">{inviteMsg}</span>}
            </button>
          )}

          <div className={`acct-phone ${verified ? "ok" : "no"}`}>
            {verified ? (
              <>
                <ShieldCheck size={15} strokeWidth={2.2} />
                <div>
                  <div className="acct-phone-t">전화번호 인증됨</div>
                  {user.phone && <div className="acct-phone-n">{user.phone}</div>}
                </div>
              </>
            ) : (
              <>
                <ShieldAlert size={15} strokeWidth={2.2} />
                <div className="acct-phone-t">전화번호 미인증</div>
              </>
            )}
          </div>

          {!verified && (
            <button className="acct-item primary" onClick={() => { setOpen(false); setVerifyOpen(true); }}>
              전화번호 인증하기
            </button>
          )}

          {pushSupported() && (
            <button className="acct-item" onClick={togglePush} disabled={pushBusy}>
              {pushOn ? <BellOff size={13} strokeWidth={2.2} /> : <Bell size={13} strokeWidth={2.2} />}
              {pushBusy ? "처리 중…" : pushOn ? "알림 끄기" : "알림 켜기 (관심단지·상담)"}
            </button>
          )}
          {pushMsg && <div className="acct-pushmsg">{pushMsg}</div>}

          <button className="acct-item danger" onClick={() => logout()}>
            <LogOut size={13} strokeWidth={2.2} /> 로그아웃
          </button>

          <div className="acct-legal">
            <a href="/terms">이용약관</a>
            <span className="sep">·</span>
            <a href="/privacy">개인정보처리방침</a>
            <div className="acct-legal-biz">
              런투온라인 · 대표 황인찬 · 문의 runtoonline@gmail.com
            </div>
          </div>
        </div>
      )}

      {verifyOpen && (
        <PhoneModal
          token={token}
          onClose={() => setVerifyOpen(false)}
          onDone={async () => { await refreshMe(); setVerifyOpen(false); }}
        />
      )}

      {rankOpen && (
        <RankTableModal
          currentLevel={isAdmin ? -1 : (user.level ?? 0)}
          onClose={() => setRankOpen(false)}
        />
      )}
    </div>
  );
}
