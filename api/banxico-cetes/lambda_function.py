import os
from datetime import datetime
import pandas as pd
import requests
import boto3

# Token de acceso Banxico
BANXICO_TOKEN = os.getenv("BANXICO_TOKEN", "1e9f07d4e173151bf1210ce6d2224eccc8abb8839c9bbc5f0ff5f01c524faec7")

BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1"

# IDs correctos de CETES (rendimiento, fecha de subasta)
CETES_SERIES = {
    "CETES_28": "SF60633",
    "CETES_91": "SF60634",
    "CETES_182": "SF60635",
    "CETES_364": "SF60636"
}


def obtener_tasa_oportuna(series_ids, token):
    """Obtiene el valor más reciente disponible de todas las series CETES."""
    ids = ",".join(series_ids)
    url = f"{BASE}/series/{ids}/datos/oportuno"
    headers = {
        "Bmx-Token": token,
        "Accept": "application/json",
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error fetching CETES data: {e}")
        raise


def fetch_cetes_data(token):
    """Descarga tasas CETES oportunas desde la API de Banxico"""
    print("Consultando tasas CETES mas recientes (ultima subasta Banxico)...")
    
    series_ids = list(CETES_SERIES.values())
    data = obtener_tasa_oportuna(series_ids, token)
    
    # Convertir JSON a DataFrame
    series = data.get("bmx", {}).get("series", [])
    rows = []
    for s in series:
        sid = s.get("idSerie")
        titulo = s.get("titulo")
        datos = s.get("datos", [])
        for d in datos:
            rows.append({
                "serie_id": sid,
                "titulo": titulo,
                "fecha": d.get("fecha"),
                "tasa": d.get("dato")
            })
    
    if not rows:
        raise ValueError("No se recibieron datos. Verifica el token o las series.")
    
    df = pd.DataFrame(rows)
    df["tasa"] = pd.to_numeric(df["tasa"], errors="coerce")
    df["fetched_at"] = datetime.now().isoformat()
    df["source_url"] = f"{BASE}/series"
    
    print(f"Successfully fetched {len(df)} CETES records")
    return df


def main(event):
    # Get token and bucket (optional, with defaults)
    token = event.get('token', BANXICO_TOKEN) if event else BANXICO_TOKEN
    bucket_name = event.get('bucket', 'scrapping-divisas') if event else 'scrapping-divisas'

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Fetch data from Banxico API
    df = fetch_cetes_data(token)

    # Save CSV file
    print("Saving CSV file...")
    csv_path = f"/tmp/banxico_cetes_{timestamp}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # Upload file to S3
    try:
        print("Uploading file to S3...")
        print("Bucket name: ", bucket_name)

        csv_key = f"banxico/cetes/banxico_cetes_{timestamp}.csv"

        s3_client = boto3.client('s3')

        # Upload CSV
        s3_client.upload_file(csv_path, bucket_name, csv_key)
        print(f"Uploaded {csv_key} to S3")

    except Exception as e:
        print(f"Error uploading to S3: {e}")
        raise

    # Clean up temporary files
    try:
        os.remove(csv_path)
        print("Temporary files cleaned up")
    except Exception as e:
        print(f"Warning: Could not clean up temp files: {e}")

    print(f"{len(df)} registros de CETES Banxico procesados correctamente")

    return {
        'statusCode': 200,
        'message': f'CETES Banxico extraidos correctamente: {len(df)} registros',
        'bucket_name': bucket_name,
        'csv_key': csv_key,
        'records_count': len(df)
    }


def handler(event, context):
    try:
        return main(event)
    except Exception as e:
        print(f"Critical error in handler: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': f'Critical error: {str(e)}',
        }
