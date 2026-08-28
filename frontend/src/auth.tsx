import { createClient, type Session } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { setAuthReturn, takeAuthReturn } from "./lib/authreturn";

// 인증 전용 Supabase 클라이언트. 데이터는 supabase.ts 의 로컬 stub(local_api)으로
// 가지만, 로그인/세션만 진짜 Supabase Auth(카카오 provider)를 쓴다.
// 카카오 OAuth 콜백은 Supabase 호스팅 콜백이 받으므로 local_api 를 공개할 필요 없음.
const URL = import.meta.env.VITE_SUPABASE_URL;
const ANON = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const authClient =
  URL && ANON
    ? createClient(URL, ANON, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
      })
    : null;

export type AuthUser = {
  id: string; name: string; avatar: string | null; email?: string;
  phone?: string | null; phoneVerified?: boolean; memberNo?: number | null;
  points?: number; rank?: string; emoji?: string; level?: number;
  nextRank?: string | null; nextEmoji?: string | null; nextAt?: number | null; aiCost?: number;
  nickname?: string | null; needsNickname?: boolean;
  needsConsent?: boolean; marketingOptIn?: boolean;
  earned?: number; nextRemaining?: number | null;
  realtorPromo?: { office_name: string | null } | null;
  isRealtorMember?: boolean;
};

type AuthState = {
  user: AuthUser | null;
  token: string | null;
  ready: boolean;        // 초기 세션 복원 완료 여부
  configured: boolean;   // Supabase 인증 설정 존재 여부
  isAdmin: boolean;      // 관리자 여부 (백엔드 /me 기준)
  adminChecked: boolean; // /me 확인 완료 여부 (관리자 라우트 깜빡임 방지)
  refreshMe: () => Promise<void>; // /me 재조회 (전화번호 인증 후 등)
};

const API = import.meta.env.VITE_API_BASE;

type MeInfo = {
  isAdmin: boolean; email?: string; phone?: string | null;
  phoneVerified?: boolean; memberNo?: number | null;
  points?: number; rank?: string; emoji?: string; level?: number;
  nextRank?: string | null; nextEmoji?: string | null; nextAt?: number | null; aiCost?: number;
  nickname?: string | null; needsNickname?: boolean;
  needsConsent?: boolean; marketingOptIn?: boolean;
  earned?: number; nextRemaining?: number | null;
  realtorPromo?: { office_name: string | null } | null;
  isRealtorMember?: boolean;
};

// 반환 null = '일시 실패(네트워크·토큰갱신 레이스·API 재시작)' — 이전 권한을 유지해야 함.
// {isAdmin:false} 는 '확정적 비관리자'(200 응답)일 때만. 혼동하면 관리자 페이지가
// 작업 중 홈으로 튕기는 버그가 된다(2026-07-03 매물점검 중 이탈 제보).
async function fetchMe(token: string | null): Promise<MeInfo | null> {
  if (!token || !API) return { isAdmin: false };
  try {
    const r = await fetch(`${API}/me`, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) return null;
    const d = await r.json();
    return {
      isAdmin: !!d.is_admin, email: d.email, phone: d.phone,
      phoneVerified: !!d.phone_verified, memberNo: d.member_no ?? null,
      points: d.points ?? 0, rank: d.rank, emoji: d.emoji, level: d.level,
      nextRank: d.next_rank ?? null, nextEmoji: d.next_emoji ?? null,
      nextAt: d.next_at ?? null, aiCost: d.ai_cost,
      nickname: d.nickname ?? null, needsNickname: !!d.needs_nickname,
      needsConsent: !!d.needs_consent, marketingOptIn: !!d.marketing_opt_in,
      earned: d.points_earned ?? 0, nextRemaining: d.next_remaining ?? null,
      realtorPromo: d.realtor_promo ?? null,
      isRealtorMember: !!d.is_realtor_member,
    };
  } catch {
    return null;
  }
}

function sessionToUser(session: Session | null): { user: AuthUser | null; token: string | null } {
  if (!session?.user) return { user: null, token: null };
  const m = (session.user.user_metadata ?? {}) as Record<string, string>;
  const name =
    m.name || m.full_name || m.nickname || m.user_name || m.preferred_username ||
    session.user.email?.split("@")[0] || "회원";
  return {
    user: { id: session.user.id, name, avatar: m.avatar_url || m.picture || null },
    token: session.access_token,
  };
}

