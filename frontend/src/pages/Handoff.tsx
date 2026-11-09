import { useEffect, useState } from "react";
import { authClient } from "../auth";

// 다른 출처(지도 시험판 testv2.koczip.com)에서 로그인한 세션을 넘겨받는 페이지.
// 토큰은 URL 해시(#at=…&rt=…&to=/admin)로만 오므로 서버·로그에 남지 않는다. 받자마자 해시를 지우고 목적지로 간다.
export default function Handoff() {
  const [msg, setMsg] = useState("로그인 상태를 옮기는 중…");
  useEffect(() => {
    const h = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const at = h.get("at") || "", rt = h.get("rt") || "";
    let to = h.get("to") || "/";
    if (!to.startsWith("/") || to.startsWith("//")) to = "/";
    window.history.replaceState(null, "", "/handoff");
    if (!authClient || !at || !rt) { window.location.replace(to); return; }
    authClient.auth.setSession({ access_token: at, refresh_token: rt })
      .then(({ error }) => { if (error) setMsg("로그인을 옮기지 못했어요. 다시 로그인해 주세요."); window.location.replace(to); })
      .catch(() => { setMsg("로그인을 옮기지 못했어요."); window.location.replace(to); });
  }, []);
  return <div className="muted" style={{ padding: 40, textAlign: "center" }}>{msg}</div>;
}
