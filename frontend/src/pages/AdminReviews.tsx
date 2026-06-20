import { useEffect, useState } from "react";
import { Loading } from "../components/Loading";
import { Link } from "react-router-dom";

const API_BASE = import.meta.env.VITE_API_BASE;

type Pending = {
  id: number;
  realtor_id: string;
  author_name: string;
  rating: number;
  body: string;
  doc_name: string | null;
  created_at: string;
};

// 인증리뷰 검수 — 첨부 서류를 확인하고 승인/거부. 승인 시 (거래인증) 뱃지가
// 부여되고 별점이 평점 집계에 반영됨. 결정 시점에 서류 파일은 폐기된다.
// (로그인·권한 시스템 연동 전까지 로컬 전용 도구)
export default function AdminReviews() {
  const [items, setItems] = useState<Pending[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = () => {
    if (!API_BASE) { setError("local API가 필요합니다 (VITE_API_BASE)."); setLoading(false); return; }
    setLoading(true);
    fetch(`${API_BASE}/admin/reviews/pending`)
      .then((r) => r.json())
      .then((j) => { setItems(j.items ?? []); setLoading(false); })
      .catch((e) => { setError(String(e)); setLoading(false); });
  };
  useEffect(load, []);

  async function decide(id: number, action: "approve" | "reject") {
    let reason: string | null = null;
    if (action === "reject") {
      reason = window.prompt("거부 사유 (선택, 작성자에게는 비공개):") ?? "";
    }
    setBusyId(id);
    try {
      const r = await fetch(`${API_BASE}/admin/reviews/${id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: action === "reject" ? JSON.stringify({ reason }) : undefined,
      });
      if (!r.ok) throw new Error((await r.json()).detail ?? `HTTP ${r.status}`);
      setItems((prev) => prev.filter((it) => it.id !== id));
    } catch (e) {
      alert(`실패: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusyId(null);
    }
  }

  if (loading) return <Loading />;
  if (error) return <div style={{ color: "crimson" }}>{error}</div>;

  return (
    <>
      <div className="section-title">인증리뷰 검수 ({items.length}건 대기)</div>
      <div className="muted" style={{ marginBottom: 12 }}>
        첨부 서류(계약서·확인설명서 등)로 실제 거래 여부를 확인하고 승인/거부하세요.
        결정 시 서류는 즉시 폐기됩니다.
      </div>
      {items.length === 0 && <div className="muted">검수 대기중인 인증리뷰가 없습니다.</div>}
      <div className="review-list">
        {items.map((it) => (
          <div key={it.id} className="review-item admin">
            <div className="review-head">
              <Link to={`/realtor/${it.realtor_id}`} className="review-author">
                중개사 {it.realtor_id}
              </Link>
              <span className="stars" style={{ fontSize: 14 }}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <span key={n} className={n <= it.rating ? "star on" : "star"}>★</span>
                ))}
              </span>
              <span className="muted review-date">{(it.created_at || "").slice(0, 16)}</span>
            </div>
            <div className="review-body">{it.body}</div>
            <div className="review-author-line muted">작성자: {it.author_name}</div>
            <div className="admin-actions">
              {it.doc_name ? (
                <a
                  className="contact-btn"
                  href={`${API_BASE}/admin/reviews/${it.id}/document`}
                  target="_blank"
                  rel="noreferrer"
                >📎 서류 보기 ({it.doc_name})</a>
              ) : (
                <span className="muted">첨부 서류 없음</span>
              )}
              <button
                className="review-submit"
                disabled={busyId === it.id}
                onClick={() => decide(it.id, "approve")}
              >승인</button>
              <button
                className="review-reject"
                disabled={busyId === it.id}
                onClick={() => decide(it.id, "reject")}
              >거부</button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