const AuthCtx = createContext<AuthState>({
  user: null, token: null, ready: false, configured: false, isAdmin: false, adminChecked: false,
  refreshMe: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null, token: null, ready: !authClient, configured: !!authClient,
    isAdmin: false, adminChecked: !authClient, refreshMe: async () => {},
  });

  const earnedRef = useRef<number | undefined>(undefined);
  const navigate = useNavigate();

  const mergeMe = (info: MeInfo | null) => {
    if (!info) return;  // 일시 실패 — 이전 권한·프로필 유지(관리자 홈 튕김 방지)
    // 누적 획득 포인트가 늘었으면(이전 값을 알 때만) 축하 토스트 이벤트 발행.
    const prev = earnedRef.current;
    const now = info.earned;
    if (typeof prev === "number" && typeof now === "number" && now > prev) {
      window.dispatchEvent(new CustomEvent("koczip:points", { detail: {
        delta: now - prev, earned: now, rank: info.rank, level: info.level,
        nextRank: info.nextRank ?? null, nextRemaining: info.nextRemaining ?? null,
      }}));
    }
    if (typeof now === "number") earnedRef.current = now;
    setState((s) => ({
      ...s, isAdmin: info.isAdmin, adminChecked: true,
      user: s.user
        ? { ...s.user, email: info.email ?? s.user.email,
            phone: info.phone ?? null, phoneVerified: !!info.phoneVerified,
            memberNo: info.memberNo ?? null,
            points: info.points ?? 0, rank: info.rank, emoji: info.emoji, level: info.level,
            nextRank: info.nextRank ?? null, nextEmoji: info.nextEmoji ?? null,
            nextAt: info.nextAt ?? null, aiCost: info.aiCost,
            nickname: info.nickname ?? null, needsNickname: !!info.needsNickname,
            needsConsent: !!info.needsConsent, marketingOptIn: !!info.marketingOptIn,
            earned: info.earned ?? 0, nextRemaining: info.nextRemaining ?? null,
            realtorPromo: info.realtorPromo ?? null }
        : s.user,
    }));
  };

  useEffect(() => {
    captureReferral();   // 진입 시 ?ref 캡처
    if (!authClient) return;
    initNativeAuthDeepLink();   // iOS 앱 OAuth 딥링크 복귀 리스너 등록
    let alive = true;
    const apply = async (session: Session | null, event?: string) => {
      const { user, token } = sessionToUser(session);
      if (!alive) return;
      // 토큰 자동갱신·탭 포커스마다 onAuthStateChange가 재호출된다. 같은 유저면 /me에서
      // 채운 enriched 필드(phoneVerified·nickname·points 등)를 유지해야 인증배지가 깜빡이지
      // 않는다. 새 유저(로그인 전환)·로그아웃 때만 초기화.
      setState((s) => {
        const same = !!(user && s.user && s.user.id === user.id);
        const nextUser: AuthUser | null =
          !user ? null
          : (same && s.user) ? { ...s.user, name: user.name, avatar: user.avatar }
          : user;
        return {
          ...s, token, ready: true, configured: true,
          isAdmin: same ? s.isAdmin : false,
          adminChecked: !token ? true : (same ? s.adminChecked : false),
          user: nextUser,
        };
      });
      // OAuth 는 항상 랜딩(origin)으로 돌아온다. 흐름 중간에 로그인했다면 그 화면으로
      // 되돌려 준다 — 안 그러면 콕집요청에 적어 둔 조건이 통째로 날아간다.
      // /me 응답을 기다리면(재시도 시 2.5초) 그동안 랜딩이 보이므로 먼저 옮긴다.
      if (token && event === "SIGNED_IN" && window.location.pathname === "/") {
        const back = takeAuthReturn();
        if (back) navigate(back, { replace: true });
      }
      if (token) {
        let info = await fetchMe(token);
        if (!alive) return;
        if (!info) {  // 일시 실패 — 2.5초 후 1회 재시도(초기 로드 실패로 '확인 중' 고착 방지)
          await new Promise((res) => setTimeout(res, 2500));
          if (!alive) return;
          info = await fetchMe(token);
          if (!alive) return;
        }
        mergeMe(info);
        // 실제 로그인 순간에만 서버에 로그인 기록 남김 (토큰 갱신/탭복원 제외)
        if (event === "SIGNED_IN" && API) {
          fetch(`${API}/events/login`, { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
        }
        // 온보딩에서 알림 받기로 했고(권한 허용) 아직 구독 안 됐으면 — 로그인 시 조용히 구독 저장.
        // (1번 일반 사용자가 권한만 먼저 받고 로그인은 나중에 한 경우 자동 연결)
        import("./lib/push").then((m) => m.maybeAutoSubscribe(token)).catch(() => {});
        // 중개사 회원이라고 로그인 직후 /lounge 로 옮기던 동작은 제거했다(2026-08-04 사용자 지시:
        // 보던 화면에서 튕겨 나가 오히려 불편). 라운지는 상단 메뉴로 직접 들어간다.
      }
    };
    authClient.auth.getSession().then(({ data }) => apply(data.session));
    const { data: sub } = authClient.auth.onAuthStateChange((e, session) => apply(session, e));
    return () => { alive = false; sub.subscription.unsubscribe(); };
  }, []);

  const refreshMe = async () => {
    const { data } = (await authClient?.auth.getSession()) ?? { data: { session: null } };
    const token = data.session?.access_token ?? null;
    if (token) mergeMe(await fetchMe(token));
  };

  return <AuthCtx.Provider value={{ ...state, refreshMe }}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  return useContext(AuthCtx);
}

// ── iOS 앱(Capacitor) 네이티브 OAuth ───────────────────────────────────────
// 앱 웹뷰에서 signInWithOAuth 전체 리다이렉트를 쓰면 Google 이 accounts.google.com 을
// 외부 사파리로 열어(정책상 embedded webview 차단) 세션이 사파리에 갇힌다. 그래서
// iOS 앱에서는 인앱 SFSafariViewController(@capacitor/browser)로 열고, 인증 후
// 커스텀 스킴(com.koczip.app://oauth) 딥링크로 앱에 복귀해 코드를 교환한다.
const isIOSApp = () =>
  typeof navigator !== "undefined" && /KoczipApp\/iOS/.test(navigator.userAgent);
const OAUTH_REDIRECT = "com.koczip.app://oauth";

async function nativeOAuth(provider: "google" | "kakao" | "apple", scopes: string) {
  const { data, error } = await authClient!.auth.signInWithOAuth({
    provider,
    options: { redirectTo: OAUTH_REDIRECT, skipBrowserRedirect: true, scopes },
  });
  if (error || !data?.url) { alert("로그인을 시작할 수 없습니다. 잠시 후 다시 시도해주세요."); return; }
  const { Browser } = await import("@capacitor/browser");
  await Browser.open({ url: data.url, presentationStyle: "popover" });
}

// 딥링크(com.koczip.app://oauth?code=…) 수신 → 세션 교환. 앱 시작 시 1회 등록.
let _deepLinkInited = false;
export function initNativeAuthDeepLink() {
  if (_deepLinkInited || !isIOSApp() || !authClient) return;
  _deepLinkInited = true;
  import("@capacitor/app").then(({ App }) => {
    App.addListener("appUrlOpen", async ({ url }) => {
      if (!url || !url.startsWith("com.koczip.app://oauth")) return;
      try {
        const code = new URLSearchParams(url.split("?")[1] || "").get("code");
        if (code) {
          await authClient!.auth.exchangeCodeForSession(code);
        } else if (url.includes("access_token")) {   // implicit 폴백
          const p = new URLSearchParams(url.split("#")[1] || "");
          const at = p.get("access_token"), rt = p.get("refresh_token");
          if (at && rt) await authClient!.auth.setSession({ access_token: at, refresh_token: rt });
        }
      } catch (e) {
        console.error("oauth deeplink", e);
        alert("로그인 처리 중 문제가 발생했어요. 다시 시도해주세요.");
      } finally {
        try { const { Browser } = await import("@capacitor/browser"); await Browser.close(); } catch { /* 이미 닫힘 */ }
      }
    });
  }).catch(() => { _deepLinkInited = false; });
}

export async function loginKakao() {
  if (!authClient) {
    alert("로그인 서버(Supabase)가 설정되지 않았습니다.");
    return;
  }
  setAuthReturn();   // 돌아올 화면 기억 — 콕집요청처럼 흐름 중간에 로그인하는 경우
  if (isIOSApp()) { await nativeOAuth("kakao", "profile_nickname profile_image account_email plusfriends"); return; }
  await authClient.auth.signInWithOAuth({
    provider: "kakao",
    options: {
      redirectTo: window.location.origin,
      // 카카오 동의항목 — 닉네임·프로필사진·이메일. 전화번호(phone_number)는
      // 비즈 검수가 필요해 요청하지 않음(전화 인증은 알리고 SMS로 별도 처리).
      // plusfriends: 콕집 카톡채널(_ackPX) 친구 추가 상태를 읽어 친구톡 발송 대상
      // 관리에 쓴다. 자동 채널 추가 자체는 카카오 콘솔[간편가입] 설정으로 동작하고,
      // 이 동의항목은 "친구인지"를 읽기 위한 것(선택 동의라 거부해도 로그인은 됨).
      scopes: "profile_nickname profile_image account_email plusfriends",
    },
  });
}

// 인앱 브라우저(webview) 감지 — Google OAuth는 webview에서 차단되므로 외부 브라우저로 보내야 함.
export function isInAppBrowser(): boolean {
  return inAppBrowser().inApp;
}
function inAppBrowser(): { inApp: boolean; kakao: boolean; android: boolean } {
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  const ios = /iPhone|iPad|iPod/i.test(ua);
  const kakao = /KAKAOTALK/i.test(ua);
  const named = /(Instagram|FBAN|FBAV|FB_IAB|Line\/|NAVER\(|DaumApps|Band\/|KAKAOSTORY|Snapchat|Threads|TossApp|coupang|wadiz)/i.test(ua);
  const android = !ios && (named || /;\s*wv\)/i.test(ua));
  const iosInapp = ios && (kakao || named);
  return { inApp: kakao || android || iosInapp, kakao, android };
}

// 주어진 URL을 외부(시스템) 브라우저로 연다 — webview 차단 우회.
function openExternalUrl(url: string) {
  const { kakao, android } = inAppBrowser();
  if (kakao) {
    window.location.href = "kakaotalk://web/openExternal?url=" + encodeURIComponent(url);
    return;
  }
  if (android) {
    const noScheme = url.replace(/^https?:\/\//, "");
    window.location.href = "intent://" + noScheme + "#Intent;scheme=https;package=com.android.chrome;end";
    return;
  }
  // iOS 비카카오 인앱: 강제 전환 스킴이 없어 새 창 시도(일부만 동작) — 안내는 InAppBrowserBanner가 담당.
  window.open(url, "_blank");
}

export async function loginGoogle() {
  if (!authClient) {
    alert("로그인 서버(Supabase)가 설정되지 않았습니다.");
    return;
  }
  setAuthReturn();   // 돌아올 화면 기억
  if (isIOSApp()) { await nativeOAuth("google", "openid email profile"); return; }
  // 인앱 브라우저면: Google이 webview를 막으므로(PKCE도 같은 브라우저서 시작·완료돼야 함)
  // 앱 자체를 외부 브라우저로 열고, 거기서 자동으로 Google 로그인을 트리거한다(?login=google).
  // 이 경우엔 브라우저 자체가 바뀌어 sessionStorage 가 안 따라가므로 URL 로 넘긴다.
  if (inAppBrowser().inApp) {
    const back = window.location.pathname + window.location.search;
    openExternalUrl(window.location.origin + "/?login=google"
      + (back !== "/" ? `&back=${encodeURIComponent(back)}` : ""));
    return;
  }
  await authClient.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: window.location.origin, scopes: "openid email profile" },
  });
}

