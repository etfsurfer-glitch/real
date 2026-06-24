// 공유 유틸 — 섹션을 이미지로 캡처(워터마크 포함), 클립보드/파일/카카오/URL.
// html2canvas·Kakao SDK 는 CDN 에서 필요 시 동적 로드(번들 안 키움).

import { KAKAO_JS_KEY } from "./kakaomap";

const H2C_SRC = "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js";
const KAKAO_SRC = "https://t1.kakaocdn.net/kakao_js_sdk/2.7.2/kakao.min.js";

function loadScript(src: string, globalName: string): Promise<unknown> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const w = window as any;
  if (w[globalName]) return Promise.resolve(w[globalName]);
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve(w[globalName]));
      existing.addEventListener("error", reject);
      return;
    }
    const s = document.createElement("script");
    s.src = src; s.async = true;
    s.onload = () => resolve(w[globalName]);
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

// 요소를 캔버스로 캡처하고 하단에 '콕집 + URL' 워터마크를 그린다.
export async function captureToCanvas(el: HTMLElement): Promise<HTMLCanvasElement> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const html2canvas = (await loadScript(H2C_SRC, "html2canvas")) as any;
  const scale = Math.min(2.5, (window.devicePixelRatio || 1) * 1.5);

  // 가로 스크롤되는 표(.rank-scroll 등)는 보이는 폭만 캡처되므로, 캡처 동안 전체 폭으로 펼친다.
  const scrollers: HTMLElement[] = [];
  el.querySelectorAll<HTMLElement>("*").forEach((n) => {
    const ox = getComputedStyle(n).overflowX;
    if ((ox === "auto" || ox === "scroll") && n.scrollWidth > n.clientWidth + 1) scrollers.push(n);
  });
  const saved = scrollers.map((s) => ({ s, css: s.style.cssText }));
  scrollers.forEach((s) => {
    s.style.overflow = "visible"; s.style.overflowX = "visible";
    s.style.width = "max-content"; s.style.maxWidth = "none";
  });
  void el.offsetWidth; // 강제 리플로우
  const fullW = Math.max(el.scrollWidth, el.offsetWidth);
  const fullH = Math.max(el.scrollHeight, el.offsetHeight);

  let src: HTMLCanvasElement;
  try {
    src = await html2canvas(el, {
      backgroundColor: "#ffffff", scale, useCORS: true, logging: false,
      width: fullW, height: fullH,
      windowWidth: Math.max(document.documentElement.clientWidth, fullW),
      // 공유 바·버튼류는 캡처 이미지에서 제외
      ignoreElements: (node: Element) =>
        node.classList?.contains("share-bar") || node.classList?.contains("no-capture"),
    });
  } finally {
    saved.forEach(({ s, css }) => { s.style.cssText = css; }); // 원상복구
  }
  const foot = Math.round(36 * scale);
  const out = document.createElement("canvas");
  out.width = src.width; out.height = src.height + foot;
  const ctx = out.getContext("2d")!;
  ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, out.width, out.height);
  ctx.drawImage(src, 0, 0);
  // 워터마크 푸터
  ctx.fillStyle = "#f4f6f9"; ctx.fillRect(0, src.height, out.width, foot);
  const cy = src.height + foot / 2;
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#1268d3"; ctx.font = `700 ${Math.round(18 * scale)}px sans-serif`;
  ctx.fillText("콕집", Math.round(16 * scale), cy);
  ctx.fillStyle = "#9aa4b0"; ctx.font = `${Math.round(13 * scale)}px sans-serif`;
  const url = window.location.origin + window.location.pathname;
  ctx.fillText(url, Math.round(66 * scale), cy + Math.round(1 * scale));
  return out;
}

function toBlob(c: HTMLCanvasElement): Promise<Blob> {
  return new Promise((res) => c.toBlob((b) => res(b!), "image/png"));
}

export async function downloadImage(el: HTMLElement, name: string): Promise<void> {
  const blob = await toBlob(await captureToCanvas(el));
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `${name}.png`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

export async function copyImage(el: HTMLElement): Promise<boolean> {
  try {
    const blob = await toBlob(await captureToCanvas(el));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const CI = (window as any).ClipboardItem;
    if (!CI || !navigator.clipboard?.write) return false;
    await navigator.clipboard.write([new CI({ "image/png": blob })]);
    return true;
  } catch { return false; }
}

// 캡처 이미지를 dataURL 로 — 토론장 글쓰기로 넘길 때 사용.
export async function captureToDataUrl(el: HTMLElement): Promise<string> {
  return (await captureToCanvas(el)).toDataURL("image/png");
}

// 공유→토론장: 캡처 이미지를 모듈 변수에 임시 보관(SPA 네비게이션 간 유지). 글쓰기 페이지가 꺼내 씀.
let _forumDraft: { dataUrl: string; title: string } | null = null;
export function stashForumImage(dataUrl: string, title: string): void { _forumDraft = { dataUrl, title }; }
export function takeForumImage(): { dataUrl: string; title: string } | null {
  const d = _forumDraft; _forumDraft = null; return d;
}

export async function copyText(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

// 모바일 기본 공유시트(카카오톡·문자 등 설치된 앱 노출). 가장 안정적 — 설치 프롬프트 없음.
// 사용자가 취소(AbortError)해도 실패로 처리하지 않는다.
export async function shareNative(title: string, url: string, desc?: string): Promise<boolean> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nav = navigator as any;
  if (!nav.share) return false;
  try {
    await nav.share({ title: `[콕집] ${title}`, text: desc ? `[콕집] ${title}\n${desc}` : `[콕집] ${title}`, url });
    return true;
  } catch (e) {
    // 사용자가 공유시트를 닫은 경우(취소)는 실패 아님
    if (e && (e as { name?: string }).name === "AbortError") return true;
    return false;
  }
}

// 피드형 카카오 공유 — 이미지(OG 명함 카드)·제목·설명을 직접 지정. 중개사 홈페이지 공유용.
export async function shareKakaoFeed(title: string, desc: string, imageUrl: string, url: string): Promise<boolean> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Kakao = (await loadScript(KAKAO_SRC, "Kakao")) as any;
    if (Kakao && !Kakao.isInitialized()) Kakao.init(KAKAO_JS_KEY);
    Kakao.Share.sendDefault({
      objectType: "feed",
      content: { title, description: desc || "", imageUrl,
        link: { webUrl: url, mobileWebUrl: url } },
      buttons: [{ title: "홈페이지 보기", link: { webUrl: url, mobileWebUrl: url } }],
    });
    return true;
  } catch { return false; }
}

// URL만 네이티브 공유시트로(모바일) — 카카오톡 선택 시 그쪽이 URL의 OG(명함 카드)를 스크랩해
// 가로 링크카드로 예쁘게 보여준다. (SDK 피드 공유의 세로 크롭 문제 회피) '콕집' 접두 없음.
export async function shareUrlNative(title: string, url: string): Promise<boolean> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nav = navigator as any;
  if (!nav.share) return false;
  try { await nav.share({ title, url }); return true; }
  catch (e) { return (e as { name?: string })?.name === "AbortError"; }
}

export async function shareKakao(title: string, url: string, desc?: string): Promise<boolean> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Kakao = (await loadScript(KAKAO_SRC, "Kakao")) as any;
    if (Kakao && !Kakao.isInitialized()) Kakao.init(KAKAO_JS_KEY);
    Kakao.Share.sendDefault({
      objectType: "text",
      text: `[콕집] ${title}${desc ? "\n" + desc : ""}`,
      link: { webUrl: url, mobileWebUrl: url },
    });
    return true;
  } catch { return false; }
}
