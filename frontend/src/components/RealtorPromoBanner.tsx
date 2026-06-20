import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { Building2, X } from "lucide-react";

const KEY = "koczip_realtor_promo_dismissed";

// 로그인 사용자의 인증번호가 중개사무소와 일치하는데 아직 라운지 미연결이면,
// 무료 홈페이지 만들기를 1회 안내(닫으면 다시 안 뜸).
export default function RealtorPromoBanner() {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(KEY) === "1"; } catch { return false; }
  });
  if (!user?.realtorPromo || dismissed) return null;
  const office = user.realtorPromo.office_name;
  const close = () => { try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } setDismissed(true); };
  return (
    <div className="rpromo">
      <Link to="/lounge" className="rpromo-tx" onClick={() => { try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } }}>
        <Building2 size={16} strokeWidth={2.3} aria-hidden />
        <span><b>{office ?? "내 사무소"}</b> 사장님이세요? <b>무료 홈페이지</b>를 만들어보세요 — 휴대폰 인증으로 바로 시작 <b>→</b></span>
      </Link>
      <button className="rpromo-x" onClick={close} aria-label="닫기"><X size={15} /></button>
    </div>
  );
}