// Sign in with Apple — App Store 심사지침 4.8(소셜로그인 제공 시 애플 로그인 동등 제공) 대응.
// 리다이렉트(signInWithOAuth) 플로우는 supabase.co 도메인 검증이 불가해 막힌다. 그래서
// 앱=네이티브 ASAuthorization(플러그인), 웹=Apple JS 팝업 으로 identity token 을 받아
// Supabase signInWithIdToken 으로 로그인한다(도메인 검증·Return URL 리다이렉트 불필요).
export const APPLE_LOGIN_ENABLED = true;

// Apple 로그인 버튼 노출 조건 — 현재 웹 브라우저 Apple(JS 팝업)은 Services ID 의
// koczip.com 도메인 검증 대기(콘솔 피커 버그)라 눌러도 실패한다. 그래서 네이티브 시트가
// 정상 동작하는 iOS 앱에서만 노출한다. 웹 검증 완료되면 이 조건을 확장(브라우저 포함)한다.
export const appleLoginVisible = () => APPLE_LOGIN_ENABLED && isIOSApp();

const APPLE_WEB_CLIENT_ID = "com.koczip.signin"; // Services ID — 웹 Apple JS 의 client_id
const APPLE_BUNDLE_ID = "com.koczip.app";        // App ID — 앱 네이티브 flow
const APPLE_REDIRECT = "https://koczip.com/auth/apple"; // Services ID 에 등록된 Return URL(팝업이라 실제 리다이렉트는 없음)

