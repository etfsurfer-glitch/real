// 네이버 매물을 별도 팝업창(window.open)으로 — 탭이 아닌 가운데 작은 창으로 열려
// 내 페이지는 뒤에 그대로 남는다(체류 유지). 네이버가 iframe(X-Frame-Options)을
// 막아 in-page 임베드는 불가하므로 팝업이 최선. 팝업 차단 시 새 탭으로 폴백.
export function openListingPopup(url: string) {
  const w = 900, h = 860;
  const left = window.screenX + Math.max(0, (window.outerWidth - w) / 2);
  const top = window.screenY + Math.max(0, (window.outerHeight - h) / 2);
  const win = window.open(
    url, "kokzip_listing",
    `popup=yes,width=${w},height=${h},left=${left},top=${top},scrollbars=yes,resizable=yes`,
  );
  if (!win) window.open(url, "_blank", "noopener");
}
