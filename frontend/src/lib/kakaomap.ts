// 카카오맵 JS SDK 로더 & 포맷 헬퍼 (지도보기 / 급매찾기(지도) 공용).
// 카카오 로그인용 JS 키(VITE_KAKAO_JS_KEY)를 그대로 사용. 카카오 개발자콘솔에
// 플랫폼>Web 도메인(koczip.com 등)을 등록해야 SDK 가 로드된다.

declare global {
  interface Window { kakao: any }
}

// 카카오 JavaScript 키(공개·도메인 잠금). 클라이언트 번들에 노출되는 게 정상이며
// koczip.com 도메인 화이트리스트로 보호된다. CF 빌드 env 설정과 무관하게 항상
// 동작하도록 소스에 고정(어드민 키 유출 사고 재발 방지 + 대시보드 의존 제거).
export const KAKAO_JS_KEY = "9a1273ee261418f745229285f7e86021";
const KEY = KAKAO_JS_KEY;
let sdkPromise: Promise<void> | null = null;

export function loadKakao(): Promise<void> {
  if (sdkPromise) return sdkPromise;
  sdkPromise = new Promise((resolve, reject) => {
    if (window.kakao && window.kakao.maps) { resolve(); return; }
    if (!KEY) { reject(new Error("VITE_KAKAO_JS_KEY 미설정")); return; }
    const s = document.createElement("script");
    // autoload=false → kakao.maps.load 로 명시적 초기화(안정적)
    // libraries=services → 지역명→좌표 지오코딩(지역 드롭다운 이동)에 사용
    s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KEY}&autoload=false&libraries=services`;
    s.async = true;
    s.onload = () => window.kakao.maps.load(() => resolve());
    s.onerror = () => reject(new Error("카카오맵 SDK 로드 실패"));
    document.head.appendChild(s);
  });
  return sdkPromise;
}

// 지역명("서울특별시 강남구") → 좌표. 지도 드롭다운 이동용.
// addressSearch 실패 시 키워드(장소) 검색으로 폴백.
export async function geocodeRegion(query: string): Promise<{ lat: number; lng: number } | null> {
  await loadKakao();
  const kakao = window.kakao;
  if (!kakao?.maps?.services) return null;
  const geocoder = new kakao.maps.services.Geocoder();
  const byAddress = await new Promise<{ lat: number; lng: number } | null>((resolve) => {
    geocoder.addressSearch(query, (res: any[], status: string) => {
      if (status === kakao.maps.services.Status.OK && res[0]) {
        resolve({ lat: parseFloat(res[0].y), lng: parseFloat(res[0].x) });
      } else resolve(null);
    });
  });
  if (byAddress) return byAddress;
  // 폴백: 행정구역명 키워드 검색
  const places = new kakao.maps.services.Places();
  return new Promise((resolve) => {
    places.keywordSearch(query, (res: any[], status: string) => {
      if (status === kakao.maps.services.Status.OK && res[0]) {
        resolve({ lat: parseFloat(res[0].y), lng: parseFloat(res[0].x) });
      } else resolve(null);
    });
  });
}

// 원(won) → "78억" / "7.8억" / "5,400만" 식 짧은 표기
export function wonShort(v: number | null | undefined): string {
  if (v == null || v <= 0) return "-";
  const eok = v / 1e8;
  if (eok >= 10) return `${Math.round(eok)}억`;
  if (eok >= 1) return `${eok.toFixed(1)}억`;
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}

export function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch] as string));
}
