import { useState } from "react";
import SupportLink from "./SupportLink";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { Compass, X, ArrowLeft, ArrowRight, BadgePercent, LayoutDashboard, ShieldAlert, Award, Building2,
  SlidersHorizontal, Calculator, ShieldCheck, type LucideIcon } from "lucide-react";

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
    icon: SlidersHorizontal, q: "조건에 맞는 단지를 찾고 싶어요", menu: "맞춤단지", to: "/finder",
    desc: "평형·가격·연차·갭 같은 조건을 걸어 단지를 추려요.",
    how: "시·군·구를 고르고 평형대·매매가·입주년차·세대수·전세가율·갭·방수·초등학교 거리 등으로 좁히면 됩니다. 조건은 저장해 두고 다시 쓸 수 있어요.",
  },
  {
    icon: Calculator, q: "이 집을 사면 돈이 얼마나 드는지 알고 싶어요", menu: "아파트매수계산기", to: "/buy-calculator",
    desc: "취득세·중개보수·채권·등기비까지 실제로 나가는 돈 전부.",
    how: "매매가와 보유 상황(생애최초·다주택 여부)을 넣으면 취득세율과 대출 한도가 자동으로 잡히고, 필요한 현금이 얼마인지 나옵니다.",
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
  {
    icon: ShieldCheck, q: "중개사인데 매물 광고에 빠진 게 없는지 보고 싶어요", menu: "중개사 라운지 → 매물점검", to: "/lounge",
    desc: "표시·광고 의무사항 누락을 건축물대장과 대조해 점검.",
    how: "라운지에서 내 사무소를 연결한 뒤 ‘매물점검’ 탭을 열면, 층·면적·주차·관리비·방향 등 빠진 항목을 매물별로 짚어줍니다.",
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
            <div className="tut-cs"><SupportLink variant="banner" sub="더 궁금하거나 막히는 게 있으면" label="고객센터" context="tutorial" /></div>
          </div>
        </div>, document.body)}
    </>
  );
}
