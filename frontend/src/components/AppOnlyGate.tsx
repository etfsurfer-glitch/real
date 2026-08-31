import type { ReactNode } from "react";
import { Smartphone } from "lucide-react";
import { isInstalledApp, STORE } from "../lib/appmode";

// 앱 전용 화면 게이트 — 콕집 앱(안드로이드 TWA / iOS Capacitor) 안에서만 children 을 보여준다.
// 앱이 아닌 브라우저에서 열면 내용 대신 '앱 설치 유도' 카드(양쪽 스토어)를 렌더한다.
// (이 게이트는 앱 안에서는 절대 렌더되지 않으므로, 여기서 양쪽 스토어를 노출해도 심사지침 2.3.10 무관.)
export default function AppOnlyGate({ title, desc, children }:
    { title?: string; desc?: ReactNode; children: ReactNode }) {
  if (isInstalledApp()) return <>{children}</>;
  return (
    <div className="appgate">
      <div className="appgate-box">
        <span className="appgate-ic"><Smartphone size={38} strokeWidth={1.7} aria-hidden /></span>
        <h2>{title || "앱에서만 열 수 있어요"}</h2>
        <p>{desc || <>이 화면은 <b>콕집 앱</b>에서만 이용할 수 있어요.<br />앱을 설치하고 다시 열어주세요.</>}</p>
        <div className="appgate-stores">
          <a className="store-btn ios" href={STORE.ios} target="_blank" rel="noreferrer" aria-label="App Store 에서 다운로드">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden>
              <path d="M16.37 1.43c0 1.14-.49 2.27-1.18 3.08-.74.9-1.99 1.57-2.99 1.57-.12 0-.23-.02-.3-.03-.01-.06-.04-.22-.04-.39 0-1.15.57-2.27 1.21-2.98.8-.94 2.14-1.64 3.25-1.68.03.13.05.28.05.43zM20.93 17.14c-.03.07-.46 1.58-1.52 3.12-.94 1.34-1.94 2.71-3.43 2.71-1.52 0-1.9-.88-3.63-.88-1.7 0-2.3.91-3.67.91-1.38 0-2.33-1.26-3.43-2.8-1.29-1.82-2.32-4.63-2.32-7.28 0-4.28 2.8-6.55 5.55-6.55 1.45 0 2.68.95 3.6.95.87 0 2.22-1.01 3.9-1.01.61 0 2.89.06 4.37 2.19-.13.09-2.38 1.37-2.38 4.19 0 3.26 2.85 4.42 2.96 4.45z" />
            </svg>
            <span><i>Download on the</i>App Store</span>
          </a>
          <a className="store-btn play" href={STORE.general} target="_blank" rel="noreferrer" aria-label="Google Play 에서 다운로드">
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden>
              <path fill="#00D2FF" d="M3.6 2.4c-.3.3-.5.8-.5 1.4v16.4c0 .6.2 1.1.5 1.4l.1.1L13 12.1v-.2L3.7 2.3l-.1.1z" />
              <path fill="#00E676" d="M16.3 15.3 13 12.1v-.2l3.3-3.3.1.1 3.9 2.2c1.1.6 1.1 1.7 0 2.3l-4 2.1z" />
              <path fill="#FF3D00" d="M16.4 15.2 13 11.9 3.6 21.6c.4.4 1 .4 1.7 0l11.1-6.4z" />
              <path fill="#FFC400" d="M16.4 8.7 5.3 2.4c-.7-.4-1.3-.4-1.7 0L13 11.9l3.4-3.2z" />
            </svg>
            <span><i>GET IT ON</i>Google Play</span>
          </a>
        </div>
        <p className="appgate-hint">이미 설치했다면 앱에서 이 메뉴를 열어주세요.</p>
      </div>
    </div>
  );
}
