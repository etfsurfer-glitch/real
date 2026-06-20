import { useRegionFilter } from "./RegionSelect";
import { geocodeRegion } from "../lib/kakaomap";

// 지도(지도보기·급매지도)에서 시도/시군구/읍면동을 골라 "적용"을 누르면
// 그 위치로 지도를 이동시킨다. 드롭다운 변경은 목록 채우기/선택만 하고
// 지도 이동·데이터 호출은 적용 시 1번만 일어난다(낭비 방지).
//   onMove(lat, lng, level) — 시도=넓게(9), 시군구=중간(6), 읍면동=가깝게(4)
export default function MapRegionPicker({
  onMove,
}: {
  onMove: (lat: number, lng: number, level: number) => void;
}) {
  const rf = useRegionFilter();

  const nameOf = (list: { code: string; name: string }[], code: string) =>
    list.find((x) => x.code === code)?.name || "";

  const apply = async () => {
    let query = "";
    let level = 9;
    if (rf.dong) {
      query = `${nameOf(rf.sidos, rf.sido)} ${nameOf(rf.sigungus, rf.sigungu)} ${nameOf(rf.dongs, rf.dong)}`;
      level = 4;
    } else if (rf.sigungu) {
      query = `${nameOf(rf.sidos, rf.sido)} ${nameOf(rf.sigungus, rf.sigungu)}`;
      level = 6;
    } else if (rf.sido) {
      query = nameOf(rf.sidos, rf.sido);
      level = 9;
    } else {
      return;
    }
    const c = await geocodeRegion(query.trim());
    if (c) onMove(c.lat, c.lng, level);
  };

  return (
    <div className="map-region">
      <label className="filter-select">
        <span>시도</span>
        <select value={rf.sido} onChange={(e) => rf.setSido(e.target.value)}>
          <option value="">지역선택</option>
          {rf.sidos.map((s) => (
            <option key={s.code} value={s.code}>{s.name}</option>
          ))}
        </select>
      </label>
      <label className="filter-select">
        <span>시군구</span>
        <select value={rf.sigungu} onChange={(e) => rf.setSigungu(e.target.value)} disabled={!rf.sido}>
          <option value="">{rf.sido ? "전체" : "(시도 먼저)"}</option>
          {rf.sigungus.map((s) => (
            <option key={s.code} value={s.code}>{s.name}</option>
          ))}
        </select>
      </label>
      <label className="filter-select">
        <span>읍면동</span>
        <select value={rf.dong} onChange={(e) => rf.setDong(e.target.value)} disabled={!rf.sigungu}>
          <option value="">{rf.sigungu ? "전체" : "(시군구 먼저)"}</option>
          {rf.dongs.map((s) => (
            <option key={s.code} value={s.code}>{s.name}</option>
          ))}
        </select>
      </label>
      <button type="button" className="map-apply" onClick={apply} disabled={!rf.sido}>
        적용
      </button>
    </div>
  );
}
