# -*- coding: utf-8 -*-
"""에스원 임대안내문 파서 시제품 — 추출 수율 실측용.

양식: 빌딩 1개 = 1쪽. 좌측 PROPERTY OVERVIEW(라벨 x~249 / 값 x~322),
우측 상단 SPACE AVAILABILITY(공실 층별), 우측 중단 RENT(임대조건), 하단 CONTACT POINT.
한글 PDF 라 어절 사이 공백이 사라진다("서울시중구세종대로73") — 숫자·단위는 멀쩡하므로
수치 추출에는 지장이 없고, 주소는 뒤에서 지오코더에 넣기 전에 따로 손본다.
"""
import json, os, re, sys
import fitz

OV_LABELS = ("주소", "교통", "연면적", "빌딩규모", "준공연도", "전용율", "전용률",
             "기준층면적", "엘리베이터", "주차사항", "특이사항")


def lines_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            t = "".join(s["text"] for s in l["spans"]).strip()
            if t:
                x0, y0, x1, _ = l["bbox"]
                out.append({"x": x0, "y": y0, "xc": (x0 + x1) / 2, "t": t})
    return sorted(out, key=lambda r: (r["y"], r["x"]))


def find(ls, txt):
    for r in ls:
        if r["t"].replace(" ", "").startswith(txt.replace(" ", "")):
            return r
    return None


def overview(ls):
    """라벨 열(x<300)과 값 열(300<=x<500)을 y 로 맞춘다. 값이 여러 줄이면 묶는다."""
    labs = [r for r in ls if r["x"] < 300 and r["t"].replace(" ", "") in
            [s.replace(" ", "") for s in OV_LABELS]]
    vals = [r for r in ls if 300 <= r["x"] < 500]
    if not labs:
        return {}
    labs.sort(key=lambda r: r["y"])
    # 라벨 y 는 값 블록의 '중앙'이다(주차사항처럼 값이 3줄이면 첫 값이 라벨보다 위에 있다).
    # 그래서 구간은 이웃 라벨과의 중점으로 끊는다. 라벨 y 를 시작점으로 삼으면 한 칸씩 밀린다.
    out = {}
    for i, lab in enumerate(labs):
        prev_y = labs[i - 1]["y"] if i else lab["y"] - 16
        next_y = labs[i + 1]["y"] if i + 1 < len(labs) else lab["y"] + 36
        lo = (prev_y + lab["y"]) / 2
        hi = (lab["y"] + next_y) / 2
        got = [v["t"] for v in sorted(vals, key=lambda r: r["y"]) if lo <= v["y"] < hi]
        if got:
            out[lab["t"].replace("전용율", "전용률")] = " ".join(got)
    return out


def table(ls, title, cols, y_stop):
    """제목 아래의 표를 읽는다. 헤더 x 중심에 가장 가까운 칸으로 배정."""
    h = find(ls, title)
    if not h:
        return []
    hdr = {}
    for c in cols:                      # 헤더 칸 위치 찾기
        for r in ls:
            if r["y"] > h["y"] - 2 and r["y"] < h["y"] + 30 and r["t"].replace(" ", "") == c:
                hdr[c] = r["xc"]
                break
    if len(hdr) < 2:
        return []
    hy = max(ls[i]["y"] for i in range(len(ls))
             if ls[i]["t"].replace(" ", "") in hdr and abs(ls[i]["y"] - h["y"]) < 30)
    body = [r for r in ls if hy + 4 < r["y"] < y_stop and r["x"] > min(hdr.values()) - 40]
    rows = {}
    for r in body:
        key = round(r["y"] / 6)
        col = min(hdr, key=lambda c: abs(hdr[c] - r["xc"]))
        rows.setdefault(key, {})[col] = r["t"]
    return [v for _k, v in sorted(rows.items()) if len(v) >= 2]


def parse_page(page, pno):
    ls = lines_of(page)
    if not find(ls, "PROPERTY OVERVIEW"):
        return None
    name = next((r["t"] for r in ls if r["x"] < 230 and r["y"] < 110), None)
    ov = overview(ls)
    cp = find(ls, "CONTACT POINT")
    rent_h = find(ls, "RENT")
    avail = table(ls, "SPACE AVAILABILITY", ("층", "임대면적", "전용면적", "입주시기"),
                  rent_h["y"] - 6 if rent_h else 240)
    rent = table(ls, "RENT", ("층", "보증금", "임대료", "관리비"),
                 cp["y"] - 6 if cp else 340)
    return {"page": pno, "name": name, "overview": ov, "avail": avail, "rent": rent}


def main(paths):
    allout = []
    print(f"{'파일':<34}{'쪽':>5}{'빌딩':>6}{'이름':>6}{'주소':>6}{'연면적':>7}"
          f"{'준공':>6}{'공실행':>7}{'임대료행':>8}")
    print("-" * 86)
    for p in paths:
        d = fitz.open(p)
        npages = d.page_count
        recs = [r for r in (parse_page(d.load_page(i), i + 1)
                            for i in range(npages)) if r]
        d.close()
        nm = sum(1 for r in recs if r["name"])
        ad = sum(1 for r in recs if r["overview"].get("주소"))
        ar = sum(1 for r in recs if r["overview"].get("연면적"))
        yr = sum(1 for r in recs if r["overview"].get("준공연도"))
        av = sum(len(r["avail"]) for r in recs)
        rt = sum(len(r["rent"]) for r in recs)
        print(f"{os.path.basename(p)[:33]:<34}{npages:>5}{len(recs):>6}"
              f"{nm:>6}{ad:>6}{ar:>7}{yr:>6}{av:>7}{rt:>8}")
        allout.append({"src": os.path.basename(p), "bld": recs})
    tot_b = sum(len(a["bld"]) for a in allout)
    tot_a = sum(len(r["avail"]) for a in allout for r in a["bld"])
    tot_r = sum(len(r["rent"]) for a in allout for r in a["bld"])
    print("-" * 86)
    print(f"빌딩페이지 {tot_b} · 공실행 {tot_a} · 임대료행 {tot_r}")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s1_parsed.json")
    with open(out, "w") as f:
        json.dump(allout, f, ensure_ascii=False)
    print("저장:", out)


if __name__ == "__main__":
    main(sys.argv[1:])
