import asyncio
from playwright.async_api import async_playwright
from browser import open_page, shot, BASE
async def main():
    async with async_playwright() as p:
        b, page = await open_page(p, 1440, 900)
        await page.goto(BASE + "/lovelace/klima"); await shot(page, "dashboard", wait=4000)
        await b.close()
asyncio.run(main())
