# -*- coding: utf-8 -*-
"""생성 사진을 팝업 슬라이드용으로 자른다.

자르는 기준은 구도가 아니라 **글자**다. 이미지 모델은 한글을 못 쓴다 — 간판이나
메모지에 깨진 글자가 남으면 그 한 곳 때문에 사진 전체가 가짜로 보인다. 그래서
깨진 글자가 있는 쪽을 프레임 밖으로 밀어낸다.
"""
import sys
sys.path.append("/Users/hcode/Library/Python/3.9/lib/python/site-packages")
from PIL import Image

W, H = 1080, 720                                      # 3:2, 팝업 이미지 밴드용

# (파일, 가로 앵커 0~1, 세로 앵커 0~1, 확대율)  앵커는 '남길 중심'
JOBS = [
    ("05_store.png",       "x_store.jpg",   0.52, 0.50, 1.00),  # 간판 '연우외' 우상단 → 왼쪽으로
    ("06_hf_portrait_a.png","s3_rank.jpg",   0.60, 0.44, 1.34),  # 좌우 메모지 깨진 글자 잘라냄
    ("02_docs.png",        "s2_audit.jpg",   0.38, 0.55, 1.10),  # 우측 도장 라벨 글자 잘라냄
    ("01_agent.png",       "s1_diary.jpg",    0.46, 0.52, 1.06),
    ("04_consult.png",     "s4_req.jpg",     0.42, 0.74, 1.34),  # 상단 간판 글자 밀어냄
    ("03_desk.png",        "s5_assist.jpg",  0.33, 0.56, 1.34),  # 탁상달력 깨진 글자 왼쪽으로 밀어냄
]

for src, dst, ax, ay, zoom in JOBS:
    im = Image.open("img/" + src).convert("RGB")
    iw, ih = im.size
    # 목표 비율에 맞춘 최대 크롭 박스를 zoom 으로 좁힌 뒤 앵커 위치에 놓는다
    cw = min(iw, int(ih * W / H)) / zoom
    ch = cw * H / W
    if ch > ih:
        ch = ih / zoom
        cw = ch * W / H
    x = min(max(ax * iw - cw / 2, 0), iw - cw)
    y = min(max(ay * ih - ch / 2, 0), ih - ch)
    out = im.crop((int(x), int(y), int(x + cw), int(y + ch))).resize((W, H), Image.LANCZOS)
    out.save("img/" + dst, "JPEG", quality=84, optimize=True, progressive=True)
    print(f"{dst:16} {out.size}  ← {src} {iw}x{ih}")
