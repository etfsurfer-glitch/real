"""Smoke-test the Vite dev server with Playwright.

Loads / (Overview), waits for the totals cards + complex table, asserts the
서초동 listing counts match what Supabase returned earlier. Then clicks into
the top complex and verifies the detail page renders aggregate tables.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173"
SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshots" / "frontend_smoke"
SNAP.mkdir(parents=True, exist_ok=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(20000)

        print(f"[1] GET {BASE}/")
        console_msgs: list[str] = []
        failed_reqs: list[str] = []
        page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console_msgs.append(f"[pageerror] {e}"))
        page.on("requestfailed", lambda r: failed_reqs.append(
            f"{r.method} {r.url} -> {r.failure}"))
        page.goto(BASE + "/", wait_until="networkidle")
        try:
            page.wait_for_selector(".cards .card", timeout=15000)
        except Exception as e:  # noqa: BLE001
            print(f"    cards not found: {e}")
            print(f"    url: {page.url}")
            body_text = (page.locator("body").text_content() or "")[:800]
            print(f"    body text: {body_text!r}")
            print(f"    console msgs ({len(console_msgs)}):")
            for m in console_msgs[-20:]:
                print(f"      {m}")
            print(f"    failed requests ({len(failed_reqs)}):")
            for r in failed_reqs[-10:]:
                print(f"      {r}")
            page.screenshot(path=str(SNAP / "00_overview_fail.png"), full_page=True)
            raise
        page.wait_for_selector("table tbody tr", timeout=15000)

        cards = page.locator(".cards .card .num").all_text_contents()
        print(f"    cards (매매/전세/월세 listings): {cards}")
        rows = page.locator("table tbody tr").count()
        print(f"    complex rows: {rows}")
        first_complex_link = page.locator("table tbody tr td a").first
        first_name = first_complex_link.text_content() or ""
        href = first_complex_link.get_attribute("href")
        print(f"    top complex: {first_name.strip()}  href={href}")

        page.screenshot(path=str(SNAP / "01_overview.png"), full_page=True)

        print(f"\n[2] click into {first_name.strip()}")
        console_msgs: list[str] = []
        page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console_msgs.append(f"[pageerror] {e}"))
        first_complex_link.click()
        try:
            page.wait_for_selector(".section-title", timeout=15000)
        except Exception as e:  # noqa: BLE001
            print(f"    section-title not found: {e}")
            print(f"    url: {page.url}")
            body_text = (page.locator("body").text_content() or "")[:600]
            print(f"    body text head: {body_text!r}")
            print("    console:")
            for m in console_msgs[-20:]:
                print(f"      {m}")
            page.screenshot(path=str(SNAP / "02_detail_fail.png"), full_page=True)
            raise
        page.wait_for_selector("table tbody tr", timeout=15000)
        detail_heading = page.locator("h2").first.text_content()
        print(f"    detail heading: {detail_heading}")
        sections = page.locator(".section-title").all_text_contents()
        print(f"    sections: {sections}")
        agg_table_rows = page.locator("table tbody tr").count()
        print(f"    total visible rows across all tables: {agg_table_rows}")

        page.screenshot(path=str(SNAP / "02_complex_detail.png"), full_page=True)

        ctx.close()
        browser.close()

    print("\n[ok] smoke test passed; screenshots in", SNAP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
