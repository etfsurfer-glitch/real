import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

// 포인트 적립 축하 토스트. auth가 누적포인트 증가를 감지해 발행하는
// 'koczip:points' 이벤트를 듣고 "축하합니다! +N P · 다음 레벨까지 M P" 를 띄운다.
type Toast = { id: number; delta: number; nextRank: string | null; nextRemaining: number | null };

export default function PointsToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  useEffect(() => {
    const onPts = (e: Event) => {
      const d = (e as CustomEvent).detail as Toast;
      if (!d || !d.delta) return;
      const id = ++idRef.current;
      setToasts((t) => [...t, { id, delta: d.delta, nextRank: d.nextRank, nextRemaining: d.nextRemaining }]);
      window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
    };
    window.addEventListener("koczip:points", onPts);
    return () => window.removeEventListener("koczip:points", onPts);
  }, []);

  if (!toasts.length) return null;

  return createPortal(
    <div className="pts-toast-wrap">
      {toasts.map((t) => (
        <div key={t.id} className="pts-toast">
          <div className="pts-toast-head">
            <span className="pts-emoji">🎉</span> 축하합니다! <b>+{t.delta.toLocaleString()}P</b> 받았어요
          </div>
          <div className="pts-toast-sub">
            {t.nextRemaining != null && t.nextRank
              ? <>다음 <b>{t.nextRank}</b>까지 <b>{t.nextRemaining.toLocaleString()}P</b> 남았어요</>
              : <>최고 등급에 도달했어요 👑</>}
          </div>
        </div>
      ))}
    </div>,
    document.body,
  );
}
