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

    // 일시적 실패(배포 재시작·콜드·순간 네트워크)는 자동 재시도로 흡수한다.
    // 네트워크 오류(Failed to fetch)와 게이트웨이 오류(502/503/504)만 재시도 — 4xx·500은 즉시 실패.
    const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));
    const run = async () => {
      const MAX_TRIES = 3;
      for (let attempt = 1; attempt <= MAX_TRIES; attempt++) {
        const t0 = performance.now();
        try {
          const r = await fetch(url, { signal: ctrl.signal });
          const client_ms = performance.now() - t0;
          const server_hdr = r.headers.get("X-Process-Time");
          const server_ms = server_hdr ? Number(server_hdr) * 1000 : null;
          recordTiming({ url, client_ms, server_ms, status: r.status, at: new Date().toISOString() });
          const tag = `[api] ${client_ms.toFixed(0)}ms`
            + (server_ms != null ? ` (서버 ${server_ms.toFixed(0)}ms)` : "")
            + ` · ${r.status} · ${url}` + (attempt > 1 ? ` (재시도 ${attempt - 1})` : "");
          if (client_ms >= 1000) console.warn(tag); else console.log(tag);
          // 502/503/504 = 일시적 게이트웨이(배포 재시작 등) → 잠깐 뒤 재시도
          if ((r.status === 502 || r.status === 503 || r.status === 504) && attempt < MAX_TRIES) {
            await sleep(400 * attempt);
            if (cancelled) return;
            continue;
          }
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          const j = await r.json();
          if (!cancelled) { setData(j as T); setLoading(false); }
          return;
        } catch (e: unknown) {
          if (cancelled) return;
          if (e instanceof DOMException && e.name === "AbortError") return;
          // 네트워크 오류(TypeError: Failed to fetch)는 일시적일 수 있음 → 재시도
          if (e instanceof TypeError && attempt < MAX_TRIES) {
            await sleep(400 * attempt);
            if (cancelled) return;
            continue;
          }
          const msg = e instanceof Error ? e.message : String(e);
          // 끝내 실패 — 영어 원문 대신 친화적 안내(특히 네트워크 오류).
          const friendly = (e instanceof TypeError || /failed to fetch/i.test(msg))
            ? "일시적으로 연결이 끊겼어요 — 잠시 후 다시 시도해주세요."
            : msg;
          setError(friendly);
          setLoading(false);
          return;
        }
      }
    };

    const timer = setTimeout(run, debounceMs);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [url, debounceMs]);

  return { data, loading, error };
}
