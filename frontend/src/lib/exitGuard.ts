// 중개사앱(TWA) OS 뒤로가기 종료 방지.
// TWA에선 하드웨어/제스처 뒤로가기가 웹 히스토리를 pop하다가 바닥에서 앱을 '종료'시킨다.
// 무의식적으로 뒤로가기를 누르면 앱이 꺼지는 걸 막는다:
//   - 화면 안(더 뒤로 갈 앱 화면이 있음) → 평소처럼 이전 화면으로.
//   - 앱 진입점(더 뒤로 갈 곳이 없어 다음 뒤로가기가 종료) → "한 번 더 누르면 종료" 토스트,
//     2초 안에 한 번 더 눌러야 실제 종료.
// react-router v6는 history.state.idx로 히스토리 깊이를 관리한다(첫 진입 = idx 0).
import { isInstalledApp } from "./appmode";

function idx(): number {
  try { return (window.history.state && typeof window.history.state.idx === "number")
    ? window.history.state.idx : 0; } catch { return 0; }
}

let toastEl: HTMLDivElement | null = null;
let toastTimer: number | undefined;
function showToast(msg: string) {
  if (!toastEl) {
    toastEl = document.createElement("div");
    toastEl.className = "koczip-exit-toast";
    toastEl.setAttribute("role", "status");
    document.body.appendChild(toastEl);
  }
  toastEl.textContent = msg;
  toastEl.classList.add("on");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { toastEl?.classList.remove("on"); }, 1900);
}

let installed = false;

// App 셸 마운트 시 1회 호출. 설치앱(TWA/PWA)에서만 동작.
export function installExitGuard(): () => void {
  if (installed || typeof window === "undefined" || !isInstalledApp()) return () => {};
  installed = true;

  // 진입점(idx 0)이면, 뒤로가기가 걸릴 '바닥 한 칸'을 만들어 둔다.
  // (바닥에서 그냥 뒤로가기 하면 TWA가 종료돼 popstate조차 안 뜨므로, 잡을 자리를 확보)
  try {
    if (idx() <= 0) window.history.pushState(window.history.state, "", window.location.href);
  } catch { /* noop */ }

  let armedAt = 0;

  const onPop = () => {
    // pop 후 새 위치의 idx. 0이면 = 앱 바닥(다음 뒤로가기가 종료) → 종료 가드.
    if (idx() <= 0) {
      const now = Date.now();
      if (now - armedAt < 2000) {
        // 2초 내 두 번째 → 실제 종료: 가드 해제 후 바닥을 한 번 더 pop.
        window.removeEventListener("popstate", onPop);
        installed = false;
        window.history.back();
        return;
      }
      armedAt = now;
      // 종료를 막고 앱에 머문다 — 바닥 위에 한 칸 다시 쌓는다.
      window.history.pushState(window.history.state, "", window.location.href);
      showToast("한 번 더 누르면 종료됩니다");
    }
    // idx > 0 이면 앱 내 이전 화면으로 간 것 — 그대로 둔다.
  };

  window.addEventListener("popstate", onPop);
  return () => {
    window.removeEventListener("popstate", onPop);
    installed = false;
  };
}
