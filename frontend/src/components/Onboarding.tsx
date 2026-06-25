import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Search, Building2, ChevronRight, Bell } from "lucide-react";
import { useAuth, loginKakao, loginGoogle } from "../auth";
import { PhoneModal } from "./PhoneVerify";
import { acceptPush, pushSupported } from "../lib/push";

// 안드로이드 '앱'(TWA/설치형) 첫 실행 1회만 — 사용자 구분 온보딩.
//  1) 일반(실거래·급매 조회) → 로그인 없이 바로 사용. AI는 이용 시 로그인 안내(AiChat 게이트가 처리).
//  2) 중개사(매물장·홈페이지) → 카카오/구글 가입 → 번호인증(사무소 연결, 스킵 가능).
function isForced(): boolean {
  try { return new URLSearchParams(window.location.search).get("onboard") === "1"; } catch { return false; }
}
function isAndroidApp(): boolean {
  if (typeof window === "undefined") return false;
  try {
    if (isForced()) return true; // 테스트 강제
    const ua = navigator.userAgent || "";
    const isAndroid = /Android/i.test(ua);
    const twa = document.referrer.startsWith("android-app://");
    const standalone = !!window.matchMedia && window.matchMedia("(display-mode: standalone)").matches;
    return twa || (isAndroid && standalone);
  } catch { return false; }
}

const DONE_KEY = "koczip_onboarded";

export default function Onboarding() {
  const { user, token } = useAuth();
  const [show, setShow] = useState(() => {
    try { return isAndroidApp() && (isForced() || !localStorage.getItem(DONE_KEY)); } catch { return false; }
  });
  // choose→(general)→notify / choose→realtor→phone→notify
  const [step, setStep] = useState<"choose" | "realtor" | "phone" | "notify">("choose");
  const [utype, setUtype] = useState<"general" | "realtor">("general");
  const [pushBusy, setPushBusy] = useState(false);

  // 중개사 흐름에서 로그인 완료되면 번호인증 단계로 자동 전환
  useEffect(() => {
    if (step === "realtor" && user && token) setStep("phone");
  }, [step, user, token]);

  const finish = () => {
    try { localStorage.setItem(DONE_KEY, "1"); localStorage.setItem("koczip_user_type", utype); } catch { /* ignore */ }
    setShow(false);
  };
  // 알림 soft-ask 단계로(권한 미지원 기기면 바로 종료)
  const toNotify = () => { if (pushSupported()) setStep("notify"); else finish(); };
  const onAcceptPush = async () => {
    setPushBusy(true);
    await acceptPush(token);   // 로그인(중개사)이면 구독까지, 미로그인(일반)이면 권한만+플래그→로그인 시 자동구독
    setPushBusy(false);
    finish();
  };

  if (!show) return null;

  // 번호인증 단계: PhoneModal(자체 모달) 단독 표시 — 완료/스킵 모두 알림 단계로(사무소 연결은 라운지가 처리).
  if (step === "phone" && token) {
    return <PhoneModal token={token} onClose={toNotify} onDone={toNotify} />;
  }

  return createPortal(
    <div className="onb">
      <div className="onb-card">
        {step === "choose" && (
          <>
            <div className="onb-brand">
              <img src="/logo.svg" alt="" width={30} height={30} />
              <span>콕집</span>
            </div>
            <h2 className="onb-title">어떻게 이용하시나요?</h2>
            <p className="onb-sub">맞는 걸 고르면 딱 맞게 시작해 드려요.</p>

            <button className="onb-opt" onClick={() => { setUtype("general"); toNotify(); }}>
              <span className="onb-opt-ic a"><Search size={22} strokeWidth={2.2} /></span>
              <span className="onb-opt-tx">
                <b>실거래·급매를 보고 싶어요</b>
                <em>로그인 없이 바로 둘러볼 수 있어요. (AI 질문은 로그인 후)</em>
              </span>
              <ChevronRight size={18} className="onb-opt-go" />
            </button>

            <button className="onb-opt" onClick={() => { setUtype("realtor"); setStep("realtor"); }}>
              <span className="onb-opt-ic b"><Building2 size={22} strokeWidth={2.2} /></span>
              <span className="onb-opt-tx">
                <b>중개사입니다</b>
                <em>매물장·홈페이지까지 — 내 사무소와 연결해 드려요.</em>
              </span>
              <ChevronRight size={18} className="onb-opt-go" />
            </button>

            <button className="onb-skip" onClick={finish}>건너뛰기</button>
          </>
        )}

        {step === "realtor" && (
          <>
            <div className="onb-brand"><Building2 size={26} strokeWidth={2.2} /><span>중개사 가입</span></div>
            <h2 className="onb-title">카카오 또는 구글로 시작하기</h2>
            <p className="onb-sub">가입 후 번호 인증하면 내 사무소와 자동으로 연결돼요.</p>
            <div className="onb-auth">
              <button className="auth-btn kakao" onClick={() => loginKakao()}>
                <KakaoIcon /> 카카오로 시작하기
              </button>
              <button className="auth-btn google" onClick={() => loginGoogle()}>
                <GoogleIcon /> 구글로 시작하기
              </button>
            </div>
            <button className="onb-back" onClick={() => setStep("choose")}>← 뒤로</button>
          </>
        )}

        {step === "notify" && (
          <>
            <div className="onb-brand"><Bell size={24} strokeWidth={2.2} /><span>알림 받기</span></div>
            {utype === "realtor" ? (
              <>
                <h2 className="onb-title">중요한 변동을 놓치지 마세요</h2>
                <p className="onb-sub">관심 단지·관심 사무소의 <b>매물 변동, 신고가·급매, 상담 신청</b>을 바로 알려드려요.</p>
              </>
            ) : (
              <>
                <h2 className="onb-title">관심 단지 알림을 받아보세요</h2>
                <p className="onb-sub">찜한 단지의 <b>신고가·급매 등장</b>을 매일 체크해 알려드려요. (로그인 후 적용)</p>
              </>
            )}
            <div className="onb-auth">
              <button className="auth-btn kakao" disabled={pushBusy} onClick={onAcceptPush}>
                <Bell size={15} /> {pushBusy ? "설정 중…" : "알림 받기"}
              </button>
            </div>
            <button className="onb-skip" onClick={finish}>나중에 할게요</button>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}

function KakaoIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 3C6.48 3 2 6.36 2 10.5c0 2.66 1.8 5 4.51 6.32-.15.52-.97 3.36-1 3.59 0 0-.02.17.09.24.11.07.24.02.24.02.32-.05 3.74-2.45 4.33-2.87.59.08 1.2.13 1.83.13 5.52 0 10-3.36 10-7.5S17.52 3 12 3z" />
    </svg>
  );
}
function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z" />
    </svg>
  );
}
