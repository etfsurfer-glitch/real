"""Smoke test for admin suggestions tab."""
from __future__ import annotations
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshots" / "admin_smoke"
SNAP.mkdir(parents=True, exist_ok=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = ctx.new_page()
        page.set_default_timeout(15000)

        print(f"[1] GET {BASE}/")
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.wait_for_selector("table tbody tr", timeout=15000)

        # Click suggestions tab
        print("\n[2] click '의심 매칭' tab")
        page.locator("#tab-sug").click()
        page.wait_for_selector("#sug-tbody tr", timeout=15000)
        rows = page.locator("#sug-tbody tr").count()
        chips = page.locator("#sug-chips .chip").all_text_contents()
        badge = page.locator("#sug-badge").text_content()
        print(f"    badge: {badge}")
        print(f"    chips: {chips}")
        print(f"    rows visible: {rows}")
        # First 3 rows
        for i in range(min(3, rows)):
            cells = page.locator("#sug-tbody tr").nth(i).locator("td").all_text_contents()
            print(f"    row{i}: {cells[:6]}")

        page.screenshot(path=str(SNAP / "04_suggestions.png"), full_page=True)
        ctx.close()
        browser.close()

    print(f"\n[ok] smoke passed; screenshot at {SNAP}/04_suggestions.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
