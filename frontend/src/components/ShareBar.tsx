import { useState, type RefObject } from "react";
import { useNavigate } from "react-router-dom";
import { ImageDown, Copy, Link2, MessagesSquare } from "lucide-react";
import { saveImage, copyImage, copyText, shareKakao, shareNative, captureToDataUrl, stashForumImage } from "../lib/share";
import { useAuth } from "../auth";

// 섹션 공유 바 — 이미지 저장/복사, 카카오 공유, URL 복사. 이미지엔 콕집+URL 워터마크.
export default function ShareBar({ targetRef, title, fileName }: {
  targetRef: RefObject<HTMLElement | null>; title: string; fileName: string;
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const flash = (m: string) => { setMsg(m); window.setTimeout(() => setMsg(""), 1800); };
  const url = typeof window !== "undefined" ? window.location.href : "";
  const navigate = useNavigate();
  const { token } = useAuth();

  const onSave = async () => {
    if (!targetRef.current || busy) return;
    setBusy(true);
    try {
      const r = await saveImage(targetRef.current, fileName);
      flash(r === "album" ? "‘이미지 저장’을 누르면 앨범에 저장돼요"
        : r === "download" ? "이미지 저장됨" : "이미지 생성 실패");
    } finally { setBusy(false); }
  };
  const onCopyImg = async () => {
    if (!targetRef.current || busy) return;
    setBusy(true);
    const ok = await copyImage(targetRef.current);
    setBusy(false);
    flash(ok ? "이미지 복사됨" : "이미지 복사 미지원 — 저장으로 받아주세요");
  };
  const onKakao = async () => {
    // 모바일: OS 공유시트(카카오톡 포함) 우선 — 설치 프롬프트 없이 가장 안정적
    if (await shareNative(title, url)) return;
    // 데스크탑 등: 카카오 SDK 공유
    const ok = await shareKakao(title, url); if (!ok) flash("카카오 공유 실패");
  };
  const onUrl = async () => { flash((await copyText(url)) ? "URL 복사됨" : "URL 복사 실패"); };
  const onForum = async () => {
    if (!targetRef.current || busy) return;
    if (!token) { flash("로그인 후 이용해주세요"); return; }
    setBusy(true);
    try {
      const dataUrl = await captureToDataUrl(targetRef.current);
      stashForumImage(dataUrl, title);
      navigate("/forum/new");
    } catch { flash("이미지 생성 실패"); }
    finally { setBusy(false); }
  };

  return (
    <div className="share-bar">
      {msg && <span className="share-msg">{msg}</span>}
      <button onClick={onSave} disabled={busy} title="이미지 저장">
        <ImageDown size={14} strokeWidth={2.2} /> {busy ? "처리중…" : "이미지"}
      </button>
      <button onClick={onCopyImg} disabled={busy} title="이미지 복사">
        <Copy size={14} strokeWidth={2.2} /> 복사
      </button>
      <button onClick={onKakao} className="kakao" title="카카오톡 공유">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
          <path d="M12 3C6.48 3 2 6.36 2 10.5c0 2.66 1.8 5 4.51 6.32-.15.52-.97 3.36-1 3.59 0 0-.02.17.09.24.11.07.24.02.24.02.32-.05 3.74-2.45 4.33-2.87.59.08 1.2.13 1.83.13 5.52 0 10-3.36 10-7.5S17.52 3 12 3z" />
        </svg>
        카카오
      </button>
      <button onClick={onUrl} title="URL 복사">
        <Link2 size={14} strokeWidth={2.2} /> URL
      </button>
      <button onClick={onForum} className="to-forum" disabled={busy} title="토론장으로 보내기">
        <MessagesSquare size={14} strokeWidth={2.2} /> 토론장
      </button>
    </div>
  );
}
