// CF Pages Function — 접속자 대략 위치(위경도/도시). request.cf 가 무료 제공(transform 불필요).
// 우리동네 중개사 기본값용. 동 단위가 아니라 도시/구 수준이라 사용자가 드롭다운으로 수정 가능.
export function onRequest(context) {
  const cf = context.request.cf || {};
  const body = {
    lat: cf.latitude != null ? Number(cf.latitude) : null,
    lng: cf.longitude != null ? Number(cf.longitude) : null,
    city: cf.city || null,
    region: cf.region || null,
    country: cf.country || null,
  };
  return new Response(JSON.stringify(body), {
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
