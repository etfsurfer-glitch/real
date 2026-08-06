// 단지 목록 어디서든 '비교 담기' — FavHeart 옆에 둔다. 담기면 파란 체크, 꽉 차면 안내.
import { useEffect, useState } from "react";
import { GitCompare } from "lucide-react";
import { subscribeCompare, inCompare, toggleCompare, compareFull } from "../lib/comparestore";

export default function CompareButton({ complexNo, complexName }: {
  complexNo: string; complexName?: string;
}) {
  const [, force] = useState(0);
  const [warn, setWarn] = useState(false);
  useEffect(() => subscribeCompare(() => force((n) => n + 1)), []);

  const on = inCompare(complexNo);
  const click = (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    const r = toggleCompare(complexNo, complexName || "단지");
    if (r.full) { setWarn(true); setTimeout(() => setWarn(false), 1600); }
  };

  return (
    <button type="button" className={"cmp-btn" + (on ? " on" : "")} onClick={click}
      aria-label={on ? "비교에서 빼기" : "비교 담기"}
      title={on ? "비교에서 빼기" : (compareFull() ? "비교는 최대 4개까지" : "비교 담기")}>
      <GitCompare size={12.5} strokeWidth={2.4} aria-hidden />
      <span className="cmp-btn-label">{on ? "담김" : "비교"}</span>
      {warn && <span className="cmp-btn-warn">최대 4개</span>}
    </button>
  );
}
