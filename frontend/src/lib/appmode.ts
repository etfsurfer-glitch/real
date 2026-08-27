// 어느 앱에서 실행 중인지 판별 — 일반앱(com.koczip.app) / 중개사앱(com.koczip.realtor) / 브라우저.
// TWA는 실행 시 document.referrer 에 "android-app://<패키지명>" 을 넣어준다(가장 신뢰성 높은 신호).
// SPA 클라이언트 이동은 referrer 를 바꾸지 않으므로 세션 내내 유효 → 모듈 변수에만 캐시.
// (localStorage 는 두 앱이 같은 koczip.com origin 을 공유하면 값이 섞일 수 있어 쓰지 않는다.)
export type AppMode = "general" | "realtor" | "browser";

let _cached: AppMode | null = null;

export function appMode(): AppMode {
  if (_cached) return _cached;
  let m: AppMode = "browser";
  try {
    const ua = (typeof navigator !== "undefined" && navigator.userAgent) || "";
    // iOS 콕집 앱(Capacitor WKWebView) — capacitor.config.ts 의 appendUserAgent 꼬리표로 판별.
    if (ua.includes("KoczipApp/iOS")) { _cached = "general"; return _cached; }
    const ref = (typeof document !== "undefined" && document.referrer) || "";
    if (ref.startsWith("android-app://com.koczip.realtor")) m = "realtor";
    else if (ref.startsWith("android-app://com.koczip.app")) m = "general";
    else {
      // referrer 유실(하드리로드 등) 폴백: 설치형(standalone)이면 시작 경로로 추정.
      const standalone = typeof window !== "undefined" && !!window.matchMedia
        && window.matchMedia("(display-mode: standalone)").matches;
      if (standalone) {
        m = (typeof location !== "undefined" && location.pathname.startsWith("/biz")) ? "realtor" : "general";
      }
    }
  } catch { /* SSR·차단 환경 — browser 로 */ }
  _cached = m;
  return m;
}

export const isGeneralApp = () => appMode() === "general";
export const isRealtorApp = () => appMode() === "realtor";
export const isInstalledApp = () => appMode() !== "browser";
// iOS 콕집 앱(Capacitor WKWebView) 여부 — 타 플랫폼 스토어 링크 노출 차단용(심사지침 2.3.10).
export const isIOSApp = () =>
  typeof navigator !== "undefined" && /KoczipApp\/iOS/.test(navigator.userAgent);

// 스토어 링크 — 앱 미게시 상태에선 설치 페이지가 준비중일 수 있으나 게시 즉시 연결된다.
export const STORE = {
  general: "https://play.google.com/store/apps/details?id=com.koczip.app&hl=ko",
  realtor: "https://play.google.com/store/apps/details?id=com.koczip.realtor&hl=ko",
  ios: "",   // TODO: App Store 게시 후 https://apps.apple.com/app/id{APP_ID} 로 교체
};

// 기기 플랫폼에 맞는 일반앱 스토어 링크. iOS Safari 는 App Store, 그 외는 Play.
// (iOS 앱 미게시 동안 STORE.ios 가 비어 있으면 Play 로 폴백 — 게시 후 STORE.ios 채우면 자동 전환.)
export function generalStoreUrl(): string {
  try {
    const ua = navigator.userAgent || "";
    // iOS 는 App Store 만 안내(미게시 시 빈 값 → 타 플랫폼 스토어 링크를 노출하지 않는다, 심사지침 2.3.10).
    if (/iPhone|iPad|iPod/i.test(ua)) return STORE.ios;
  } catch { /* SSR */ }
  return STORE.general;
}
