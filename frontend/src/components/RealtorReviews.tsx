import { useEffect, useState } from "react";
import { Loading } from "./Loading";
import { useAuth, loginKakao } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

type Review = {
  id: number;
  author_name: string;
  is_admin?: boolean;
  review_type: "general" | "verified";
  verified: boolean;
  rating: number | null;
  body: string;
  created_at: string;
};

type ReviewsResp = {
  summary: { avg_rating: number | null; verified_count: number; total_count: number };
  items: Review[];
};

function Stars({ value, size = 14 }: { value: number; size?: number }) {
  return (
    <span className="stars" style={{ fontSize: size }} aria-label={`별점 ${value}점`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={n <= value ? "star on" : "star"}>★</span>
      ))}
    </span>
  );
}

function StarInput({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <span className="stars input" style={{ fontSize: 26 }}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          type="button"
          key={n}
          className={n <= (hover || value) ? "star on" : "star"}
          onMouseEnter={() => setHover(n)}
          onMouseLeave={() => setHover(0)}
          onClick={() => onChange(n)}
          aria-label={`${n}점`}
        >★</button>
      ))}
    </span>
  );
}

function fmtDate(s: string): string {
  // sqlite datetime('now') → "YYYY-MM-DD HH:MM:SS" (UTC). 날짜만 노출.
  return (s || "").slice(0, 10);
}

