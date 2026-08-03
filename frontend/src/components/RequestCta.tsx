import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";

/** 콕집요청 유도 배너 — 화면마다 보고 있던 조건을 그대로 넘겨준다.
 *  같은 문구를 여기 한 곳에서만 관리해, 화면마다 말이 달라지지 않게 한다. */
export default function RequestCta({
  title, sub, q, sido, sigungu, dong, asset, trade, area, compact,
}: {
  title?: string;
  sub?: string;
  q?: string;                       // AI 질문 원문(있으면 조건 자동 해석)
  sido?: string; sigungu?: string; dong?: string;
  asset?: string; trade?: string; area?: string;
  compact?: boolean;                // 목록 사이에 끼울 때 쓰는 좁은 형태
}) {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (sido) p.set("sido", sido.slice(0, 2));
  if (sigungu) p.set("sigungu", sigungu.slice(0, 5));
  if (dong) p.set("dong", dong.slice(0, 10));
  if (asset) p.set("asset", asset);
  if (trade) p.set("trade", trade);
  if (area) p.set("area", area);
  const to = `/request${p.toString() ? `?${p}` : ""}`;

  return (
    <div className={`rcta${compact ? " rcta-compact" : ""}`}>
      <div className="rcta-txt">
        <b><Sparkles size={15} strokeWidth={2.4} aria-hidden /> {title || "찾는 조건을 남겨 보세요"}</b>
        <span>{sub || "그 동네 중개사무소가 조건에 맞는 매물을 찾아 연락드려요. 무료입니다."}</span>
      </div>
      <Link className="rcta-btn" to={to}>콕집요청 보내기</Link>
    </div>
  );
}
