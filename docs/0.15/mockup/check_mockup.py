"""Screenshot every design, tab and concept of the mock-up, and drag the History essay on each
surface with Playwright's mouse to prove the drag works everywhere before Jonathan sees it."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE = Path(__file__).parent
OUT = HERE / "shots"; OUT.mkdir(exist_ok=True)
CHROME = str(Path.home() / ".cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
DESIGNS = ["classic", "timeline", "mission", "bento", "retro", "clay"]
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME)
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    for design in DESIGNS:
        for tab in ("day", "week", "month"):
            concepts = page.evaluate("() => 0") if False else None
            page.goto(f"file://{HERE}/index.html?design={design}&tab={tab}")
            variants = page.evaluate("t => Object.keys(window.__mock.S && (t==='month' ? {A:1} : ({}) ) )", tab)
            variants = ["A"] if tab == "month" else page.evaluate(f"() => Object.keys(({json.dumps({})}))") or []
            variants = ["A"] if tab == "month" else page.evaluate(
                "([d,t]) => { const s = document.querySelectorAll('[data-concept]'); return s.length ? [...s].map(b => b.dataset.concept) : ['A']; }", [design, tab])
            for concept in variants:
                page.goto(f"file://{HERE}/index.html?design={design}&tab={tab}&concept={concept}")
                page.wait_for_timeout(150)
                name = f"{design}-{tab}-{concept}"
                frame = page.locator("#frame")
                frame.screenshot(path=str(OUT / f"{name}.png"))
                outcome = {"surface": name}
                if tab == "month":
                    chip = page.locator(".mchip", has_text="History essay").first
                    target = page.locator('.cell[data-dom="26"]')
                    a, b = chip.bounding_box(), target.bounding_box()
                    page.mouse.move(a["x"] + 20, a["y"] + a["height"] / 2); page.mouse.down()
                    for k in range(1, 13):
                        page.mouse.move(a["x"] + 20 + (b["x"] + 40 - a["x"] - 20) * k / 12, a["y"] + (b["y"] + 50 - a["y"]) * k / 12)
                        page.wait_for_timeout(16)
                    page.mouse.up()
                    got = page.evaluate("() => window.__mock.S.blocks.find(b => b.title === 'History essay')")
                    outcome["result"] = "PASS" if got["dom"] == 26 and got["start"] == 19 * 60 else f"FAIL {got['dom']} {got['start']}"
                else:
                    # Move the essay 90 minutes later on its own day (Thursday 24).
                    page.evaluate("() => { window.__mock.S.day = 3; window.__mock.render(); }")
                    page.goto(f"file://{HERE}/index.html?design={design}&tab={tab}&concept={concept}")
                    page.wait_for_timeout(100)
                    geo = page.evaluate("""() => {
                      const blk = [...document.querySelectorAll('.blk')].find(b => b.querySelector('b')?.textContent === 'History essay');
                      if (!blk) return null;
                      blk.scrollIntoView({block: 'center', inline: 'center'});
                      const t = blk.closest('.track')._track, r = blk.getBoundingClientRect();
                      const ppm = (t.axis === 'v' ? t.el.offsetHeight : t.el.offsetWidth) / (t.to - t.from);
                      const ang = t.angle * Math.PI / 180;
                      const d = 90 * ppm;
                      const dx = t.axis === 'v' ? -Math.sin(ang) * d : Math.cos(ang) * d, dy = t.axis === 'v' ? Math.cos(ang) * d : Math.sin(ang) * d;
                      return {x: r.left + r.width / 2, y: r.top + r.height / 2, dx, dy};
                    }""")
                    if geo is None:
                        outcome["result"] = "FAIL essay not drawn"
                    else:
                        page.mouse.move(geo["x"], geo["y"]); page.mouse.down()
                        for k in range(1, 16):
                            page.mouse.move(geo["x"] + geo["dx"] * k / 15, geo["y"] + geo["dy"] * k / 15); page.wait_for_timeout(16)
                        page.wait_for_timeout(80)
                        frame.screenshot(path=str(OUT / f"{name}-held.png"))
                        page.mouse.up()
                        got = page.evaluate("() => window.__mock.S.blocks.find(b => b.title === 'History essay')")
                        outcome["result"] = "PASS" if (got["dom"], got["start"]) == (24, 20 * 60 + 30) else f"FAIL {got['dom']} {got['start']}"
                if errors:
                    outcome["errors"] = errors[:]; errors.clear()
                results.append(outcome)
                print(outcome, flush=True)
    browser.close()
json.dump(results, open(OUT / "results.json", "w"), indent=1)
print(sum(r["result"] == "PASS" for r in results), "/", len(results))
