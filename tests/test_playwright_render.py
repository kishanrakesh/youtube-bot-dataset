import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--use-gl=swiftshader",
                "--disable-software-rasterizer",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        page = await browser.new_page()
        await page.goto("https://www.youtube.com/channel/UCfELkWGi_zyokp6VJVL6aXg", wait_until="networkidle")
        await page.wait_for_selector("#contents", timeout=15000)
        text = await page.inner_text("body")
        print("Visible text snippet:", text)
        await page.screenshot(path="/tmp/yt_test.png", full_page=True)
        await browser.close()

asyncio.run(main())
