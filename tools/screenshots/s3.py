import asyncio, re, aiohttp, ha
from playwright.async_api import async_playwright
from browser import open_page, shot, BASE, OUT
from s2 import dialog_shot, submit

async def registry():
    async with aiohttp.ClientSession() as s:
        a = await ha.token(s)
        async with ha.WS(s, a) as w:
            return await w.call(type="config/device_registry/list")

async def main():
    devices = {d["name"]: d["id"] for d in await registry()}
    async with async_playwright() as p:
        b, page = await open_page(p, 1280, 1500)
        integ = BASE + "/config/integrations/integration/pm_heizung"
        # Zentrale Schritt 1 und 5 erneut (korrigierte Übersetzung)
        await page.goto(integ); await page.wait_for_timeout(3000)
        await page.get_by_label("Konfigurieren").first.click()
        for name in ["zentrale_1_personen", "zentrale_2_abwesenheit", "zentrale_3_sperre", "zentrale_4_luft", "zentrale_5_beratung"]:
            await dialog_shot(page, name); await submit(page)
        await page.wait_for_timeout(1500)
        # Raum bearbeiten (Wohnzimmer = letzter Raum in der Liste)
        await page.goto(integ); await page.wait_for_timeout(3000)
        await page.get_by_label("Raum bearbeiten").nth(3).click()
        for name in ["raum_1_geraete", "raum_2_temperaturen", "raum_3_verhalten", "raum_4_luft"]:
            await dialog_shot(page, name); await submit(page)
        await page.wait_for_timeout(1500)
        # Detaildialog des Raumthermostats
        await page.set_viewport_size({"width": 1280, "height": 1100})
        await page.goto(BASE + "/lovelace/klima?more-info-entity-id=climate.pm_wohnzimmer")
        await dialog_shot(page, "thermostat_dialog")
        await page.keyboard.press("Escape")
        # Geräteseiten
        await page.set_viewport_size({"width": 1280, "height": 1000})
        await page.goto(BASE + f"/config/devices/device/{devices['Wohnzimmer Heizung']}")
        await shot(page, "geraet_heizung", wait=3000)
        await page.goto(BASE + f"/config/devices/device/{devices['Wohnzimmer Luft']}")
        await shot(page, "geraet_luft", wait=3000)
        await page.goto(BASE + f"/config/devices/device/{devices['PM Klima']}")
        await shot(page, "geraet_zentrale", wait=3000)
        await b.close()
asyncio.run(main())
