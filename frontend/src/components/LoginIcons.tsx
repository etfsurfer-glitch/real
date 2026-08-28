import { loginKakao, loginGoogle, loginApple, APPLE_LOGIN_ENABLED } from "../auth";

// 축소형 로그인 — '로그인' 라벨 + 브랜드 아이콘 버튼(카카오·구글·Apple).
// 3개 풀버튼이 헤더를 밀던 문제 해결: 마크로 즉시 인지, 클릭 1회로 로그인.
// 서비스명은 aria-label 로만(마크가 무엇인지 말해준다).

const Kakao = () => (
  <svg viewBox="0 0 24 24" aria-hidden width="20" height="20">
    <path fill="#3a1d1d" d="M12 3C6.48 3 2 6.36 2 10.5c0 2.66 1.8 5 4.51 6.32-.15.52-.97 3.36-1 3.59 0 0-.02.17.09.24.11.07.24.02.24.02.32-.05 3.74-2.45 4.33-2.87.59.08 1.2.13 1.83.13 5.52 0 10-3.36 10-7.5S17.52 3 12 3z" />
  </svg>
);
const Google = () => (
  <svg viewBox="0 0 48 48" aria-hidden width="19" height="19">
    <path fill="#4285F4" d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z" />
    <path fill="#34A853" d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z" />
    <path fill="#FBBC05" d="M11.69 28.18C11.25 26.86 11 25.45 11 24s.25-2.86.69-4.18v-5.7H4.34A21.99 21.99 0 0 0 2 24c0 3.55.85 6.91 2.34 9.88l7.35-5.7z" />
    <path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z" />
  </svg>
);
const Apple = () => (
  <svg viewBox="0 0 24 24" aria-hidden width="18" height="18">
    <path fill="#fff" d="M16.37 1.43c0 1.14-.49 2.27-1.18 3.08-.74.9-1.99 1.57-2.99 1.57-.12 0-.23-.02-.3-.03-.01-.06-.04-.22-.04-.39 0-1.15.57-2.27 1.21-2.98.8-.94 2.14-1.64 3.25-1.68.03.13.05.28.05.43zM20.93 17.14c-.03.07-.46 1.58-1.52 3.12-.94 1.34-1.94 2.71-3.43 2.71-1.52 0-1.9-.88-3.63-.88-1.7 0-2.3.91-3.67.91-1.38 0-2.33-1.26-3.43-2.8-1.29-1.82-2.32-4.63-2.32-7.28 0-4.28 2.8-6.55 5.55-6.55 1.45 0 2.68.95 3.6.95.87 0 2.22-1.01 3.9-1.01.61 0 2.89.06 4.37 2.19-.13.09-2.38 1.37-2.38 4.19 0 3.26 2.85 4.42 2.96 4.45z" />
  </svg>
);

export default function LoginIcons(
  { compact = false, label = "로그인" }: { compact?: boolean; label?: string | null },
) {
  return (
    <span className={`loginicons${compact ? " compact" : ""}`}>
      {label && <span className="loginicons-lbl">{label}</span>}
      <span className="loginicons-row">
        <button className="li-btn kakao" onClick={() => loginKakao()} aria-label="카카오로 로그인" title="카카오로 로그인"><Kakao /></button>
        <button className="li-btn google" onClick={() => loginGoogle()} aria-label="구글로 로그인" title="구글로 로그인"><Google /></button>
        {APPLE_LOGIN_ENABLED && (
          <button className="li-btn apple" onClick={() => loginApple()} aria-label="Apple로 로그인" title="Apple로 로그인"><Apple /></button>
        )}
      </span>
    </span>
  );
}
