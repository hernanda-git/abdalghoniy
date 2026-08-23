import asyncio
import json
from playwright.async_api import async_playwright

URL = "https://ag.warga-digital.com"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path="/usr/bin/chromium-browser", args=["--no-sandbox", "--disable-dev-shm-usage"])
        report = []
        for width in (390, 768, 1440):
            page = await browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
            console_errors = []
            failed = []
            sockets = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("requestfailed", lambda req: failed.append(req.url))
            page.on("websocket", lambda ws: sockets.append(ws.url))
            await page.goto(URL, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(6000)
            text = await page.locator("body").inner_text()
            report.append({
                "width": width,
                "overflow": await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"),
                "panel_count": await page.locator(".intel-card").count(),
                "unavailable_count": await page.locator(".intel-card", has_text="UNAVAILABLE").count(),
                "has_rsi": "RSI" in text,
                "has_order_book": "Order book" in text,
                "has_liquidation_unavailable": "No liquidation stream supplied" in text,
                "has_freshness": "Freshness:" in text,
                "has_rate_limit": "Rate limit" in text,
                "console_errors": console_errors,
                "failed_requests": failed,
                "websockets": sockets,
            })
            await page.close()
        await browser.close()
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
