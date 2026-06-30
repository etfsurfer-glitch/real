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

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
