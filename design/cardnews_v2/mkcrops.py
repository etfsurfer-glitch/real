# -*- coding: utf-8 -*-
"""카드뉴스 v2 개선안 PDF 에 넣을 근거 이미지(크롭·합성)를 만든다.
손으로 그리지 않는다 — 실제 출력물 PNG 를 잘라 쓴다."""
from PIL import Image, ImageDraw
from pathlib import Path

D = Path(__file__).resolve().parent / "cards"
O = Path(__file__).resolve().parent / "ev"
O.mkdir(exist_ok=True)

jj = Image.open(D / "261013_0816.png").convert("RGB")   # 무순위 줍줍
ca = Image.open(D / "261008_1023.png").convert("RGB")   # 청약 일정
nw = Image.open(D / "261012_1305.png").convert("RGB")   # 뉴스
mk = Image.open(D / "261006_0904.png").convert("RGB")   # 오늘의 시장

# ① 인스타 프로필 격자(1:1 중앙 크롭)에서 잘려 나가는 영역
im = jj.copy(); dr = ImageDraw.Draw(im, "RGBA")
dr.rectangle([0, 0, 1080, 135], fill=(225, 29, 72, 110))
dr.rectangle([0, 1215, 1080, 1350], fill=(225, 29, 72, 110))
im.save(O / "ev_crop.png")
jj.crop((0, 1150, 1080, 1350)).save(O / "ev_brandbar.png")

# ② 워터마크가 내용 위에 얹히는 자리
jj.crop((40, 420, 560, 580)).resize((1040, 320)).save(O / "ev_wm.png")

# ③ 히어로 사진 띠 — 1080×330 에 실제로 담긴 것
jj.crop((0, 0, 1080, 330)).save(O / "ev_hero.png")

# ④ 같은 뼈대 두 장 — 청약 vs 줍줍
sb = Image.new("RGB", (1080, 700), "white")
sb.paste(jj.crop((0, 0, 1080, 700)).resize((535, 347)), (0, 0))
sb.paste(ca.crop((0, 0, 1080, 700)).resize((535, 347)), (545, 0))
sb.paste(jj.crop((0, 700, 1080, 1350)).resize((535, 322)), (0, 357))
sb.paste(ca.crop((0, 700, 1080, 1350)).resize((535, 322)), (545, 357))
sb.save(O / "ev_same.png")

# ⑤ 같은 뜻인데 반대 색 — 줍줍 분양가(빨강) vs 청약 분양가(파랑)
cc = Image.new("RGB", (1080, 240), "white")
cc.paste(jj.crop((40, 440, 540, 560)).resize((530, 127)), (0, 5))
cc.paste(ca.crop((40, 440, 540, 560)).resize((530, 127)), (545, 5))
cc.paste(jj.crop((540, 700, 1040, 820)).resize((530, 127)), (0, 140))
cc.paste(ca.crop((540, 440, 1040, 560)).resize((530, 127)), (545, 140))
cc.save(O / "ev_color.png")

# ⑥ 뉴스 — 썸네일이 있는 줄과 없는 줄
nw.crop((30, 290, 1050, 980)).save(O / "ev_news.png")

# ⑦ 격자 6칸 — 1위와 6위가 같은 무게
jj.crop((30, 330, 1050, 1120)).save(O / "ev_flat.png")

# ⑧ 오늘의 시장 — 숫자 스케일
mk.crop((30, 290, 1050, 760)).save(O / "ev_duo.png")

for p in sorted(O.iterdir()):
    print(p.name, Image.open(p).size)
