import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PenLine, ImagePlus, X } from "lucide-react";
import { useAuth } from "../auth";
import { takeForumImage } from "../lib/share";

const API = import.meta.env.VITE_API_BASE;

export default function ForumCompose() {
  const { token, user, refreshMe } = useAuth();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [imgUrl, setImgUrl] = useState<string | null>(null);   // 미리보기 dataURL/objectURL
  const [imgBlob, setImgBlob] = useState<Blob | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement | null>(null);

  // 공유→토론장으로 넘어온 이미지 받기 (한 번만)
  useEffect(() => {
    const d = takeForumImage();
    if (d) {
      setImgUrl(d.dataUrl);
      fetch(d.dataUrl).then((r) => r.blob()).then(setImgBlob).catch(() => {});
      if (d.title) setTitle((t) => t || d.title);
    }
  }, []);

  if (!token) return <div className="muted" style={{ padding: 20 }}>로그인 후 글을 쓸 수 있어요.</div>;
  if (user?.needsNickname)
    return <div className="muted" style={{ padding: 20 }}>닉네임을 먼저 설정해주세요.</div>;

  const pickFile = (f: File) => {
    setImgBlob(f);
    setImgUrl(URL.createObjectURL(f));
  };

  const submit = async () => {
    if (busy) return;
    if (title.trim().length < 2) { setErr("제목을 2자 이상 입력해주세요"); return; }
    setBusy(true); setErr("");
    try {
      const fd = new FormData();
      fd.append("title", title.trim());
      fd.append("body", body.trim());
      if (imgBlob) fd.append("image", imgBlob, "share.png");
      const r = await fetch(`${API}/forum/posts`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd,
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { setErr(typeof d.detail === "string" ? d.detail : "등록 실패"); return; }
      if (d.awarded) await refreshMe();   // +10P 적립 시 포인트 배지 갱신
      navigate(`/forum/${d.id}`);
    } finally { setBusy(false); }
  };

  return (
    <div className="forum-wrap">
      <div className="section-title"><PenLine size={16} strokeWidth={2.2} /> 토론장 글쓰기</div>
      <div className="muted" style={{ fontSize: 12.5, marginTop: -4 }}>
        닉네임 <b>{user?.nickname}</b> 으로 등록됩니다.
      </div>

      <input className="forum-input" placeholder="제목" maxLength={120}
        value={title} onChange={(e) => setTitle(e.target.value)} />

      {imgUrl && (
        <div className="forum-img-preview">
          <img src={imgUrl} alt="첨부 이미지" />
          <button className="forum-img-x" title="이미지 제거"
            onClick={() => { setImgUrl(null); setImgBlob(null); }}><X size={15} /></button>
        </div>
      )}

      <textarea className="forum-textarea" rows={9} maxLength={8000}
        placeholder="내용을 입력하세요. (공유에서 넘어온 이미지가 함께 첨부돼요)"
        value={body} onChange={(e) => setBody(e.target.value)} />

      <input ref={fileRef} type="file" accept="image/*" hidden
        onChange={(e) => e.target.files?.[0] && pickFile(e.target.files[0])} />

      <div className="forum-compose-foot">
        {err && <span className="cr-msg" style={{ color: "crimson" }}>{err}</span>}
        <button className="auth-btn ghost" onClick={() => fileRef.current?.click()}>
          <ImagePlus size={14} /> 이미지
        </button>
        <button className="ai-send" disabled={busy} onClick={submit}>
          {busy ? "등록 중…" : "등록"}
        </button>
      </div>
    </div>
  );
}
