// 바닥 회사정보·약관 — 운영 푸터와 같은 내용. PC 는 지도 아래 한 줄 띠, 휴대폰은 더보기 메뉴 아래 작은 글.
// 이용약관·개인정보처리방침은 운영 페이지 컴포넌트(글만 있는 JSX)를 지도 안 모달에 그대로 띄운다.
import Terms from "../src/pages/Terms";
import Privacy from "../src/pages/Privacy";

export type LegalKind = "terms" | "privacy";
const CS_URL = "https://pf.kakao.com/_ackPX/chat";

export const COMPANY = [
  "런투온라인", "대표 황인찬", "사업자등록번호 628-11-03169", "통신판매업신고 2026-진건퇴계원-114",
  "경기도 남양주시 진건읍 사릉로157번길 3, 1층 103호 A172", "전화 070-7954-4114", "문의 runtoonline@gmail.com",
];

export function FootBar({ onLegal, onAd }: { onLegal: (k: LegalKind) => void; onAd: () => void }) {
  return (
    <footer className="t2-foot">
      <span className="brand">콕집</span>
      {COMPANY.map((t) => <span key={t}>{t}</span>)}
      <a href={CS_URL} target="_blank" rel="noreferrer">고객센터</a>
      <button onClick={onAd}>광고문의</button>
      <button onClick={() => onLegal("terms")}>이용약관</button>
      <button className="b" onClick={() => onLegal("privacy")}>개인정보처리방침</button>
      <span className="note">매물 정보는 참고용이며 거래 전 반드시 현장 확인 바랍니다.</span>
    </footer>
  );
}

// 휴대폰 더보기 메뉴 아래 붙는 작은 글
export function FootNote({ onLegal, onAd }: { onLegal: (k: LegalKind) => void; onAd: () => void }) {
  return (
    <div className="t2-more-foot" onClick={(e) => e.stopPropagation()}>
      <div className="lnks">
        <button onClick={() => onLegal("terms")}>이용약관</button>
        <button className="b" onClick={() => onLegal("privacy")}>개인정보처리방침</button>
        <a href={CS_URL} target="_blank" rel="noreferrer">고객센터</a>
        <button onClick={onAd}>광고문의</button>
      </div>
      <p>{COMPANY.join(" · ")}</p>
      <p>매물 정보는 참고용이며 거래 전 반드시 현장 확인 바랍니다.</p>
    </div>
  );
}

export function LegalModal({ kind, onClose }: { kind: LegalKind; onClose: () => void }) {
  return (
    <div className="t2-modal" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="t2-modal-in legal" onClick={(e) => e.stopPropagation()}>
        <div className="t2-ph"><h2>{kind === "terms" ? "이용약관" : "개인정보처리방침"}</h2><button className="t2-x" onClick={onClose} aria-label="닫기">×</button></div>
        <div className="t2-legal">{kind === "terms" ? <Terms /> : <Privacy />}</div>
      </div>
    </div>
  );
}
