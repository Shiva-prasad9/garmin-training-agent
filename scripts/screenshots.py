"""Screenshot every dashboard view (dark, light, phone width) for a visual review. Also reports browser console errors.

    .venv/bin/python scripts/serve.py --port 8765        # in one terminal
    .venv/bin/python scripts/screenshots.py data/screenshots

Needs the dev tools once: .venv/bin/pip install -r requirements-dev.txt and .venv/bin/playwright install chromium
Usage: screenshots.py <outdir> [base_url]
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8765"
errors = []

with sync_playwright() as p:
    b = p.chromium.launch()
    for theme, w, h, tag in [("dark", 1440, 900, "desktop-dark"), ("light", 1440, 900, "desktop-light"), ("dark", 390, 844, "mobile-dark")]:
        ctx = b.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
        ctx.add_init_script(f"try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}")
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(f"[{tag}] console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errors.append(f"[{tag}] pageerror: {e}"))
        page.goto(base + "/#/overview"); page.wait_for_selector(".kpis, .empty, .panel", timeout=15000); page.wait_for_timeout(1200)
        page.screenshot(path=str(out / f"{tag}-overview.png"), full_page=True)
        if tag != "mobile-dark":
            page.goto(base + "/#/activities/all"); page.wait_for_selector(".month, .empty", timeout=15000); page.wait_for_timeout(1000)
            page.screenshot(path=str(out / f"{tag}-activities.png"), full_page=True)
            row = page.locator(".act.clickable").first
            if row.count():
                row.click(); page.wait_for_selector(".dv-tiles, .dv-body .empty", timeout=15000); page.wait_for_timeout(1500)
                page.screenshot(path=str(out / f"{tag}-detail.png"))
                page.keyboard.press("Escape")
            page.goto(base + "/#/guide"); page.wait_for_timeout(600)
            page.screenshot(path=str(out / f"{tag}-guide.png"))
        ctx.close()
    b.close()
print("\n".join(errors) or "no console errors")
