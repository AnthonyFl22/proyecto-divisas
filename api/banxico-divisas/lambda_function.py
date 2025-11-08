import os
from datetime import datetime, timedelta
import pandas as pd
import requests
import boto3

# Token de acceso Banxico
BANXICO_TOKEN = os.getenv("BANXICO_TOKEN", "1e9f07d4e173151bf1210ce6d2224eccc8abb8839c9bbc5f0ff5f01c524faec7")

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

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()

        data = r.json()
        serie = data["bmx"]["series"][0]["datos"]

        df = pd.DataFrame(serie)
        df.columns = ["fecha", "valor"]
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df
    except Exception as e:
        print(f"Error fetching series {serie_id}: {e}")
        raise


def fetch_banxico_data(token, start_date=None, end_date=None):
    """Descarga varias divisas desde la API de Banxico"""
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now().replace(day=1)).strftime("%Y-%m-%d")

    print(f"Fetching Banxico data from {start_date} to {end_date}")

    all_data = []
    for divisa, serie_id in SERIES.items():
        print(f"Descargando {divisa} ({serie_id}) ...")
        try:
            df = fetch_series_data(serie_id, token, start_date, end_date)
            df["divisa"] = divisa
            all_data.append(df)
        except Exception as e:
            print(f"Warning: Failed to fetch {divisa}: {e}")
            continue

    if not all_data:
        raise ValueError("No data could be fetched from any series")

    result = pd.concat(all_data, ignore_index=True)
    result["fetched_at"] = datetime.now().isoformat()
    result["source_url"] = "https://www.banxico.org.mx/SieAPIRest/service/v1/"
    result = result[["divisa", "fecha", "valor", "fetched_at", "source_url"]]

    print(f"Successfully fetched {len(result)} records")
    return result


def main(event):
    # Get token and bucket (optional, with defaults)
    token = event.get('token', BANXICO_TOKEN) if event else BANXICO_TOKEN
    bucket_name = event.get('bucket', 'scrapping-divisas') if event else 'scrapping-divisas'

    # Calculate previous day's date (for scheduled invocation at 00:05 AM UTC-6)
    today = datetime.now()
    previous_day = today - timedelta(days=1)
    end_date = previous_day.strftime("%Y-%m-%d")
    
    # Set start_date to the same as end_date to retrieve only the previous day
    start_date = end_date

    print(f"Fetching data for previous day: {end_date} (from {start_date} to {end_date})")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Fetch data from Banxico API
    df = fetch_banxico_data(token, start_date, end_date)

    # Save CSV file
    print("Saving CSV file...")
    csv_path = f"/tmp/banxico_divisas_{timestamp}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # Upload file to S3
    try:
        print("Uploading file to S3...")
        print("Bucket name: ", bucket_name)

        csv_key = f"banxico/divisas/banxico_divisas_{timestamp}.csv"

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

    print(f"{len(df)} registros de divisas Banxico procesados correctamente")

    return {
        'statusCode': 200,
        'message': f'Divisas Banxico extraídas correctamente: {len(df)} registros',
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

