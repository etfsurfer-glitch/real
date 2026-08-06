// 매수 예상지역 → 규제 구분(규제지역/비규제) · 토지거래허가구역 · 방공제 지역 자동 판정.
// 현행 검증(2026-07-08 웹 확인, 정책브리핑·금융위·국토부):
//  · 규제지역(투기과열지구·조정대상지역) = 서울 25개구 전역 + 경기 15곳
//     - 10.15 대책(2025.10.16 효력): 과천·광명·하남·의왕·수원(영통·장안·팔달)·
//       성남(분당·수정·중원)·안양 동안·용인 수지
//     - 2026.6.30 추가(규제 7.1·토허 7.5 효력, ~2027.12.31): 화성 동탄구·용인 기흥구·구리시
//  · 위 규제지역 전체가 토지거래허가구역(아파트 대상, 2년 실거주 의무·갭투자 불가)으로도 지정됨
//  · 규제지역 LTV 40%(생애최초 예외 70%)·한도 15억↓6억/15~25억4억/25억↑2억
//  ※ 지정 변경 시 이 파일과 buycalc.ts loanRegulation 블록만 수정.
import type { RegionalType, LoanRegion } from "./buycalc";

// 규제지역 경기 시군구 5자리 코드 (서울은 sido=11 전역이라 별도)
const REGULATED_GYEONGGI = new Set([
  "41290", // 과천시
  "41210", // 광명시
  "41135", "41131", "41133", // 성남 분당·수정·중원
  "41117", "41111", "41115", // 수원 영통·장안·팔달
  "41173", // 안양 동안구
  "41465", // 용인 수지구
  "41430", // 의왕시
  "41450", // 하남시
  // 2026.6.30 추가
  "41597", // 화성 동탄구
  "41463", // 용인 기흥구
  "41310", // 구리시
]);

const METRO_SIDO = new Set(["26", "27", "29", "30", "31"]); // 부산·대구·광주·대전·울산 (방공제 2,800)
const CAPITAL_SIDO = new Set(["11", "41", "28"]);           // 수도권(서울·경기·인천) — 6억 캡 대상

// 방공제 5,000만원(과밀억제권역) 경기 시군구 코드 접두 — 수도권정비계획법 기준.
// 서울 전역·인천 대부분도 과밀이나 별도 처리. 나머지 경기(성장관리·자연보전)는 2,000만원.
const GAMIL_GYEONGGI_PREFIX = [
  "41150", // 의정부
  "41310", // 구리
  "41450", // 하남
  "4128",  // 고양(덕양·일산동·일산서)
  "4111",  // 수원(장안·권선·팔달·영통)
  "4113",  // 성남(수정·중원·분당)
  "4117",  // 안양(만안·동안)
  "41190", // 부천
  "41210", // 광명
  "41290", // 과천
  "41430", // 의왕
  "41410", // 군포
  "41360", // 남양주(일부 과밀 — 근사)
  "41390", // 시흥(일부 과밀 — 근사)
];
const isGamilGyeonggi = (sgg5: string) => GAMIL_GYEONGGI_PREFIX.some((p) => sgg5.startsWith(p));

export type RegionClass = {
  loanRegion: LoanRegion;       // 규제지역 / 수도권 비규제 / 지방
  regionalType: RegionalType;   // 방공제·채권 지역구분(자동, 조정 가능)
  isRegulated: boolean;
  isTohuh: boolean;             // 토지거래허가구역(현재 규제지역과 동일 범위)
  regLabel: string;             // "규제지역 · 토지거래허가구역" 등
  regTone: "danger" | "warn" | "ok";
  notes: string[];
};

/** 시도코드(2자리 이상)·시군구코드(5자리 이상)로 규제/토허/방공제 자동 판정. */
export function classifyRegion(sidoCode: string, sgguCode: string): RegionClass {
  const sido = (sidoCode || "").slice(0, 2);
  const sgg = (sgguCode || "").slice(0, 5);
  const isSeoul = sido === "11";
  const isRegulated = isSeoul || REGULATED_GYEONGGI.has(sgg);

  const loanRegion: LoanRegion = isRegulated ? "regulated"
    : CAPITAL_SIDO.has(sido) ? "capital" : "other";

  // 방공제 지역구분(자동 확정) — 서울=5,500 / 과밀억제권역=5,000 / 광역시=2,800 / 그 밖=2,000
  const regionalType: RegionalType = isSeoul ? "seoul"
    : sido === "28" ? "overconcentration"                    // 인천 대부분 과밀
    : sido === "41" ? (isGamilGyeonggi(sgg) ? "overconcentration" : "other")
    : METRO_SIDO.has(sido) ? "metro"
    : "other";

  const isTohuh = isRegulated;   // 현행: 규제지역 = 토지거래허가구역
  const notes: string[] = [];
  let regLabel: string;
  let regTone: RegionClass["regTone"];
  if (isRegulated) {
    regLabel = "규제지역 · 토지거래허가구역";
    regTone = "danger";
    notes.push("주택담보대출은 집값의 40%까지 (생애최초로 처음 사면 70%까지)");
    notes.push("대출 총액은 집값이 15억 이하면 최대 6억, 15억~25억이면 최대 4억, 25억을 넘으면 최대 2억까지만 나옵니다 (생애최초도 이 한도는 동일)");
    notes.push("아파트를 사려면 구청 허가가 필요하고, 2년간 실제로 살아야 합니다 (전세 끼고 사는 갭투자 불가)");
  } else if (loanRegion === "capital") {
    regLabel = "수도권 비규제지역";
    regTone = "warn";
    notes.push("주택담보대출은 집값의 70%까지, 다만 금액은 최대 6억까지만 나옵니다");
    notes.push("이미 집이 있는 분(다주택·기존 집 유지)이 추가로 사면 주택담보대출이 나오지 않습니다");
  } else {
    regLabel = "지방 비규제지역";
    regTone = "ok";
    notes.push("주택담보대출은 집값의 70%까지 (생애최초 80%, 이미 집이 있으면 60%)");
    notes.push("대출 총액 한도는 없습니다");
  }
  return { loanRegion, regionalType, isRegulated, isTohuh, regLabel, regTone, notes };
}
