// 주택 구입 비용 계산 로직 — 레퍼런스(zento.kr home-buying-funds-calculator) 번들
// 디컴파일 분석 후 동일 산식으로 복제 (2026-07-07). 전부 원(₩) 단위, 클라이언트 즉시 계산.

export type RegionalType = "seoul" | "overconcentration" | "metro" | "other";
export type LoanRegion = "regulated" | "capital" | "other";

export type CalcInput = {
  salePrice: number;            // 매매가
  loanAmount: number;           // 대출금(요청액)
  currentCash: number;          // 보유 현금
  downPaymentRatio: number;     // 계약금 비율 % (기본 10)
  hasDownPaymentPaid: boolean;  // 계약금 지불 완료 → 실제현금 = 보유현금+계약금
  hasDefenseFund: boolean;      // 방공제 적용
  regionalType: RegionalType;   // 방공제·채권 도시구분
  manualDefenseFund: number | null;
  isAdjustedArea: boolean;      // 조정대상지역
  loanRegion: LoanRegion;       // 대출규제 지역구분 (규제지역/수도권 비규제/그 외)
  houseCount: number;           // 구입 전 보유 주택 수 0~3
  isOver85m2: boolean;
  isFirstTime: boolean;
  isTempTwoHouse: boolean;      // 일시적 2주택
  standardPrice: number;        // 시가표준액 (등록면허세·채권 기준)
  contingencyRatio: number;     // 예비비 비율 % (기본 10)
  brokerageFeePreset: "auto" | "manual";
  manualBrokerageFee: number;
  lawyerFeePreset: "auto" | "manual";
  manualLawyerFee: number;
  managementDeposit: number;    // 관리비예치금
  cleaningFeePreset: "none" | "basic" | "premium" | "manual";
  manualCleaningFee: number;
  movingFeePreset: "none" | "small" | "medium" | "large" | "manual";
  manualMovingFee: number;
  interiorFeePreset: "none" | "basic" | "standard" | "premium" | "manual";
  manualInteriorFee: number;
};

export const DEFAULT_INPUT: CalcInput = {
  salePrice: 500_000_000, loanAmount: 300_000_000, currentCash: 200_000_000,
  downPaymentRatio: 10, hasDownPaymentPaid: false,
  hasDefenseFund: true, regionalType: "seoul", manualDefenseFund: null,
  isAdjustedArea: false, loanRegion: "regulated", houseCount: 0, isOver85m2: false,
  isFirstTime: false, isTempTwoHouse: false,
  standardPrice: 350_000_000, contingencyRatio: 10,
  brokerageFeePreset: "auto", manualBrokerageFee: 0,
  lawyerFeePreset: "auto", manualLawyerFee: 0,
  managementDeposit: 0,
  cleaningFeePreset: "none", manualCleaningFee: 0,
  movingFeePreset: "medium", manualMovingFee: 0,
  interiorFeePreset: "none", manualInteriorFee: 0,
};

// ---- 개별 산식 (레퍼런스 동일) --------------------------------------------

/** 취득세 — 누진 산식. 생애최초(1주택 이하·85㎡ 이하·6억 이하)는 감면 반영 실효세액. */
export function acquisitionTax(i: CalcInput): number {
  const p = i.salePrice;
  if (i.isFirstTime && i.houseCount <= 1 && !i.isOver85m2 && p <= 6e8) {
    if (p <= 6e7) return Math.floor(p * 0.005);
    return Math.floor(3e5 + (p - 6e7) * 0.008);
  }
  if (i.isTempTwoHouse && i.houseCount === 2) return Math.floor(p * 0.01);
  if (i.houseCount <= 1) {
    if (p <= 6e7) return Math.floor(p * 0.01);
    if (p <= 6e8) return Math.floor(6e5 + (p - 6e7) * 0.013);
    if (p <= 9e8) return Math.floor(7_620_000 + (p - 6e8) * 0.028);
    return Math.floor(16_020_000 + (p - 9e8) * 0.04);
  }
  if (i.houseCount === 2) return Math.floor(p * (i.isAdjustedArea ? 0.08 : 0.01));
  return Math.floor(p * (i.isAdjustedArea ? 0.12 : 0.03));
}

export const localEducationTax = (acq: number) => Math.floor(acq * 0.1);

