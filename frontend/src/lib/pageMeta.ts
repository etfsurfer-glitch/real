import { useEffect } from "react";

// 페이지별 동적 <head> 메타 — 사용자 화면(본문)은 그대로 두고, 탭 제목/검색 스니펫/
// OG 만 페이지에 맞게 바꾼다. Googlebot은 JS 렌더 후 이 값을 읽어 색인에 반영.
// 언마운트 시 기본값으로 복원해 다른 페이지가 잘못된 메타를 물려받지 않게 한다.

const DEFAULT_TITLE = "콕집 — 부동산 매물·실거래·중개사 분석 | koczip";
const DEFAULT_DESC =
  "전국 아파트·오피스텔 실거래가·매물·중개사무소를 매일 분석. 급매·저평가 단지, 시세 통계, AI 질의응답, 부동산 토론장까지 콕집에서.";

function setTag(selector: string, attr: "name" | "property", key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(selector);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function setCanonical(url: string) {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", "canonical");
    document.head.appendChild(el);
  }
  el.setAttribute("href", url);
}

export function usePageMeta(title?: string, description?: string, canonicalPath?: string) {
  useEffect(() => {
    if (title) {
      document.title = title;
      setTag('meta[property="og:title"]', "property", "og:title", title);
    }
    if (description) {
      setTag('meta[name="description"]', "name", "description", description);
      setTag('meta[property="og:description"]', "property", "og:description", description);
    }
    if (canonicalPath) {
      const url = `https://koczip.com${canonicalPath}`;
      setCanonical(url);
      setTag('meta[property="og:url"]', "property", "og:url", url);
    }
    return () => {
      // 기본값 복원
      document.title = DEFAULT_TITLE;
      setTag('meta[name="description"]', "name", "description", DEFAULT_DESC);
      setTag('meta[property="og:title"]', "property", "og:title", "콕집 — 부동산 매물·실거래·중개사 분석");
      setTag('meta[property="og:description"]', "property", "og:description",
        "실거래·매물을 AI에게 물어보고, 토론장에서 의견을 나눠요. 전국 매물·실거래가·중개사 데이터를 매일 갱신·분석.");
      setCanonical("https://koczip.com/");
      setTag('meta[property="og:url"]', "property", "og:url", "https://koczip.com/");
    };
  }, [title, description, canonicalPath]);
}
