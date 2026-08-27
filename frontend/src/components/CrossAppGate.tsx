import { Link } from "react-router-dom";
import { Building2, Home, Download } from "lucide-react";
import { STORE, isIOSApp } from "../lib/appmode";

// 앱 분리 안내 — 현재 앱에서 '다른 앱 전용' 기능에 들어왔을 때만 표시.
// 중요: 브라우저(홈페이지)에서는 절대 호출하지 않는다 — 웹은 모든 기능을 그대로 쓴다.
// target="realtor": 일반앱에서 중개사 기능 접근 → 중개사앱 설치 유도.
// target="general": 중개사앱에서 일반 기능 접근 → 일반앱 설치 유도.
export default function CrossAppGate({ target }: { target: "realtor" | "general" }) {
  const info = target === "realtor"
    ? {
        Icon: Building2,
        app: "콕집 중개사",
        title: "중개사 전용 기능이에요",
        desc: "중개사라운지·매물장·매물점검·상담관리는 공인중개사 전용 '콕집 중개사' 앱에서 이용하실 수 있어요.",
        store: STORE.realtor,
        back: "/",
        backLabel: "콕집 홈으로",
      }
    : {
        Icon: Home,
        app: "콕집",
        title: "일반 서비스 기능이에요",
        desc: "실거래·급매·시세·단지 정보 등 일반 서비스는 '콕집' 앱에서 이용하실 수 있어요.",
        store: STORE.general,
        back: "/biz",
        backLabel: "중개사 홈으로",
      };
  const { Icon } = info;
  return (
    <div className="xgate">
      <div className="xgate-card">
        <div className="xgate-ic"><Icon size={30} strokeWidth={2} /></div>
        <h2>{info.title}</h2>
        <p>{info.desc}</p>
        {!isIOSApp() && (
          <a className="xgate-cta" href={info.store} target="_blank" rel="noopener noreferrer">
            <Download size={17} strokeWidth={2.4} /> {info.app} 앱 설치하기
          </a>
        )}
        <Link to={info.back} className="xgate-back">{info.backLabel}</Link>
      </div>
    </div>
  );
}
