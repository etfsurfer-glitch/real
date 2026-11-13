// 방향 표기 — 상가·사무실·지식산업센터·공장은 방향 기준이 주출입구로 정해져 있다
// (원본 등록 화면에 기준 선택란이 없음, 2026-11-12 원본 대조·사용자 확인). 표시·광고 기준 병기.
const NONRES = /상가|점포|판매|근린|사무|지식산업|공장|창고/;

export function dirLabel(direction?: string | null, type?: string | null): string {
  const d = (direction || "").trim();
  if (!d) return "";
  if (d.includes("기준")) return d;
  const t = type || "";
  if (t.includes("상가주택") || !NONRES.test(t)) return d;
  return `${d}(주출입구 기준)`;
}
