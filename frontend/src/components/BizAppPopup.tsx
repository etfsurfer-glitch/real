import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router-dom";
import { X, ChevronRight } from "lucide-react";

const KEY = "koczip_bizpop_hide";    // 영구 숨김 — '다시 보지 않기'를 체크하고 닫은 사람만
const SEEN = "koczip_bizpop_seen";   // 이번 세션엔 한 번만
const PLAY = "https://play.google.com/store/apps/details?id=com.koczip.realtor";

// 중개사 전용 앱 출시 팝업.
//  사진은 전부 우리가 만든 것이고 글자는 한 자도 사진에 넣지 않았다 — 이미지에 박힌
//  글자는 흐릿하거나 깨지면 그 한 곳 때문에 사진 전체가 가짜로 보인다. 모든 글은 DOM 에 있다.
//  /biz·/lounge(이미 중개사) 와 관리자·이벤트 화면에서는 뜨지 않는다.
const SLIDES = [
  {
    img: "/promo/biz/s1_diary.jpg",
    kicker: "매물장",
    title: "전화 받으면서\n한 줄로 등록",
    body: "「한마루럭키 104동 1103호 매매 12억 남향」 이렇게 적으면 끝. 나머지 칸은 건축물대장에서 채워 넣습니다.",
  },
  {
    img: "/promo/biz/s2_audit.jpg",
    kicker: "과태료 점검",
    title: "무료 과태료 점검",
    body: "표시·광고 의무사항을 건축물대장과 대조합니다. 빠진 항목만 짚어 드려요.",
  },
  {
    img: "/promo/biz/s3_rank.jpg",
    kicker: "매물 순위",
    title: "내 매물이\n몇 등인지 봅니다",
    body: "같은 물건에 걸린 광고 중 내 것이 몇 번째인지, 단지에서 몇 등인지 매일 확인해요.",
  },
  {
    img: "/promo/biz/s4_req.jpg",
    kicker: "콕집요청",
    title: "손님 요청이\n내 사무소로 옵니다",
    body: "콕집에서 원하는 조건을 남긴 손님이 그 동네 사무소로 전달됩니다. 매물이 많을수록 자주 옵니다.",
  },
  {
    img: "/promo/biz/s5_assist.jpg",
    kicker: "콕비서",
    title: "오늘 잔금 있어?\n물어보면 답합니다",
    body: "일정·손님·어제 바뀐 내 매물. 아침 10시, 오후 4시에 먼저 알려줍니다.",
  },
];

export default function BizAppPopup() {
  const loc = useLocation();
  const [show, setShow] = useState(false);
  const [i, setI] = useState(0);
  const [dontShow, setDontShow] = useState(false);
  const held = useRef(false);                 // 사용자가 한 번이라도 넘기면 자동넘김 중단
  const x0 = useRef(0);

  useEffect(() => {
    const p = loc.pathname;
    if (typeof location !== "undefined" && location.search.includes("shot=1")) return;
    if (p.startsWith("/biz") || p.startsWith("/lounge") || p.startsWith("/admin")
        || p.startsWith("/event") || p.startsWith("/me/coupons")) return;
    try {
      if (localStorage.getItem(KEY)) return;
      if (sessionStorage.getItem(SEEN)) return;
    } catch { return; }
    const t = setTimeout(() => {              // 첫실행 인트로 스플래시 뒤에 뜨도록
      setShow(true);
      try { sessionStorage.setItem(SEEN, "1"); } catch { /* ignore */ }
    }, 1400);
    return () => clearTimeout(t);
    // 최초 1회만 판단(경로 이동마다 재평가하지 않음)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!show || held.current) return;
    const t = setTimeout(() => setI((n) => (n + 1) % SLIDES.length), 3800);
    return () => clearTimeout(t);
  }, [show, i]);

  const go = (n: number) => { held.current = true; setI((n + SLIDES.length) % SLIDES.length); };
  const close = () => {
    if (dontShow) { try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } }
    setShow(false);
  };

  if (!show) return null;
  const s = SLIDES[i];
  return createPortal(
    <div className="bzpop-ov" onClick={close} role="presentation">
      <div
        className="bzpop"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="콕집 중개사 앱 출시"
        onTouchStart={(e) => { x0.current = e.touches[0].clientX; }}
        onTouchEnd={(e) => {
          const d = e.changedTouches[0].clientX - x0.current;
          if (Math.abs(d) > 40) go(i + (d < 0 ? 1 : -1));
        }}
      >
        <button className="bzpop-x" onClick={close} aria-label="닫기"><X size={18} /></button>

        <div className="bzpop-shots">
          {SLIDES.map((v, n) => (
            <img key={v.img} src={v.img} alt="" aria-hidden={n !== i}
                 className={n === i ? "on" : ""} loading={n === 0 ? "eager" : "lazy"} />
          ))}
          <div className="bzpop-veil" />
          <span className="bzpop-kicker">{s.kicker}</span>
        </div>

        <div className="bzpop-body">
          <h2 className="bzpop-title">{s.title}</h2>
          <p className="bzpop-desc">{s.body}</p>

          <div className="bzpop-dots" role="tablist" aria-label="기능 넘기기">
            {SLIDES.map((v, n) => (
              <button key={v.img} role="tab" aria-selected={n === i} aria-label={v.kicker}
                      className={n === i ? "on" : ""} onClick={() => go(n)} />
            ))}
          </div>

          <a className="bzpop-cta" href={PLAY} target="_blank" rel="noopener noreferrer">
            Play 스토어에서 받기 <ChevronRight size={17} strokeWidth={2.6} aria-hidden />
          </a>

          <label className="bzpop-dont">
            <input type="checkbox" checked={dontShow}
                   onChange={(e) => setDontShow(e.target.checked)} />
            <span>다시 보지 않기</span>
          </label>
        </div>
      </div>
    </div>,
    document.body,
  );
}
