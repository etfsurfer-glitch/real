import { useState } from "react";
import { createPortal } from "react-dom";
import { Sparkles, Check, Clock3, X } from "lucide-react";
import { useAuth } from "../auth";

// 로그인 시 노출되는 업데이트 공지.
// 새 업데이트가 생기면 아래 UPDATE 만 갱신하면 됨 — version 이 바뀌면
// '다시 안보기'로 닫았던 사용자에게도 새 공지가 다시 노출된다.
const UPDATE = {
  version: "2026.07.11",
  date: "2026.07.11",
  done: [
    "매물검색 속도 개선",
    "매물정보 10% 추가 개선",
  ],
  upcoming: [
    "속도 추가 개선중",
  ],
};

const SEEN_KEY = `koczip_update_seen_${UPDATE.version}`;      // 영구(다시 안보기)
const CLOSED_KEY = `koczip_update_closed_${UPDATE.version}`;  // 세션(창닫기)

export default function UpdateNotice() {
  const { user, ready } = useAuth();
  const [show, setShow] = useState(true);

  // 로그인 사용자에게만, 아직 안 본 경우에만 노출
  if (!ready || !user || !show) return null;
  try {
    if (localStorage.getItem(SEEN_KEY)) return null;      // 다시 안보기
    if (sessionStorage.getItem(CLOSED_KEY)) return null;  // 이번 세션에 이미 닫음
  } catch { /* storage 접근 불가 시 그냥 노출 */ }

  const close = () => {
    try { sessionStorage.setItem(CLOSED_KEY, "1"); } catch { /* ignore */ }
    setShow(false);
  };
  const never = () => {
    try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* ignore */ }
    setShow(false);
  };

  return createPortal(
    <div className="upd-ov" onClick={close}>
      <div className="upd-card" onClick={(e) => e.stopPropagation()}>
        <button className="upd-x" onClick={close} aria-label="닫기"><X size={18} /></button>
        <div className="upd-head">
          <span className="upd-badge"><Sparkles size={14} strokeWidth={2.4} /> 업데이트</span>
          <span className="upd-date">{UPDATE.date}</span>
        </div>
        <h2 className="upd-title">이번 업데이트 소식</h2>

        <ul className="upd-list">
          {UPDATE.done.map((t, i) => (
            <li key={i} className="upd-item done">
              <span className="upd-ic done"><Check size={14} strokeWidth={3} /></span>
              <span>{t}</span>
            </li>
          ))}
        </ul>

        {UPDATE.upcoming.length > 0 && (
          <>
            <div className="upd-sec">업데이트 예정</div>
            <ul className="upd-list">
              {UPDATE.upcoming.map((t, i) => (
                <li key={i} className="upd-item soon">
                  <span className="upd-ic soon"><Clock3 size={13} strokeWidth={2.6} /></span>
                  <span>{t}</span>
                </li>
              ))}
            </ul>
          </>
        )}

        <div className="upd-btns">
          <button className="upd-btn ghost" onClick={never}>다시 안보기</button>
          <button className="upd-btn primary" onClick={close}>창닫기</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