export function ruralSpecialTax(i: CalcInput, acq: number): number {
  return i.houseCount <= 1 && !i.isOver85m2 && i.salePrice <= 6e8
    ? 0 : Math.floor(acq * 0.1);
}

export const registrationTax = (standardPrice: number) => Math.floor(standardPrice * 0.002);

/** 인지세 — 대출금액 기준 (근저당 설정) */
export function stampTax(loan: number): number {
  if (loan <= 1e7) return 0;
  if (loan <= 5e7) return 5e4;
  if (loan <= 1e8) return 1e5;
  return 15e4;
}

/** 국민주택채권 실부담액 = 매입액(시가표준액×의무매입률) × 할인율 12% */
export function nationalHousingBond(standardPrice: number, isCity: boolean): number {
  const e = standardPrice;
  const r = e < 2e7 ? 0
    : e < 5e7 ? 0.013
    : e < 1e8 ? (isCity ? 0.019 : 0.014)
    : e < 16e7 ? (isCity ? 0.021 : 0.016)
    : e < 26e7 ? (isCity ? 0.023 : 0.018)
    : e < 6e8 ? (isCity ? 0.026 : 0.021)
    : (isCity ? 0.031 : 0.026);
  return Math.floor(Math.floor(e * r) * 0.12);
}

// ---- 정부 대출규제 (2025.6.27·10.15 대책 기준 — 정책 변경 시 이 블록만 수정) ----
//  · 수도권·규제지역: 2주택 이상 추가구입, 1주택 유지 추가구입 → 주담대 금지
//  · 규제지역 LTV 50% (무주택·처분조건부, 생애최초 포함) / 수도권 비규제 70%
//  · 비규제 지방: 무주택 70%, 생애최초 80%, 1주택 유지·다주택 60%
//  · 수도권·규제지역 주담대 총액 캡: 15억↓ 6억 / 15~25억 4억 / 25억↑ 2억
export type LoanReg = {
  banned: boolean; reason: string;
  ltv: number; ltvAmt: number; cap: number | null; maxLoan: number;
  buyerLabel: string;
};

export function loanRegulation(i: Pick<CalcInput,
  "salePrice" | "loanRegion" | "houseCount" | "isTempTwoHouse" | "isFirstTime">): LoanReg {
  const capitalOrReg = i.loanRegion !== "other";
  const buyer =
    i.houseCount === 0 ? "무주택"
    : i.isTempTwoHouse ? "처분조건부(일시적 2주택)"
    : i.houseCount === 1 ? "1주택 유지"
    : "다주택";

  if (capitalOrReg && (buyer === "다주택" || buyer === "1주택 유지")) {
    return { banned: true, buyerLabel: buyer,
      reason: `수도권·규제지역 ${buyer} 추가 구입은 주담대가 금지됩니다 (2025.6.27 대책)`,
      ltv: 0, ltvAmt: 0, cap: null, maxLoan: 0 };
  }
  let ltv: number;
  if (i.loanRegion === "regulated") ltv = 0.5;
  else if (i.loanRegion === "capital") ltv = 0.7;
  else if (buyer === "1주택 유지" || buyer === "다주택") ltv = 0.6;
  else ltv = i.isFirstTime ? 0.8 : 0.7;

  const ltvAmt = Math.floor(i.salePrice * ltv);
  let cap: number | null = null;
  if (capitalOrReg) {
    cap = i.salePrice <= 1_500_000_000 ? 600_000_000
      : i.salePrice <= 2_500_000_000 ? 400_000_000 : 200_000_000;
  }
  return { banned: false, buyerLabel: buyer, reason: "",
    ltv, ltvAmt, cap, maxLoan: Math.min(ltvAmt, cap ?? Infinity) };
}

export function defenseFundAmount(t: RegionalType): number {
  switch (t) {
    case "seoul": return 55_000_000;
    case "overconcentration": return 50_000_000;
    case "metro": return 28_000_000;
    default: return 20_000_000;
  }
}

const BROKERAGE = [
  { max: 5e7, rate: 0.006, limit: 25e4 },
  { max: 2e8, rate: 0.005, limit: null },
  { max: 6e8, rate: 0.004, limit: null },
  { max: 9e8, rate: 0.005, limit: null },
  { max: Infinity, rate: 0.009, limit: null },
] as const;

export function brokerageFee(price: number): number {
  for (const b of BROKERAGE) {
    if (price <= b.max) {
      const f = Math.floor(price * b.rate);
      return b.limit ? Math.min(f, b.limit) : f;
    }
  }
  return 0;
}

