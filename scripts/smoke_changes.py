"""Smoke test for the /changes page."""
from __future__ import annotations
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://real-6mp.pages.dev"
SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshots" / "frontend_smoke"
SNAP.mkdir(parents=True, exist_ok=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(20000)

        url = BASE + "/changes"
        print(f"[1] GET {url}")
        console: list[str] = []
        page.on("console", lambda m: console.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console.append(f"[pageerror] {e}"))
        page.goto(url, wait_until="networkidle")

        page.wait_for_selector("table tbody tr", timeout=20000)
        rows = page.locator("table tbody tr").count()
        h2 = page.locator("h2").first.text_content()
        chips = page.locator("button").all_text_contents()
        print(f"    h2: {h2}")
        print(f"    chips: {chips}")
        print(f"    rows: {rows}")

        # Sample first 3 rows
        for i in range(min(3, rows)):
            cells = page.locator(f"table tbody tr").nth(i).locator("td").all_text_contents()
            print(f"    row{i}: {cells}")

        page.screenshot(path=str(SNAP / "03_changes.png"), full_page=True)
        ctx.close()
        browser.close()

    print(f"\n[ok] smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