export function RealtorReviews(
  { realtorId, onSummary }: { realtorId: string; onSummary?: (total: number) => void },
) {
  const [data, setData] = useState<ReviewsResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!API_BASE) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/realtor/${encodeURIComponent(realtorId)}/reviews`)
      .then((r) => r.json())
      .then((j) => {
        if (!cancelled) {
          setData(j);
          setLoading(false);
          if (j?.summary && typeof j.summary.total_count === "number") onSummary?.(j.summary.total_count);
        }
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [realtorId, reloadKey, onSummary]);

  const reload = () => setReloadKey((k) => k + 1);

  return (
    <div className="reviews" id="realtor-reviews">
      <div className="section-title">
        중개사무소 리뷰
        {data && data.summary.verified_count > 0 && data.summary.avg_rating != null && (
          <span className="review-summary">
            <Stars value={Math.round(data.summary.avg_rating)} />
            <b>{data.summary.avg_rating.toFixed(1)}</b>
            <span className="muted">거래인증 {data.summary.verified_count}건</span>
          </span>
        )}
      </div>

      <ReviewForm realtorId={realtorId} onSubmitted={reload} />

      {loading && <Loading />}
      {data && data.items.length === 0 && (
        <div className="muted" style={{ padding: "12px 0" }}>
          아직 등록된 리뷰가 없습니다. 첫 리뷰를 남겨보세요.
        </div>
      )}
      <div className="review-list">
        {data?.items.map((r) => (
          <div key={r.id} className="review-item">
            <div className="review-head">
              {r.is_admin && <span className="admin-badge">관리자</span>}
              <span className="review-author">{r.author_name}</span>
              {r.verified && <span className="badge verified">✓ 거래인증</span>}
              {r.verified && r.rating != null && <Stars value={r.rating} />}
              <span className="muted review-date">{fmtDate(r.created_at)}</span>
            </div>
            <div className="review-body">{r.body}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReviewForm({ realtorId, onSubmitted }: { realtorId: string; onSubmitted: () => void }) {
  const { user, token, ready, configured } = useAuth();
  const [mode, setMode] = useState<"general" | "verified">("general");
  const [body, setBody] = useState("");
  const [rating, setRating] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const reset = () => { setBody(""); setRating(0); setFile(null); };

  // 로그인 회원만 작성 가능. 미설정/미로그인 시 로그인 유도 카드.
  if (configured && ready && !user) {
    return (
      <div className="review-form review-login-gate">
        <div className="muted" style={{ marginBottom: 10 }}>
          리뷰는 로그인한 회원만 작성할 수 있습니다.
        </div>
        <button className="auth-btn kakao" onClick={() => loginKakao()}>
          <span className="kakao-icon" aria-hidden>💬</span> 카카오 로그인하고 리뷰 쓰기
        </button>
      </div>
    );
  }

  async function submit() {
    setMsg(null);
    if (!token) { setMsg({ kind: "err", text: "로그인이 필요합니다." }); return; }
    if (body.trim().length < 2) { setMsg({ kind: "err", text: "내용을 2자 이상 입력해주세요." }); return; }
    if (mode === "verified") {
      if (rating < 1) { setMsg({ kind: "err", text: "별점을 선택해주세요." }); return; }
      if (!file) { setMsg({ kind: "err", text: "거래를 입증할 서류를 첨부해주세요." }); return; }
    }
    const auth = { Authorization: `Bearer ${token}` };
    setBusy(true);
    try {
      if (mode === "general") {
        const r = await fetch(`${API_BASE}/realtor/${encodeURIComponent(realtorId)}/reviews`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...auth },
          body: JSON.stringify({ body: body.trim() }),
        });
        if (!r.ok) throw new Error((await r.json()).detail ?? `HTTP ${r.status}`);
        setMsg({ kind: "ok", text: "리뷰가 등록되었습니다." });
        reset();
        onSubmitted();
      } else {
        const fd = new FormData();
        fd.append("rating", String(rating));
        fd.append("body", body.trim());
        fd.append("document", file as File);
        const r = await fetch(`${API_BASE}/realtor/${encodeURIComponent(realtorId)}/reviews/verified`, {
          method: "POST",
          headers: auth,
          body: fd,
        });
        if (!r.ok) throw new Error((await r.json()).detail ?? `HTTP ${r.status}`);
        setMsg({ kind: "ok", text: "인증리뷰가 접수되었습니다. 서류 확인 후 (거래인증) 뱃지와 함께 게시됩니다." });
        reset();
      }
    } catch (e) {
      setMsg({ kind: "err", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="review-form">
      {user && (
        <div className="review-as muted">
          <b>{user.nickname ?? "회원"}</b> 님으로 작성
        </div>
      )}
      <div className="review-tabs">
        <button
          className={mode === "general" ? "active" : ""}
          onClick={() => { setMode("general"); setMsg(null); }}
        >일반 리뷰</button>
        <button
          className={mode === "verified" ? "active" : ""}
          onClick={() => { setMode("verified"); setMsg(null); }}
        >인증 리뷰 <span className="badge verified">✓ 거래인증</span></button>
      </div>

      <div className="review-form-note muted">
        {mode === "general"
          ? "거래 경험이나 의견을 자유롭게 남겨주세요. 일반 리뷰는 별점 없이 의견만 게시됩니다."
          : "본인의 계약서·중개대상물 확인설명서 등 거래를 입증할 수 있는 서류를 첨부하면, 관리자 확인 후 별점과 함께 (거래인증) 뱃지가 부여됩니다. 첨부 서류는 인증 확인 즉시 폐기됩니다."}
      </div>

      {mode === "verified" && (
        <div className="review-rating-row">
          <span className="muted">별점</span>
          <StarInput value={rating} onChange={setRating} />
        </div>
      )}

      <textarea
        className="review-textarea"
        placeholder={mode === "general" ? "이 중개사무소에 대한 의견을 남겨주세요" : "거래 경험을 자세히 남겨주세요"}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        maxLength={2000}
        rows={3}
      />

      <div className="review-form-row">
        {mode === "verified" && (
          <label className="review-file">
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.heic,image/*,application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <span>{file ? `📎 ${file.name}` : "📎 서류 첨부"}</span>
          </label>
        )}
        <button className="review-submit" onClick={submit} disabled={busy}>
          {busy ? "등록 중…" : "등록"}
        </button>
      </div>

      {msg && (
        <div className={`review-msg ${msg.kind}`}>{msg.text}</div>
      )}
    </div>
  );
}
