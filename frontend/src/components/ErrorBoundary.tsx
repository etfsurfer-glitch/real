import { Component, type ErrorInfo, type ReactNode } from "react";

// 렌더 중 예외가 나면 React 는 트리 전체를 언마운트해 화면이 하얗게 비어버린다.
// 이 경계가 그걸 잡아서, 빈 화면 대신 실제 오류 메시지를 보여준다 (재현 시 원인 특정용).
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div style={{ padding: 24 }}>
        <h2 style={{ color: "#c0392b", margin: "0 0 8px" }}>화면을 그리는 중 오류가 났어요</h2>
        <p className="muted" style={{ marginBottom: 12 }}>
          아래 메시지를 알려주시면 정확히 고칠 수 있어요. 다른 탭으로 이동하거나 새로고침 해보세요.
        </p>
        <pre style={{
          whiteSpace: "pre-wrap", background: "#f6f8fa", padding: 12,
          borderRadius: 8, fontSize: 12, color: "#a03000", overflow: "auto",
        }}>
          {error.message || String(error)}
        </pre>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button
            onClick={() => this.setState({ error: null })}
            style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #ccc",
                     background: "white", cursor: "pointer", fontSize: 13 }}
          >다시 시도</button>
          <button
            onClick={() => window.location.reload()}
            style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid var(--c-primary)",
                     background: "white", color: "var(--c-primary)", cursor: "pointer", fontSize: 13 }}
          >새로고침</button>
          <a
            href="/"
            style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid var(--c-primary)",
                     background: "var(--c-primary)", color: "white", textDecoration: "none", fontSize: 13 }}
          >메인으로</a>
        </div>
      </div>
    );
  }
}
