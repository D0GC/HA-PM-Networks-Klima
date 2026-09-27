import asyncio, re
from playwright.async_api import async_playwright
from browser import open_page, shot, BASE, OUT

async def dialog_shot(page, name):
    await page.wait_for_timeout(1800)
    box = await page.evaluate("""() => {
      const vw = innerWidth, vh = innerHeight; let best = null;
      const walk = (r) => { for (const e of r.querySelectorAll('*')) {
          const b = e.getBoundingClientRect();
          if (b.width > 300 && b.width < vw * 0.9 && b.height > 150 && b.height <= vh &&
              getComputedStyle(e).borderTopLeftRadius !== '0px' && (!best || b.width * b.height > best.width * best.height))
            best = {x: b.x, y: b.y, width: b.width, height: b.height};
          if (e.shadowRoot) walk(e.shadowRoot); } };
      const d = document.querySelector('home-assistant');
      const find = (r) => { for (const e of r.querySelectorAll('*')) { if (e.tagName === 'HA-DIALOG') return e; if (e.shadowRoot) { const f = find(e.shadowRoot); if (f) return f; } } return null; };
      const dlg = find(document); if (!dlg) return null; walk(dlg.shadowRoot || dlg); return best; }""")
    if box:
        pad = 0
        clip = {"x": max(box["x"] - pad, 0), "y": max(box["y"] - pad, 0),
                "width": box["width"] + 2 * pad, "height": box["height"] + 2 * pad}
        await page.screenshot(path=f"{OUT}/{name}.png", clip=clip)
    else:
        await page.screenshot(path=f"{OUT}/{name}.png")
    print("shot", name, box and (int(box["width"]), int(box["height"])))

async def submit(page):
    await page.get_by_role("button", name=re.compile(r"^(OK|Absenden|Weiter|Senden|Fertig)$")).last.click()

async def main():
    async with async_playwright() as p:
        b, page = await open_page(p, 1280, 1500)
        await page.goto(BASE + "/config/integrations/integration/pm_heizung")
        await page.set_viewport_size({"width": 1280, "height": 900})
        await shot(page, "integration", wait=3000)
        await page.set_viewport_size({"width": 1280, "height": 1500})
        # Zentrale konfigurieren (Options-Flow, 5 Schritte)
        await page.get_by_label("Konfigurieren").first.click()
        for i, name in enumerate(["zentrale_1_personen", "zentrale_2_abwesenheit", "zentrale_3_sperre",
                                  "zentrale_4_luft", "zentrale_5_beratung"]):
            await dialog_shot(page, name)
            await submit(page)
        await page.wait_for_timeout(2000)
        await page.keyboard.press("Escape")
        await b.close()
if __name__ == "__main__":
    asyncio.run(main())
