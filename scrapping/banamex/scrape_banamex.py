import asyncio
import gzip
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

async def scrape_banamex_playwright_async():
    url = "https://www.banamex.com/economia-finanzas/es/mercado-de-divisas/index.html"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Cargando página Banamex...")
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("p[ndivisa]", timeout=30000)

        # Extraer todos los elementos con atributo ndivisa
        divisas_elements = await page.query_selector_all("p[ndivisa]")

        data = {}
        for el in divisas_elements:
            name = await el.get_attribute("ndivisa")
            value = (await el.inner_text()).strip()
            data[name] = value

        # Estructurar la información
        rows = []
        for base in ["usd", "euro", "libra", "yen"]:
            compra = data.get(f"{base}_com")
            venta = data.get(f"{base}_ven")
            if compra or venta:
                rows.append({
                    "divisa": base.upper(),
                    "compra": float(compra) if compra else None,
                    "venta": float(venta) if venta else None
                })

        df = pd.DataFrame(rows)
        df["fetched_at"] = datetime.now().isoformat()
        df["source_url"] = url

        csv_path = f"banamex_divisas_{timestamp}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        # Guardar HTML renderizado (capa bronze)
        html_path = f"banamex_raw_{timestamp}.html.gz"
        html = await page.content()
        with gzip.open(html_path, "wt", encoding="utf-8") as f:
            f.write(html)

        await browser.close()

        print(f"{len(df)} divisas extraídas correctamente")
        print(df)

if __name__ == "__main__":
    asyncio.run(scrape_banamex_playwright_async())
