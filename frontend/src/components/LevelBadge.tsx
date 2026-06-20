// 계급을 직관적 레벨 숫자(Lv.0~)로 표시. 제일 낮은 부린이=Lv.0.
// 기존 오브젝트 이모지(🐣👟🧰…) 대신 "누가 더 높은지" 바로 보이는 숫자 뱃지 +
// 그 아래에 등급명(관리소장 등)을 세로로 함께 표기.
export const tierOf = (lv: number) =>
  lv >= 12 ? "gold" : lv >= 9 ? "violet" : lv >= 6 ? "blue" : lv >= 3 ? "green" : "bronze";

export function LevelBadge({ level, rank, className = "" }: {
  level?: number | null; rank?: string | null; className?: string;
}) {
  if (level == null) return null;
  return (
    <span className={`lv-badge-wrap ${className}`}>
      <span className={`lv-badge lv-${tierOf(level)}`}>Lv.{level}</span>
      {rank && <span className="lv-name">{rank}</span>}
    </span>
  );
}
