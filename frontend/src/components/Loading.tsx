// 데이터 호출 중 표시하는 공용 로딩 인디케이터.
// API 가 한 번에 응답해 실제 진행률을 알 수 없으므로, 움직이는 indeterminate
// 바로 "멈춘 게 아니라 불러오는 중"임을 알린다. 모든 페이지에서 재사용.
export function Loading({ label = "불러오는 중..." }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="loading-bar"><span /></div>
      <div className="loading-label">{label}</div>
    </div>
  );
}
