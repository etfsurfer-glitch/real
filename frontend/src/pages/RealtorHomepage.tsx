import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Phone, MessageCircle, MapPin, Building2 } from "lucide-react";
import { Loading } from "../components/Loading";
import { useAuth } from "../auth";
import { openListingPopup } from "../lib/listingPopup";
import { loadKakao, geocodeRegion } from "../lib/kakaomap";

// 거래유형 → 네이버 코드. 매물 클릭 시 네이버 단지 매물을 작은 팝업창으로.
const TRADE_CODE: Record<string, string> = { "매매": "A1", "전세": "B1", "월세": "B2" };
function naverComplexUrl(complexNo: string, tradeType: string): string {
  const c = TRADE_CODE[tradeType] || "";
  return `https://new.land.naver.com/complexes/${complexNo}${c ? `?tradeTypes=${c}` : ""}`;
}
// 비단지(상가·사무실·빌라·단독)는 단지가 없어 개별 매물 딥링크로 — 트래픽을 네이버로.
function naverArticleUrl(articleNo: string): string {
  return `https://m.land.naver.com/article/info/${articleNo}`;
}
// 우리 6구분 — 상단탭 순서. 아파트·오피=단지기반, 나머지=비단지(딥링크).
const CATEGORY_ORDER = ["아파트", "오피스텔", "상가", "사무실", "빌라/연립", "단독/다가구", "빌딩", "토지", "공장", "지식산업센터", "재개발"];

const API_BASE = import.meta.env.VITE_API_BASE;

type Office = { realtor_id: string; realtor_name: string | null; address?: string | null; representative?: string | null; tel?: string | null; cell?: string | null; latitude?: number | null; longitude?: number | null };
type Listing = {
  category?: string; type?: string; complex_no: string | null; complex_name: string | null;
  building_name?: string | null; trade_type: string; price: number; rent_price?: number | null;
  price_text?: string; rent_price_text?: string; excl_use_ar: number | null; area_name: string | null;
  count: number; article_no?: string | null; floor_info?: string; direction?: string;
  confirm_ymd?: string; address?: string; feature_desc?: string; naver_url?: string;
};
type Cfg = {
  realtor_id: string; slug: string | null; slogan: string | null; intro: string | null;
  specialties: string | null; biz_hours: string | null; kakao_url: string | null;
  consult_tel: string | null; map_memo: string | null;
  has_photo: { apt?: boolean; rep?: boolean; office?: boolean };
  photos?: { apt?: string | null; rep?: string | null; office?: string | null };
  published: boolean;
};
type Resp = { config: Cfg; office: Office; listings: Listing[] };

