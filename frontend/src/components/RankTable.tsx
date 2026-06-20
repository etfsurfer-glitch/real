import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { tierOf } from "./LevelBadge";

// 백엔드 local_api.py RANKS 미러 — 누적 획득 포인트 임계값 기준 계급 사다리.
// (사용으로 잔액이 줄어도 계급은 누적 획득으로 유지)
export const RANKS: { name: string; points: number }[] = [
  { name: "부린이", points: 0 },       { name: "임장러", points: 200 },     { name: "동대표", points: 400 },
  { name: "관리소장", points: 700 },   { name: "단지대표", points: 1100 },  { name: "통장", points: 1600 },
  { name: "주민센터장", points: 2200 },{ name: "구청장", points: 3000 },    { name: "시장", points: 4000 },
  { name: "도지사", points: 8000 },    { name: "장관", points: 15000 },     { name: "국무총리", points: 26000 },
  { name: "국회의원", points: 45000 }, { name: "국회의장", points: 85000 }, { name: "대통령", points: 150000 },
  { name: "조물주", points: 300000 }, { name: "건물주", points: 500000 },  // 조물주 위에 건물주 — 최종 등급
];

// 계급표 모달. header(backdrop-filter)·계정 드롭다운 안에서 열려도 viewport
// 정중앙에 뜨도록 portal 로 document.body 에 렌더.
export function RankTableModal({ currentLevel, onClose }: { currentLevel: number; onClose: () => void }) {
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card rank-table-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">계급표</span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="rank-table">
          {RANKS.map((r, i) => (
            <div key={i} className={`rt-row${i === currentLevel ? " cur" : ""}`}>
              <span className={`lv-badge lv-${tierOf(i)}`}>Lv.{i}</span>
              <span className="rt-nm">{r.name}</span>
              <span className="rt-pt">{r.points.toLocaleString()}P</span>
            </div>
          ))}
        </div>
        <div className="rank-table-note">누적 획득 포인트 기준 · 포인트를 써도 계급은 유지됩니다</div>
      </div>
    </div>,
    document.body,
  );
}
