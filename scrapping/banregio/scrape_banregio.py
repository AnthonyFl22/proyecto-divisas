import asyncio
import gzip
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

async def scrape_banregio_async():
    url = "https://www.banregio.com/divisas.php"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("Extrayendo la data de BanRegio...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60000)

        # Esperar a que aparezca un valor numérico
        await page.wait_for_selector("td:has-text('$')", timeout=10000)
        await page.wait_for_timeout(2000)  # seguridad extra

        html = await page.content()

        # Guardar HTML (Bronze)
        html_path = f"banregio_raw_{timestamp}.html.gz"
        with gzip.open(html_path, "wt", encoding="utf-8") as f:
            f.write(html)
        print(f" HTML renderizado guardado en: {html_path}")

        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", class_="table c-lightergray table-bordered")

        if not table:
            print(" No se encontró la tabla de divisas.")
            await browser.close()
            return

        headers = [td.get_text(strip=True) for td in table.find_all("td", class_="c-orange")]
        tbody = table.find("tbody")
        tr_compra, tr_venta = tbody.find_all("tr")

        compra_vals = [td.get_text(strip=True).replace("$", "").strip() for td in tr_compra.find_all("td")[1::2]]
        venta_vals = [td.get_text(strip=True).replace("$", "").strip() for td in tr_venta.find_all("td")[1::2]]

        rows = []
        for divisa, compra, venta in zip(headers, compra_vals, venta_vals):
            rows.append({
                "divisa": divisa,
                "compra": float(compra),
                "venta": float(venta),
            })

        df = pd.DataFrame(rows)
        df["fetched_at"] = datetime.now().isoformat()
        df["source_url"] = url

        csv_path = f"banregio_divisas_{timestamp}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        print(f"{len(df)} divisas extraídas de Banregio")
        print(df)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_banregio_async())
