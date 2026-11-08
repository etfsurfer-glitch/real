// 콕집요청(한 사무소 지정) — 운영 POST /requests 를 pick_mode=choose 로 부른다.
// 로그인은 운영과 같은 Supabase Auth. 전화 인증·제3자 제공 동의는 서버가 다시 확인한다.
import { useEffect, useState } from "react";
import { createClient, type Session } from "@supabase/supabase-js";
import { areaLabel } from "../src/lib/area";

const API = "https://api.koczip.com";
const SITE = "https://koczip.com";
const URL_ = import.meta.env.VITE_SUPABASE_URL;
const ANON = import.meta.env.VITE_SUPABASE_ANON_KEY;
export const auth = URL_ && ANON
  ? createClient(URL_, ANON, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } })
  : null;

export type ReqTarget = {
  realtor_id: string; realtor_name: string;
  complex: { name: string; cortar: string; addr: string };
  listing?: { article_no: string; area_name: string; excl: number | null; floor_info: string; price_text: string };
};

export const login = (provider: "kakao" | "google") => auth?.auth.signInWithOAuth({
  provider,
  options: {
    // 로그인 뒤 보던 화면(지도 위치·단지)으로 돌아온다
    redirectTo: window.location.href,
    scopes: provider === "kakao" ? "profile_nickname profile_image account_email" : "openid email profile",
  },
});

export const logout = () => auth?.auth.signOut();
// 세션에서 보여 줄 내 이름(카카오/구글 프로필 이름 → 이메일 앞부분)
export const sessionName = (s: Session | null) => {
  const m: any = s?.user?.user_metadata || {};
  return String(m.nickname || m.name || m.full_name || s?.user?.email?.split("@")[0] || "회원");
};

// 로그인 세션 — 요청 모달·관심단지·리뷰 쓰기가 같이 쓴다
export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    auth?.auth.getSession().then(({ data }) => setSession(data.session));
    const sub = auth?.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub?.data.subscription.unsubscribe();
  }, []);
  return session;
}
export const authHeaders = (s: Session | null): Record<string, string> => (s ? { Authorization: `Bearer ${s.access_token}` } : {});

// 로그인 안내(작은 블록) — 어디서든 같은 모양
export function LoginBox({ why }: { why: string }) {
  return (
    <div className="t2-login">
      <p>{why}</p>
      <button className="kakao" onClick={() => login("kakao")}>카카오로 로그인</button>
      <button className="google" onClick={() => login("google")}>구글로 로그인</button>
    </div>
  );
}

export function RequestModal({ target, onClose }: { target: ReqTarget; onClose: () => void }) {
  const session = useSession();
  const [me, setMe] = useState<{ phone_verified?: boolean; nickname?: string } | null>(null);
  const [memo, setMemo] = useState(() => target.listing
    ? `${target.complex.name} ${target.listing.area_name}타입 ${target.listing.floor_info}층 ${target.listing.price_text} 매물(매물번호 ${target.listing.article_no}) 보고 싶어요. 비슷한 조건 매물도 알려 주세요.`
    : `${target.complex.name} 매물 찾고 있어요.`);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ proposals_url?: string } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!session) { setMe(null); return; }
    fetch(`${API}/me`, { headers: { Authorization: `Bearer ${session.access_token}` } })
      .then((r) => (r.ok ? r.json() : null)).then(setMe).catch(() => setMe(null));
  }, [session]);

  const send = async () => {
    if (!session) return;
    setBusy(true); setErr("");
    const c = target.complex.cortar;
    const l = target.listing;
    try {
      const r = await fetch(`${API}/requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` },
        body: JSON.stringify({
          pick_mode: "choose", realtor_ids: [target.realtor_id], target_count: 1, consent: true,
          name: me?.nickname || "", asset: "apt", trade: "A1",
          sido: c ? c.slice(0, 2) + "00000000" : "", sigungu: c ? c.slice(0, 5) + "00000" : "", cortar: c,
          region_name: target.complex.addr,
          area_txt: l ? `${l.area_name}${l.excl ? ` · ${areaLabel(l.excl)}` : ""}` : "",
          budget_txt: l ? l.price_text : "",
          memo,
        }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "보내지 못했어요");
      setDone(j);
    } catch (e: any) {
      setErr(e.message || "보내지 못했어요");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="t2-modal" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="t2-modal-in" onClick={(e) => e.stopPropagation()}>
        <div className="t2-ph"><h2>콕집요청</h2><button className="t2-x" onClick={onClose} aria-label="닫기">×</button></div>
        <p className="t2-to"><b>{target.realtor_name}</b> 에만 보내요</p>
        {target.listing && (
          <div className="t2-reqsum">
            {target.complex.name} · {target.listing.area_name}타입{target.listing.excl ? ` (${areaLabel(target.listing.excl)})` : ""} · {target.listing.floor_info}층 · <b>{target.listing.price_text}</b>
          </div>
        )}
        {done ? (
          <div className="t2-done">
            <b>요청을 보냈어요.</b>
            <p>사무소가 매물을 제안하면 알림으로 알려 드려요. 내 번호는 넘어가지 않아요.</p>
            {done.proposals_url && <a href={done.proposals_url} target="_blank" rel="noreferrer">받은 제안 보기 ↗</a>}
          </div>
        ) : !session ? (
          <LoginBox why="요청을 보내려면 로그인이 필요해요." />
        ) : me && !me.phone_verified ? (
          <div className="t2-login">
            <p>요청을 보내려면 휴대폰 인증이 한 번 필요해요. 인증은 콕집에서 하고 다시 와 주세요.</p>
            <a className="t2-cta1" href={`${SITE}/request`} target="_blank" rel="noreferrer">콕집에서 휴대폰 인증하기 ↗</a>
          </div>
        ) : (
          <>
            <label className="t2-fld">요청 내용
              <textarea value={memo} onChange={(e) => setMemo(e.target.value)} rows={4} maxLength={1000} />
            </label>
            <label className="t2-agree">
              <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
              <span>위 요청 내용과 닉네임을 <b>{target.realtor_name}</b>에 전달하는 데 동의해요. 연락처는 넘기지 않아요 — 제안을 받은 뒤 마음에 드는 곳에만 직접 연락하시면 돼요.</span>
            </label>
            {err && <p className="t2-err">{err}</p>}
            <button className="t2-cta1" disabled={!agree || busy || !memo.trim()} onClick={send}>{busy ? "보내는 중…" : "이 사무소에 콕집요청 보내기"}</button>
          </>
        )}
      </div>
    </div>
  );
}
