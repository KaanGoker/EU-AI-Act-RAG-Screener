"""Take the README screenshots from a running screener.

    python tools/screenshots.py --base-url http://127.0.0.1:7860 --out assets

Writes four files to --out:
- screenshot-result.png   result of a screening, light theme, 1440x900
- screenshot-reader.png   the reader beside the result, a quote highlighted, light theme, 1440x900
- screenshot-mobile.png   result on a phone, light theme, 390x844
- screenshot-dark.png     result, dark theme, 1440x900

Needs Playwright and its Chromium: pip install -r requirements-dev.txt, then
python -m playwright install chromium. Every run makes two screenings, so it counts twice
against the server's rate limit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DEFAULT_DESCRIPTION = (
    "We are a software company in Ghent and sell a cloud tool to HR departments across the EU. "
    "The tool reads incoming CVs and cover letters, extracts skills and experience with a language model, "
    "and ranks every applicant against the job ad with a score from 0 to 100. "
    "Recruiters see the ranked list and usually only open the top 20 applications. "
    "Applicants below a score of 40 get an automatic rejection mail."
)

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}


def open_page(browser, base_url: str, viewport: dict, theme: str, mobile: bool = False) -> Page:
    context = browser.new_context(
        viewport=viewport,
        device_scale_factor=2 if mobile else 1,
        is_mobile=mobile,
        has_touch=mobile,
        color_scheme=theme,
    )
    # The page reads the theme from localStorage before the first paint.
    context.add_init_script(f"try {{ localStorage.setItem('screener-theme', '{theme}'); }} catch (e) {{}}")
    page = context.new_page()
    page.goto(base_url, wait_until="networkidle")
    return page


def accept_terms(page: Page) -> None:
    page.wait_for_selector("#terms[open]", timeout=15_000)
    page.click("#terms-accept")
    page.wait_for_function("() => !document.getElementById('terms').open")


def screen(page: Page, description: str, timeout_s: float) -> None:
    page.fill("#desc", description)
    page.check("input[name=role][value=provider]")
    page.click("#screen-btn")
    page.wait_for_selector("#result:not([hidden]) .rsec", timeout=timeout_s * 1000)
    # let fonts and the entry animation settle
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(800)


def close_panel(page: Page) -> None:
    if page.evaluate("() => document.documentElement.classList.contains('aside-open')"):
        page.locator("#aside-panel [data-close]").first.click()
        page.wait_for_function("() => !document.documentElement.classList.contains('aside-open')")
        page.wait_for_timeout(300)


def show_result_top(page: Page) -> None:
    page.evaluate(
        "() => { const r = document.getElementById('result');"
        " const head = document.querySelector('.masthead');"
        " const off = head ? head.getBoundingClientRect().height : 0;"
        " window.scrollTo(0, r.getBoundingClientRect().top + window.scrollY - off - 16); }"
    )
    page.wait_for_timeout(300)


def open_quote(page: Page) -> None:
    quote = page.locator("#result .quote:not(.is-unverified)").first
    if quote.count() == 0:
        quote = page.locator("#result .quote").first
    quote.scroll_into_view_if_needed()
    quote.click()
    page.wait_for_function("() => document.documentElement.classList.contains('aside-open')")
    page.wait_for_selector("#reader-body mark", timeout=10_000)
    page.locator("#reader-body mark").first.scroll_into_view_if_needed()
    page.wait_for_timeout(600)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default="http://127.0.0.1:7860")
    ap.add_argument("--out", default="assets", help="folder for the PNG files")
    ap.add_argument("--description", default=DEFAULT_DESCRIPTION, help="the system description to screen")
    ap.add_argument("--timeout", type=float, default=150, help="seconds to wait for a result")
    ap.add_argument("--headed", action="store_true", help="show the browser")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/") + "/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        try:
            page = open_page(browser, base, DESKTOP, "light")
            accept_terms(page)
            screen(page, args.description, args.timeout)
            close_panel(page)
            show_result_top(page)
            page.screenshot(path=str(out / "screenshot-result.png"))
            print("wrote", out / "screenshot-result.png")

            open_quote(page)
            page.screenshot(path=str(out / "screenshot-reader.png"))
            print("wrote", out / "screenshot-reader.png")

            # Dark theme on the same result, switched with the page's own button.
            close_panel(page)
            page.click("#theme-toggle")
            page.wait_for_function("() => document.documentElement.getAttribute('data-theme') === 'dark'")
            page.wait_for_timeout(400)
            show_result_top(page)
            page.screenshot(path=str(out / "screenshot-dark.png"))
            print("wrote", out / "screenshot-dark.png")
            page.context.close()

            phone = open_page(browser, base, MOBILE, "light", mobile=True)
            accept_terms(phone)
            screen(phone, args.description, args.timeout)
            show_result_top(phone)
            phone.screenshot(path=str(out / "screenshot-mobile.png"))
            print("wrote", out / "screenshot-mobile.png")
            phone.context.close()
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
