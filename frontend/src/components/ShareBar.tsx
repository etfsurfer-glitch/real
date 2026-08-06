import { useEffect, type RefObject } from "react";
import { setShareTarget, clearShareTarget } from "../lib/sharestore";

// 예전엔 인라인 공유바(이미지/복사/카카오/URL/토론장)였으나, 전역 플로팅 공유버튼(ShareFab)으로 통합했다.
// 이제 이 컴포넌트는 아무것도 렌더하지 않고, 페이지의 공유 대상(캡처 ref·제목·파일명)만 전역 스토어에 등록한다.
// 14개 페이지의 <ShareBar targetRef title fileName/> 호출부를 그대로 두어도 인라인 바만 사라지고
// 우하단 '공유하기' 플로팅 버튼(사용법 위)에서 동일 기능이 뜬다.
export default function ShareBar({ targetRef, title, fileName }: {
  targetRef: RefObject<HTMLElement | null>; title: string; fileName: string;
}) {
  useEffect(() => {
    setShareTarget({ ref: targetRef, title, fileName });
    return () => clearShareTarget(targetRef);
  }, [targetRef, title, fileName]);
  return null;
}
