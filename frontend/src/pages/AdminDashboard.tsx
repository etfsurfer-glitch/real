import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Users, ScrollText, Wrench, ShieldAlert, ClipboardCheck, Home as HomeIcon,
  UserCheck, Coins, Bot, LogIn, MessagesSquare, Star, Layers,
} from "lucide-react";
import { useAuth } from "../auth";
import { Loading } from "../components/Loading";

const API_BASE = import.meta.env.VITE_API_BASE;

type Overview = {
  members: { total: number; verified: number; with_nickname: number; points_total: number };
  activity: { logins_today: number; logins_7d: number; ai_today: number; ai_7d: number; active_7d: number; events_today: number };
  moderation: { reviews_pending: number; resident_pending: number; realtors_unmatched: number };
  content: { forum_posts: number; forum_comments: number; complex_reviews: number; realtor_reviews: number };
  snapshot: { date: string | null; listings: number };
};

const n = (v: number | null | undefined) => (v ?? 0).toLocaleString();

function Kpi({ icon: Icon, label, value, sub }: {
  icon: typeof Users; label: string; value: string; sub?: string;
}) {
  return (
    <div className="card">
      <div className="label" style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
        <Icon size={13} strokeWidth={2.2} aria-hidden /> {label}
      </div>
      <div className="num">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

const TOOLS: { to: string; label: string; icon: typeof Users; desc: string;
  badge?: (o: Overview) => number }[] = [
  { to: "/admin/users", label: "사용자 관리", icon: Users, desc: "가입 회원 · 인증 · 포인트" },
  { to: "/admin/logs", label: "활동 로그", icon: ScrollText, desc: "로그인 · 조회 · AI 질문 추이" },
  { to: "/admin/reviews", label: "리뷰 검수", icon: ClipboardCheck, desc: "인증리뷰 서류 승인/거부",
    badge: (o) => o.moderation.reviews_pending },
  { to: "/admin/resident", label: "입주민 인증", icon: HomeIcon, desc: "거주 입증 서류 승인",
    badge: (o) => o.moderation.resident_pending },
  { to: "/admin/realtor-match", label: "중개사 매칭", icon: Wrench, desc: "vworld 매칭 검토",
    badge: (o) => o.moderation.realtors_unmatched },
  { to: "/admin/suspicious", label: "의심 중개사", icon: ShieldAlert, desc: "허위/중복 의심 탐지" },
];

export default function AdminDashboard() {
  const { token } = useAuth();
  const [o, setO] = useState<Overview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!API_BASE || !token) return;
    fetch(`${API_BASE}/admin/overview`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setO).catch((e) => setErr(String(e)));
  }, [token]);

  if (err) return <div style={{ color: "crimson" }}>오류: {err}</div>;
  if (!o) return <Loading />;

  const pendingTotal = o.moderation.reviews_pending + o.moderation.resident_pending;

  return (
    <>
      <h2 style={{ margin: "0 0 4px", fontSize: 19, fontWeight: 700 }}>관리자 대시보드</h2>
      <div className="muted" style={{ marginBottom: 16 }}>
        최신 스냅샷 {o.snapshot.date ?? "—"} · 매물 {n(o.snapshot.listings)}건
        {pendingTotal > 0 && <span style={{ color: "#d23b3b", fontWeight: 600 }}> · 검수 대기 {pendingTotal}건</span>}
      </div>

      <div className="section-title"><Users size={15} /> 회원</div>
      <div className="cards">
        <Kpi icon={Users} label="전체 회원" value={n(o.members.total)}
          sub={`닉네임 설정 ${n(o.members.with_nickname)}`} />
        <Kpi icon={UserCheck} label="전화 인증" value={n(o.members.verified)}
          sub={`미인증 ${n(o.members.total - o.members.verified)}`} />
        <Kpi icon={Coins} label="유통 포인트" value={n(o.members.points_total)} sub="전 회원 보유 합계" />
        <Kpi icon={LogIn} label="활성 사용자(7일)" value={n(o.activity.active_7d)} sub="고유 user_id" />
      </div>

      <div className="section-title"><Bot size={15} /> 활동</div>
      <div className="cards">
        <Kpi icon={LogIn} label="오늘 로그인" value={n(o.activity.logins_today)} sub={`7일 ${n(o.activity.logins_7d)}`} />
        <Kpi icon={Bot} label="오늘 AI 질문" value={n(o.activity.ai_today)} sub={`7일 ${n(o.activity.ai_7d)}`} />
        <Kpi icon={ScrollText} label="오늘 이벤트" value={n(o.activity.events_today)} sub="전체 활동 로그" />
        <Kpi icon={Layers} label="최신 스냅샷 매물" value={n(o.snapshot.listings)} sub={o.snapshot.date ?? "—"} />
      </div>

      <div className="section-title"><MessagesSquare size={15} /> 콘텐츠</div>
      <div className="cards">
        <Kpi icon={MessagesSquare} label="토론장 글" value={n(o.content.forum_posts)}
          sub={`댓글 ${n(o.content.forum_comments)}`} />
        <Kpi icon={Star} label="단지 리뷰" value={n(o.content.complex_reviews)} />
        <Kpi icon={ClipboardCheck} label="중개사 리뷰" value={n(o.content.realtor_reviews)}
          sub={`검수대기 ${n(o.moderation.reviews_pending)}`} />
        <Kpi icon={Wrench} label="미매칭 중개사" value={n(o.moderation.realtors_unmatched)} />
      </div>

      <div className="section-title"><Wrench size={15} /> 관리 도구</div>
      <div className="admin-tools">
        {TOOLS.map((t) => {
          const badge = t.badge ? t.badge(o) : 0;
          return (
            <Link key={t.to} to={t.to} className="admin-tool-card">
              <div className="admin-tool-ic"><t.icon size={18} strokeWidth={2.1} /></div>
              <div className="admin-tool-main">
                <div className="admin-tool-title">
                  {t.label}
                  {badge > 0 && <span className="admin-tool-badge">{badge}</span>}
                </div>
                <div className="admin-tool-desc">{t.desc}</div>
              </div>
            </Link>
          );
        })}
      </div>
    </>
  );
}
