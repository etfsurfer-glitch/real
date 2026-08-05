// 면적 표기 사이트 표준 — "25평(59㎡)" 형식. m2 인자는 항상 '전용면적(㎡)'.
// 평은 흔히 부르는 평형(공급 기준 관용값): 전용 59㎡=25평, 84㎡=34평 …
// 대표 전용면적 → 관용 평형 표(근처면 그 평형, 그 외는 전용율 ~0.73 근사).
const STD: [number, number][] = [
  [29, 12], [33, 14], [36, 15], [39, 17], [43, 18], [46, 20], [49, 21],
  [51, 22], [55, 24], [59, 25], [69, 29], [72, 30], [74, 32], [79, 33],
  [84, 34], [91, 37], [99, 40], [101, 41], [109, 43], [114, 46],
  [125, 49], [134, 51], [145, 55], [164, 60],
];

/** 전용면적(㎡) → 관용 평형(정수). 값이 없으면 null. */
export function pyeong(m2?: number | null): number | null {
  if (!m2 || m2 <= 0) return null;
  let best: number | null = null, bd = Infinity;
  for (const [a, p] of STD) { const d = Math.abs(a - m2); if (d < bd) { bd = d; best = p; } }
  if (bd <= 3.5) return best;                 // 표준 평형 근처면 관용 평형
  return Math.round(m2 / 3.3058 / 0.73);      // 그 외 근사
}

/** 사이트 표준 면적 표기 "25평(59㎡)". m2=전용면적.
 *  supply(공급면적㎡)를 주면 평을 그 값에서 바로 구한다 — 관용 표는 전용률 0.73 을
 *  가정해서 전용률이 높은 구축에서 틀린다(한마루럭키 전용 102/공급 123 = 83%,
 *  표로는 41평이지만 실제는 37평).
 *  paren:false → "25평 59㎡", pyeongOnly → "25평", areaOnly → "59㎡". */
export function areaLabel(
  m2?: number | null,
  opts?: { paren?: boolean; pyeongOnly?: boolean; areaOnly?: boolean; supply?: number | null },
): string {
  if (m2 == null || m2 <= 0 || isNaN(m2)) return "-";
  const a = Math.round(m2);
  if (opts?.areaOnly) return `${a}㎡`;
  const sup = opts?.supply;
  const p = sup && sup > 0 ? Math.round(sup / 3.3058) : pyeong(m2);
  if (!p) return `${a}㎡`;
  if (opts?.pyeongOnly) return `${p}평`;
  return opts?.paren === false ? `${p}평 ${a}㎡` : `${p}평(${a}㎡)`;
}
