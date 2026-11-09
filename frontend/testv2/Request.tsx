// 콕집요청(한 사무소 지정) — 운영 POST /requests 를 pick_mode=choose 로 부른다.
// 로그인은 운영과 같은 Supabase Auth. 전화 인증·제3자 제공 동의는 서버가 다시 확인한다.
import { useEffect, useState } from "react";
import { API as _API } from "./Drawer";
import { createClient, type Session } from "@supabase/supabase-js";
import { areaLabel } from "../src/lib/area";

const API = "https://api.koczip.com";
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

const errText = (d: any, status: number) => {
  const det = d?.detail;
  if (typeof det === "string") return det;
  if (det && typeof det === "object" && "message" in det) return String(det.message);
  return `오류 ${status}`;
};

// ── 휴대폰 인증(한 번) — 매물의뢰·콕집요청·내 정보가 같이 쓴다 ───────────────────
export function PhoneBlock({ session, onDone }: { session: Session; onDone: () => void }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [devCode, setDevCode] = useState("");
  const H = { "Content-Type": "application/json", ...authHeaders(session) };
  const send = async () => {
    if (busy) return; setBusy(true); setMsg(""); setDevCode("");
    try {
      const r = await fetch(`${_API}/me/phone/send-code`, { method: "POST", headers: H, body: JSON.stringify({ phone }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(errText(d, r.status));
      setSent(true); setCode(""); if (d.dev_code) setDevCode(String(d.dev_code));
    } catch (e: any) { setMsg(e.message || "보내지 못했어요"); } finally { setBusy(false); }
  };
  const verify = async () => {
    if (busy) return; setBusy(true); setMsg("");
    try {
      const r = await fetch(`${_API}/me/phone/verify`, { method: "POST", headers: H, body: JSON.stringify({ code }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(errText(d, r.status));
      onDone();
    } catch (e: any) { setMsg(e.message || "확인하지 못했어요"); } finally { setBusy(false); }
  };
  return (
    <div className="t2-phone">
      <p>중개사무소가 제안을 남기면 알려 드릴 번호예요. 본인 명의 휴대폰으로 한 번만 인증해요. 번호는 중개사무소에 넘어가지 않아요.</p>
      <div className="row">
        <input inputMode="numeric" maxLength={11} placeholder="휴대폰 번호(숫자만)" value={phone} readOnly={sent}
          onChange={(e) => setPhone(e.target.value.replace(/[^0-9]/g, ""))} onKeyDown={(e) => { if (e.key === "Enter" && !sent) send(); }} />
        {!sent ? <button disabled={busy || phone.length < 10} onClick={send}>{busy ? "발송 중…" : "인증번호 받기"}</button>
          : <button className="ghost" onClick={() => { setSent(false); setCode(""); setMsg(""); }}>번호 변경</button>}
      </div>
      {sent && (
        <>
          <p className="ok">{phone.replace(/(\d{3})(\d{3,4})(\d{4})/, "$1-$2-$3")} 로 인증번호를 보냈어요. 5분 안에 넣어 주세요.</p>
          <div className="row">
            <input inputMode="numeric" maxLength={6} autoComplete="one-time-code" placeholder="인증번호 6자리" value={code} autoFocus
              onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, ""))} onKeyDown={(e) => { if (e.key === "Enter") verify(); }} />
            <button disabled={busy || code.length < 6} onClick={verify}>{busy ? "확인 중…" : "인증 완료"}</button>
          </div>
          <button className="lnk" disabled={busy} onClick={send}>문자가 안 왔나요? 다시 보내기</button>
        </>
      )}
      {devCode && <p className="t2-snote">개발 모드 인증번호 {devCode}</p>}
      {msg && <p className="t2-err">{msg}</p>}
    </div>
  );
}

// ── 내 정보(작은 창): 닉네임 · 휴대폰 인증 · 로그아웃 — 운영 설정 페이지 대신 지도 안에서 ──
export function MeModal({ session, onClose, onLogout }: { session: Session; onClose: () => void; onLogout: () => void }) {
  const [me, setMe] = useState<{ phone_verified?: boolean; nickname?: string | null; member_no?: number | null } | null>(null);
  const [nick, setNick] = useState("");
  const [chk, setChk] = useState<{ available: boolean; reason?: string | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const load = () => fetch(`${_API}/me`, { headers: authHeaders(session) }).then((x) => (x.ok ? x.json() : null)).then((j) => { setMe(j); setNick(j?.nickname || ""); }).catch(() => setMe(null));
  useEffect(() => { load(); }, [session]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const n = nick.trim(); setChk(null);
    if (!n || n === (me?.nickname || "")) return;
    const t = setTimeout(() => fetch(`${_API}/me/nickname/check?name=${encodeURIComponent(n)}`, { headers: authHeaders(session) }).then((x) => x.json()).then(setChk).catch(() => {}), 350);
    return () => clearTimeout(t);
  }, [nick]);   // eslint-disable-line react-hooks/exhaustive-deps
  const save = async () => {
    setBusy(true); setMsg("");
    try {
      const x = await fetch(`${_API}/me/nickname`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders(session) }, body: JSON.stringify({ nickname: nick.trim() }) });
      const j = await x.json().catch(() => ({}));
      if (!x.ok) throw new Error(errText(j, x.status));
      setMsg(j.awarded ? `닉네임을 정했어요. 첫 설정 ${j.awarded}p 적립.` : "닉네임을 바꿨어요."); load();
    } catch (e: any) { setMsg(e.message); } finally { setBusy(false); }
  };
  const changed = nick.trim() && nick.trim() !== (me?.nickname || "");
  return (
    <div className="t2-modal" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="t2-modal-in" onClick={(e) => e.stopPropagation()}>
        <div className="t2-ph"><h2>내 정보</h2><button className="t2-x" onClick={onClose} aria-label="닫기">×</button></div>
        <p className="t2-to"><b>{sessionName(session)}</b> · {session.user?.email || ""}{me?.member_no ? ` · 회원번호 ${me.member_no}` : ""}</p>
        <div className="t2-me-sec">
          <h3>닉네임 <small>글·리뷰·AI 호칭에 써요. 한글·영문·숫자·_ 2~12자</small></h3>
          <div className="row">
            <input value={nick} maxLength={12} placeholder={me?.nickname || "닉네임"} onChange={(e) => setNick(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && changed && chk?.available) save(); }} />
            <button disabled={busy || !changed || (chk != null && !chk.available)} onClick={save}>{busy ? "저장 중…" : me?.nickname ? "바꾸기" : "정하기"}</button>
          </div>
          {chk && changed && <p className={chk.available ? "ok" : "t2-err"}>{chk.available ? "쓸 수 있어요" : chk.reason || "쓸 수 없는 닉네임이에요"}</p>}
          {msg && <p className="ok">{msg}</p>}
        </div>
        <div className="t2-me-sec">
          <h3>휴대폰 인증</h3>
          {me == null ? <p className="t2-snote">불러오는 중…</p> : me.phone_verified ? <p className="ok">인증 완료. 제안 도착 알림을 받을 수 있어요.</p>
            : <PhoneBlock session={session} onDone={() => { setMe({ ...me, phone_verified: true }); }} />}
        </div>
        <button className="t2-cta1 ghost" onClick={() => { onLogout(); onClose(); }}>로그아웃</button>
        <button className="t2-lnk mut t2-withdraw" onClick={async () => {
          if (!window.confirm("정말 탈퇴하시겠어요?\n회원정보·포인트·작성한 글/리뷰가 모두 삭제되며 되돌릴 수 없습니다.")) return;
          const x = await fetch(`${_API}/me`, { method: "DELETE", headers: authHeaders(session) }).catch(() => null);
          if (!x || !x.ok) { setMsg("탈퇴 처리에 실패했어요. 잠시 후 다시 시도해 주세요."); return; }
          onLogout(); onClose();
        }}>회원 탈퇴</button>
      </div>
    </div>
  );
}

export function RequestModal({ target, onClose, onMine }: { target: ReqTarget; onClose: () => void; onMine?: () => void }) {
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
            {onMine ? <button className="t2-cta1" style={{ marginTop: 10 }} onClick={() => { onClose(); onMine(); }}>받은 제안 보기</button> : <p>받은 제안은 매물의뢰 창의 내 요청에서 볼 수 있어요.</p>}
          </div>
        ) : !session ? (
          <LoginBox why="요청을 보내려면 로그인이 필요해요." />
        ) : me && !me.phone_verified ? (
          <PhoneBlock session={session} onDone={() => setMe({ ...me, phone_verified: true })} />
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
