import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { NewsletterCard, useNewsletterData } from "./AdminNewsletter";

const API = import.meta.env.VITE_API_BASE;
type Region = { code: string; name: string };

/** SNS 워커가 헤드리스 크롬으로 캡처하는 렌더 전용 페이지.
 *  화면 크롬 없이 A4 카드만 1240px 원본 크기로 그린다.
 *  준비되면 body[data-nl="ready"] 를 세워 워커가 캡처 시점을 잡는다.
 *  (내용은 랜딩과 같은 공개 정보라 별도 인증을 두지 않는다 — 검색엔 noindex.) */
export default function RenderNewsletter() {
  const [sp] = useSearchParams();
  const sido = sp.get("sido") || "";
  const sigungu = sp.get("sigungu") || "";
  const dong = sp.get("dong") || "";
  const [names, setNames] = useState<{ sido: string; sgg: string; dong: string }>(
    { sido: "", sgg: "", dong: "" });
  const { deals, dig, loading } = useNewsletterData(sido, sigungu, dong);

  useEffect(() => {
    document.title = "콕집 뉴스레터";
    const m = document.createElement("meta");
    m.name = "robots"; m.content = "noindex,nofollow";
    document.head.appendChild(m);
    document.body.style.background = "#fff";
    return () => { m.remove(); };
  }, []);

  useEffect(() => {
    if (!sido) return;
    const pick = (arr: Region[], code: string) => arr.find((x) => x.code === code)?.name || "";
    Promise.all([
      fetch(`${API}/stats/changes/sido-list`).then((r) => r.json()).then((j) => j.items || []).catch(() => []),
      sigungu ? fetch(`${API}/stats/sigungu-list?sido=${sido.slice(0, 2)}`).then((r) => r.json())
        .then((j) => j.items || []).catch(() => []) : Promise.resolve([]),
      dong ? fetch(`${API}/stats/dong-list?sigungu=${sigungu.slice(0, 5)}`).then((r) => r.json())
        .then((j) => j.items || []).catch(() => []) : Promise.resolve([]),
    ]).then(([a, b, c]: Region[][]) => setNames({
      sido: pick(a, sido), sgg: pick(b, sigungu), dong: pick(c, dong),
    }));
  }, [sido, sigungu, dong]);

  const regionName = useMemo(
    () => [names.sido, names.sgg, names.dong].filter(Boolean).join(" ") || "전국",
    [names]);

  const ready = !loading && !!dig && !!names.sido;
  useEffect(() => { document.body.dataset.nl = ready ? "ready" : "loading"; }, [ready]);

  return (
    <div style={{ width: 1240, background: "#fff" }}>
      <NewsletterCard regionName={regionName} deals={deals} dig={dig} />
    </div>
  );
}
