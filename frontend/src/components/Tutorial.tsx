import { useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { Compass, X, ArrowLeft, ArrowRight, BadgePercent, LayoutDashboard, ShieldAlert, Award, Building2, type LucideIcon } from "lucide-react";

type Guide = { icon: LucideIcon; q: string; menu: string; to: string; desc: string; how: string };

// 사용 목적 → 필요한 상단 메뉴 안내. 기능이 늘어나도 여기만 추가하면 됨.
const GUIDES: Guide[] = [
  {
    icon: BadgePercent, q: "급매를 찾고 있어요", menu: "급매찾기", to: "/quick-deals",
    desc: "시세보다 싸게 나온 매물을 콕 집어드려요.",
    how: "지역·평형·거래유형을 고르면, 같은 단지 실거래 평균보다 싼 매물이 할인율 순으로 나옵니다.",
  },
  {
    icon: LayoutDashboard, q: "우리동네 시세를 알고 싶어요", menu: "TODAY", to: "/today",
    desc: "내 동네의 실거래·급매·시세를 한눈에.",
    how: "동네를 한 번 고르면 기억해서, 들어올 때마다 우리동네 최고가·상승·거래·급매를 보여줘요.",
  },
  {
    icon: ShieldAlert, q: "빌라 깡통전세가 걱정돼요", menu: "깡통전세지수", to: "/jeonse-check",
    desc: "빌라 전세의 깡통 위험을 공시가격(HUG) 기준으로 판정.",
    how: "지도에서 빌라를 누르거나 주소 검색 → 전용면적 선택 → 전세보증금을 넣으면 위험도를 알려줘요.",
  },
  {
    icon: Award, q: "공인중개사 랭킹을 알고 싶어요", menu: "중개사무소 랭킹", to: "/realtors/dong",
    desc: "우리 동네 중개사를 매물수·직원수·업력으로 비교.",
    how: "동을 고르면 그 동네 중개사무소 순위가 나오고, 사무소명으로 직접 검색도 됩니다.",
  },
  {
    icon: Building2, q: "중개사인데 홈페이지를 만들고 싶어요", menu: "중개사 라운지", to: "/lounge",
    desc: "공인중개사 무료 홈페이지 + 상담 리드 관리.",
    how: "전화 인증으로 내 사무소를 연결하면, 매물·시세·연락처가 자동 노출되는 홈페이지가 무료로 생깁니다.",
  },
];

export default function Tutorial() {
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<Guide | null>(null);
  const nav = useNavigate();

  const close = () => { setOpen(false); setSel(null); };
  const go = (g: Guide) => { close(); nav(g.to); };

  return (
    <>
      <button className="tut-fab" onClick={() => setOpen(true)} aria-label="사용법">
        <Compass size={20} strokeWidth={2.4} aria-hidden /> <span>사용법</span>
      </button>

      {open && createPortal(
        <div className="tut-ov" onClick={close}>
          <div className="tut-card" onClick={(e) => e.stopPropagation()}>
            <button className="tut-x" onClick={close} aria-label="닫기"><X size={16} /></button>

            {!sel ? (
              <>
                <div className="tut-head"><Compass size={18} /> 어떤 게 필요하세요?</div>
                <p className="tut-sub">목적을 고르면 어느 메뉴를 쓰면 되는지 알려드릴게요.</p>
                <div className="tut-opts">
                  {GUIDES.map((g, i) => (
                    <button key={i} className="tut-opt" onClick={() => setSel(g)}>
                      <span className="tut-opt-ic"><g.icon size={17} /></span>
                      <span className="tut-opt-q">{g.q}</span>
                      <ArrowRight size={15} className="tut-opt-ar" />
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <div className="tut-guide">
                <button className="tut-back" onClick={() => setSel(null)}><ArrowLeft size={14} /> 다른 목적</button>
                <div className="tut-g-ic"><sel.icon size={26} /></div>
                <div className="tut-g-menu">상단 메뉴 <b>{sel.menu}</b></div>
                <div className="tut-g-desc">{sel.desc}</div>
                <div className="tut-g-how"><b>이렇게 써요</b><br />{sel.how}</div>
                <button className="tut-g-go" onClick={() => go(sel)}>{sel.menu} 바로가기 <ArrowRight size={16} /></button>
              </div>
            )}
          </div>
        </div>, document.body)}
    </>
  );
}
