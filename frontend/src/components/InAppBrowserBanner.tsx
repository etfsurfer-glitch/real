import { useEffect, useState } from "react";

// 인앱 브라우저(카카오톡 등 웹뷰) 차단 게이트.
// 웹뷰에서는 구글 로그인 등이 정책상 막히거나, OAuth가 외부 브라우저로 핸드오프되며
// 세션이 안 잡히므로, 기본 브라우저로 이동해야만 이용 가능하도록 전체화면으로 가로막는다.
type Kind = "kakaotalk" | "android-inapp" | "ios-inapp" | null;

function detectInApp(): Kind {
  if (typeof navigator === "undefined") return null;
  const ua = navigator.userAgent || "";
  // 네이버 앱 인앱 브라우저는 로그인이 정상 작동 → 외부브라우저 안내 게이트 제외(사용자 요청).
  if (/NAVER\(/i.test(ua)) return null;
  if (/KAKAOTALK/i.test(ua)) return "kakaotalk";
  // 이름이 알려진 인앱 앱들 (안드/iOS 공통)
  const named = /(Instagram|FBAN|FBAV|FB_IAB|Line\/|DaumApps|Band\/|KAKAOSTORY|Snapchat|wadiz|coupang|TossApp|Threads)/i.test(ua);
  const ios = /iPhone|iPad|iPod/i.test(ua);
  if (ios) {
    // iOS는 WKWebView에 "; wv)" 마커가 없다. 정식 브라우저(Safari/Chrome/Firefox/Edge)는
    // UA에 Safari·CriOS·FxiOS·EdgiOS 중 하나를 포함 → 그게 전혀 없으면 인앱 웹뷰로 본다.
    const standalone = (navigator as unknown as { standalone?: boolean }).standalone === true
      || (typeof window !== "undefined" && !!window.matchMedia && window.matchMedia("(display-mode: standalone)").matches);
    const realBrowser = /Safari/i.test(ua) || /CriOS|FxiOS|EdgiOS/i.test(ua);
    if (!standalone && (named || !realBrowser)) return "ios-inapp";
    return null;
  }
  // 안드로이드: 이름 있는 인앱 또는 일반 웹뷰("; wv)")
  if (named || /;\s*wv\)/i.test(ua)) return "android-inapp";
  return null;
}

const HOUSE_SVG =
  `<svg width="44" height="44" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">` +
  `<path d="M 50 10 L 92 46 L 92 92 L 8 92 L 8 46 Z" fill="#1268d3"/>` +
  `<path d="M 28 58 L 44 73 L 74 42" stroke="#fff" stroke-width="11" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`;

const SKIP_KEY = "koczip_inapp_skip";

export default function InAppBrowserBanner() {
  const kind = detectInApp();
  const url = typeof window !== "undefined" ? window.location.href : "";
  const [skipped, setSkipped] = useState(() => {
    try { return sessionStorage.getItem(SKIP_KEY) === "1"; } catch { return false; }
  });

  const openExternal = () => {
    if (kind === "kakaotalk") {
      window.location.href = "kakaotalk://web/openExternal?url=" + encodeURIComponent(url);
    } else if (kind === "android-inapp") {
      const noScheme = url.replace(/^https?:\/\//, "");
      window.location.href =
        "intent://" + noScheme + "#Intent;scheme=https;package=com.android.chrome;end";
    } else {
      alert("화면 우측 상단 메뉴(··· 또는 공유)에서 'Safari로 열기' 또는 '다른 브라우저로 열기'를 선택해주세요.");
    }
  };

  // 진입 즉시 외부 브라우저로 자동 전환 시도(실패 시 아래 버튼이 폴백).
  // - 카카오톡: 전용 스킴 / - 안드로이드 일반 인앱(쓰레드 등): intent 스킴으로 Chrome 자동 오픈.
  // - iOS 인앱: OS 정책상 자동 전환 불가 → 게이트 버튼/안내로만 처리.
  useEffect(() => {
    if (kind === "kakaotalk") {
      window.location.href = "kakaotalk://web/openExternal?url=" + encodeURIComponent(url);
    } else if (kind === "android-inapp") {
      const noScheme = url.replace(/^https?:\/\//, "");
      window.location.href =
        "intent://" + noScheme + "#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=" +
        encodeURIComponent(url) + ";end";
    }
  }, [kind, url]);

  if (!kind || skipped) return null;

  const skip = () => { try { sessionStorage.setItem(SKIP_KEY, "1"); } catch { /* ignore */ } setSkipped(true); };

  return (
    <div className="inapp-gate">
      <div className="inapp-gate-box">
        <span className="inapp-gate-logo" dangerouslySetInnerHTML={{ __html: HOUSE_SVG }} />
        <h2>기본 브라우저에서 열어주세요</h2>
        <p>
          카카오톡 등 인앱 브라우저에서는 <b>구글 로그인이 풀리거나 일부 기능이 제한</b>됩니다.
          아래 버튼을 눌러 <b>기본 브라우저(Chrome/Safari)</b>에서 이용해 주세요.
        </p>
        <button className="inapp-gate-btn" onClick={openExternal}>기본 브라우저로 열기</button>
        {kind === "ios-inapp" && (
          <p className="inapp-gate-hint">
            버튼이 안 되면 화면 우측 상단 <b>···</b>(또는 공유 아이콘) → <b>'Safari로 열기'</b>를 눌러주세요.
          </p>
        )}
        <button className="inapp-gate-skip" onClick={skip}>로그인 없이 이 화면에서 계속 둘러보기</button>
      </div>
    </div>
  );
}
