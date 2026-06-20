import { useEffect, useState } from "react";
import { useAuth } from "../auth";

// 우하단 floating debug — 최근 API 호출 timing 표시. 관리자 전용.
// useFetchJson 이 window.__apiTimings 에 누적. 200ms 마다 polling 해서 리렌더.

type ApiTiming = {
  url: string;
  client_ms: number;
  server_ms: number | null;
  status: number;
  at: string;
};

declare global {
  interface Window { __apiTimings?: ApiTiming[]; __perfBadgeOn?: boolean }
}

export function PerfBadge() {
  const { isAdmin } = useAuth();
  const [open, setOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try { return localStorage.getItem("perfBadge") === "1"; } catch { return false; }
  });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!open) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 300);
    return () => window.clearInterval(id);
  }, [open]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    try { localStorage.setItem("perfBadge", next ? "1" : "0"); } catch {}
  };

  const timings = (typeof window !== "undefined" ? window.__apiTimings : []) || [];
  void tick; // re-render trigger

  // 마지막 5건 + 평균 (현재 페이지 진입 후 모든 호출)
  if (!isAdmin) return null;  // 관리자에게만 노출(디버그 위젯)

  const recent = timings.slice(0, 5);
  const totalCount = timings.length;
  const avgClient = totalCount
    ? Math.round(timings.reduce((s, t) => s + t.client_ms, 0) / totalCount)
    : 0;

  const baseStyle: React.CSSProperties = {
    position: "fixed",
    right: 12,
    bottom: 12,
    zIndex: 9999,
    fontFamily: "ui-monospace, SFMono-Regular, monospace",
  };

  if (!open) {
    return (
      <button
        onClick={toggle}
        title="API 응답 시간 패널 열기"
        style={{
          ...baseStyle,
          width: 36, height: 36,
          borderRadius: "50%",
          border: "1px solid #1268d3",
          background: "white",
          color: "#1268d3",
          cursor: "pointer",
          fontSize: 14,
          boxShadow: "0 2px 6px rgba(0,0,0,0.12)",
        }}
      >⏱</button>
    );
  }

  return (
    <div style={{
      ...baseStyle,
      width: 360,
      background: "white",
      border: "1px solid #1268d3",
      borderRadius: 8,
      padding: 10,
      boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
      fontSize: 11,
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between",
        alignItems: "center", marginBottom: 8,
      }}>
        <span style={{ fontWeight: 700, color: "#1268d3" }}>
          API 호출 ({totalCount}건) · 평균 {avgClient}ms
        </span>
        <button
          onClick={toggle}
          style={{
            border: "none", background: "transparent", cursor: "pointer",
            color: "#999", fontSize: 16, lineHeight: 1, padding: 0,
          }}
          title="닫기"
        >×</button>
      </div>
      {recent.length === 0 && (
        <div style={{ color: "#999" }}>아직 호출 없음. 페이지 이동/필터 변경 시 표시됩니다.</div>
      )}
      <div>
        {recent.map((t, i) => {
          const slow = t.client_ms >= 1000;
          const path = (() => {
            try { return new URL(t.url).pathname + new URL(t.url).search; }
            catch { return t.url; }
          })();
          return (
            <div key={i} style={{
              display: "flex", gap: 6, padding: "3px 0",
              borderBottom: i < recent.length - 1 ? "1px dashed #eee" : "none",
              color: slow ? "#c0392b" : "#333",
            }}>
              <span style={{
                fontWeight: 600, minWidth: 50, textAlign: "right",
              }}>{Math.round(t.client_ms)}ms</span>
              {t.server_ms != null && (
                <span style={{ color: "#888", minWidth: 56, textAlign: "right" }}>
                  서버 {Math.round(t.server_ms)}
                </span>
              )}
              <span style={{
                color: t.status >= 400 ? "#c0392b" : "#666",
                minWidth: 28,
              }}>{t.status}</span>
              <span style={{
                overflow: "hidden", textOverflow: "ellipsis",
                whiteSpace: "nowrap", flex: 1,
              }} title={t.url}>{path}</span>
            </div>
          );
        })}
      </div>
      <div style={{
        marginTop: 6, paddingTop: 6, borderTop: "1px solid #eee",
        color: "#999", fontSize: 10,
      }}>
        Console에 매 호출마다 [api] 로그. {">="}1초는 ⚠️ warning.
      </div>
    </div>
  );
}
