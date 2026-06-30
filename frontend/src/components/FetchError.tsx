import { Link } from "react-router-dom";

/**
 * 데이터 로드 실패 시 친화적 메시지 + 탈출 경로(다시 시도·메인으로).
 * 페이지가 에러로 막혔을 때 사용자가 빠져나갈 수 있게 한다.
 */
export default function FetchError({ message, inline }: { message?: string | null; inline?: boolean }) {
  const friendly = message && !/failed to fetch/i.test(message) ? message : "일시적으로 연결이 끊겼어요";
  return (
    <div style={{ padding: inline ? "14px 0" : "30px 16px", textAlign: "center" }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "#c0392b", marginBottom: 5 }}>{friendly}</div>
      <div className="muted" style={{ fontSize: 12.5, marginBottom: 14 }}>
        잠시 후 다시 시도하거나 메인으로 이동하세요.
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
        <button onClick={() => window.location.reload()}
          style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #d4d9e0", background: "#fff",
            color: "#475569", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
          다시 시도
        </button>
        <Link to="/" style={{ padding: "7px 16px", borderRadius: 8, background: "var(--c-primary)",
          color: "#fff", fontSize: 13, fontWeight: 700, textDecoration: "none", display: "inline-flex", alignItems: "center" }}>
          메인으로
        </Link>
      </div>
    </div>
  );
}
