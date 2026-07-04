// 실거래 히스토리 공용 — 단지상세 실거래 탭·종합 탭이 함께 사용 (2026-07-04)
// 전월세 계약 연쇄(같은 평형·층·종전금액)와 팝업 렌더를 한 곳에 모아 중복 방지.

export type RentLike = {
  deal_ymd: string; deposit: number; monthly_rent: number;
  excl_use_ar: number | null; floor: number | null;
  contract_type: string | null; contract_term: string | null;
  use_rr_right: string | null; pre_deposit: number | null; pre_monthly_rent: number | null;
};

export const fmtDot = (ymd: string) => ymd.slice(2).replace(/-/g, ".");

export function wonKr(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 1e8) {
    const e = Math.floor(v / 1e8), m = Math.floor((v % 1e8) / 1e4);
    return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`;
  }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}

const akey = (m2: number | null | undefined) => (m2 == null ? null : Math.round(m2 * 100) / 100);

/** 같은 유닛(평형·층) 추정 과거 계약 연쇄 — 종전 보증금/월세 일치를 따라간다. */
export function rentChain<T extends RentLike>(r: T, all: T[]): T[] {
  const chain = [r];
  let cur: T = r;
  for (let i = 0; i < 6; i++) {
    if (!cur.pre_deposit) break;
    const prev = all.find((x) => x !== cur && x.deal_ymd < cur.deal_ymd
      && akey(x.excl_use_ar) === akey(cur.excl_use_ar)
      && x.floor === cur.floor
      && x.deposit === cur.pre_deposit
      && (cur.pre_monthly_rent ? x.monthly_rent === cur.pre_monthly_rent : true));
    if (!prev) break;
    chain.push(prev);
    cur = prev;
  }
  return chain;
}

/** 전월세 계약 히스토리 팝업 (실거래 탭·종합 탭 공용) */
export function RentHistModal({ r, all, kind, onClose }: {
  r: RentLike; all: RentLike[]; kind: "jeonse" | "wolse"; onClose: () => void;
}) {
  const color = kind === "wolse" ? "#1f9d63" : "#7048e8";
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420 }}>
        <div className="modal-head">
          <span className="modal-title">{fmtDot(r.deal_ymd)} 계약 히스토리</span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}>✕</button>
        </div>
        <div className="muted" style={{ fontSize: 12, margin: "2px 0 10px" }}>
          {r.excl_use_ar != null && `전용 ${Math.round(r.excl_use_ar)}㎡`}
          {r.floor != null && ` · ${r.floor}층`} — 같은 조건(평형·층·종전금액)으로 추적한 이력입니다
        </div>
        <div style={{ display: "grid", gap: 0 }}>
          {rentChain(r, all).map((h, i) => (
            <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "9px 0",
              borderTop: i > 0 ? "1px solid #f1f5f9" : "none", flexWrap: "wrap" }}>
              <span style={{ fontSize: 12.5, color: "#64748b", fontVariantNumeric: "tabular-nums", width: 68 }}>{fmtDot(h.deal_ymd)}</span>
              <b style={{ fontSize: 15, color, whiteSpace: "nowrap" }}>
                {kind === "wolse" ? "월세" : "전세"} {wonKr(h.deposit)}{kind === "wolse" && ` / ${Math.round(h.monthly_rent / 10000)}만`}
              </b>
              {h.use_rr_right === "사용" && <span className="txf-b" style={{ background: "#fef2f2", color: "#d23b3b" }}>갱신요구권</span>}
              {h.use_rr_right !== "사용" && (h.contract_type ?? "").includes("갱신") && <span className="txf-b" style={{ background: "#f1f5f9", color: "#475569" }}>재계약</span>}
              {(h.contract_type ?? "").includes("신규") && <span className="txf-b" style={{ background: "#e8f1fd", color: "#1268d3" }}>신규</span>}
              {h.contract_term && <span style={{ marginLeft: "auto", fontSize: 12, color: "#8296ab", fontVariantNumeric: "tabular-nums" }}>{h.contract_term.replace("~", " ~ ")}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export type SaleLike = {
  deal_ymd: string; deal_amount: number; excl_use_ar: number | null; floor: number | null;
  dealing_gbn?: string | null; dong?: string | null; registered?: boolean; silv_kind?: string | null;
};

/** 매매 — 같은 평형(±1.5㎡)의 최근 거래 이력 팝업 */
export function SaleHistModal({ r, all, onClose }: {
  r: SaleLike; all: SaleLike[]; onClose: () => void;
}) {
  const rows = all
    .filter((x) => x.excl_use_ar != null && r.excl_use_ar != null && Math.abs(x.excl_use_ar - r.excl_use_ar) <= 1.5)
    .sort((a, b) => b.deal_ymd.localeCompare(a.deal_ymd))
    .slice(0, 10);
  // 신고가: 시간순으로 최고가 경신 거래 표시
  const best = new Set<SaleLike>();
  let max = 0;
  for (const x of [...rows].sort((a, b) => a.deal_ymd.localeCompare(b.deal_ymd))) {
    if (!x.silv_kind && x.deal_amount > max) { max = x.deal_amount; best.add(x); }
  }
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420 }}>
        <div className="modal-head">
          <span className="modal-title">전용 {r.excl_use_ar != null ? Math.round(r.excl_use_ar) : "-"}㎡ 매매 이력</span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}>✕</button>
        </div>
        <div style={{ display: "grid", gap: 0 }}>
          {rows.map((h, i) => (
            <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "9px 0",
              borderTop: i > 0 ? "1px solid #f1f5f9" : "none", flexWrap: "wrap",
              background: h === r ? "#f6faff" : undefined }}>
              <span style={{ fontSize: 12.5, color: "#64748b", fontVariantNumeric: "tabular-nums", width: 68 }}>{fmtDot(h.deal_ymd)}</span>
              <b style={{ fontSize: 15, color: "#1268d3", whiteSpace: "nowrap" }}>{wonKr(h.deal_amount)}</b>
              {best.has(h) && <span className="txf-b" style={{ background: "#fef2f2", color: "#d23b3b" }}>신고가</span>}
              {h.silv_kind && <span className="txf-b" style={{ background: "#f0e9ff", color: "#6b39c9" }}>{h.silv_kind}</span>}
              {h.dealing_gbn === "직거래" && <span className="txf-b" style={{ background: "#fff7ea", color: "#c4791a" }}>직거래</span>}
              {h.registered && <span className="txf-b" style={{ background: "#eefaf2", color: "#1f9d63" }}>등기</span>}
              <span style={{ marginLeft: "auto", fontSize: 12, color: "#8296ab" }}>
                {h.floor != null && `${h.floor}층`}{h.dong ? ` · ${h.dong}${String(h.dong).endsWith("동") ? "" : "동"}` : ""}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
