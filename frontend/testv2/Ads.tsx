// 지도 광고 자리(5곳)와 광고 안내 모달. 광고가 없으면 자리를 그리지 않는다. 랭킹·급매 순위와 섞지 않고 '광고' 꼬리표를 단다.
import { useEffect, useState } from "react";
import { API, getJson } from "./Drawer";

export type Ad = { id: number; slot: string; scope: string; code: string; title: string; sub: string; url: string; image_url: string;
  complex_no: string; realtor_id: string; lat: number | null; lng: number | null; advertiser: string };
export type AdSlots = { pin: Ad[]; realtor_top: Ad[]; deals_top: Ad[]; stats_band: Ad[]; info_life: Ad[] };
export const NO_ADS: AdSlots = { pin: [], realtor_top: [], deals_top: [], stats_band: [], info_life: [] };

export function useAds(sgg: string | undefined, dong: string | undefined): AdSlots {
  const [ads, setAds] = useState<AdSlots>(NO_ADS);
  useEffect(() => {
    let off = false;
    getJson(`/map/ads?sigungu=${(sgg || "").slice(0, 5)}&dong=${dong || ""}`).then((j) => { if (!off) setAds({ ...NO_ADS, ...(j.slots || {}) }); }).catch(() => { if (!off) setAds(NO_ADS); });
    return () => { off = true; };
  }, [sgg, dong]);
  return ads;
}

export const adClick = (ad: Ad) => { fetch(`${API}/map/ads/${ad.id}/click`, { method: "POST" }).catch(() => {}); };

// 목록 한 줄짜리 광고(급매 첫 칸 · 중개사 상단). onGo: 단지 광고면 지도의 그 단지로, 사무소 광고면 사무소 창으로
export function AdRow({ ad, onGo, onRealtor }: { ad: Ad; onGo?: (no: string, name: string) => void; onRealtor?: (id: string) => void }) {
  const go = () => {
    adClick(ad);
    if (ad.complex_no && onGo) onGo(ad.complex_no, ad.title);
    else if (ad.realtor_id && onRealtor) onRealtor(ad.realtor_id);
    else if (ad.url) window.open(ad.url, "_blank", "noreferrer");
  };
  return (
    <button className="t2-adrow" onClick={go}>
      <span className="t2-adtag">광고</span>
      {ad.image_url && <img src={ad.image_url} alt="" />}
      <span className="t"><b>{ad.title}</b>{ad.sub && <em>{ad.sub}</em>}</span>
      {ad.advertiser && <small>{ad.advertiser}</small>}
    </button>
  );
}

// 통계 창 아래 가로 띠 · 단지정보 아래 생활 광고
export function AdBand({ ad }: { ad: Ad }) {
  return (
    <a className="t2-adband" href={ad.url || "#"} target={ad.url ? "_blank" : undefined} rel="noreferrer" onClick={() => adClick(ad)}>
      <span className="t2-adtag">광고</span>
      {ad.image_url && <img src={ad.image_url} alt="" />}
      <span className="t"><b>{ad.title}</b>{ad.sub && <em>{ad.sub}</em>}</span>
      {ad.advertiser && <small>{ad.advertiser}</small>}
    </a>
  );
}

// ── 광고 안내(상품·가격·문의) ──
const AD_MAIL = "mailto:runtoonline@gmail.com?subject=" + encodeURIComponent("콕집 광고문의");
const CS_URL = "https://pf.kakao.com/_ackPX/chat";
const PRODUCTS: { k: string; name: string; where: string; who: string; price: string; unit: string }[] = [
  { k: "pin", name: "광고 핀", where: "매물찾기 지도 위 금색 핀. 누르면 분양 안내 페이지 또는 단지로", who: "분양·입주 현장, 모델하우스", price: "구 1곳 월 20만원", unit: "시·도 전체 월 120만원 · 구당 핀 최대 3곳 순환" },
  { k: "realtor_top", name: "중개사무소 상단 노출", where: "중개사 랭킹 1위 위 고정 1칸 + 그 동 단지 서랍 중개사 탭 맨 위", who: "공인중개사무소", price: "동 1곳 월 5만원", unit: "동마다 1곳 독점 · 구 전체 월 30만원" },
  { k: "deals_top", name: "급매 목록 첫 칸", where: "매물찾기 왼쪽 급매 목록(휴대폰은 아래 시트) 맨 위 한 줄", who: "그 지역 단지·사무소·분양", price: "구 1곳 월 15만원", unit: "구당 1칸" },
  { k: "stats_band", name: "통계 창 띠", where: "실거래·호가·거래량·투자 통계 18개 화면 아래 가로 한 줄", who: "금융·분양·부동산 서비스", price: "월 25만원", unit: "전국 노출 · 2곳 순환" },
  { k: "info_life", name: "생활 광고", where: "단지 서랍 단지정보 탭 맨 아래 한 줄", who: "인테리어·이사·청소·가전", price: "구 1곳 월 8만원", unit: "전국 월 40만원" },
];

