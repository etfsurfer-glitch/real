"""Quick sanity check: read counts and a few rows back from Supabase."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector import supabase_uploader  # noqa: E402


def main() -> int:
    supa = supabase_uploader.get_client()

    print("=== table counts ===")
    for tbl in ("regions", "complexes", "listings_current",
                "complex_daily_agg", "region_daily_agg"):
        r = supa.table(tbl).select("*", count="exact", head=True).execute()
        print(f"  {tbl:<22} rows={r.count}")

    print("\n=== region_daily_agg ===")
    label = {"A1": "매매", "B1": "전세", "B2": "월세"}
    r = supa.table("region_daily_agg").select("*").execute()
    for row in r.data:
        nm = label.get(row["trade_type"], row["trade_type"])
        print(f"  {row['snapshot_date']} cortar={row['cortar_no']} "
              f"{nm}({row['trade_type']}): "
              f"listings={row['listing_count']} complexes={row['complex_count']}")

    print("\n=== top 5 단지 by listing count ===")
    r = supa.table("complex_daily_agg").select(
        "complex_no, listing_count, trade_type, area_name"
    ).order("listing_count", desc=True).limit(5).execute()
    for row in r.data:
        cn = supa.table("complexes").select("complex_name").eq(
            "complex_no", row["complex_no"]
        ).execute()
        name = cn.data[0]["complex_name"] if cn.data else "?"
        nm = label.get(row["trade_type"], row["trade_type"])
        print(f"  {row['complex_no']:<8} {name:<25} "
              f"{row['area_name']:<6} {nm}: {row['listing_count']}")

    print("\n=== 가격 sanity (서초 푸르지오 써밋 매매 sample) ===")
    r = supa.table("listings_current").select(
        "article_no, area_name, floor_info, deal_or_warrant_price_text, deal_or_warrant_price"
    ).eq("complex_no", "109119").eq("trade_type", "A1").limit(5).execute()
    for row in r.data:
        p = row["deal_or_warrant_price"]
        print(f"  {row['article_no']} {row['area_name']:<6} {row['floor_info']:<6} "
              f"{row['deal_or_warrant_price_text']:<12} -> {p:>15,}원" if p
              else f"  {row['article_no']} (no price)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
