// 통합 셸 모드 선택 — 기기·앱 컨텍스트로 레일(데스크톱) vs 탭바(모바일·앱)를 고른다.
// 단일 코드/기능셋 위에서 셸만 바뀐다(중개사앱·라운지 통합, 2026-09-14 확정).
import { useSyncExternalStore } from "react";
import { isRealtorApp } from "./appmode";

export type ShellMode = "rail" | "railmini" | "tabbar";

// 데스크톱=풀 레일(≥1024), 태블릿=아이콘 레일(768~1024), 그 미만·설치앱=탭바.
export const RAIL_MIN = 1024;
export const RAILMINI_MIN = 768;

export function currentShellMode(): ShellMode {
  if (typeof window === "undefined") return "tabbar";
  if (isRealtorApp()) return "tabbar";                 // 설치 중개사앱 = 항상 앱 셸
  const w = window.innerWidth;
  if (w >= RAIL_MIN) return "rail";
  if (w >= RAILMINI_MIN) return "railmini";
  return "tabbar";
}

function subscribe(cb: () => void): () => void {
  window.addEventListener("resize", cb);
  return () => window.removeEventListener("resize", cb);
}

export function useShellMode(): ShellMode {
  return useSyncExternalStore(subscribe, currentShellMode, () => "tabbar");
}

// 데스크톱 레일 = 기본 ON(2026-09-15 승격). 되돌림은 ?ui=off(개인 저장).
//   ?ui=rail  → 켬(off 저장 해제)   ?ui=off → 끔(개인만, 저장)
export function railFlagOn(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const ui = new URLSearchParams(window.location.search).get("ui");
    if (ui === "rail") { localStorage.removeItem("biz_ui_off"); return true; }
    if (ui === "off") { localStorage.setItem("biz_ui_off", "1"); return false; }
    return localStorage.getItem("biz_ui_off") !== "1";   // 기본 ON
  } catch { return true; }
}

// 레일 셸 사용 여부 + 아이콘(mini) 모드. 데스크톱=풀, 태블릿=아이콘.
export function useRailShell(): { on: boolean; mini: boolean } {
  const mode = useShellMode();
  const on = (mode === "rail" || mode === "railmini") && railFlagOn();
  return { on, mini: mode === "railmini" };
}
