import { useEffect, useRef, useState } from "react";

/** 새로고침·뒤로가기·재접속 시에도 마지막 설정을 기억하는 useState.
 *  localStorage 백업. 필터·드롭다운이 기본값으로 리셋되는 것 방지.
 *  key는 페이지·필터별 고유(예: "txstats:trade"). 지역처럼 전역 공유는 같은 key 사용. */
export function useStickyState<T>(key: string, initial: T): [T, (v: T | ((p: T) => T)) => void] {
  const [v, setV] = useState<T>(() => {
    if (typeof window === "undefined") return initial;
    try {
      const s = window.localStorage.getItem(key);
      return s != null ? (JSON.parse(s) as T) : initial;
    } catch {
      return initial;
    }
  });
  const kref = useRef(key);
  kref.current = key;
  useEffect(() => {
    try {
      window.localStorage.setItem(kref.current, JSON.stringify(v));
    } catch { /* quota/private mode */ }
  }, [v]);
  return [v, setV];
}
