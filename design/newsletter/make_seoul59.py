#!/usr/bin/env python3
"""서울 59㎡ · 12억 이하 · 500세대 이상 단지 뉴스레터.

데이터는 박스에서 뽑아 둔 두 파일을 쓴다(nl59.json = 실거래 집계, nl59_ask.json = 현재 호가).
    python3 design/newsletter/make_seoul59.py <실거래json> <호가json> <출력html>
"""
import json
import sys
from pathlib import Path

TX, ASK, OUT = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
rows = json.loads(TX.read_text(encoding="utf-8"))
ask = {a["cno"]: a for a in json.loads(ASK.read_text(encoding="utf-8"))}

BASE_N, BASE_MED, BASE_SHARE = 8989, 930000000, 68.3
ASOF = "2026-08-07"


def eok(v):
    """원 → '9억 3,000'. 매물장·보도자료와 같은 표기."""
    if not v:
        return "-"
    man = round(v / 10000)
    e, m = divmod(man, 10000)
    return f"{e}억" + (f" {m:,}" if m else "") if e else f"{m:,}만"


def py_(m2):
    return round(m2 / 3.3058)


for r in rows:
    a = ask.get(r["cno"])
    r["ask_lo"] = a["ask_lo"] if a else None
    r["ask_n"] = a["ask_n"] if a else 0
    # 호가가 실거래 중앙값보다 얼마나 위인지 — 지금 사려면 얼마를 더 줘야 하는가
    r["gap"] = (round((r["ask_lo"] / r["med"] - 1) * 100)
                if r["ask_lo"] and r["med"] else None)

rows.sort(key=lambda r: r["med"])
BANDS = [(0, 600000000, "6억 미만"), (600000000, 800000000, "6억대·7억대"),
         (800000000, 1000000000, "8억대·9억대"), (1000000000, 1_200_000_001, "10억~12억")]
band_n = [(lb, sum(1 for r in rows if lo <= r["med"] < hi)) for lo, hi, lb in BANDS]

gus = {}
for r in rows:
    gus.setdefault(r["gu"] or "기타", []).append(r)
gu_order = sorted(gus, key=lambda g: (len(gus[g]) * -1, g))

