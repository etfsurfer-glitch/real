import { useEffect, useState } from "react";

// 인앱 브라우저(카카오톡 등)에서 열렸을 때 외부 브라우저로 '자동' 전환 시도.
// 홈페이지(중개사/공개)는 인앱에서도 열람 가능하므로 차단 게이트는 두지 않고,
// - 안드로이드: openExternal/intent 로 버튼 없이 바로 외부 브라우저로(성공률 높음)
// - iOS: OS 정책상 자동 불가 → 하단 안내바만(닫기 가능)
function detect(ua: string): { kakao: boolean; ios: boolean; androidInapp: boolean } {
  const ios = /iPhone|iPad|iPod/i.test(ua);
  const kakao = /KAKAOTALK/i.test(ua);
  const androidInapp = !ios && /(; wv\)|Instagram|FBAN|FBAV|FB_IAB|Line\/|NAVER\(|DaumApps)/i.test(ua);
  return { kakao, ios, androidInapp };
}

export default function InAppAutoExternal() {
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  const url = typeof window !== "undefined" ? window.location.href : "";
  const { kakao, ios, androidInapp } = detect(ua);
  const inIOSInapp = ios && (kakao || /Instagram|FBAN|FBAV|Line\/|NAVER\(|DaumApps/i.test(ua));
  const [hint, setHint] = useState(false);

  useEffect(() => {
    if (kakao) {
      // 카카오톡: 외부 브라우저 자동 전환(안드로이드 즉시 동작, iOS는 미동작 가능)
      window.location.href = "kakaotalk://web/openExternal?url=" + encodeURIComponent(url);
      if (ios) { const t = setTimeout(() => setHint(true), 1300); return () => clearTimeout(t); }
    } else if (androidInapp) {
      const noScheme = url.replace(/^https?:\/\//, "");
      window.location.href = "intent://" + noScheme + "#Intent;scheme=https;package=com.android.chrome;end";
    } else if (inIOSInapp) {
      setHint(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!hint) return null;
  return (
    <div style={{ position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 90, background: "#13294b",
      color: "#fff", padding: "12px 16px", fontSize: 13, display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ flex: 1 }}>더 편하게 보려면 우측 상단 <b>···</b> → <b>‘Safari로 열기’</b>를 눌러주세요.</span>
      <button onClick={() => setHint(false)} aria-label="닫기"
        style={{ background: "none", border: "none", color: "#aebbcf", fontSize: 18, cursor: "pointer" }}>×</button>
    </div>
  );
}