const LAWYER = [
  { max: 1e8, fee: 5e5 }, { max: 3e8, fee: 7e5 },
  { max: 5e8, fee: 1e6 }, { max: Infinity, fee: 15e5 },
] as const;
export function lawyerFee(price: number): number {
  for (const l of LAWYER) if (price <= l.max) return l.fee;
  return 15e5;
}

export const CLEANING = { none: 0, basic: 2e5, premium: 5e5 } as const;
export const MOVING = { none: 0, small: 1e6, medium: 15e5, large: 2e6 } as const;
export const INTERIOR = { none: 0, basic: 0.03, standard: 0.05, premium: 0.08 } as const;

// ---- 통합 계산 -------------------------------------------------------------

export type CostItem = {
  id: string; label: string; amount: number;
  stage: "contract" | "loan" | "balance" | "registration" | "move";
  category: "public" | "loan-registration" | "practical" | "other";
  formula?: string; note?: string;
};

export const STAGE_LABEL: Record<CostItem["stage"], string> = {
  contract: "계약 단계", loan: "대출 준비", balance: "잔금 단계",
  registration: "등기 단계", move: "입주 준비",
};
export const STAGE_ORDER: CostItem["stage"][] = ["contract", "loan", "balance", "registration", "move"];

export type CalcResult = {
  items: CostItem[];
  downPayment: number;         // 계약금
  actualLoan: number;          // 방공제 차감 후 실수령 대출
  defenseFund: number;
  balancePayment: number;      // 잔금(현금 필요)
  taxTotal: number;            // 공적 비용 합계
  extraTotal: number;          // 부대비용 합계(계약금·잔금 제외)
  minRequiredCash: number;     // 최소 필요현금(대출 제외 전체)
  totalWithLoan: number;       // 대출 포함 총 필요자금
  actualCash: number;          // 실제 현금(계약금 지불완료 반영)
  cashGap: number;             // 실제현금 - 최소필요현금
};

