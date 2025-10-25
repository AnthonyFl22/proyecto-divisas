import asyncio
import gzip
import json
import re
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

URL = "https://www.bbva.mx/personas/informacion-financiera-al-dia.html"

# Helpers
PRICE_RX = re.compile(r"[-+]?\d+(?:[\.,]\d+)?")
def norm_price(s: str) -> float | None:
    if not s:
        return None
    s = s.replace("$", "").replace("\xa0", " ").strip()
    m = PRICE_RX.search(s)
    if not m:
        return None
    v = m.group(0).replace(",", "")
    return float(v)

COOKIE_SELECTORS = [
    "#onetrust-accept-btn-handler",
    "button#onetrust-accept-btn-handler",
    "button:has-text('Aceptar')",
    "button:has-text('Acepto')",
    "button:has-text('Aceptar todas')",
]

DIVISAS_CARD_SEL = "div.col.col-sm-6.col-md-6.col-lg.text-center.border-disable"
NAME_SEL = "span.precio-indi-2"
PRICE_SEL = "span.precio-c"

async def accept_cookies(page):
    for sel in COOKIE_SELECTORS:
        try:
            btn = await page.wait_for_selector(sel, timeout=3000)
            if btn:
                await btn.click()
                await page.wait_for_timeout(500)
                return True
        except PWTimeout:
            continue
    return False

async def extract_from_frame(frame) -> list[dict]:
    """Intenta extraer desde un frame (iframe o main) con la estructura conocida."""
    try:
        await frame.wait_for_selector(NAME_SEL, timeout=2500)
    except PWTimeout:
        return []

    html = await frame.content()
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(DIVISAS_CARD_SEL)
    rows = []
    for div in cards:
        try:
            nombre = div.select_one(NAME_SEL)
            precios = div.select(PRICE_SEL)
            if not nombre or not precios:
                continue
            compra = norm_price(precios[0].get_text(strip=True)) if len(precios) > 0 else None
            venta = norm_price(precios[1].get_text(strip=True)) if len(precios) > 1 else None
            rows.append({"divisa": nombre.get_text(strip=True), "compra": compra, "venta": venta})
        except Exception:
            continue
    return rows

async def sniff_network_for_rates(page) -> list[dict]:
    """Plan B: si no logramos leer del DOM, revisa respuestas de red para hallar datos de divisas."""
    collected = []

    def looks_interesting(url: str) -> bool:
        url_l = url.lower()
        keys = ["divisa", "divisas", "tipo", "cambio", "exchange", "rates", "fx"]
        return any(k in url_l for k in keys)

    responses = []

    def on_response(resp):
        try:
            if looks_interesting(resp.url):
                responses.append(resp)
        except Exception:
            pass

    page.on("response", on_response)

    # Navega otra vez a la sección por si carga assets diferidos
    await page.reload(wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(2000)

    # Procesa respuestas
    for resp in responses:
        try:
            ct = resp.headers.get("content-type", "").lower()
            body = None
            if "application/json" in ct:
                body = await resp.json()
            else:
                txt = await resp.text()
                # Si es HTML, intenta parsear con los mismos selectores
                if "<html" in txt.lower():
                    soup = BeautifulSoup(txt, "lxml")
                    cards = soup.select(DIVISAS_CARD_SEL)
                    tmp = []
                    for div in cards:
                        nombre = div.select_one(NAME_SEL)
                        precios = div.select(PRICE_SEL)
                        if not nombre or not precios:
                            continue
                        compra = norm_price(precios[0].get_text(strip=True)) if len(precios) > 0 else None
                        venta = norm_price(precios[1].get_text(strip=True)) if len(precios) > 1 else None
                        tmp.append({"divisa": nombre.get_text(strip=True), "compra": compra, "venta": venta})
                    if tmp:
                        collected.extend(tmp)
                        break
                else:
                    # Heurística: buscar pares compra/venta y nombres comunes en texto plano/JSON embebido
                    if any(k in txt.lower() for k in ["dólar", "dolar", "euro", "yen", "libra"]):
                        # Muy best-effort: no siempre funcionará
                        # (preferimos DOM o JSON real)
                        pass

            if isinstance(body, dict) or isinstance(body, list):
                # Si algún día BBVA expone JSON, aquí podrías mapear las claves a divisa/compra/venta.
                # De momento dejamos placeholder para no romper.
                pass
        except Exception:
            continue

    return collected

async def scrape_bbva_async():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("Extrayendo la data de BBVA...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            ),
            locale="es-MX",
        )
        page = await context.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        # 1) Aceptar cookies si aparece banner
        await accept_cookies(page)

        # 2) Dar tiempo a que se inyecte el iframe
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except PWTimeout:
            pass

        # 3) Primero intenta en el frame principal (por si ya está embebido)
        rows = await extract_from_frame(page.main_frame)

        # 4) Si no hay datos, recorre TODOS los iframes y busca la estructura ahí
        if not rows:
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    frame_rows = await extract_from_frame(frame)
                    if frame_rows:
                        rows = frame_rows
                        break
                except Exception:
                    continue

        # 5) Plan B (sniffing de red)
        if not rows:
            rows = await sniff_network_for_rates(page)

        # 6) Persistencia (bronze + csv)
        # Guarda el HTML del frame que sí tenía contenido (o de la página principal si no hubo suerte)
        try:
            html_for_bronze = await (page.main_frame.content() if not page.frames else page.frames[-1].content())
        except Exception:
            html_for_bronze = await page.content()

        bronze_path = f"bbva_raw_{ts}.html.gz"
        with gzip.open(bronze_path, "wt", encoding="utf-8") as f:
            f.write(html_for_bronze)
        print(f" HTML renderizado guardado en: {bronze_path}")

        if not rows:
            print("⚠️ No pude extraer divisas. Posible cambio de estructura o protección adicional en el iframe.")
            await browser.close()
            return

        df = pd.DataFrame(rows)
        df["fetched_at"] = datetime.now().isoformat()
        df["source_url"] = URL

        csv_path = f"bbva_divisas_{ts}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        print(f"✅ {len(df)} divisas extraídas de BBVA")
        print(df)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_bbva_async())