function randomNonce(len = 32): string {
  const a = new Uint8Array(len);
  crypto.getRandomValues(a);
  return Array.from(a, (b) => ("0" + b.toString(16)).slice(-2)).join("");
}
async function sha256hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf), (b) => ("0" + b.toString(16)).slice(-2)).join("");
}

// 웹: Apple JS SDK(팝업) → id_token. SDK 는 CDN 에서 1회 로드.
async function webAppleIdToken(hashedNonce: string): Promise<string> {
  await new Promise<void>((resolve, reject) => {
    if ((window as any).AppleID) return resolve();
    const s = document.createElement("script");
    s.src = "https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js";
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("apple-js-load-fail"));
    document.head.appendChild(s);
  });
  const AppleID = (window as any).AppleID;
  AppleID.auth.init({
    clientId: APPLE_WEB_CLIENT_ID,
    scope: "name email",
    redirectURI: APPLE_REDIRECT,
    usePopup: true,
    nonce: hashedNonce,
  });
  const data = await AppleID.auth.signIn();
  const token = data?.authorization?.id_token;
  if (!token) throw new Error("no-id-token");
  return token;
}

export async function loginApple() {
  if (!authClient) {
    alert("로그인 서버(Supabase)가 설정되지 않았습니다.");
    return;
  }
  setAuthReturn();
  const rawNonce = randomNonce();
  const hashedNonce = await sha256hex(rawNonce);
  try {
    let idToken: string | undefined;
    if (isIOSApp()) {
      const { SignInWithApple } = await import("@capacitor-community/apple-sign-in");
      const res = await SignInWithApple.authorize({
        clientId: APPLE_BUNDLE_ID,
        redirectURI: APPLE_REDIRECT,
        scopes: "name email",
        nonce: hashedNonce,
      });
      idToken = res.response?.identityToken;
    } else {
      idToken = await webAppleIdToken(hashedNonce);
    }
    if (!idToken) throw new Error("no-identity-token");
    const { error } = await authClient.auth.signInWithIdToken({
      provider: "apple",
      token: idToken,
      nonce: rawNonce,
    });
    if (error) throw error;
    // 성공 → onAuthStateChange(SIGNED_IN) 가 세션 반영·화면 처리
  } catch (e: any) {
    const msg = String(e?.message || e?.error || e || "");
    // 사용자가 팝업/시트를 닫은 경우는 조용히 무시
    if (/popup_closed|user_cancel|1001|1000|canceled|cancelled|closed|AuthorizationError/i.test(msg)) return;
    console.error("apple login", e);
    alert("Apple 로그인 중 문제가 발생했어요. 다시 시도해주세요.");
  }
}

export async function logout() {
  await authClient?.auth.signOut();
}

// 공유 링크의 ?ref=회원번호 를 저장(OAuth 리다이렉트 후에도 유지). 가입(전화인증) 시 사용.
const REF_KEY = "kokzip_ref";
export function captureReferral() {
  try {
    const ref = new URLSearchParams(window.location.search).get("ref");
    if (ref && /^\d+$/.test(ref)) localStorage.setItem(REF_KEY, ref);
  } catch { /* ignore */ }
}
export function getReferral(): number | null {
  try { const v = localStorage.getItem(REF_KEY); return v ? Number(v) : null; } catch { return null; }
}
export function clearReferral() { try { localStorage.removeItem(REF_KEY); } catch { /* ignore */ } }
