import { useEffect, useState, useCallback, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MessagesSquare, PenLine, ThumbsUp, ThumbsDown, MessageCircle, Image as ImageIcon, Search, X } from "lucide-react";
import { useAuth } from "../auth";
import { LevelBadge } from "../components/LevelBadge";

const API = import.meta.env.VITE_API_BASE;

type Post = {
  id: number; nickname: string; title: string; excerpt: string;
  has_image: boolean; up: number; down: number; score: number;
  comment_count: number; created_at: string;
  rank?: string; emoji?: string; level?: number; is_admin?: boolean;
};

function ago(iso: string): string {
  const t = new Date((iso || "").replace(" ", "T") + "Z").getTime();
  if (!t) return "";
  const s = Math.floor((Date.now() - t) / 1000);
  if (s < 60) return "방금";
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  return `${Math.floor(s / 86400)}일 전`;
}

export default function ForumList() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [sort, setSort] = useState<"recent" | "hot">("recent");
  const [items, setItems] = useState<Post[] | null>(null);
  const [query, setQuery] = useState("");      // 입력값
  const [q, setQ] = useState("");              // 디바운스 적용된 검색어
  const timer = useRef<number | null>(null);

  // 검색어 디바운스
  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setQ(query.trim()), 300);
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, [query]);

  const load = useCallback(() => {
    if (!API) return;
    setItems(null);
    const qs = `sort=${sort}&limit=40${q ? `&q=${encodeURIComponent(q)}` : ""}`;
    fetch(`${API}/forum/posts?${qs}`)
      .then((r) => r.json()).then((d) => setItems(d.items ?? [])).catch(() => setItems([]));
  }, [sort, q]);
  useEffect(() => { load(); }, [load]);

  const write = () => {
    if (!token) { alert("로그인 후 글을 쓸 수 있어요."); return; }
    navigate("/forum/new");
  };

  return (
    <div className="forum-wrap">
      <div className="forum-head">
        <div className="section-title" style={{ margin: 0 }}>
          <MessagesSquare size={17} strokeWidth={2.2} /> 토론장
        </div>
        <button className="ai-send forum-write-btn" onClick={write}>
          <PenLine size={14} /> 글쓰기
        </button>
      </div>
      <div className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>
        부동산 이슈·급매·시세 무엇이든. 누구나 글·댓글·추천/비추천 할 수 있어요.
      </div>

      <div className="forum-controls">
        <div className="forum-search">
          <Search size={15} aria-hidden />
          <input value={query} placeholder="제목·내용·닉네임 검색"
            onChange={(e) => setQuery(e.target.value)} />
          {query && <button className="forum-search-x" onClick={() => setQuery("")} title="지우기"><X size={14} /></button>}
        </div>
        <div className="sort-toggle forum-sort">
          <button className={sort === "recent" ? "on" : ""} onClick={() => setSort("recent")}>최신순</button>
          <button className={sort === "hot" ? "on" : ""} onClick={() => setSort("hot")}>인기순</button>
        </div>
      </div>

      {!items ? <div className="muted">불러오는 중…</div>
        : items.length === 0 ? (
          <div className="muted" style={{ padding: 24, textAlign: "center" }}>
            {q ? `'${q}' 검색 결과가 없어요.` : "아직 글이 없어요. 첫 글을 남겨보세요!"}
          </div>
        ) : (
        <div className="forum-list">
          {items.map((p) => (
            <Link key={p.id} to={`/forum/${p.id}`} className="forum-row">
              <div className="forum-score" title="공감 / 비공감">
                <span className="fs-up"><ThumbsUp size={13} strokeWidth={2.1} /> {p.up}</span>
                <span className="fs-down"><ThumbsDown size={13} strokeWidth={2.1} /> {p.down}</span>
              </div>
              <div className="forum-row-main">
                <div className="forum-row-title">
                  {p.has_image && <ImageIcon size={13} className="forum-img-chip" />}
                  {p.title}
                </div>
                {p.excerpt && <div className="forum-row-excerpt">{p.excerpt}</div>}
                <div className="forum-row-meta">
                  {p.is_admin
                    ? <span className="admin-badge">관리자</span>
                    : <LevelBadge level={p.level} rank={p.rank} />}
                  <b>{p.nickname}</b>
                  · {ago(p.created_at)}
                  <span className="forum-cc"><MessageCircle size={12} /> {p.comment_count}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
