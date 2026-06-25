"""매물 있는 단지의 검색 sitemap 생성 → frontend/public/sitemap-complexes.xml
사용: python scripts/build_complex_sitemap.py [YYYY-MM-DD]
"""
import sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "naverreal.sqlite"
OUT = ROOT / "frontend" / "public" / "sitemap-complexes.xml"
LASTMOD = sys.argv[1] if len(sys.argv) > 1 else "2026-06-16"
BASE = "https://koczip.com/complex/"

c = sqlite3.connect(DB)
rows = [r[0] for r in c.execute(
    "SELECT DISTINCT complex_no FROM listings_current WHERE complex_no IS NOT NULL")]
rows.sort()
parts = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for no in rows:
    parts.append(f"<url><loc>{BASE}{no}</loc><lastmod>{LASTMOD}</lastmod>"
                 f"<changefreq>weekly</changefreq><priority>0.6</priority></url>")
parts.append("</urlset>")
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"{OUT.name}: {len(rows)} complexes, {OUT.stat().st_size//1024} KB")
