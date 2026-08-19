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

// 지도 컨트롤 오버레이 — 모든 지도 공용(좌하단): 확대·축소·스카이뷰·내 위치.
// 카카오 기본 컨트롤 대신 콕집 스타일로 통일. 컨테이너에 중복 부착 방지.
// setZoomable(false)인 지도(랜딩)에서도 버튼 확대·축소는 동작해 스크롤 보호와 양립.
export function attachMapControls(map: any, container: HTMLElement | null, opts?: {
  sky?: boolean;      // 스카이뷰 토글(기본 true)
  locate?: boolean;   // 내 위치 이동(기본 true)
  onLocate?: (lat: number, lng: number) => void;  // 내위치 이동 후 훅 — 페이지가 해당 지역 데이터 로드에 사용
}) {
  if (!map || !container) return;
  const kakao = window.kakao;
  container.querySelector(".kmc")?.remove();
  const sky = opts?.sky !== false;
  const locate = opts?.locate !== false;

  const box = document.createElement("div");
  box.className = "kmc";
  const btn = (label: string, title: string, onClick: () => void, cls = "") => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "kmc-btn" + (cls ? " " + cls : "");
    b.innerHTML = label;
    b.title = title;
    b.setAttribute("aria-label", title);
    b.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
    return b;
  };
  box.appendChild(btn("+", "지도 확대", () => map.setLevel(map.getLevel() - 1)));
  box.appendChild(btn("−", "지도 축소", () => map.setLevel(map.getLevel() + 1)));
  if (sky) {
    let on = false;
    const sb = btn("위성", "스카이뷰 전환", () => {
      on = !on;
      map.setMapTypeId(on ? kakao.maps.MapTypeId.HYBRID : kakao.maps.MapTypeId.ROADMAP);
      sb.classList.toggle("on", on);
    }, "kmc-sky");
    box.appendChild(sb);
  }
  if (locate && "geolocation" in navigator) {
    box.appendChild(btn(
      // lucide 'locate-fixed' 미니 SVG(외부요청 없음)
      '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="2" x2="5" y1="12" y2="12"/><line x1="19" x2="22" y1="12" y2="12"/><line x1="12" x2="12" y1="2" y2="5"/><line x1="12" x2="12" y1="19" y2="22"/><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>',
      "내 위치로 이동",
      () => navigator.geolocation.getCurrentPosition(
        (pos) => {
          map.setLevel(Math.min(map.getLevel(), 5));
          map.panTo(new kakao.maps.LatLng(pos.coords.latitude, pos.coords.longitude));
          opts?.onLocate?.(pos.coords.latitude, pos.coords.longitude);
        },
        () => { /* 권한 거부 — 조용히 무시 */ },
        { timeout: 6000 }),
      "kmc-loc"));
  }
  container.appendChild(box);
}

// 좌표 → 법정동 코드(B코드 10자리)·이름. 내위치로 지역 필터를 맞출 때 사용.
// dong은 읍면동 수준으로 정규화(법정동코드 구조: 시군구5+읍면동3+리2 → 리 절사).
export async function coordToRegion(lat: number, lng: number):
    Promise<{ code: string; sido: string; sigungu: string; dong: string; name: string } | null> {
  await loadKakao();
  const kakao = window.kakao;
  if (!kakao?.maps?.services) return null;
  const geocoder = new kakao.maps.services.Geocoder();
  return new Promise((resolve) => {
    geocoder.coord2RegionCode(lng, lat, (res: any[], status: string) => {
      if (status === kakao.maps.services.Status.OK) {
        const b = res.find((r) => r.region_type === "B") || res[0];
        if (b?.code) {
          resolve({ code: b.code, sido: b.code.slice(0, 2) + "00000000",   // 셀렉트 코드 형식(10자리)
                    sigungu: b.code.slice(0, 5) + "00000",
                    dong: b.code.slice(0, 8) + "00", name: b.address_name });
          return;
        }
      }
      resolve(null);
    });
  });
}

// 원(won) → "78억" / "7.8억" / "5,400만" 식 짧은 표기
export function wonShort(v: number | null | undefined): string {
  if (v == null || v <= 0) return "-";
  const eok = v / 1e8;
  if (eok >= 100) return `${Math.round(eok)}억`;         // 100억↑ 은 정수(공간 절약)
  if (eok >= 1) {                                        // 12.5억 → "12.5억", 13.0억 → "13억"
    const s = eok.toFixed(1);
    return `${s.endsWith(".0") ? s.slice(0, -2) : s}억`;
  }
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}

export function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch] as string));
}
