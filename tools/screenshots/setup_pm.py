import asyncio, aiohttp, ha, json
B = ha.BASE
ROOMS = [
    ("Wohnzimmer", "wohnzimmer", "wohnzimmer", {"fenstersensoren": ["binary_sensor.fenster_wohnzimmer"]},
     {"co2_sensor": "sensor.wohnzimmer_co2", "pm25_sensor": "sensor.wohnzimmer_pm2_5",
      "luftreiniger": "fan.luftreiniger_wohnzimmer", "luftreiniger_filter": ["sensor.luftreiniger_filter"]}),
    ("Küche", "kuche", "kueche", {"fenstersensoren": ["binary_sensor.fenster_kuche"]}, {}),
    ("Schlafzimmer", "schlafzimmer", "schlafzimmer", {}, {}),
    ("Bad", "bad", "bad", {"fenstersensoren": ["binary_sensor.fenster_bad"]}, {"nassraum": True}),
]
async def post(s, h, url, data):
    r = await s.post(B + url, headers=h, json=data)
    j = await r.json()
    if r.status >= 400 or j.get("errors"): raise RuntimeError((url, r.status, j))
    return j
async def m():
    async with aiohttp.ClientSession() as s:
        h = {"Authorization": "Bearer " + await ha.token(s)}
        f = await post(s, h, "/api/config/config_entries/flow", {"handler": "pm_heizung"})
        fid = f["flow_id"]
        steps = [
            {"personen": ["person.anna", "person.ben"],
             "anwesenheit_entitaeten": ["input_boolean.anna_zuhause", "input_boolean.ben_zuhause"],
             "sprache": "auto"},
            {"absenkung": 3, "mindesttemperatur": 16, "fern_absenkung": 2, "vorheizstufe": "balance",
             "eigener_nahradius": 3, "eigener_mittelradius": 8, "eigener_fernradius": 20,
             "annaeherung_erforderlich": True, "verlassen_verzoegerung": 5},
            {"aussentemperatur_sensor": "sensor.aussentemperatur", "aussentemperatur_grenze": 17,
             "freigabe_entitaet": "input_boolean.heizperiode", "sperre_wirkung": "zeitplan",
             "sperre_mindesthaltezeit": 15},
            {"luft_aussenfeuchte": "sensor.aussenluftfeuchte"},
            {"beratung_push": True, "beratung_alexa": False, "beratung_panel": False,
             "beratung_push_zuordnung": "person.anna: notify.mobile_app_annas_telefon",
             "beratung_ruhe_beginn": "22:00:00", "beratung_ruhe_ende": "07:00:00", "beratung_abstand": 120},
        ]
        for data in steps:
            f = await post(s, h, f"/api/config/config_entries/flow/{fid}", data)
        entry_id = f["result"]["entry_id"]
        print("entry", entry_id)
        for title, slug, sched, dev, air in ROOMS:
            f = await post(s, h, "/api/config/config_entries/subentries/flow", {"handler": [entry_id, "raum"]})
            fid = f["flow_id"]
            d1 = {"name": title, "klimageraete": [f"climate.thermostat_{slug}"],
                  "temperatursensor": f"sensor.{slug}_temperatur", "feuchtesensor": f"sensor.{slug}_luftfeuchte",
                  "zeitplan": f"schedule.heizplan_{sched}", "zeitplan_attribut": "temperatur", **dev}
            comfort = {"Bad": 22, "Schlafzimmer": 18}.get(title, 21)
            d2 = {"komforttemperatur": comfort, "ecotemperatur": 17 if title == "Schlafzimmer" else 18,
                  "frostschutztemperatur": 7, "min_temperatur": 5, "max_temperatur": 25}
            d3 = {"overlay_modus": "naechster_block", "overlay_minuten": 60, "boost_minuten": 30,
                  "fenster_verzoegerung_offen": 30, "fenster_verzoegerung_zu": 10, "fenster_aktion": "frostschutz",
                  "aus_mit_frostschutz": False, "externe_aenderung_uebernehmen": True,
                  "extern_aus_als_fenster": False}
            d4 = {"nassraum": False, "frsi": 0.75, "nacht_beginn": "22:00:00", "nacht_ende": "07:00:00",
                  "luftreiniger_pause": 60, "luftreiniger_haltezeit": 10, **air}
            for d in (d1, d2, d3, d4):
                f = await post(s, h, f"/api/config/config_entries/subentries/flow/{fid}", d)
            print(title, f.get("type"))
asyncio.run(m())
