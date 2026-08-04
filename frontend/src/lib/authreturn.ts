// OAuth 로그인 후 '원래 보던 화면'으로 돌려보내기.
//
// Supabase redirectTo 에 경로를 실어 보내는 방법도 있지만, 그건 대시보드 redirect
// allowlist 에 그 경로가 등록돼 있어야 하고 아니면 조용히 Site URL(랜딩)로 떨어진다.
// 서버 설정에 기대지 않도록 브라우저에 남겨 두고 돌아온 뒤 우리가 직접 이동한다.
//
// sessionStorage 를 쓰는 이유: 탭을 닫으면 사라져야 한다(다음에 앱을 열었을 때
// 엉뚱하게 옛 화면으로 튀지 않게). OAuth 왕복은 같은 탭에서 끝난다.
const KEY = "koczip_auth_return";
const MAX_AGE = 10 * 60 * 1000;   // 10분 — 그보다 오래 걸린 로그인은 문맥이 이미 끊겼다

/** 로그인 시작 직전에 호출. 기본값은 지금 보고 있는 경로(쿼리 포함). */
export function setAuthReturn(path?: string) {
  try {
    const to = path ?? window.location.pathname + window.location.search;
    if (to === "/" || !to.startsWith("/")) return;   // 랜딩은 저장할 이유가 없다
    sessionStorage.setItem(KEY, JSON.stringify({ to, at: Date.now() }));
  } catch { /* 저장 불가면 기존처럼 랜딩으로 — 기능은 계속 동작 */ }
}

/** 한 번만 꺼내 쓴다(꺼내면 지운다). 없거나 오래됐으면 null. */
export function takeAuthReturn(): string | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    sessionStorage.removeItem(KEY);
    const { to, at } = JSON.parse(raw);
    if (!to || typeof to !== "string" || Date.now() - at > MAX_AGE) return null;
    return to;
  } catch { return null; }
}
