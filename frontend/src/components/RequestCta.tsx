import { Link } from "react-router-dom";
import { Lock } from "lucide-react";

/** 콕집요청 유도 배너 — 화면마다 보고 있던 조건을 그대로 넘겨준다.
 *  같은 문구를 여기 한 곳에서만 관리해, 화면마다 말이 달라지지 않게 한다.
 *
 *  이 기능의 값어치는 '조건을 남기면 매물을 찾아준다'가 아니라 '그러면서 내 번호는
 *  넘어가지 않는다'에 있다. 그래서 배지로 그 사실을 먼저 세우고 제목·본문이 뒤를
 *  받친다. 배지와 '연락처는 넘기지 않아요' 문장은 화면에서 못 바꾸게 고정해 둔다. */
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
  // ★ 자르지 말 것. 요청 페이지의 지역 드롭다운은 10자리 cortar 코드(1168000000)로 고르는데
  //   2·5자리를 넘기면 어느 항목과도 안 맞아 지역이 통째로 비어 들어간다(실측).
  if (sido) p.set("sido", sido);
  if (sigungu) p.set("sigungu", sigungu);
  if (dong) p.set("dong", dong);
  if (asset) p.set("asset", asset);
  if (trade) p.set("trade", trade);
  if (area) p.set("area", area);
  const to = `/request${p.toString() ? `?${p}` : ""}`;

  return (
    <div className={`rcta${compact ? " rcta-compact" : ""}`}>
      <div className="rcta-txt">
        <span className="rcta-badge"><Lock size={12} strokeWidth={2.9} aria-hidden /> 내 번호 비공개</span>
        <b>{title || "조건만 남기면 매물을 보내드려요"}</b>
        <p className="rcta-sub">
          {sub || "이 동네 중개사무소가 조건에 맞는 매물을 찾아 제안합니다."}{" "}
          <i>연락처는 넘기지 않아요.</i> 받은 제안 중 마음에 드는 곳에만 직접 전화하시면 됩니다.
        </p>
      </div>
      {/* 버튼 문구는 메뉴·내 요청함·문자 안내와 같은 '콕집요청'으로 맞춘다 —
          여기서만 다른 말을 쓰면 나중에 메뉴에서 이 기능을 못 찾는다. */}
      <Link className="rcta-btn" to={to}>콕집요청 보내기</Link>
    </div>
  );
}
