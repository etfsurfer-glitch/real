// 비회원 AI 이용량을 세는 기준이 되는 방문자 ID.
//
// 쿠키를 쓰지 않는 이유: koczip.com → api.koczip.com 은 교차 사이트라 쿠키를 보내려면
// credentials 를 켜야 하고, 그러면 서버 CORS 의 allow_origins="*" 를 못 쓴다(전 엔드포인트 영향).
// 그래서 localStorage 로 만든 ID 를 헤더로 보낸다. 지우면 초기화되지만 서버가 IP 상한을
// 함께 걸어 두므로 그것만으로 무제한이 되지는 않는다.
const KEY = "koczip_visitor_id";

export function visitorId(): string {
  try {
    let v = localStorage.getItem(KEY);
    if (!v) {
      v = (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`);
      localStorage.setItem(KEY, v);
    }
    return v;
  } catch {
    // 사파리 프라이빗 모드 등 localStorage 차단 — 서버가 IP 로 센다
    return "";
  }
}

/** fetch 헤더에 펼쳐 쓴다: { ...visitorHeader() } */
export function visitorHeader(): Record<string, string> {
  const v = visitorId();
  return v ? { "X-Visitor-Id": v } : {};
}
