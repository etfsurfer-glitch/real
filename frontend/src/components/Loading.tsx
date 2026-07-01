import { useEffect, useState } from "react";

// 데이터 호출 중 표시하는 공용 로딩 인디케이터.
// API 가 한 번에 응답해 실제 진행률을 알 수 없으므로, 움직이는 indeterminate
// 바로 "멈춘 게 아니라 불러오는 중"임을 알린다. 모든 페이지에서 재사용.
// slowHint: 로딩이 오래 걸릴 때(기본 2.5초 후) 아래에 보여줄 안내(예: "매물이 많으면 더 걸릴 수 있어요").
export function Loading({ label = "불러오는 중...", slowHint, slowAfterMs = 2500 }:
  { label?: string; slowHint?: string; slowAfterMs?: number }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!slowHint) return;
    const t = setTimeout(() => setSlow(true), slowAfterMs);
    return () => clearTimeout(t);
  }, [slowHint, slowAfterMs]);
  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="loading-bar"><span /></div>
      <div className="loading-label">{label}</div>
      {slow && slowHint && (
        <div className="loading-label" style={{ fontSize: 12, opacity: 0.75, marginTop: 2 }}>{slowHint}</div>
      )}
    </div>
  );
}
