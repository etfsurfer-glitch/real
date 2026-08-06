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
