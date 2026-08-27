import type { ReactNode } from "react";
import { Smartphone, Download } from "lucide-react";
import { isInstalledApp, generalStoreUrl } from "../lib/appmode";

// 앱 전용 화면 게이트 — 콕집 안드로이드 앱(TWA) 안에서만 children 을 보여준다.
// 앱이 아닌 브라우저에서 열면 내용 대신 '앱 설치 유도' 카드를 렌더한다.
// (이벤트·쿠폰함처럼 앱 전용 기능을 감싸는 용도. 판별은 lib/appmode 의 referrer/standalone 신호.)
export default function AppOnlyGate({ title, desc, children }:
    { title?: string; desc?: ReactNode; children: ReactNode }) {
  if (isInstalledApp()) return <>{children}</>;
  const storeUrl = generalStoreUrl();   // iOS 웹에서는 빈 값(타 플랫폼 스토어 링크 미노출)
  return (
    <div className="appgate">
      <div className="appgate-box">
        <span className="appgate-ic"><Smartphone size={38} strokeWidth={1.7} aria-hidden /></span>
        <h2>{title || "앱에서만 열 수 있어요"}</h2>
        <p>{desc || <>이 화면은 <b>콕집 앱</b>에서만 이용할 수 있어요.<br />앱에서 다시 열어주세요.</>}</p>
        {storeUrl && (
          <a className="appgate-btn" href={storeUrl} target="_blank" rel="noreferrer">
            <Download size={17} strokeWidth={2.4} aria-hidden /> 콕집 앱 설치하기
          </a>
        )}
        <p className="appgate-hint">이미 설치했다면 앱에서 이 메뉴를 열어주세요.</p>
      </div>
    </div>
  );
}
