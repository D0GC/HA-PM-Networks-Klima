"""Playwright-Hilfen: angemeldete Seite der Demo-Instanz."""
import asyncio, json, os
from playwright.async_api import async_playwright
BASE = "http://127.0.0.1:8123"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "bilder")

async def open_page(p, width=1280, height=820, dark=False):
    browser = await p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)
    ctx = await browser.new_context(viewport={"width": width, "height": height},
                                    device_scale_factor=2, locale="de-DE",
                                    color_scheme="dark" if dark else "light",
                                    timezone_id="Europe/Berlin")
    page = await ctx.new_page()
    await page.goto(BASE + "/")
    await page.wait_for_selector("input[name=username]", timeout=30000)
    await page.fill("input[name=username]", "anna")
    await page.fill("input[name=password]", "demo-demo")
    await page.keyboard.press("Enter")
    await page.wait_for_function("() => !location.search.includes(\"auth_callback\") && !!document.querySelector(\"home-assistant\")", timeout=30000)
    await page.wait_for_timeout(4000)
    await page.wait_for_timeout(2500)
    return browser, page

async def shot(page, name, clip=None, wait=1500):
    await page.wait_for_timeout(wait)
    kw = {"path": f"{OUT}/{name}.png"}
    if clip: kw["clip"] = clip
    await page.screenshot(**kw)
    print("shot", name)
