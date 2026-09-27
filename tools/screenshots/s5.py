import asyncio, aiohttp, ha, json
from playwright.async_api import async_playwright
from browser import open_page, shot, BASE

async def main():
    async with aiohttp.ClientSession() as s:
        a = await ha.token(s); h = {"Authorization": "Bearer " + a}
        entry = (await (await s.get(BASE + "/api/config/config_entries/entry?domain=pm_heizung", headers=h)).json())[0]["entry_id"]
        f = await (await s.post(BASE + "/api/config/config_entries/subentries/flow", headers=h, json={"handler": [entry, "raum"]})).json()
        fid = f["flow_id"]
        for d in ({"name": "Gästezimmer", "klimageraete": ["climate.thermostat_gaestezimmer"], "zeitplan_attribut": "temperatur"},
                  {"komforttemperatur": 20, "ecotemperatur": 17, "frostschutztemperatur": 7, "min_temperatur": 5, "max_temperatur": 25},
                  {"overlay_modus": "naechster_block", "overlay_minuten": 60, "boost_minuten": 30, "fenster_verzoegerung_offen": 30, "fenster_verzoegerung_zu": 10, "fenster_aktion": "frostschutz", "aus_mit_frostschutz": False, "externe_aenderung_uebernehmen": True, "extern_aus_als_fenster": False},
                  {"nassraum": False, "frsi": 0.75, "nacht_beginn": "22:00:00", "nacht_ende": "07:00:00", "luftreiniger_pause": 60, "luftreiniger_haltezeit": 10}):
            f = await (await s.post(BASE + f"/api/config/config_entries/subentries/flow/{fid}", headers=h, json=d)).json()
        print(f.get("type"))
        await asyncio.sleep(8)
        # Abhängigkeiten als Beispielantwort sichern
        r = await s.post(BASE + "/api/services/pm_heizung/abhaengigkeiten?return_response", headers=h, json={})
        json.dump(await r.json(), open("abhaengigkeiten.json", "w"), ensure_ascii=False, indent=2)
        st = await (await s.get(BASE + "/api/states/climate.pm_wohnzimmer", headers=h)).json()
        json.dump(st["attributes"], open("attribute.json", "w"), ensure_ascii=False, indent=2)
    async with async_playwright() as p:
        b, page = await open_page(p, 1280, 800)
        await page.goto(BASE + "/config/repairs"); await shot(page, "reparatur", wait=3000)
        await page.get_by_text("Thermostat für Gästezimmer nicht gefunden").click()
        await page.wait_for_timeout(2000)
        from s2 import dialog_shot
        await dialog_shot(page, "reparatur_dialog")
        await b.close()
    async with aiohttp.ClientSession() as s:
        a = await ha.token(s)
        async with ha.WS(s, a) as w:
            subs = await w.call(type="config_entries/subentries/list", entry_id=entry)
            for sub in subs:
                if sub["title"] == "Gästezimmer":
                    await w.call(type="config_entries/subentries/delete", entry_id=entry, subentry_id=sub["subentry_id"])
                    print("deleted")
asyncio.run(main())
