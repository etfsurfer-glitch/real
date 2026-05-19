"""Smoke-test the admin UI."""
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
        console: list[str] = []
        failed: list[str] = []
        page.on("console", lambda m: console.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console.append(f"[pageerror] {e}"))
        page.on("requestfailed", lambda r: failed.append(
            f"{r.method} {r.url} -> {r.failure}"))
        page.on("response", lambda r: print(f"    HTTP {r.status} {r.url}") if "/api/" in r.url else None)
        page.goto(BASE + "/", wait_until="domcontentloaded")
        try:
            page.wait_for_selector("table tbody tr", timeout=15000)
        except Exception as e:  # noqa: BLE001
            print(f"\n    [TIMEOUT] {e}")
            print(f"    url: {page.url}")
            tbody_html = page.locator("tbody").inner_html()[:300]
            print(f"    tbody html: {tbody_html!r}")
            stats_text = page.locator("#stats").text_content()
            print(f"    stats text: {stats_text!r}")
            print(f"    console msgs:")
            for m in console[-20:]:
                print(f"      {m}")
            print(f"    failed requests:")
            for r in failed:
                print(f"      {r}")
            page.screenshot(path=str(SNAP / "00_fail.png"), full_page=True)
            raise

        # Stats banner
        stats = page.locator("#stats").text_content()
        print(f"    stats: {stats}")

        # Method chips
        chips = page.locator(".chip").all_text_contents()
        print(f"    chips ({len(chips)}): {chips[:3]} ...")

        rows = page.locator("table tbody tr").count()
        print(f"    rows: {rows}")

        # Click unmatched chip
        print("\n[2] click unmatched chip")
        for chip in page.locator(".chip").all():
            t = chip.text_content() or ""
            if "unmatched" in t:
                chip.click()
                break
        page.wait_for_function(
            "() => document.querySelector('table tbody tr')?.dataset.id !== undefined"
        )
        page.wait_for_timeout(400)
        rows = page.locator("table tbody tr").count()
        first_apt = page.locator("table tbody tr").first.locator("td").nth(1).text_content()
        print(f"    unmatched rows visible: {rows}  first apt: {first_apt}")
        page.screenshot(path=str(SNAP / "01_unmatched.png"), full_page=True)

        # Click first row -> detail
        print("\n[3] click first row")
        page.locator("table tbody tr").first.click()
        page.wait_for_selector("#detail .kv")
        kv_keys = page.locator("#detail .kv .k").all_text_contents()
        candidates = page.locator("#detail .candidate").count()
        print(f"    detail kv keys ({len(kv_keys)}): {kv_keys[:5]}")
        print(f"    candidates shown: {candidates}")
        page.screenshot(path=str(SNAP / "02_detail.png"), full_page=True)

        # Search test
        print("\n[4] search '래미안'")
        page.locator("#search").fill("래미안")
        page.locator("#search").press("Enter")
        page.wait_for_timeout(500)
        rows = page.locator("table tbody tr").count()
        first_apt = page.locator("table tbody tr").first.locator("td").nth(1).text_content() if rows else None
        print(f"    rows: {rows}  first: {first_apt}")
        page.screenshot(path=str(SNAP / "03_search.png"), full_page=True)

        ctx.close()
        browser.close()

    print("\n[ok] admin smoke passed; screenshots in", SNAP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
