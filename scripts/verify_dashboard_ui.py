"""Real-browser acceptance checks for the public paper-only dashboard."""
from __future__ import annotations

import json
import sys
from playwright.sync_api import sync_playwright


URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787/"
WIDTHS = (390, 768, 1440)


def verify() -> list[dict]:
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="/snap/bin/chromium", args=["--no-sandbox"])
        for width in WIDTHS:
            page = browser.new_page(viewport={"width": width, "height": 900})
            console_errors: list[str] = []
            api_failures: list[str] = []
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: console_errors.append(str(error)))
            page.on("response", lambda response: api_failures.append(f"{response.status} {response.url}") if "/api/" in response.url and response.status >= 400 else None)
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_selector(".decision-cockpit", timeout=30_000)
            page.wait_for_timeout(8_000)
            result = page.evaluate("""() => ({
                overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                paper: document.body.innerText.includes('PAPER ONLY'),
                cockpit: Boolean(document.querySelector('.decision-cockpit')),
                priorityLevels: document.querySelectorAll('.priority-level').length,
                smcEvents: document.querySelectorAll('.smc-event').length,
                confidence: Boolean(document.querySelector('.confidence-block')),
                scenarios: Boolean(document.querySelector('.scenario-map')),
                timeframes: document.querySelector('.timeframe-strip')?.innerText || '',
                legacyDom: Boolean(document.querySelector('#legacy-intelligence')),
                orderBookSource: document.querySelector('.order-card .source-line')?.textContent || '',
                liquidation: document.querySelector('.liquidation-card')?.textContent || '',
                consoleErrors: []
            })""")
            result["consoleErrors"] = console_errors
            result["apiFailures"] = api_failures
            result["width"] = width
            assert result["overflow"] == 0, result
            assert result["paper"], result
            assert result["cockpit"], result
            assert result["priorityLevels"] <= 8, result
            assert result["smcEvents"] <= 8, result
            assert result["confidence"], result
            assert result["scenarios"], result
            assert all(key in result["timeframes"] for key in ("1H", "4H", "1D")), result
            assert not result["legacyDom"], result
            assert "Bitget" in result["orderBookSource"], result
            assert "No reliable public liquidation stream" in result["liquidation"], result
            assert not result["consoleErrors"], result
            assert not result["apiFailures"], result
            results.append(result)
            page.close()
        browser.close()
    return results


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
