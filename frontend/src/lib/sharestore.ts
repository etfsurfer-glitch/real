import type { RefObject } from "react";

// 현재 페이지의 공유 대상(스크린샷 캡처 ref·제목·파일명)을 전역 플로팅 공유버튼(ShareFab)에 넘긴다.
// 페이지는 <ShareBar targetRef title fileName/>로 등록만 하고, 실제 공유 UI는 ShareFab 한 곳에서 뜬다.
export type ShareTarget = {
  ref: RefObject<HTMLElement | null> | null;
  title: string;
  fileName: string;
};

let _cur: ShareTarget = { ref: null, title: "콕집", fileName: "콕집" };
const _subs = new Set<() => void>();

export function getShareTarget(): ShareTarget { return _cur; }
export function subscribeShare(fn: () => void): () => void {
  _subs.add(fn);
  return () => { _subs.delete(fn); };
}
function _emit() { _subs.forEach((f) => { try { f(); } catch { /* ignore */ } }); }

export function setShareTarget(t: ShareTarget) { _cur = t; _emit(); }

/** 등록 해제 — 내가 등록한 대상일 때만 비운다(페이지 전환 중 새 대상이 이미 들어왔으면 건드리지 않음). */
export function clearShareTarget(ref?: ShareTarget["ref"]) {
  if (ref && _cur.ref !== ref) return;
  _cur = { ref: null, title: "콕집", fileName: "콕집" };
  _emit();
}
