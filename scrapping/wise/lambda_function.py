import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import os
import re
import gzip

def scrape_wise_usd_to_mxn():
    url = "https://wise.com/"
    print("Cargando página de Wise...")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/118.0.5993.70 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    # Guardar el HTML crudo (capa bronze)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    html_path = os.path.join(output_dir, f"wise_raw_{timestamp}.html.gz")
    with gzip.open(html_path, "wt", encoding="utf-8") as f:
        f.write(response.text)
    print(f" HTML guardado en: {html_path}")


    soup = BeautifulSoup(response.text, "html.parser")
    boton = soup.find("button", {"aria-describedby": "rateLabel"})

    if not boton:
        raise ValueError(" No se encontró el botón con la tasa de cambio en Wise.")

    texto = boton.get_text(strip=True)
    print(f"Texto encontrado: {texto}")

    match = re.search(r"1\s*([A-Z]{3})\s*=\s*([\d.]+)\s*([A-Z]{3})", texto)
    if not match:
        raise ValueError("No se pudo extraer la información del tipo de cambio.")

    base_currency, rate, quote_currency = match.groups()

    df = pd.DataFrame([{
        "base_currency": base_currency,
        "quote_currency": quote_currency,
        "exchange_rate": float(rate),
        "source_url": url,
        "fetched_at": datetime.now().isoformat()
    }])

    csv_path = os.path.join(output_dir, f"wise_usd_mxn_{timestamp}.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(df)

if __name__ == "__main__":
    scrape_wise_usd_to_mxn()