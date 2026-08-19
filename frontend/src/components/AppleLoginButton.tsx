import { APPLE_LOGIN_ENABLED, loginApple } from "../auth";

// Apple 로그인 버튼 — App Store 심사지침 4.8(소셜로그인 제공 시 애플 로그인 동등 제공) 대응.
// Apple HIG: 검정 배경·흰 애플 로고·"Apple로 로그인". Supabase Apple provider 설정 전엔 숨김.
export default function AppleLoginButton({ className = "", label = "Apple로 로그인", style }:
    { className?: string; label?: string; style?: React.CSSProperties }) {
  if (!APPLE_LOGIN_ENABLED) return null;
  return (
    <button className={`auth-btn apple ${className}`} style={style} onClick={() => loginApple()} aria-label="Apple로 로그인">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M17.05 12.04c-.03-2.6 2.12-3.85 2.22-3.91-1.21-1.77-3.09-2.02-3.76-2.05-1.6-.16-3.12.94-3.93.94-.81 0-2.06-.92-3.39-.9-1.74.03-3.35 1.01-4.25 2.57-1.81 3.14-.46 7.79 1.3 10.34.86 1.25 1.89 2.65 3.23 2.6 1.3-.05 1.79-.84 3.36-.84 1.57 0 2.01.84 3.39.81 1.4-.02 2.29-1.27 3.15-2.53.99-1.45 1.4-2.85 1.42-2.93-.03-.01-2.72-1.04-2.75-4.13M14.5 4.5c.71-.86 1.19-2.06 1.06-3.25-1.02.04-2.26.68-2.99 1.54-.66.76-1.23 1.98-1.08 3.15 1.14.09 2.3-.58 3.01-1.44" />
      </svg>
      <span>{label}</span>
    </button>
  );
}
