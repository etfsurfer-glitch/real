import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

// 서비스워커가 새 버전으로 교체(controllerchange)되면 페이지를 1회 자동 새로고침.
// → 배포 후 사용자가 옛 캐시 앱을 계속 쓰는 문제(예: 로그인 scope 불일치) 방지.
if ("serviceWorker" in navigator) {
  let refreshing = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (refreshing) return;
    refreshing = true;
    window.location.reload();
  });
}

// 앱을 다시 열 때(백그라운드 → 포그라운드) 새 버전이 있는지 확인한다.
//
// 왜 필요한가 — 설치앱(TWA)은 최근앱에서 되살리면 페이지가 새로 뜨지 않는다. 그래서
// 서비스워커가 갱신을 확인할 기회가 없고, 고쳐서 배포해도 앱은 옛 화면을 며칠이고 그대로
// 쓴다. 실제로 라운지 튕김을 고친 뒤에도 한 중개사의 앱은 25분 뒤까지 옛 코드로 돌았고,
// 본인은 '아직 안 된다'고 알려 왔다(2026-10-22). 완전 종료를 안내하는 건 해법이 아니다.
//
// 새 워커가 있으면 skipWaiting·clientsClaim 으로 바로 장악하고, 위의 controllerchange 가
// 한 번 새로고침한다. 복귀 직후는 사용자가 막 돌아온 시점이라 새로고침이 가장 덜 방해된다.
if ("serviceWorker" in navigator) {
  let lastCheck = 0;
  const checkUpdate = () => {
    if (document.visibilityState !== "visible") return;
    const now = Date.now();
    if (now - lastCheck < 60_000) return;      // 1분 쓰로틀 — 탭 전환마다 두드리지 않는다
    lastCheck = now;
    navigator.serviceWorker.getRegistration()
      .then((r) => r?.update())
      .catch(() => { /* 네트워크 없음 등 — 다음 복귀 때 다시 본다 */ });
  };
  document.addEventListener("visibilitychange", checkUpdate);
  window.addEventListener("focus", checkUpdate);
}

// 배포로 자산(청크)이 교체된 뒤, 옛 페이지를 띄워둔 사용자가 삭제된 청크를 동적 import 하면
// "Failed to fetch (dynamically imported module)"가 난다. 1회 새로고침으로 최신 자산을 받게 한다.
// (세션당 1회만 — 무한 새로고침 루프 방지.)
window.addEventListener("vite:preloadError", () => {
  if (sessionStorage.getItem("koczip:preloadReloaded")) return;
  sessionStorage.setItem("koczip:preloadReloaded", "1");
  window.location.reload();
});

// 일부 인앱 WebView(카카오/TWA)에서 SW 캐시 손상으로 styles.css만 실패해 '무스타일'로 뜨는 현상 자가복구.
// styles.css의 .koczip-css-probe(position:absolute)가 적용됐는지 확인 → 안 됐으면 SW·캐시 정리 후 1회 새로고침.
window.addEventListener("load", () => {
  setTimeout(async () => {
    if (sessionStorage.getItem("koczip:cssHeal")) return;   // 세션당 1회(루프 방지)
    const probe = document.createElement("div");
    probe.className = "koczip-css-probe";
    probe.setAttribute("aria-hidden", "true");
    document.body.appendChild(probe);
    const styled = getComputedStyle(probe).position === "absolute";
    probe.remove();
    if (styled) return;   // CSS 정상
    sessionStorage.setItem("koczip:cssHeal", "1");
    try {
      if ("serviceWorker" in navigator) {
        const regs = await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.map((r) => r.unregister()));
      }
      if ("caches" in window) {
        const keys = await caches.keys();
        await Promise.all(keys.map((k) => caches.delete(k)));
      }
    } catch { /* 무시 */ }
    window.location.reload();
  }, 1500);
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
