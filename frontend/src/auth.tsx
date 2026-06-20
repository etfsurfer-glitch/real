import { createClient, type Session } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

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
};

async function fetchMe(token: string | null): Promise<MeInfo> {
  if (!token || !API) return { isAdmin: false };
  try {
    const r = await fetch(`${API}/me`, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) return { isAdmin: false };
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
    };
  } catch {
    return { isAdmin: false };
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

  const mergeMe = (info: MeInfo) => {
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
      if (token) {
        const info = await fetchMe(token);
        if (!alive) return;
        mergeMe(info);
        // 실제 로그인 순간에만 서버에 로그인 기록 남김 (토큰 갱신/탭복원 제외)
        if (event === "SIGNED_IN" && API) {
          fetch(`${API}/events/login`, { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
        }
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

export async function loginKakao() {
  if (!authClient) {
    alert("로그인 서버(Supabase)가 설정되지 않았습니다.");
    return;
  }
  await authClient.auth.signInWithOAuth({
    provider: "kakao",
    options: {
      redirectTo: window.location.origin,
      // 카카오 동의항목 — 닉네임·프로필사진·이메일만 요청. 전화번호(phone_number)는
      // 비즈 검수가 필요한 항목이라 요청하지 않음(전화 인증은 알리고 SMS로 별도 처리).
      scopes: "profile_nickname profile_image account_email",
    },
  });
}

export async function loginGoogle() {
  if (!authClient) {
    alert("로그인 서버(Supabase)가 설정되지 않았습니다.");
    return;
  }
  await authClient.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: window.location.origin,
      scopes: "openid email profile",
    },
  });
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