function won(v: number): string {
  if (v >= 1e8) {
    const eok = Math.floor(v / 1e8), man = Math.floor((v % 1e8) / 1e4);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
// 사진 마커 → 실제 URL. preset:NAME → /presets/NAME.webp, upload → API 서브, null → 기본 없음
function photoSrc(cfg: Cfg, kind: "apt" | "rep" | "office"): string | null {
  const m = cfg.photos?.[kind];
  if (!m) return null;
  if (m.startsWith("preset:")) return `/presets/${m.slice(7)}.webp`;
  return `${API_BASE}/public/homepage/${cfg.slug}/photo/${kind}`;
}

export default function RealtorHomepage() {
  const { slug = "" } = useParams();
  const [sp] = useSearchParams();
  const preview = sp.get("preview") === "1";
  const { token, ready } = useAuth();
  const [d, setD] = useState<Resp | null>(null);
  const [err, setErr] = useState(false);
  const [leadOpen, setLeadOpen] = useState(false);

  useEffect(() => {
    if (!API_BASE) { setErr(true); return; }
    if (preview) {
      // 게시 전 본인 미리보기 — 로그인 토큰으로 draft 데이터 조회(콕집 도메인에서만 가능)
      if (!ready) return;            // 인증 준비 대기
      if (!token) { setErr(true); return; }
      fetch(`${API_BASE}/lounge/homepage/preview`, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
        .then(setD).catch(() => setErr(true));
      return;
    }
    fetch(`${API_BASE}/public/homepage/${encodeURIComponent(slug)}`)
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then(setD).catch(() => setErr(true));
  }, [slug, preview, ready, token]);

  useEffect(() => {
    if (d?.office.realtor_name) document.title = `${d.office.realtor_name} | 콕집`;
  }, [d]);

  if (err) return <div className="muted" style={{ padding: 40, textAlign: "center" }}>
    {preview ? "미리보기는 콕집에 로그인한 본인만 볼 수 있어요. (라운지에서 ‘임시저장’ 후 미리보기)" : "홈페이지를 찾을 수 없습니다."}
  </div>;
  if (!d) return <Loading />;

  const { config: cfg, office, listings } = d;
  const name = office.realtor_name ?? "공인중개사무소";
  const tel = cfg.consult_tel || office.tel || office.cell || "";
  const telDigits = tel.replace(/[^0-9+]/g, "");
  const specs = (cfg.specialties || "").split(/[,·]/).map((s) => s.trim()).filter(Boolean);
  const officeImg = photoSrc(cfg, "office"), repImg = photoSrc(cfg, "rep");
  // 히어로 배경: 사무소 사진 > (명함 슬롯이 기본 아파트 이미지일 때) 아파트 이미지 > 네이비
  const aptIsPreset = (cfg.photos?.apt || "").startsWith("preset:");
  const heroBg = officeImg || (aptIsPreset ? photoSrc(cfg, "apt") : null);

  return (
    <div className="rh">
      {/* 콕집 네비바 — 은은하게, 인기메뉴로 콕집 유입 */}
      <div className="rh-nav">
        <a className="rh-nav-brand" href="https://koczip.com" target="_blank" rel="noreferrer">
          <img src="https://koczip.com/logo.svg" alt="" width="18" height="18" /> 콕집
        </a>
        <nav className="rh-nav-menu">
          <a href="https://koczip.com/quick-deals" target="_blank" rel="noreferrer">급매찾기</a>
          <a href="https://koczip.com/tx-stats/record-high" target="_blank" rel="noreferrer">주요 실거래</a>
          <a href="https://koczip.com/overview" target="_blank" rel="noreferrer">전국 시세</a>
          <a href="https://koczip.com/" target="_blank" rel="noreferrer">AI 질문</a>
        </nav>
      </div>
      {preview && (
        <div style={{ background: "#1268d3", color: "#fff", textAlign: "center", padding: "8px 12px", fontSize: 13, fontWeight: 600 }}>
          미리보기 {cfg.published ? "(게시됨)" : "(게시 전 — 아직 공개되지 않았어요)"} · 내용을 수정하려면 라운지로 돌아가세요
        </div>
      )}
      {/* 히어로 */}
      <section className="rh-hero" style={heroBg ? { backgroundImage: `linear-gradient(rgba(8,20,40,.55),rgba(8,20,40,.7)), url(${heroBg})` } : undefined}>
        <div className="rh-hero-in">
          {repImg
            ? <img className="rh-rep" src={repImg} alt="대표" />
            : <div className="rh-rep rh-rep-ph"><Building2 size={34} aria-hidden /></div>}
          <h1>{name}</h1>
          {cfg.slogan && <p className="rh-slogan">{cfg.slogan}</p>}
          {office.representative && <p className="rh-rep-name">대표 {office.representative}</p>}
          <div className="rh-hero-cta">
            {telDigits && <a className="rh-btn rh-btn-tel" href={`tel:${telDigits}`}><Phone size={16} /> 전화상담</a>}
            {cfg.kakao_url && <a className="rh-btn rh-btn-kakao" href={cfg.kakao_url} target="_blank" rel="noreferrer"><MessageCircle size={16} /> 카카오톡</a>}
            <button className="rh-btn rh-btn-consult" onClick={() => setLeadOpen(true)}>상담신청</button>
          </div>
        </div>
      </section>

      <div className="rh-body">
        {cfg.intro && (
          <section className="rh-sec"><h2>소개</h2><p className="rh-intro">{cfg.intro}</p></section>
        )}
        {(specs.length > 0 || cfg.biz_hours) && (
          <section className="rh-sec rh-info">
            {specs.length > 0 && <div><b>전문분야</b><div className="rh-chips">{specs.map((s) => <span key={s} className="rh-chip">{s}</span>)}</div></div>}
            {cfg.biz_hours && <div><b>영업시간</b><div>{cfg.biz_hours}</div></div>}
          </section>
        )}

        {listings.length > 0 && <ListingsSection listings={listings} />}

        <section className="rh-sec"><h2><MapPin size={16} aria-hidden /> 오시는 길</h2>
          {office.address && <p className="rh-addr">{office.address}</p>}
          {cfg.map_memo && <p className="muted">{cfg.map_memo}</p>}
          <OfficeMap lat={office.latitude} lng={office.longitude} address={office.address} name={office.realtor_name} />
        </section>

        <footer className="rh-foot">
          <span>{name}</span>
          <span className="muted"> · powered by <a href="https://koczip.com" target="_blank" rel="noreferrer">콕집</a></span>
        </footer>
      </div>

      {/* 바이럴 CTA — 다른 중개사 유입 (공개 페이지에만) */}
      {!preview && (
        <a className="rh-promo" href="https://koczip.com/lounge" target="_blank" rel="noreferrer">
          공인중개사라면 <b>홈페이지 무료로 만들기 →</b>
        </a>
      )}

      {/* 플로팅 버튼 */}
      <div className="rh-float">
        {telDigits && <a className="rh-fab rh-fab-tel" href={`tel:${telDigits}`} aria-label="전화"><Phone size={20} /></a>}
        {cfg.kakao_url && <a className="rh-fab rh-fab-kakao" href={cfg.kakao_url} target="_blank" rel="noreferrer" aria-label="카카오톡"><MessageCircle size={20} /></a>}
        <button className="rh-fab rh-fab-consult" onClick={() => setLeadOpen(true)}>상담<br />신청</button>
      </div>

      {leadOpen && <LeadModal slug={cfg.slug!} name={name} onClose={() => setLeadOpen(false)} />}
    </div>
  );
}

const TRADE_ORDER = ["매매", "전세", "월세"];

const RH_PAGE = 24;
function rhFmtYmd(s?: string) { return s && s.length === 8 ? `${s.slice(4, 6)}/${s.slice(6, 8)}` : (s || ""); }
function ListingsSection({ listings }: { listings: Listing[] }) {
  const [cat, setCat] = useState("전체");
  const [trade, setTrade] = useState("전체");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(RH_PAGE);
  const reset = () => setShown(RH_PAGE);

  // 카테고리 상단탭 — 보유한 것만
  const presentCats = CATEGORY_ORDER.filter((c) => listings.some((l) => (l.category || "아파트") === c));
  const catTabs = presentCats.length > 1 ? ["전체", ...presentCats] : presentCats;
  const byCat = cat === "전체" ? listings : listings.filter((l) => (l.category || "아파트") === cat);

  const present = TRADE_ORDER.filter((t) => byCat.some((l) => l.trade_type === t));
  const tabs = present.length > 1 ? ["전체", ...present] : present;
  let rows = trade === "전체" ? byCat : byCat.filter((l) => l.trade_type === trade);
  const ql = q.trim();
  if (ql) rows = rows.filter((l) => (l.complex_name || "").includes(ql) || (l.building_name || "").includes(ql)
    || (l.address || "").includes(ql) || (l.area_name || "").includes(ql));
  const visible = rows.slice(0, shown);

  return (
    <section className="rh-sec">
      <div className="rh-listings-head">
        <h2>보유 매물 <span className="muted">{rows.length.toLocaleString()}건</span></h2>
        {catTabs.length > 1 && (
          <div className="rh-cat-filter">
            {catTabs.map((c) => (
              <button key={c} className={cat === c ? "on" : ""}
                onClick={() => { setCat(c); setTrade("전체"); reset(); }}>{c}</button>
            ))}
          </div>
        )}
        {tabs.length > 0 && (
          <div className="rh-trade-filter">
            {tabs.map((t) => (
              <button key={t} className={trade === t ? "on" : ""} onClick={() => { setTrade(t); reset(); }}>{t}</button>
            ))}
          </div>
        )}
      </div>
      {listings.length > 8 && (
        <div className="rh-list-tools">
          <input className="rh-search" placeholder="단지·건물·지역 검색" value={q}
            onChange={(e) => { setQ(e.target.value); reset(); }} />
        </div>
      )}
      <div className="rl-listings">
        {visible.map((l, i) => {
          const url = l.complex_no ? naverComplexUrl(l.complex_no, l.trade_type)
            : (l.article_no ? naverArticleUrl(l.article_no) : (l.naver_url || null));
          const price = l.trade_type === "월세" && l.rent_price_text
            ? `${l.price_text || won(l.price)}/${l.rent_price_text}`
            : (l.price_text || won(l.price));
          const meta = [l.excl_use_ar ? `전용 ${l.excl_use_ar}㎡` : "", l.floor_info ? `${l.floor_info}층` : "",
            l.direction, l.confirm_ymd ? `확인 ${rhFmtYmd(l.confirm_ymd)}` : ""].filter(Boolean).join(" · ");
          return (
            <a key={l.article_no || i} className="rl-lcard" href={url || "#"} target="_blank" rel="noreferrer"
              onClick={(e) => { e.preventDefault(); if (url) openListingPopup(url); }}>
              <div className="rl-lc-head">
                <span className={`mlj-trade tr-${l.trade_type}`}>{l.trade_type}</span>
                {l.type && <span className="rl-lc-type">{l.type}</span>}
                <b className="rl-lc-title">{l.complex_name || l.building_name || l.area_name || "매물"}</b>
                <span className="rl-lc-price">{price}</span>
              </div>
              {l.address && <div className="rl-lc-addr"><MapPin size={11} aria-hidden /> {l.address}</div>}
              {meta && <div className="rl-lc-meta">{meta}</div>}
            </a>
          );
        })}
      </div>
      {visible.length < rows.length && (
        <button className="rh-more" onClick={() => setShown((s) => s + RH_PAGE * 2)}>
          더보기 (+{(rows.length - visible.length).toLocaleString()}건)
        </button>
      )}
    </section>
  );
}

// 사무소 위치 카카오맵 임베드 — 좌표 있으면 바로, 없으면 주소 지오코딩으로 중심 잡음.
function OfficeMap({ lat, lng, address, name }: {
  lat?: number | null; lng?: number | null; address?: string | null; name?: string | null;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        let c: { lat: number; lng: number } | null = (lat && lng) ? { lat, lng } : null;
        if (!c && address) c = await geocodeRegion(address);
        if (cancelled) return;
        if (!c) { setFailed(true); return; }
        await loadKakao();
        if (cancelled || !ref.current) return;
        const kakao = window.kakao;
        const pos = new kakao.maps.LatLng(c.lat, c.lng);
        const map = new kakao.maps.Map(ref.current, { center: pos, level: 4 });
        map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
        new kakao.maps.Marker({ position: pos, map });
        if (name) {
          new kakao.maps.CustomOverlay({
            position: pos, yAnchor: 2.3, map,
            content: `<div class="rh-maplabel">${name.replace(/</g, "&lt;")}</div>`,
          });
        }
      } catch { if (!cancelled) setFailed(true); }
    })();
    return () => { cancelled = true; };
  }, [lat, lng, address, name]);
  if (failed) return null;
  return <div ref={ref} className="rh-map" />;
}