export function calculate(i: CalcInput): CalcResult {
  const items: CostItem[] = [];
  const downPayment = Math.floor(i.salePrice * (i.downPaymentRatio / 100));
  items.push({ id: "down-payment", stage: "contract", category: "other",
    label: "계약금", amount: downPayment, formula: `매매가 × ${i.downPaymentRatio}%` });

  const acq = acquisitionTax(i);
  items.push({ id: "acq", stage: "balance", category: "public", label: "취득세",
    amount: acq, note: "주택 수·지역·면적·생애최초 기준 자동 계산" });
  items.push({ id: "edu", stage: "balance", category: "public", label: "지방교육세",
    amount: localEducationTax(acq), formula: "취득세 × 10%" });
  const rural = ruralSpecialTax(i, acq);
  items.push({ id: "rural", stage: "balance", category: "public", label: "농어촌특별세",
    amount: rural, note: rural === 0 ? "면제 조건 충족" : undefined });
  items.push({ id: "regi", stage: "registration", category: "public", label: "등록면허세",
    amount: registrationTax(i.standardPrice), formula: "시가표준액 × 0.2%" });
  items.push({ id: "stamp", stage: "loan", category: "loan-registration", label: "인지세",
    amount: stampTax(i.loanAmount), note: i.loanAmount === 0 ? "대출 없음" : "대출금액 기준" });

  const isCity = i.regionalType !== "other";
  items.push({ id: "bond", stage: "registration", category: "loan-registration",
    label: "국민주택채권 실부담액", amount: nationalHousingBond(i.standardPrice, isCity),
    note: "즉시 매각(할인율 12%) 기준" });

  items.push({ id: "broker", stage: "contract", category: "practical", label: "중개보수(복비)",
    amount: i.brokerageFeePreset === "manual" ? i.manualBrokerageFee : brokerageFee(i.salePrice),
    note: i.brokerageFeePreset === "manual" ? "직접 입력" : "법정 상한 요율 기준" });
  items.push({ id: "lawyer", stage: "registration", category: "practical", label: "법무사 비용",
    amount: i.lawyerFeePreset === "manual" ? i.manualLawyerFee : lawyerFee(i.salePrice),
    note: "실제 견적은 법무사마다 차이" });
  if (i.managementDeposit > 0)
    items.push({ id: "mgmt", stage: "move", category: "practical", label: "관리비예치금",
      amount: i.managementDeposit, note: "단지마다 다름" });

  const clean = i.cleaningFeePreset === "manual" ? i.manualCleaningFee
    : CLEANING[i.cleaningFeePreset as keyof typeof CLEANING] ?? 0;
  if (clean > 0) items.push({ id: "clean", stage: "move", category: "practical",
    label: "청소 비용", amount: clean });
  const move = i.movingFeePreset === "manual" ? i.manualMovingFee
    : MOVING[i.movingFeePreset as keyof typeof MOVING] ?? 0;
  if (move > 0) items.push({ id: "move", stage: "move", category: "practical",
    label: "이사 비용", amount: move });
  const interior = i.interiorFeePreset === "manual" ? i.manualInteriorFee
    : Math.floor(i.salePrice * (INTERIOR[i.interiorFeePreset as keyof typeof INTERIOR] ?? 0));
  if (interior > 0) items.push({ id: "interior", stage: "move", category: "practical",
    label: "인테리어 비용", amount: interior });

  const contingency = Math.floor(
    items.filter((x) => x.id !== "down-payment")
      .reduce((s, x) => s + x.amount, 0) * (i.contingencyRatio / 100));
  if (contingency > 0) items.push({ id: "contingency", stage: "balance", category: "other",
    label: "예비비", amount: contingency, formula: `부대비용 합계 × ${i.contingencyRatio}%` });

  const defenseFund = i.hasDefenseFund
    ? (i.manualDefenseFund ?? defenseFundAmount(i.regionalType)) : 0;
  const actualLoan = i.loanAmount - defenseFund;
  const balancePayment = i.salePrice - downPayment - actualLoan;
  items.push({ id: "balance", stage: "balance", category: "other", label: "잔금",
    amount: balancePayment,
    formula: i.hasDefenseFund ? "매매가 - 계약금 - 실수령 대출금(방공제 차감)" : "매매가 - 계약금 - 대출금" });

  const minRequiredCash = items.reduce((s, x) => s + x.amount, 0);
  const taxTotal = items.filter((x) => x.category === "public").reduce((s, x) => s + x.amount, 0);
  const extraTotal = minRequiredCash - downPayment - balancePayment;
  const actualCash = i.hasDownPaymentPaid ? i.currentCash + downPayment : i.currentCash;
  return {
    items, downPayment, actualLoan, defenseFund, balancePayment,
    taxTotal, extraTotal, minRequiredCash,
    totalWithLoan: minRequiredCash + i.loanAmount,
    actualCash, cashGap: actualCash - minRequiredCash,
  };
}

/** 가격별 실제 적용 대출금 = min(사용자 대출금, 규제 한도) — 규제가 가격에 따라 변함 */
export function effectiveLoan(base: CalcInput, price: number): number {
  const reg = loanRegulation({ ...base, salePrice: price });
  return Math.max(0, Math.min(base.loanAmount, reg.maxLoan));
}

/** 현재 대출금·현금 기준 cashGap≥0 인 최대 매매가 (추천 연동용). 규제 한도 자동 반영. */
export function maxAffordablePrice(base: CalcInput): number {
  const feasible = (price: number) => {
    const std = base.standardPrice > 0 && base.salePrice > 0
      ? Math.floor(price * (base.standardPrice / base.salePrice))
      : Math.floor(price * 0.7);
    return calculate({ ...base, salePrice: price, standardPrice: std,
      loanAmount: effectiveLoan(base, price) }).cashGap >= 0;
  };
  if (!feasible(10_000_000)) return 0;
  let lo = 10_000_000, hi = 10_000_000_000;
  while (hi - lo > 1_000_000) {
    const mid = Math.floor((lo + hi) / 2);
    if (feasible(mid)) lo = mid; else hi = mid;
  }
  return Math.floor(lo / 1_000_000) * 1_000_000;
}

export const fmtWon = (v: number) => `${Math.floor(v).toLocaleString("ko-KR")}원`;
export const fmtEok = (v: number | null | undefined) => {
  if (v == null) return "-";
  const neg = v < 0; const a = Math.abs(v);
  const e = Math.floor(a / 1e8), m = Math.round((a % 1e8) / 1e4);
  const s = e && m ? `${e}억 ${m.toLocaleString()}` : e ? `${e}억` : `${m.toLocaleString()}만`;
  return (neg ? "-" : "") + s;
};
