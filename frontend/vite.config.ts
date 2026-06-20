import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["apple-touch-icon.png"],
      manifest: {
        name: "콕집 - 부동산 매물 분석",
        short_name: "콕집",
        description: "매물·실거래·중개사를 콕 집어드리는 부동산 분석 도구",
        theme_color: "#1268d3",
        background_color: "#ffffff",
        display: "standalone",
        start_url: "/",
        scope: "/",
        lang: "ko",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      // POST /q can't be cached by the SW (POST isn't cacheable), so the
      // service worker just precaches the app shell and lets data requests
      // pass through to the network. Static assets get cache-first.
      workbox: {
        navigateFallback: "/index.html",
        globPatterns: ["**/*.{js,css,html,png,svg,ico}"],
        // 웹푸시 핸들러(push/notificationclick)를 생성된 SW에 주입
        importScripts: ["push-sw.js"],
        // 새 배포 시 새 SW가 즉시 대기 해제·클라이언트 장악하고 옛 캐시 정리.
        // → main.tsx의 controllerchange 자동 새로고침과 합쳐 배포 즉시 반영.
        skipWaiting: true,
        clientsClaim: true,
        cleanupOutdatedCaches: true,
      },
      devOptions: { enabled: true },
    }),
  ],
  server: {
    port: 5173,
    host: true,
    proxy: {
      // /api 경로는 local_api(8000)로 프록시 — PWA가 모바일에서 same-origin 호출 가능
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
