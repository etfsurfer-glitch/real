import { useState } from "react";
import { createPortal } from "react-dom";
import { useAuth } from "../auth";

// 랜딩 이스터에그 — 누구나 보지만 빌드 스탬프처럼 지나치는 4글자.
// 전화인증(phoneVerified) 회원에게만 금빛으로 빛나고 클릭 가능. 이벤트 때 EGG만 바꾸면 됨.
const EGG = "KZ6F";

export default function EasterEgg() {
  const { user } = useAuth();
  const live = !!user?.phoneVerified;
  const [open, setOpen] = useState(false);

  return (
    <>
      <span
        className={`egg${live ? " egg-live" : ""}`}
        onClick={live ? () => setOpen(true) : undefined}
        role={live ? "button" : undefined}
        aria-hidden={!live}
      >{EGG}</span>

      {open && createPortal(
        <div className="egg-modal" onClick={() => setOpen(false)}>
          <div className="egg-card" onClick={(e) => e.stopPropagation()}>
            <div className="egg-spark">✦</div>
            <h3>인증 회원님께만 보이는 신호</h3>
            <p>
              방금 빛난 <b>{EGG}</b>를 발견하셨네요.<br />
              전화인증을 마친 분에게만 보이는 표식이에요.
            </p>
            <div className="egg-code">이벤트 코드 · <b>{EGG}</b></div>
            <p className="egg-note">이 화면을 캡처해 이벤트 안내에 따라 참여해 주세요.</p>
            <button onClick={() => setOpen(false)}>닫기</button>
          </div>
        </div>, document.body)}
    </>
  );
}
