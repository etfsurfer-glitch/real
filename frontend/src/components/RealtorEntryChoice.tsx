import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Home } from "lucide-react";
import { useAuth } from "../auth";

// 중개사 회원이 로그인했을 때 '어디로 갈지' 한 번만 묻는다.
//
// 왜 필요한가 — 중개사앱을 따로 내지 않고 한 앱에 담기로 했다(2026-08-14). 중개사는
// 손님용 화면과 업무용 라운지를 둘 다 쓰는데, 로그인할 때마다 홈에서 라운지를 찾아
// 들어가게 하면 매번 두 번 누르게 된다. 첫 로그인 때 정해두고 기억한다.
//
// 다시 바꾸고 싶으면 상단 메뉴의 '중개사라운지'로 언제든 오갈 수 있다 — 그래서
// 이 화면은 한 번만 뜨고, 되돌릴 수 없는 선택이 아니다.
const KEY = "koczip.entry.pref";          // "lounge" | "home"

export default function RealtorEntryChoice() {
  const { user, token } = useAuth();
  const nav = useNavigate();
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!token || !user?.isRealtorMember) return;
    // 홈에서만 묻는다 — 딥링크로 특정 화면에 들어온 사람을 가로막지 않는다.
    if (window.location.pathname !== "/") return;
    try {
      if (localStorage.getItem(KEY)) return;
    } catch { return; }        // 저장이 막힌 환경이면 아예 묻지 않는다(매번 뜨면 성가시다)
    setShow(true);
  }, [token, user?.isRealtorMember]);

  if (!show) return null;

  const pick = (v: "lounge" | "home") => {
    try { localStorage.setItem(KEY, v); } catch { /* 저장 실패해도 이동은 한다 */ }
    setShow(false);
    if (v === "lounge") nav("/lounge");
  };

  return (
    <div className="rec-back" role="dialog" aria-modal="true" aria-labelledby="rec-t">
      <div className="rec-card">
        <h2 id="rec-t">어디로 갈까요?</h2>
        <p>중개사 회원으로 확인됐어요. 자주 쓰는 쪽을 골라주세요.</p>
        <div className="rec-opts">
          <button type="button" onClick={() => pick("lounge")}>
            <span className="rec-ic"><Building2 size={22} strokeWidth={2} /></span>
            <b>중개사 라운지</b>
            <em>매물장·매물점검·상담·계약 일정</em>
          </button>
          <button type="button" onClick={() => pick("home")}>
            <span className="rec-ic"><Home size={22} strokeWidth={2} /></span>
            <b>일반 서비스</b>
            <em>실거래·급매·시세·단지 정보</em>
          </button>
        </div>
        <p className="rec-note">언제든 상단 메뉴에서 오갈 수 있어요.</p>
      </div>
      <style>{`
.rec-back{position:fixed;inset:0;z-index:1200;display:flex;align-items:center;
  justify-content:center;padding:20px;background:rgba(16,24,40,.55)}
.rec-card{width:100%;max-width:380px;background:var(--c-surface,#fff);border-radius:var(--r-lg,16px);
  box-shadow:var(--sh-lg,0 18px 48px rgba(16,24,40,.22));padding:22px 20px 18px}
.rec-card h2{margin:0 0 6px;font-size:19px;font-weight:800;color:var(--c-text,#18233a)}
.rec-card>p{margin:0 0 16px;font-size:13.5px;line-height:1.5;color:var(--c-text-soft,#5a6b80)}
.rec-opts{display:flex;flex-direction:column;gap:10px}
.rec-opts button{display:grid;grid-template-columns:auto 1fr;grid-template-rows:auto auto;
  gap:2px 12px;align-items:center;width:100%;padding:14px 14px;text-align:left;cursor:pointer;
  background:var(--c-surface,#fff);border:1.5px solid var(--c-border,#e3e8ef);
  border-radius:var(--r-md,12px);transition:border-color .15s,background .15s}
.rec-opts button:hover{border-color:var(--c-primary,#1268d3);background:var(--c-surface-soft,#f6f9fe)}
.rec-ic{grid-row:1/3;display:flex;align-items:center;justify-content:center;width:42px;height:42px;
  border-radius:var(--r-sm,10px);background:var(--c-primary-soft,#eaf2fd);color:var(--c-primary,#1268d3)}
.rec-opts b{font-size:15px;font-weight:800;color:var(--c-text,#18233a)}
.rec-opts em{font-style:normal;font-size:12.5px;color:var(--c-text-soft,#5a6b80)}
.rec-note{margin:14px 0 0;font-size:12px;color:var(--c-text-soft,#8b95a5);text-align:center}
      `}</style>
    </div>
  );
}
