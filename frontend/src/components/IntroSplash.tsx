import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Send, BadgePercent, ShieldAlert, Award, LineChart, type LucideIcon } from "lucide-react";

// 앱(설치형/TWA) 첫 실행 때만 잠깐 스치는 인트로.
// 콕집 마크 → 화면이 위아래로 열리며 → 주요기능 블럭이 하나씩 쌓이며 안착 → 앱 진입.
const FEATS: { icon: LucideIcon; label: string }[] = [
  { icon: Send, label: "콕집요청" },
  { icon: BadgePercent, label: "급매찾기" },
  { icon: ShieldAlert, label: "빌라 깡통전세지수" },
  { icon: Award, label: "중개사 랭킹" },
  { icon: LineChart, label: "우리동네 시세" },
];

function shouldShow(): boolean {
  if (typeof window === "undefined") return false;
  try {
    if (new URLSearchParams(window.location.search).get("intro") === "1") return true; // 테스트용 강제
    // 안드로이드 '앱'(TWA/설치형)에서만 — 일반 모바일 브라우저·PC·iOS는 제외.
    const ua = navigator.userAgent || "";
    const isAndroid = /Android/i.test(ua);
    const twa = document.referrer.startsWith("android-app://");   // TWA 런치 시그널
    const standalone = (!!window.matchMedia && window.matchMedia("(display-mode: standalone)").matches);
    const isAndroidApp = twa || (isAndroid && standalone);
    return isAndroidApp && !sessionStorage.getItem("koczip_intro");
  } catch { return false; }
}

export default function IntroSplash() {
  const [show, setShow] = useState(shouldShow);

  useEffect(() => {
    if (!show) return;
    try { sessionStorage.setItem("koczip_intro", "1"); } catch { /* ignore */ }
    const t = setTimeout(() => setShow(false), 3400);   // 5블럭 쌓임 + 잠깐 머무름 후 진입
    return () => clearTimeout(t);
  }, [show]);

  if (!show) return null;
  return createPortal(
    <div className="intro" onClick={() => setShow(false)} role="presentation">
      {/* 패널이 열리면 드러나는 주요기능 안내 */}
      <div className="intro-reveal">
        <div className="intro-brand">
          <img src="/logo.svg" alt="" width={34} height={34} />
          <span>콕집</span>
        </div>
        <div className="intro-feats">
          {FEATS.map((f, i) => (
            <span key={f.label} className="intro-block" style={{ animationDelay: `${1.12 + i * 0.13}s` }}>
              <f.icon size={17} strokeWidth={2.2} aria-hidden /> {f.label}
            </span>
          ))}
        </div>
      </div>
      {/* 위아래로 열리는 브랜드 패널 */}
      <div className="intro-panel top" />
      <div className="intro-panel bottom" />
      {/* 처음 중앙에 뜨는 큰 마크 */}
      <div className="intro-logo">
        <img src="/logo.svg" alt="콕집" width={64} height={64} />
        <span>콕집</span>
      </div>
    </div>,
    document.body,
  );
}
