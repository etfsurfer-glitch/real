import { MessageCircle } from "lucide-react";

// 콕집 고객센터 — 카카오톡 비즈니스 채널 1:1 채팅. 고객·협업 문의 공통 진입점.
// 인증이 막히는 지점(번호인증·중개사인증)·푸터·사용법 등 어디서든 재사용.
export const KAKAO_CS_URL = "https://pf.kakao.com/_ackPX/chat";

type Variant = "link" | "chip" | "button" | "banner";

export default function SupportLink({
  variant = "link",
  label = "고객센터",
  sub,
  context,
}: {
  variant?: Variant;
  label?: string;
  sub?: string;        // banner 변형의 앞 문구
  context?: string;    // 어디서 눌렀는지(분석용 쿼리) — 링크에만 부착, UI 영향 없음
}) {
  const href = KAKAO_CS_URL + (context ? `?ctx=${encodeURIComponent(context)}` : "");
  const common = { href, target: "_blank", rel: "noopener noreferrer" as const };

  if (variant === "banner") {
    return (
      <a {...common} className="cs-banner">
        <MessageCircle size={17} strokeWidth={2.3} aria-hidden />
        <span>{sub || "문제가 있으신가요?"} <b>{label}로 문의하기 →</b></span>
      </a>
    );
  }
  return (
    <a {...common} className={`cs-${variant}`}>
      <MessageCircle size={variant === "chip" ? 13 : 14} strokeWidth={2.3} aria-hidden />
      <span>{label}</span>
    </a>
  );
}
