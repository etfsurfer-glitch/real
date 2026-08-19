import type { CapacitorConfig } from "@capacitor/cli";

// 콕집 iOS 앱(App Store) — PWA(dist)를 Capacitor WKWebView 로 감싼 네이티브 셸.
// API 는 https://api.koczip.com 로 별도 호출. 안드로이드는 별도 TWA(twa/) 라 여기 대상 아님.
const config: CapacitorConfig = {
  appId: "com.koczip.app",     // iOS 번들 ID(안드로이드 패키지와 같은 리버스도메인 사용 — 네임스페이스 별개라 무방)
  appName: "콕집",
  webDir: "dist",              // vite 빌드 산출물을 번들(오프라인·심사 4.2 유리). 원격로드 원하면 server.url 지정.
  ios: {
    // 웹앱이 'iOS 콕집 앱 안'인지 판별하는 신호(UA 꼬리표) — lib/appmode 가 감지.
    appendUserAgent: "KoczipApp/iOS",
    contentInset: "always",    // 노치·다이내믹아일랜드 안전영역 대응(웹은 viewport-fit=cover 로 이미 처리)
  },
  server: {
    // 원격 로드 필수 — 카카오맵 JS SDK 는 도메인 잠금(https://koczip.com)이라 로컬 번들의
    // capacitor:// origin 에선 타일이 403 으로 막혀 지도가 안 뜬다. 실제 https origin 을 얻으려면
    // 원격 사이트를 로드해야 한다(웹 변경이 앱 재제출 없이 즉시 반영되는 이점도 있음).
    // appendUserAgent(KoczipApp/iOS)는 원격 사이트에서도 적용돼 isInstalledApp() 판별이 동작한다.
    url: "https://koczip.com",
  },
  plugins: {
    SplashScreen: { launchShowDuration: 600, backgroundColor: "#1268d3", showSpinner: false },
  },
};

export default config;
