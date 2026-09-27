import asyncio, aiohttp, ha
from playwright.async_api import async_playwright
from browser import open_page, shot, BASE, OUT
from s2 import dialog_shot, submit

async def ws(**msg):
    async with aiohttp.ClientSession() as s:
        a = await ha.token(s)
        async with ha.WS(s, a) as w:
            return await w.call(**msg)

async def main():
    async with async_playwright() as p:
        b, page = await open_page(p, 1280, 2300)
        integ = BASE + "/config/integrations/integration/pm_heizung"
        await page.goto(integ); await page.wait_for_timeout(3000)
        await page.get_by_label("Raum bearbeiten").nth(3).click()
        for name in ["raum_1_geraete", "raum_2_temperaturen", "raum_3_verhalten", "raum_4_luft"]:
            await dialog_shot(page, name); await submit(page)
        await page.wait_for_timeout(1500)
        # Raum hinzufügen – leeres Formular
        await page.goto(integ); await page.wait_for_timeout(3000)
        await page.set_viewport_size({"width": 1280, "height": 1300})
        await page.get_by_role("button", name="Raum hinzufügen").click()
        await dialog_shot(page, "raum_neu")
        await page.keyboard.press("Escape")
        # Attribute im Detaildialog
        await page.set_viewport_size({"width": 1280, "height": 2000})
        await page.goto(BASE + "/lovelace/klima?more-info-entity-id=climate.pm_wohnzimmer")
        await page.wait_for_timeout(2500)
        await page.get_by_text("Attribute", exact=True).click()
        await page.wait_for_timeout(1200)
        await page.get_by_text("Attribute", exact=True).scroll_into_view_if_needed()
        await dialog_shot(page, "thermostat_attribute")
        await b.close()
asyncio.run(main())
