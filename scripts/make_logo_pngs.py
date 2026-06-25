"""콕집 로고 PNG 생성 — PWA 아이콘 + apple-touch-icon.

집 모양 오각형 + 흰색 체크마크. Pillow 직접 그리기 (SVG 의존성 X).

Run:
  python scripts/make_logo_pngs.py
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

BRAND = (18, 104, 211, 255)   # #1268d3
WHITE = (255, 255, 255, 255)

OUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public"


def house_polygon(size: int, margin: float = 0.08) -> list[tuple[float, float]]:
    """오각형(집): 위 꼭짓점(지붕) + 양 옆 + 바닥 사각형."""
    s = size
    m = s * margin
    inner = s - 2 * m
    # 100×100 좌표계의 (50,10) (92,46) (92,92) (8,92) (8,46) 을 비례 변환.
    pts100 = [(50, 10), (92, 46), (92, 92), (8, 92), (8, 46)]
    return [(m + p[0] / 100 * inner, m + p[1] / 100 * inner) for p in pts100]


def check_polyline(size: int, margin: float = 0.08) -> list[tuple[float, float]]:
    s = size
    m = s * margin
    inner = s - 2 * m
    pts100 = [(28, 58), (44, 73), (74, 42)]
    return [(m + p[0] / 100 * inner, m + p[1] / 100 * inner) for p in pts100]


def draw_thick_line_round(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]],
                          color, width: int) -> None:
    """Round-cap + round-join 두꺼운 라인. 각 연결점·끝점에 원을 덧그려 처리."""
    r = width // 2
    for p1, p2 in zip(points, points[1:]):
        draw.line([p1, p2], fill=color, width=width)
    # 끝점/연결점 둥글게
    for x, y in points:
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=color)


def make_icon(size: int, maskable: bool = False) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if maskable:
        # maskable: 전체를 브랜드 컬러로 채우고 safe zone (안쪽 80%) 안에 흰 집 + 파란 체크
        draw.rectangle([(0, 0), (size, size)], fill=BRAND)
        inner_margin = 0.20  # safe zone 안쪽 80%
        # 안쪽에 흰 집
        house = [(p[0], p[1]) for p in house_polygon(size, inner_margin)]
        draw.polygon(house, fill=WHITE)
        # 파란 체크 (반전)
        check = check_polyline(size, inner_margin)
        line_w = max(2, int(size * 0.05))
        draw_thick_line_round(draw, check, BRAND, line_w)
    else:
        # 일반: 투명 배경에 브랜드 집 + 흰 체크
        house = house_polygon(size, margin=0.06)
        draw.polygon(house, fill=BRAND)
        check = check_polyline(size, margin=0.06)
        line_w = max(2, int(size * 0.07))
        draw_thick_line_round(draw, check, WHITE, line_w)

    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("icon-512-maskable.png", 512, True),
        ("apple-touch-icon.png", 180, False),
    ]
    for name, size, maskable in targets:
        img = make_icon(size, maskable=maskable)
        out = OUT_DIR / name
        img.save(out, "PNG")
        print(f"  wrote {out} ({size}×{size}{'  maskable' if maskable else ''})")


if __name__ == "__main__":
    main()
