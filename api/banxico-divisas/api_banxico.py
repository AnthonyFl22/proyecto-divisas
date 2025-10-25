import requests
import pandas as pd
from datetime import datetime

# Token de acceso Banxico 
BANXICO_TOKEN = "1e9f07d4e173151bf1210ce6d2224eccc8abb8839c9bbc5f0ff5f01c524faec7"

# Diccionario con las series que nos interesan
SERIES = {
    "USD": "SF43718",  
    "EUR": "SF46410",  
    "GBP": "SF46407",  
    "JPY": "SF46406",  
}

BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"


def fetch_series_data(serie_id, token, start_date, end_date):
    """Descarga datos de una serie específica"""
    url = f"{BASE_URL}/{serie_id}/datos/{start_date}/{end_date}"
    headers = {"Bmx-Token": token}

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    data = r.json()
    serie = data["bmx"]["series"][0]["datos"]

    df = pd.DataFrame(serie)
    df.columns = ["fecha", "valor"]
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df


def get_banxico_exchange_rates(token, start_date=None, end_date=None):
    """Descarga varias divisas desde la API de Banxico"""
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now().replace(day=1)).strftime("%Y-%m-%d")

    all_data = []
    for divisa, serie_id in SERIES.items():
        print(f"📡 Descargando {divisa} ({serie_id}) ...")
        df = fetch_series_data(serie_id, token, start_date, end_date)
        df["divisa"] = divisa
        all_data.append(df)

    result = pd.concat(all_data, ignore_index=True)
    result["fetched_at"] = datetime.now().isoformat()
    result["source_url"] = "https://www.banxico.org.mx/SieAPIRest/service/v1/"
    result = result[["divisa", "fecha", "valor", "fetched_at", "source_url"]]

    return result


if __name__ == "__main__":
    df = get_banxico_exchange_rates(BANXICO_TOKEN)
    print(df.tail())

    fname = f"banxico_divisas_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(fname, index=False, encoding="utf-8-sig")
    print(f" Datos guardados en {fname}")
