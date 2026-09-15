// 계약서 작성 계산 미러 — scripts/contract_domain.py 와 동일 산식(즉시성 위해 TS 복제).
// 근거: hanbang/docs/콕집_이식분석.md. 서버 저장 시 파이썬 쪽이 최종 검증한다.

// ── 한글/한자 금액 표기 ─────────────────────────────────────────────
const KO_DIG = "영일이삼사오육칠팔구";
const HJ_DIG = "零壹貳參肆伍陸柒捌玖";
const KO_SMALL = ["", "십", "백", "천"];
const HJ_SMALL = ["", "拾", "佰", "仟"];
const KO_BIG = ["", "만", "억", "조"];
const HJ_BIG = ["", "萬", "億", "兆"];

function four(n: number, dig: string, small: string[]): string {
  let out = "";
  for (let i = 3; i >= 0; i--) {
    const d = Math.floor(n / 10 ** i) % 10;
    if (!d) continue;
    out += d === 1 && i > 0 ? small[i] : dig[d] + small[i];
  }
  return out;
}

function readNumber(n: number, hanja = false): string {
  if (n === 0) return hanja ? HJ_DIG[0] : KO_DIG[0];
  const [dig, small, big] = hanja ? [HJ_DIG, HJ_SMALL, HJ_BIG] : [KO_DIG, KO_SMALL, KO_BIG];
  const parts: string[] = [];
  let unit = 0;
  while (n > 0) {
    const chunk = n % 10000;
    if (chunk) parts.push(four(chunk, dig, small) + big[unit]);
    n = Math.floor(n / 10000);
    unit++;
  }
  return parts.reverse().join("");
}

export type CostStyle = "숫자" | "한글" | "한자" | "한글+숫자" | "한자+숫자";

export function amountKorean(won: number, style: CostStyle = "한글"): string {
  won = Math.floor(won || 0);
  const numStr = `₩${won.toLocaleString()}`;
  if (style === "숫자") return numStr;
  const hanja = style.startsWith("한자");
  const body = readNumber(won, hanja);
  const text = hanja ? `一金 ${body}원整` : `일금 ${body}원정`;
  return style.endsWith("+숫자") ? `${text} (${numStr})` : text;
}

// ── 중개보수(완전판: 2021-10-19 분기·오피스텔 특례·월세환산) ─────────
type Tier = [cap: number, rate: number, limit: number | null];
const INF = Infinity;
const RATES: Record<string, Tier[]> = {
  "HOUSE|SALE|OLD": [[5e7, .006, 25e4], [2e8, .005, 80e4], [6e8, .004, null], [9e8, .005, null], [INF, .009, null]],
  "HOUSE|SALE|NEW": [[5e7, .006, 25e4], [2e8, .005, 80e4], [9e8, .004, null], [12e8, .005, null], [15e8, .006, null], [INF, .007, null]],
  "HOUSE|RENT|OLD": [[5e7, .005, 20e4], [1e8, .004, 30e4], [3e8, .003, null], [6e8, .004, null], [INF, .008, null]],
  "HOUSE|RENT|NEW": [[5e7, .005, 20e4], [1e8, .004, 30e4], [6e8, .003, null], [12e8, .004, null], [15e8, .005, null], [INF, .006, null]],
};
const CUTOVER = "2021-10-19";

export function dealAmountForCommission(mtype1: string, cost: number, fineCost = 0): number {
  cost = Math.floor(cost || 0);
  let fine = Math.floor(fineCost || 0);
  if (mtype1 === "매매" || mtype1 === "전세") return cost;
  if (mtype1 === "연세") fine = Math.floor(fine / 12);
  const v = cost + fine * 100;
  return v < 5e7 ? cost + fine * 70 : v;
}

export function commission(propertyGb: "HOUSE" | "OFFICETEL_Q" | "ETC", tradeGb: "SALE" | "RENT",
  amount: number, contractDate = ""): { fee: number; rate: number; limit: number | null; negotiable: boolean } {
  amount = Math.floor(amount || 0);
  const period = contractDate && contractDate < CUTOVER ? "OLD" : "NEW";
  if (propertyGb === "OFFICETEL_Q") {
    const rate = tradeGb === "SALE" ? .005 : .004;
    return { fee: Math.floor(amount * rate), rate, limit: null, negotiable: false };
  }
  if (propertyGb === "ETC") {
    return { fee: Math.floor(amount * .009), rate: .009, limit: null, negotiable: true };
  }
  for (const [cap, rate, lim] of RATES[`HOUSE|${tradeGb}|${period}`]) {
    if (amount < cap) {
      let fee = Math.floor(amount * rate);
      if (lim != null) fee = Math.min(fee, lim);
      const neg = period === "OLD" && amount >= (tradeGb === "SALE" ? 9e8 : 6e8);
      return { fee, rate, limit: lim, negotiable: neg };
    }
  }
  return { fee: 0, rate: 0, limit: null, negotiable: false };
}

export const autoBalance = (total: number, down = 0, mid1 = 0, mid2 = 0) =>
  Math.max(Math.floor(total || 0) - Math.floor(down || 0) - Math.floor(mid1 || 0) - Math.floor(mid2 || 0), 0);

// 유형(sub_category)→중개보수 물건유형 러프 매핑(오피스텔 특례는 사용자 체크로 확정)
export function propertyGbOf(subCategory: string, officetelQ: boolean): "HOUSE" | "OFFICETEL_Q" | "ETC" {
  if (/오피스텔/.test(subCategory)) return officetelQ ? "OFFICETEL_Q" : "ETC";
  if (/아파트|주상복합|연립|다세대|다가구|다중|도시형|주택|원룸/.test(subCategory)) return "HOUSE";
  return "ETC";
}