function LeadModal({ slug, name, onClose }: { slug: string; name: string; onClose: () => void }) {
  const [form, setForm] = useState({ name: "", phone: "", message: "" });
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = () => {
    if (!form.phone && !form.name) { alert("이름 또는 연락처를 입력해주세요."); return; }
    setBusy(true);
    fetch(`${API_BASE}/public/homepage/${encodeURIComponent(slug)}/lead`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
    }).then((r) => { if (!r.ok) throw new Error(); setDone(true); })
      .catch(() => alert("전송 실패")).finally(() => setBusy(false));
  };
  return (
    <div className="rh-modal-bg" onClick={onClose}>
      <div className="rh-modal" onClick={(e) => e.stopPropagation()}>
        {done ? (
          <>
            <h3>상담신청 완료</h3>
            <p className="muted">{name}에서 곧 연락드리겠습니다. 감사합니다!</p>
            <button className="rh-btn rh-btn-consult" onClick={onClose}>닫기</button>
          </>
        ) : (
          <>
            <h3>상담 신청</h3>
            <input className="ai-input" placeholder="이름" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className="ai-input" placeholder="연락처 (예: 010-0000-0000)" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            <textarea className="ai-input" rows={3} placeholder="문의 내용 (선택)" value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} />
            <button className="rh-btn rh-btn-consult" disabled={busy} onClick={submit}>신청하기</button>
          </>
        )}
      </div>
    </div>
  );
}