n_ask = sum(1 for r in rows if r["ask_lo"])
gaps = sorted(r["gap"] for r in rows if r["gap"] is not None)
gap_med = gaps[len(gaps) // 2] if gaps else None
hh_tot = sum(r["hh"] for r in rows)
cheapest = rows[0]
biggest = max(rows, key=lambda r: r["hh"])


def tr(r):
    g = r["gap"]
    gcls = "up" if (g is not None and g >= 8) else ("flat" if g is not None else "na")
    gtxt = (f"+{g}%" if g is not None and g > 0 else (f"{g}%" if g is not None else "—"))
    return f"""<tr>
      <td class="nm"><b>{r['nm']}</b><span class="sub">{r['dong']} · {r['apr'] or '-'}년</span></td>
      <td class="num">{r['hh']:,}</td>
      <td class="num strong">{eok(r['med'])}</td>
      <td class="num rng">{eok(r['lo'])} ~ {eok(r['hi'])}<span class="sub">{r['n']}건</span></td>
      <td class="num">{eok(r['ask_lo']) if r['ask_lo'] else '<span class="none">매물 없음</span>'}</td>
      <td class="num gap {gcls}">{gtxt}</td>
    </tr>"""


sections = []
for gu in gu_order:
    rs = gus[gu]
    med = sorted(x["med"] for x in rs)[len(rs) // 2]
    sections.append(f"""
    <section class="gu">
      <h3>{gu}<em>{len(rs)}개 단지</em><i>중앙값 {eok(med)}</i></h3>
      <div class="tw"><table>
        <thead><tr>
          <th>단지</th><th class="num">세대</th><th class="num">실거래 중앙값</th>
          <th class="num">거래 범위</th><th class="num">현재 최저 호가</th><th class="num">호가差</th>
        </tr></thead>
        <tbody>{''.join(tr(r) for r in sorted(rs, key=lambda x: x['med']))}</tbody>
      </table></div>
    </section>""")

html = f"""<title>서울 59㎡ 12억 이하 · 500세대 이상 단지 {len(rows)}곳</title>
<style>
:root{{
  --ink:#12203a; --ink2:#3d4b63; --mute:#6b7889; --faint:#9aa5b4;
  --line:#e3e8ef; --line2:#f0f3f7; --bg:#ffffff; --panel:#f7f9fc;
  --brand:#1268d3; --brand-soft:#e8f0ff; --sale:#c8372f; --up:#c8372f; --flat:#1a7f4b;
}}
:root:not([data-theme="light"]) {{}}
@media (prefers-color-scheme: dark){{
  :root:not([data-theme="light"]){{
    --ink:#e8edf5; --ink2:#c2cbd8; --mute:#98a3b3; --faint:#71808f;
    --line:#28323f; --line2:#1f2732; --bg:#121721; --panel:#19202b;
    --brand:#5da2ff; --brand-soft:#17293f; --sale:#ef7d74; --up:#ef7d74; --flat:#57c68d;
  }}
}}
:root[data-theme="dark"]{{
  --ink:#e8edf5; --ink2:#c2cbd8; --mute:#98a3b3; --faint:#71808f;
  --line:#28323f; --line2:#1f2732; --bg:#121721; --panel:#19202b;
  --brand:#5da2ff; --brand-soft:#17293f; --sale:#ef7d74; --up:#ef7d74; --flat:#57c68d;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,
    "Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
  font-size:15px;line-height:1.65;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:940px;margin:0 auto;padding:0 20px 72px}}
/* 머리 */
header{{padding:44px 0 26px;border-bottom:2px solid var(--ink)}}
.brand{{display:flex;align-items:baseline;gap:9px;margin-bottom:22px}}
.brand b{{font-size:17px;font-weight:800;letter-spacing:-.02em;color:var(--brand)}}
.brand span{{font-size:11.5px;font-weight:700;color:var(--mute);letter-spacing:.04em}}
h1{{margin:0 0 12px;font-size:clamp(27px,4.6vw,40px);font-weight:800;line-height:1.24;
  letter-spacing:-.035em;text-wrap:balance}}
h1 em{{font-style:normal;color:var(--brand)}}
.lede{{margin:0;max-width:62ch;font-size:15.5px;color:var(--ink2);line-height:1.75}}
.meta{{margin-top:18px;display:flex;flex-wrap:wrap;gap:7px}}
.meta i{{font-style:normal;font-size:11.5px;font-weight:700;color:var(--ink2);
  background:var(--panel);border:1px solid var(--line);padding:5px 11px;border-radius:999px}}
/* 요약 숫자 */
.kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);margin:30px 0 8px;border-radius:14px;overflow:hidden}}
.kpi div{{background:var(--bg);padding:18px 18px 16px}}
.kpi b{{display:block;font-size:29px;font-weight:800;letter-spacing:-.03em;
  font-variant-numeric:tabular-nums;line-height:1.15}}
.kpi b small{{font-size:15px;font-weight:700;margin-left:2px}}
.kpi span{{display:block;margin-top:4px;font-size:12px;font-weight:700;color:var(--mute)}}
.kpi u{{display:block;margin-top:7px;font-size:11.5px;color:var(--faint);text-decoration:none;line-height:1.5}}
/* 가격대 막대 */
.bands{{margin:26px 0 34px}}
.bands h2{{margin:0 0 12px}}
.band{{display:grid;grid-template-columns:110px 1fr 54px;align-items:center;gap:12px;
  padding:7px 0;border-bottom:1px solid var(--line2)}}
.band:last-child{{border-bottom:none}}
.band em{{font-style:normal;font-size:12.5px;font-weight:700;color:var(--ink2)}}
.band .bar{{height:9px;border-radius:5px;background:var(--brand);opacity:.85}}
.band .bar.b0{{opacity:.42}} .band .bar.b1{{opacity:.58}} .band .bar.b2{{opacity:.74}}
.band .v{{text-align:right;font-size:12.5px;font-weight:800;font-variant-numeric:tabular-nums}}
h2{{margin:36px 0 14px;font-size:19px;font-weight:800;letter-spacing:-.025em}}
.note{{margin:0 0 22px;font-size:13px;color:var(--mute);max-width:66ch;line-height:1.7}}
/* 구별 표 */
.gu{{margin:0 0 30px}}
.gu h3{{display:flex;align-items:baseline;gap:10px;margin:0 0 9px;padding-bottom:8px;
  font-size:16px;font-weight:800;letter-spacing:-.02em;border-bottom:1px solid var(--line)}}
.gu h3 em{{font-style:normal;font-size:11.5px;font-weight:700;color:#fff;background:var(--brand);
  padding:2px 9px;border-radius:999px}}
.gu h3 i{{font-style:normal;margin-left:auto;font-size:12.5px;font-weight:700;color:var(--mute);
  font-variant-numeric:tabular-nums}}
.tw{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{width:100%;border-collapse:collapse;font-size:13.5px;min-width:640px}}
th{{text-align:left;font-size:11px;font-weight:800;color:var(--mute);padding:0 10px 7px;
  white-space:nowrap;letter-spacing:.01em}}
td{{padding:9px 10px;border-top:1px solid var(--line2);vertical-align:top}}
tbody tr:hover td{{background:var(--panel)}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.nm b{{display:block;font-weight:700;letter-spacing:-.01em}}
.sub{{display:block;margin-top:1px;font-size:11.5px;font-weight:500;color:var(--faint)}}
.strong{{font-weight:800;color:var(--sale);font-size:14.5px}}
.rng{{color:var(--ink2);font-size:12.5px}}
.none{{color:var(--faint);font-weight:500;font-size:12px}}
.gap{{font-weight:800;font-size:12.5px}}
.gap.up{{color:var(--up)}} .gap.flat{{color:var(--flat)}} .gap.na{{color:var(--faint)}}
/* 꼬리 */
footer{{margin-top:44px;padding-top:22px;border-top:1px solid var(--line)}}
footer h2{{margin-top:0}}
footer ul{{margin:0 0 18px;padding-left:18px}}
footer li{{font-size:13px;color:var(--ink2);line-height:1.85;margin-bottom:3px}}
footer b{{font-weight:700;color:var(--ink)}}
.sign{{font-size:12px;color:var(--faint);line-height:1.7}}
.sign b{{color:var(--brand);font-weight:800}}
@media (max-width:640px){{
  .wrap{{padding:0 15px 56px}} header{{padding-top:30px}}
  .kpi b{{font-size:25px}} table{{font-size:13px}}
  .band{{grid-template-columns:88px 1fr 44px;gap:9px}}
}}
</style>

<div class="wrap">
<header>
  <div class="brand"><b>콕집</b><span>부동산 뉴스레터</span></div>
  <h1>서울에서 <em>59㎡</em>를 <em>12억 이하</em>로,<br>500세대 넘는 단지 {len(rows)}곳</h1>
  <p class="lede">
    이른바 ‘국민평형 아래 한 칸’인 전용 59㎡(약 18평)는 신혼·1~2인 가구가 가장 많이 찾는 면적입니다.
    최근 6개월 서울 59㎡ 매매는 {BASE_N:,}건, 중앙값은 {eok(BASE_MED)}이었습니다.
    그중 <b>실거래 중앙값이 12억 이하이면서 500세대가 넘는 단지</b>만 추려 자치구별로 정리했습니다.
    세대수를 기준으로 삼은 이유는 단지가 클수록 거래가 꾸준해 시세를 믿을 수 있고, 팔 때도 덜 막히기 때문입니다.
  </p>
  <div class="meta">
    <i>기준일 {ASOF}</i><i>최근 6개월 매매 실거래</i><i>전용 58.0~60.5㎡</i>
    <i>500세대 이상</i><i>해제거래 제외</i>
  </div>
</header>

<div class="kpi">
  <div><b>{len(rows)}<small>개 단지</small></b><span>조건을 모두 채운 곳</span>
    <u>{len(gu_order)}개 자치구 · 합계 {hh_tot:,}세대</u></div>
  <div><b>{eok(cheapest['med'])}</b><span>가장 낮은 중앙값</span>
    <u>{cheapest['gu']} {cheapest['nm']} · {cheapest['hh']:,}세대</u></div>
  <div><b>{BASE_SHARE}<small>%</small></b><span>서울 59㎡ 중 12억 이하 비중</span>
    <u>{BASE_N:,}건 가운데 (건수 기준)</u></div>
  <div><b>{'+' if gap_med and gap_med > 0 else ''}{gap_med}<small>%</small></b><span>호가가 실거래보다</span>
    <u>매물이 있는 {n_ask}개 단지의 중앙값</u></div>
</div>

<div class="bands">
  <h2>가격대별로 보면</h2>
  {''.join(f'''<div class="band"><em>{lb}</em>
     <div class="bar b{i}" style="width:{max(3, round(n / max(1, max(x[1] for x in band_n)) * 100))}%"></div>
     <div class="v">{n}곳</div></div>''' for i, (lb, n) in enumerate(band_n))}
</div>

<h2>자치구별 단지</h2>
<p class="note">
  <b>실거래 중앙값</b>은 최근 6개월 그 단지 59㎡ 거래의 가운데 값입니다. 한두 건의 특이 거래에
  휘둘리지 않게 평균 대신 중앙값을 썼습니다. <b>호가差</b>는 현재 가장 싼 매물 호가가 그 중앙값보다
  얼마나 위인지입니다 — 숫자가 클수록 지금 사려면 최근 거래보다 더 얹어야 한다는 뜻입니다.
  자치구는 해당 단지가 많은 순입니다.
</p>
{''.join(sections)}

<footer>
  <h2>이 목록을 어떻게 읽어야 하나</h2>
  <ul>
    <li><b>전용 59㎡는 한 숫자가 아닙니다.</b> 단지마다 58.7·59.2·59.9㎡ 등으로 갈려 있어
        58.0~60.5㎡를 같은 타입으로 묶었습니다. 표의 면적은 그 단지 거래의 평균입니다.</li>
    <li><b>중앙값이 12억 이하라는 뜻이지, 모든 집이 12억 이하라는 뜻은 아닙니다.</b>
        같은 단지에서도 층·향·수리 상태에 따라 거래 범위가 넓습니다 — 그래서 최저·최고를 함께 실었습니다.</li>
    <li><b>거래가 적은 단지는 중앙값도 흔들립니다.</b> 거래 건수를 같이 보시고, 3건 이하인 곳은
        참고치로만 보시기 바랍니다.</li>
    <li><b>실거래는 신고까지 최대 30일이 걸립니다.</b> 최근 한 달치는 아직 다 들어오지 않았을 수 있습니다.</li>
    <li><b>해제(취소)된 거래는 뺐습니다.</b> 넣으면 없던 신고가가 시세처럼 섞입니다.</li>
    <li><b>호가는 지금 광고 중인 매물</b> 기준이라 실제 거래 가능 가격과 다를 수 있습니다.
        매물이 없는 단지는 ‘매물 없음’으로 뒀습니다.</li>
  </ul>
  <p class="sign">
    자료 · 국토교통부 아파트 매매 실거래가, 단지 정보 및 매물 호가<br>
    집계 · <b>콕집</b> koczip.com · 기준일 {ASOF}<br>
    이 자료는 정보 제공을 위한 것이며 특정 단지의 매수·매도를 권유하지 않습니다.
  </p>
</footer>
</div>
"""
OUT.write_text(html, encoding="utf-8")
print(f"{OUT} · 단지 {len(rows)} · 자치구 {len(gu_order)} · {len(html):,}바이트")
