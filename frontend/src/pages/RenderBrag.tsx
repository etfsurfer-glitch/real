import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

const API = import.meta.env.VITE_API_BASE;
const PY = 3.305785;

/** SNS 홍보용 카드뉴스 렌더 페이지 — 워커(헤드리스 크롬)가 통째로 캡처한다.
 *  인스타 세로 규격 1080×1350 고정. 준비되면 body[data-nl="ready"] 를 세워 캡처 시점을 알린다.
 *  (랜딩과 같은 공개 정보만 쓰므로 별도 인증 없음 — 검색엔 noindex.) */
type Deal = {
  complex_no: number; complex_name: string; area_name: string; area1_m2: number;
  asking_min: number; avg_real: number; households: number; region_name: string;
  n_listings: number; discount_max: number;
};
type Loan = {
  article_no: string; complex_no: number; complex_name: string; area_name: string;
  area1_m2: number; price: number; floor_info: string; region_name: string; matched: string;
};

const eok = (won: number) => {
  const e = Math.floor(won / 1e8);
  const man = Math.round((won - e * 1e8) / 1e7);          // 천만 단위
  return man > 0 ? `${e}억 ${man}천` : `${e}억`;
};

export default function RenderBrag() {
  const [sp] = useSearchParams();
  const sido = sp.get("sido") || "11";
  const kind = sp.get("kind") || "";              // "" = 급매, "loan" = 주인대출 승계
  const py = Number(sp.get("py") || 30);
  const minhh = Number(sp.get("minhh") || 300);
  const [rows, setRows] = useState<Deal[] | null>(null);
  const [loans, setLoans] = useState<Loan[] | null>(null);
  const [sidoName, setSidoName] = useState("");

  useEffect(() => {
    document.title = "콕집 카드뉴스";
    const m = document.createElement("meta");
    m.name = "robots"; m.content = "noindex,nofollow";
    document.head.appendChild(m);
    document.body.style.background = "#fff";
    document.body.style.margin = "0";
    return () => { m.remove(); };
  }, []);

  useEffect(() => {
    const s2 = sido.slice(0, 2);
    fetch(`${API}/stats/changes/sido-list`).then((r) => r.json())
      .then((j) => setSidoName(((j.items || []).find((x: any) => x.code.slice(0, 2) === s2)?.name || "")
        .replace("시", "").replace("특별", "").replace("광역", "")))
      .catch(() => setSidoName(""));
    if (kind === "loan") {
      fetch(`${API}/stats/special-deals?kind=loan&sido=${s2}&sort=price_desc&limit=200`)
        .then((r) => r.json()).then((j) => setLoans(j.items || [])).catch(() => setLoans([]));
      return;
    }
    fetch(`${API}/stats/quick-deals?sido=${s2}&pyeong=${py}&days=90&min_discount=0.05`
      + `&min_samples=3&limit=200`)
      .then((r) => r.json())
      .then((j) => setRows((j.items || []).filter((d: Deal) => (d.households || 0) >= minhh)))
      .catch(() => setRows([]));
  }, [sido, py, minhh, kind]);

  const top = useMemo(() => {
    if (!rows) return [];
    return [...rows]
      .map((d) => ({ ...d, gap: d.avg_real > 0 ? (d.avg_real - d.asking_min) / d.avg_real : 0 }))
      .sort((a, b) => b.gap - a.gap)
      .slice(0, 6);
  }, [rows]);

  // 같은 물건이 여러 중개사 광고로 중복돼 카드가 한 단지로 도배된다 — 단지당 1건만 남긴다.
  const loanTop = useMemo(() => {
    const seen = new Set<string>();
    const out: Loan[] = [];
    for (const d of loans || []) {
      const key = String(d.complex_no);      // 단지당 1건 — 같은 단지가 평형별로 반복되지 않게
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(d);
      if (out.length >= 6) break;
    }
    return out;
  }, [loans]);
  const loanN = loans ? loans.length : 0;

  useEffect(() => {
    if (rows || loans) setTimeout(() => document.body.setAttribute("data-nl", "ready"), 400);
  }, [rows, loans, top, loanTop]);

  const today = new Date();
  const dateStr = `${today.getFullYear()}.${String(today.getMonth() + 1).padStart(2, "0")}`
    + `.${String(today.getDate()).padStart(2, "0")}`;

  return (
    <div id="nl-card" style={{
      width: 1080, height: 1350, boxSizing: "border-box", position: "relative",
      background: "linear-gradient(160deg,#0b2a52 0%,#1268d3 58%,#2f86e8 100%)",
      fontFamily: "'Pretendard Variable',Pretendard,-apple-system,'Apple SD Gothic Neo',sans-serif",
      color: "#fff", padding: "58px 56px 0", overflow: "hidden",
    }}>
      {/* 헤더 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <span style={{ fontSize: 40, fontWeight: 900, letterSpacing: "-.03em" }}>콕집</span>
          <span style={{ fontSize: 19, fontWeight: 600, opacity: .8 }}>koczip.com</span>
        </div>
        <span style={{ fontSize: 19, fontWeight: 600, opacity: .75 }}>{dateStr} 기준</span>
      </div>

      <div style={{ marginTop: 40 }}>
        <div style={{
          display: "inline-block", background: "rgba(255,255,255,.16)", borderRadius: 999,
          padding: "9px 20px", fontSize: 21, fontWeight: 700, letterSpacing: "-.01em",
        }}>
          {kind === "loan"
            ? `${sidoName || "전국"} · 주인대출 승계 ${loanN.toLocaleString()}건`
            : `${sidoName || "전국"} · 30평대 · ${minhh.toLocaleString()}세대 이상`}
        </div>
        <h1 style={{
          margin: "22px 0 8px", fontSize: kind === "loan" ? 60 : 66, fontWeight: 900,
          lineHeight: 1.16, letterSpacing: "-.045em",
        }}>
          {kind === "loan"
            ? <>집주인 대출<br />승계되는 매물</>
            : <>실거래보다 싸게<br />나온 매물</>}
        </h1>
        <p style={{ margin: 0, fontSize: 23, fontWeight: 500, opacity: .82, lineHeight: 1.5 }}>
          {kind === "loan"
            ? "매물 설명에 적힌 주인대출·근저당 문구를 콕집이 골라냈어요"
            : "최근 90일 실거래 평균과 지금 호가를 맞대어 본 결과"}
        </p>
      </div>

      {/* 목록 */}
      <div style={{ marginTop: 34, display: "flex", flexDirection: "column", gap: 12 }}>
        {kind === "loan" && loanTop.map((d) => (
          <div key={d.article_no} style={{
            background: "rgba(255,255,255,.97)", borderRadius: 18, padding: "17px 22px",
            display: "flex", alignItems: "center", gap: 18, color: "#0f1b2d",
            boxShadow: "0 6px 22px rgba(0,0,0,.16)",
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 30, fontWeight: 800, letterSpacing: "-.03em", whiteSpace: "nowrap",
                overflow: "hidden", textOverflow: "ellipsis",
              }}>{d.complex_name}</div>
              <div style={{ fontSize: 18, color: "#5b6b7d", marginTop: 3, fontWeight: 600 }}>
                {d.region_name} · {Math.round((d.area1_m2 || 0) / PY)}평({Math.round(d.area1_m2 || 0)}㎡)
                {d.floor_info ? ` · ${d.floor_info}층` : ""}
              </div>
            </div>
            <div style={{ textAlign: "right", flexShrink: 0 }}>
              <div style={{
                fontSize: 31, fontWeight: 900, letterSpacing: "-.03em",
                fontVariantNumeric: "tabular-nums",
              }}>{d.price ? eok(d.price) : "-"}</div>
              <div style={{ fontSize: 17, color: "#8a95a3", marginTop: 2, fontWeight: 600 }}>매매 호가</div>
            </div>
            <div style={{
              flexShrink: 0, background: "#e8f2ff", color: "#0d59b8", borderRadius: 13,
              padding: "13px 15px", textAlign: "center", minWidth: 120,
              fontSize: 20, fontWeight: 800, letterSpacing: "-.02em",
            }}>{(d.matched || "대출승계").slice(0, 6)}</div>
          </div>
        ))}
        {kind !== "loan" && top.map((d) => (
          <div key={`${d.complex_no}-${d.area_name}`} style={{
            background: "rgba(255,255,255,.97)", borderRadius: 18, padding: "17px 22px",
            display: "flex", alignItems: "center", gap: 18, color: "#0f1b2d",
            boxShadow: "0 6px 22px rgba(0,0,0,.16)",
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 30, fontWeight: 800, letterSpacing: "-.03em", whiteSpace: "nowrap",
                overflow: "hidden", textOverflow: "ellipsis",
              }}>{d.complex_name}</div>
              <div style={{ fontSize: 18, color: "#5b6b7d", marginTop: 3, fontWeight: 600 }}>
                {d.region_name} · {Math.round(d.area1_m2 / PY)}평({Math.round(d.area1_m2)}㎡)
                · {d.households.toLocaleString()}세대
              </div>
            </div>
            <div style={{ textAlign: "right", flexShrink: 0 }}>
              <div style={{
                fontSize: 31, fontWeight: 900, letterSpacing: "-.03em",
                fontVariantNumeric: "tabular-nums",
              }}>{eok(d.asking_min)}</div>
              <div style={{ fontSize: 17, color: "#8a95a3", marginTop: 2, fontWeight: 600 }}>
                실거래 평균 {eok(d.avg_real)}
              </div>
            </div>
            <div style={{
              flexShrink: 0, background: "#e8f2ff", color: "#0d59b8", borderRadius: 13,
              padding: "11px 15px", textAlign: "center", minWidth: 96,
            }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, opacity: .75 }}>평균 대비</div>
              <div style={{ fontSize: 27, fontWeight: 900, letterSpacing: "-.03em" }}>
                −{Math.round(d.gap * 100)}%
              </div>
            </div>
          </div>
        ))}
        {((kind === "loan" && loans && loanTop.length === 0)
          || (kind !== "loan" && rows && top.length === 0)) && (
          <div style={{ fontSize: 26, opacity: .85, padding: "40px 4px" }}>
            오늘은 조건에 맞는 매물이 없었어요.
          </div>
        )}
      </div>

      {/* 푸터 */}
      <div style={{
        position: "absolute", left: 56, right: 56, bottom: 42,
        display: "flex", alignItems: "flex-end", justifyContent: "space-between",
      }}>
        <div style={{ fontSize: 18, opacity: .62, lineHeight: 1.55, maxWidth: 620 }}>
          {kind === "loan"
            ? "매물 설명에 적힌 문구를 모은 것으로, 실제 승계 가능 여부·근저당 상태는 등기부와 현장에서 확인하세요."
            : "매물 호가와 국토교통부 실거래가를 매일 모아 비교한 결과입니다. 투자 권유가 아니며, 실제 거래 조건은 현장에서 확인하세요."}
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 17, opacity: .7, fontWeight: 600 }}>더 보기</div>
          <div style={{ fontSize: 33, fontWeight: 900, letterSpacing: "-.02em" }}>
            www.koczip.com
          </div>
        </div>
      </div>
    </div>
  );
}
