import { useEffect, useState } from "react";

// 드롭박스 필터로 URL 이 바뀔 때마다 호출되는 GET 요청을 안전하게 처리하는 훅.
//
//  - debounce: 빠른 연속 선택을 마지막 1건으로 합침 (기본 200ms).
//  - AbortController: 새 선택이 들어오면 직전 in-flight 요청을 실제로 중단.
//  - stale-ignore: 취소 플래그로, 늦게 도착한 이전 응답이 최신 결과를 덮어쓰지 못하게 함.
//  - timing: 응답마다 클라이언트 측정 시간 + 서버 X-Process-Time 헤더를
//    window.__apiTimings 에 기록 (DevTools 콘솔에서 확인). + 호출별 console.log.
//
// url 이 null 이면 호출하지 않는다 (예: API_BASE 미설정).

// 전역 timing buffer — 최근 50건 보관
type ApiTiming = {
  url: string;
  client_ms: number;     // 클라이언트가 본 총 소요 (네트워크 + JSON 파싱)
  server_ms: number | null;  // 서버 X-Process-Time
  status: number;
  at: string;            // ISO timestamp
};
declare global {
  interface Window {
    __apiTimings?: ApiTiming[];
  }
}
function recordTiming(entry: ApiTiming) {
  if (typeof window === "undefined") return;
  if (!window.__apiTimings) window.__apiTimings = [];
  window.__apiTimings.unshift(entry);
  if (window.__apiTimings.length > 50) window.__apiTimings.length = 50;
}

export function useFetchJson<T>(
  url: string | null,
  opts?: { debounceMs?: number },
): { data: T | null; loading: boolean; error: string | null } {
  const debounceMs = opts?.debounceMs ?? 200;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!url) {
      setLoading(false);
      return;
    }
    const ctrl = new AbortController();
    let cancelled = false;
    setLoading(true);
    setError(null);

    const timer = setTimeout(() => {
      const t0 = performance.now();
      fetch(url, { signal: ctrl.signal })
        .then(async (r) => {
          const client_ms = performance.now() - t0;
          const server_hdr = r.headers.get("X-Process-Time");
          const server_ms = server_hdr ? Number(server_hdr) * 1000 : null;
          recordTiming({
            url, client_ms, server_ms,
            status: r.status, at: new Date().toISOString(),
          });
          // 콘솔에 한 줄 로그 (서버 ms 있으면 같이)
          const tag = `[api] ${client_ms.toFixed(0)}ms`
            + (server_ms != null ? ` (서버 ${server_ms.toFixed(0)}ms)` : "")
            + ` · ${r.status} · ${url}`;
          if (client_ms >= 1000) {
            console.warn(tag);
          } else {
            console.log(tag);
          }
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then((j) => {
          if (!cancelled) {
            setData(j as T);
            setLoading(false);
          }
        })
        .catch((e: unknown) => {
          // 중단(AbortError)은 정상적인 취소이므로 무시.
          if (cancelled) return;
          if (e instanceof DOMException && e.name === "AbortError") return;
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        });
    }, debounceMs);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [url, debounceMs]);

  return { data, loading, error };
}
