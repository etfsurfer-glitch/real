// SPA 라우트 이동당 1건의 '페이지뷰'를 서버에 남긴다(관리자 페이지 분석용).
// API 호출 단위 로그는 한 페이지에서 여러 건 쌓여 방문수가 부풀므로, 이 깨끗한
// 이벤트로 분석한다. 실패는 조용히 무시(사용자 경험 무영향).
const API_BASE = import.meta.env.VITE_API_BASE;

// 동적 경로 → 정규화 키 + 대상 id. 알려진 :id 라우트만 축약, 나머지는 경로 그대로.
export function normPage(pathname: string): { key: string; ref: string | null } {
  const m = (re: RegExp, key: string) => {
    const r = re.exec(pathname);
    return r ? { key, ref: r[1] } : null;
  };
  return (
    m(/^\/complex\/([^/]+)/, "/complex/:id") ||
    m(/^\/realtor\/([^/]+)/, "/realtor/:id") ||
    m(/^\/forum\/(\d+)/, "/forum/:id") ||
    { key: pathname.replace(/\/$/, "") || "/", ref: null }
  );
}

let lastKey = "";
let lastAt = 0;

export function logPageview(pathname: string, token?: string | null) {
  if (!API_BASE) return;
  const { key, ref } = normPage(pathname);
  const now = Date.now();
  // 같은 페이지 2초 내 중복(StrictMode 이중렌더·리로드) 무시
  if (key === lastKey && now - lastAt < 2000) return;
  lastKey = key; lastAt = now;
  try {
    fetch(`${API_BASE}/events/pageview`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        path: key, ref,
        referrer: (typeof document !== "undefined" ? document.referrer : "") || undefined,
      }),
      keepalive: true,
    }).catch(() => {});
  } catch { /* 무시 */ }
}
