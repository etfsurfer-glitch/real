import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Share2, ImageDown, Copy, Link2, MessagesSquare, X } from "lucide-react";
import { saveImage, copyImage, copyText, shareKakao, shareNative, captureToDataUrl, stashForumImage } from "../lib/share";
import { useAuth } from "../auth";
import { subscribeShare, getShareTarget } from "../lib/sharestore";

// 전역 플로팅 공유버튼 — 우하단 '사용법' 위에 뜬다. 공유 대상을 등록한 페이지(ShareBar 호출)에서만 노출.
// 누르면 이미지 저장/복사·카카오·URL·토론장 메뉴가 펼쳐진다(예전 인라인 공유바와 동일 기능).
export default function ShareFab() {
  const [, force] = useState(0);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();
  const { token } = useAuth();
  useEffect(() => subscribeShare(() => force((n) => n + 1)), []);

  const t = getShareTarget();
  if (!t.ref) return null;   // 공유 대상이 등록된 페이지에서만 버튼 노출

  const url = typeof window !== "undefined" ? window.location.href : "";
  const flash = (m: string) => { setMsg(m); window.setTimeout(() => setMsg(""), 1800); };
  const el = () => t.ref?.current ?? null;
  const after = () => setOpen(false);

  const onSave = async () => {
    const e = el(); if (!e || busy) return;
    setBusy(true);
    try {
      const r = await saveImage(e, t.fileName);
      flash(r === "album" ? "‘이미지 저장’을 누르면 앨범에 저장돼요"
        : r === "download" ? "이미지 저장됨" : "이미지 생성 실패");
    } finally { setBusy(false); after(); }
  };
  const onCopyImg = async () => {
    const e = el(); if (!e || busy) return;
    setBusy(true);
    const ok = await copyImage(e);
    setBusy(false); after();
    flash(ok ? "이미지 복사됨" : "이미지 복사 미지원 — 저장으로 받아주세요");
  };
  const onKakao = async () => {
    after();
    if (await shareNative(t.title, url)) return;
    if (!(await shareKakao(t.title, url))) flash("카카오 공유 실패");
  };
  const onUrl = async () => { after(); flash((await copyText(url)) ? "URL 복사됨" : "URL 복사 실패"); };
  const onForum = async () => {
    const e = el(); if (!e || busy) return;
    if (!token) { flash("로그인 후 이용해주세요"); return; }
    setBusy(true);
    try {
      const dataUrl = await captureToDataUrl(e);
      stashForumImage(dataUrl, t.title);
      after();
      navigate("/forum/new");
    } catch { flash("이미지 생성 실패"); }
    finally { setBusy(false); }
  };

  return (
    <>
      {open && <div className="share-fab-backdrop" onClick={() => setOpen(false)} />}
      <div className="share-fab-wrap">
        {msg && <span className="share-fab-msg">{msg}</span>}
        {open && (
          <div className="share-fab-menu" role="menu">
            <button onClick={onSave} disabled={busy}><ImageDown size={15} strokeWidth={2.2} /> 이미지 저장</button>
            <button onClick={onCopyImg} disabled={busy}><Copy size={15} strokeWidth={2.2} /> 이미지 복사</button>
            <button className="kakao" onClick={onKakao}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                <path d="M12 3C6.48 3 2 6.36 2 10.5c0 2.66 1.8 5 4.51 6.32-.15.52-.97 3.36-1 3.59 0 0-.02.17.09.24.11.07.24.02.24.02.32-.05 3.74-2.45 4.33-2.87.59.08 1.2.13 1.83.13 5.52 0 10-3.36 10-7.5S17.52 3 12 3z" />
              </svg>
              카카오톡 공유
            </button>
            <button onClick={onUrl}><Link2 size={15} strokeWidth={2.2} /> URL 복사</button>
            <button className="to-forum" onClick={onForum} disabled={busy}><MessagesSquare size={15} strokeWidth={2.2} /> 토론장에 올리기</button>
          </div>
        )}
        <button className="share-fab" onClick={() => setOpen((v) => !v)} aria-label="공유하기" aria-expanded={open}>
          {open ? <X size={19} strokeWidth={2.4} aria-hidden /> : <Share2 size={18} strokeWidth={2.4} aria-hidden />}
          <span>공유하기</span>
        </button>
      </div>
    </>
  );
}