export function AdInfoModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="t2-modal" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="t2-modal-in legal" onClick={(e) => e.stopPropagation()}>
        <div className="t2-ph"><h2>광고 안내</h2><button className="t2-x" onClick={onClose} aria-label="닫기">×</button></div>
        <div className="t2-adinfo">
          <p className="t2-safe-lead">콕집 지도는 매물·실거래·중개사 자료를 보러 오는 사람에게 광고를 보여 줘요. 광고는 모두 <b>'광고' 표시</b>를 달고, 급매 순위·중개사 랭킹과 섞지 않아요.</p>
          <div className="t2-kpis">
            <div><span>하루 방문</span><b>약 370명</b><small>최근 2주 평균 · 봇 제외</small></div>
            <div><span>하루 페이지뷰</span><b>약 22,000</b><small>지도·통계·단지 화면</small></div>
            <div><span>하루 단지 조회</span><b>약 12,000</b><small>단지 서랍·핀</small></div>
          </div>
          <p className="t2-snote">2026년 11월 9일 기준. 접속이 늘면 가격을 다시 정해요. 광고주에게는 월 1회 노출·클릭 집계를 보내 드려요.</p>
          <table className="t2-tbl t2-adprice">
            <thead><tr><th>상품</th><th>자리</th><th>맞는 광고주</th><th className="num">가격(월, 부가세 별도)</th></tr></thead>
            <tbody>
              {PRODUCTS.map((p) => <tr key={p.k}><td><b>{p.name}</b></td><td style={{ whiteSpace: "normal" }}>{p.where}</td><td style={{ whiteSpace: "normal" }}>{p.who}</td><td className="num" style={{ whiteSpace: "normal" }}><b>{p.price}</b><small className="blk">{p.unit}</small></td></tr>)}
              <tr className="sum"><td><b>분양 묶음</b></td><td style={{ whiteSpace: "normal" }}>광고 핀 + 급매 목록 첫 칸 + 통계 창 띠</td><td style={{ whiteSpace: "normal" }}>분양·입주 현장</td><td className="num"><b>구 1곳 월 45만원</b><small className="blk">따로 하면 60만원</small></td></tr>
            </tbody>
          </table>
          <h3 className="t2-sh" style={{ display: "block" }}>조건</h3>
          <ul className="t2-terms">
            <li>기간은 1개월 단위, 매달 1일 시작(중간 시작은 일할 계산).</li>
            <li>소재는 제목 20자 · 설명 40자 · 연결 주소(또는 단지·사무소) · 작은 이미지 1장. 과장·허위 문구는 게재하지 않아요.</li>
            <li>부동산 광고는 표시·광고법과 공인중개사법 광고 규정을 따라야 해요. 중개사무소 광고는 등록번호·상호가 있어야 해요.</li>
            <li>게재 뒤 광고주가 원하면 7일 안에 소재를 한 번 바꿀 수 있어요.</li>
          </ul>
          <div className="t2-adcta">
            <a className="t2-cta1" href={AD_MAIL}>메일로 광고문의</a>
            <a className="t2-cta1 ghost" href={CS_URL} target="_blank" rel="noreferrer">카카오톡 고객센터로 문의</a>
          </div>
          <p className="t2-snote">런투온라인 · 대표 황인찬 · runtoonline@gmail.com · 070-7954-4114</p>
        </div>
      </div>
    </div>
  );
}
