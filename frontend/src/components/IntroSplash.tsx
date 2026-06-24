import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { BadgePercent, ShieldAlert, Award, LayoutDashboard, type LucideIcon } from "lucide-react";

// 앱(설치형/TWA) 첫 실행 때만 잠깐 스치는 인트로.
// 콕집 마크 → 화면이 위아래로 열리며 → 주요기능이 스치듯 보이고 → 앱 진입.
const FEATS: { icon: LucideIcon; label: string }[] = [
  { icon: BadgePercent, label: "급매찾기" },
  { icon: ShieldAlert, label: "빌라 깡통전세지수" },
  { icon: Award, label: "중개사 랭킹" },
  { icon: LayoutDashboard, label: "우리동네 시세" },
];

function shouldShow(): boolean {
  if (typeof window === "undefined") return false;
  try {
    if (new URLSearchParams(window.location.search).get("intro") === "1") return true; // 테스트용 강제
    const standalone = (navigator as unknown as { standalone?: boolean }).standalone === true
      || (!!window.matchMedia && window.matchMedia("(display-mode: standalone)").matches);
    return standalone && !sessionStorage.getItem("koczip_intro");
  } catch { return false; }
}

export default function IntroSplash() {
  const [show, setShow] = useState(shouldShow);

  useEffect(() => {
    if (!show) return;
    try { sessionStorage.setItem("koczip_intro", "1"); } catch { /* ignore */ }
    const t = setTimeout(() => setShow(false), 2250);
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
            <span key={f.label} className="intro-feat" style={{ animationDelay: `${1.18 + i * 0.09}s` }}>
              <f.icon size={15} /> {f.label}
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
