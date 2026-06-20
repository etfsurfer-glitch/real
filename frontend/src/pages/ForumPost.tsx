import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { ThumbsUp, ThumbsDown, ArrowLeft, MessageCircle } from "lucide-react";
import { useAuth } from "../auth";
import { LevelBadge } from "../components/LevelBadge";

const API = import.meta.env.VITE_API_BASE;

type Vote = { up: number; down: number; score: number; my_vote: number };
type Rank = { rank?: string; emoji?: string; level?: number; is_admin?: boolean };
type Post = Vote & Rank & { id: number; nickname: string; title: string; body: string;
  has_image: boolean; comment_count: number; created_at: string; is_mine: boolean };
type Comment = Vote & Rank & { id: number; nickname: string; body: string; created_at: string; is_mine: boolean };

function ago(iso: string): string {
  const t = new Date((iso || "").replace(" ", "T") + "Z").getTime();
  if (!t) return "";
  const s = Math.floor((Date.now() - t) / 1000);
  if (s < 60) return "방금"; if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`; return `${Math.floor(s / 86400)}일 전`;
}

function Votes({ type, id, v, onChange }: {
  type: "post" | "comment"; id: number; v: Vote; onChange: (nv: Vote) => void;
}) {
  const { token } = useAuth();
  const vote = async (value: number) => {
    if (!token) { alert("로그인 후 이용해주세요."); return; }
    const r = await fetch(`${API}/forum/vote`, {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ target_type: type, target_id: id, value }),
    });
    if (r.ok) { const d = await r.json(); onChange({ up: d.up, down: d.down, score: d.score, my_vote: d.my_vote }); }
  };
  return (
    <div className="vote-box">
      <button className={`vote-btn up ${v.my_vote === 1 ? "on" : ""}`} onClick={() => vote(1)} title="공감">
        <ThumbsUp size={16} strokeWidth={2.1} />
        <span className="vote-n">{v.up}</span>
      </button>
      <button className={`vote-btn down ${v.my_vote === -1 ? "on" : ""}`} onClick={() => vote(-1)} title="비공감">
        <ThumbsDown size={16} strokeWidth={2.1} />
        <span className="vote-n">{v.down}</span>
      </button>
    </div>
  );
}

export default function ForumPost() {
  const { id } = useParams<{ id: string }>();
  const { token, user, refreshMe } = useAuth();
  const [post, setPost] = useState<Post | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(() => {
    if (!API || !id) return;
    const h = token ? { Authorization: `Bearer ${token}` } : undefined;
    fetch(`${API}/forum/posts/${id}`, { headers: h })
      .then(async (r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((d) => { setPost(d.post); setComments(d.comments ?? []); })
      .catch(() => setNotFound(true));
  }, [id, token]);
  useEffect(() => { load(); }, [load]);

  const addComment = async () => {
    if (!token) { alert("로그인 후 이용해주세요."); return; }
    if (user?.needsNickname) { alert("닉네임을 먼저 설정해주세요."); return; }
    const b = text.trim();
    if (b.length < 1 || busy) return;
    setBusy(true);
    try {
      const r = await fetch(`${API}/forum/posts/${id}/comments`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ body: b }),
      });
      if (r.ok) { setText(""); load(); const d = await r.json().catch(() => ({})); if (d.awarded) await refreshMe(); }
      else { const d = await r.json().catch(() => ({})); alert(typeof d.detail === "string" ? d.detail : "등록 실패"); }
    } finally { setBusy(false); }
  };

  if (notFound) return <div className="forum-wrap"><div className="muted">글을 찾을 수 없습니다.</div></div>;
  if (!post) return <div className="forum-wrap"><div className="muted">불러오는 중…</div></div>;

  return (
    <div className="forum-wrap">
      <Link to="/forum" className="forum-back"><ArrowLeft size={14} /> 토론장</Link>

      <div className="forum-post">
        <Votes type="post" id={post.id} v={post}
          onChange={(nv) => setPost({ ...post, ...nv })} />
        <div className="forum-post-main">
          <h2 className="forum-post-title">{post.title}</h2>
          <div className="forum-post-meta">
            {post.is_admin
              ? <span className="admin-badge">관리자</span>
              : <LevelBadge level={post.level} rank={post.rank} />}
            <b>{post.nickname}</b> · {ago(post.created_at)}
          </div>
          {post.has_image && (
            <img className="forum-post-img" src={`${API}/forum/posts/${post.id}/image`} alt="첨부" />
          )}
          {post.body && <div className="forum-post-body">{post.body}</div>}
        </div>
      </div>

      <div className="forum-cmt-head">
        <MessageCircle size={15} /> 댓글 {comments.length}
      </div>

      <div className="forum-cmt-form">
        <textarea rows={2} maxLength={2000} value={text} placeholder={token ? "댓글을 입력하세요" : "로그인 후 댓글 작성 가능"}
          onChange={(e) => setText(e.target.value)} disabled={!token} />
        <button className="ai-send" disabled={busy || !text.trim()} onClick={addComment}>등록</button>
      </div>

      <div className="forum-cmt-list">
        {comments.length === 0 && <div className="muted" style={{ fontSize: 13 }}>첫 댓글을 남겨보세요.</div>}
        {comments.map((c, i) => (
          <div key={c.id} className="forum-cmt">
            <Votes type="comment" id={c.id} v={c}
              onChange={(nv) => setComments((cs) => cs.map((x, j) => j === i ? { ...x, ...nv } : x))} />
            <div className="forum-cmt-main">
              <div className="forum-cmt-meta">
                {c.is_admin
                  ? <span className="admin-badge">관리자</span>
                  : <LevelBadge level={c.level} rank={c.rank} />}
                <b>{c.nickname}</b> · {ago(c.created_at)}
              </div>
              <div className="forum-cmt-body">{c.body}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
