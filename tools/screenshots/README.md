# Screenshots der Dokumentation

Die Bilder in `docs/bilder/` stammen aus einer Demo-Instanz mit Beispieldaten (keine echte
Installation). So werden sie neu erzeugt:

```bash
pip install -r ../../requirements_test.txt playwright home-assistant-frontend
mkdir -p /tmp/pm-demo/custom_components
cp demo_configuration.yaml /tmp/pm-demo/configuration.yaml
ln -s "$PWD/../../custom_components/pm_heizung" /tmp/pm-demo/custom_components/pm_heizung
hass -c /tmp/pm-demo --skip-pip &          # fehlende Pakete ggf. nachinstallieren
```

Ablauf:

1. `ha.onboard()` einmal aufrufen (Benutzer „anna“, Passwort „demo-demo“).
2. `python setup_pm.py` – Zentrale und vier Räume anlegen.
3. `python save_dash.py ../../docs/beispiele/dashboard.yaml` – Beispiel-Dashboard speichern.
4. `python s1.py` … `python s6.py` – Dashboard, Dialoge, Geräteseiten, Reparaturhinweis,
   englische Ansicht.

Chromium: Umgebungsvariable `CHROMIUM` auf die ausführbare Datei setzen, sonst nutzt Playwright
seinen eigenen Browser.
