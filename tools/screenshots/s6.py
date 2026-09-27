import asyncio, aiohttp, ha, sys, os
from playwright.async_api import async_playwright
from browser import BASE, OUT
STEPS = lambda lang: [
    {"personen": ["person.anna", "person.ben"], "anwesenheit_entitaeten": ["input_boolean.anna_zuhause", "input_boolean.ben_zuhause"], "sprache": lang},
    {"absenkung": 3, "mindesttemperatur": 16, "fern_absenkung": 2, "vorheizstufe": "balance", "eigener_nahradius": 3, "eigener_mittelradius": 8, "eigener_fernradius": 20, "annaeherung_erforderlich": True, "verlassen_verzoegerung": 5},
    {"aussentemperatur_sensor": "sensor.aussentemperatur", "aussentemperatur_grenze": 17, "freigabe_entitaet": "input_boolean.heizperiode", "sperre_wirkung": "zeitplan", "sperre_mindesthaltezeit": 15},
    {"luft_aussenfeuchte": "sensor.aussenluftfeuchte"},
    {"beratung_push": True, "beratung_alexa": False, "beratung_panel": False, "beratung_push_zuordnung": "person.anna: notify.mobile_app_annas_telefon", "beratung_ruhe_beginn": "22:00:00", "beratung_ruhe_ende": "07:00:00", "beratung_abstand": 120},
]
async def set_lang(lang):
    async with aiohttp.ClientSession() as s:
        h = {"Authorization": "Bearer " + await ha.token(s)}
        entry = (await (await s.get(BASE + "/api/config/config_entries/entry?domain=pm_heizung", headers=h)).json())[0]["entry_id"]
        f = await (await s.post(BASE + "/api/config/config_entries/options/flow", headers=h, json={"handler": entry})).json()
        for d in STEPS(lang):
            f = await (await s.post(BASE + f"/api/config/config_entries/options/flow/{f['flow_id']}", headers=h, json=d)).json()
        print(lang, f.get("type"))
async def main():
    await set_lang("en"); await asyncio.sleep(15)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, locale="en-US", timezone_id="Europe/Berlin")
        await ctx.add_init_script("localStorage.setItem('selectedLanguage', JSON.stringify('en'))")
        page = await ctx.new_page()
        await page.goto(BASE + "/"); await page.wait_for_selector("input[name=username]")
        await page.fill("input[name=username]", "anna"); await page.fill("input[name=password]", "demo-demo")
        await page.keyboard.press("Enter"); await page.wait_for_timeout(6000)
        await page.goto(BASE + "/lovelace/klima"); await page.wait_for_timeout(5000)
        await page.screenshot(path=f"{OUT}/dashboard_en.png")
        await b.close()
    await set_lang("auto")
asyncio.run(main())
