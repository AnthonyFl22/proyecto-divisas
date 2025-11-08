import boto3
import pandas as pd
import re
from datetime import datetime
from io import BytesIO

def read_csv_from_s3(bucket_name, object_key):
    """
    Read CSV file from S3 directly into a pandas DataFrame.
    
    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key (path to file)
    
    Returns:
        pandas.DataFrame: The CSV data as a DataFrame
    """
    s3_client = boto3.client('s3')
    
    # Get object from S3
    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
    
    # Read CSV directly from S3 response body
    df = pd.read_csv(BytesIO(response['Body'].read()), encoding='utf-8-sig')
    
    return df

def get_most_recent_file_from_s3(bucket_name, parent_folder):
    s3_client = boto3.client('s3')
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=parent_folder)
    
    # Sort objects by LastModified in descending order (most recent first)
    if not 'Contents' in response:
        return None
        
    response['Contents'] = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
    object_key = response['Contents'][0]['Key']
    extracted_date = None
    date_match = re.search(r'\d{4}-\d{2}-\d{2}', object_key)
    if date_match:
        extracted_date = date_match.group()
        extracted_date = datetime.strptime(extracted_date, "%Y-%m-%d")
        return extracted_date, object_key
    else:
        return None   

def get_product_id(product_name):
    normalized_product_name = product_name.lower().strip()

    if "sin plazo" in normalized_product_name:
        return 21
    elif "30" in normalized_product_name:
        return 22
    elif "90" in normalized_product_name:
        return 23
    elif "180" in normalized_product_name:
        return 24
    elif "360" in normalized_product_name:
        return 25
    else:
        return 21


def lambda_handler(event, context):
    ENTITY_ID = 4

    bucket_name = 'scrapping-divisas'
    parent_folder = 'stori/'

    file_data = get_most_recent_file_from_s3(bucket_name, parent_folder)

    if not file_data:
        return {
            'statusCode': 404,
            'body': 'No se encontró el archivo más reciente en S3.'
        }

    extracted_date, object_key = file_data

    df = read_csv_from_s3(bucket_name, object_key)

    new_rows = []
    
    # new_rows contains: date, entity__id, product__id, rate, ingestion_ts, source_file
    for _, row in df.iterrows():
        product_name = row['producto']
        product_id = get_product_id(product_name)

        rate = float(row["tasa_anual_fija"]) if not pd.isna(row["tasa_anual_fija"]) else None
        ingestion_ts = datetime.now().isoformat()
        source_file = f"s3://{bucket_name}/{object_key}"

        # Parse fetched_at as an ISO8601 datetime string with microseconds and 'T' separator, e.g. '2025-11-08T02:10:16.148308'
        fetched_at = datetime.strptime(row['fetched_at'], "%Y-%m-%dT%H:%M:%S.%f")
        date = fetched_at.strftime("%Y-%m-%d")

        new_rows.append({
            'date': date,
            'entity__id': ENTITY_ID,
            'product__id': product_id,
            'rate': rate,
            'ingestion_ts': ingestion_ts,
            'source_file': source_file
        })

    new_df = pd.DataFrame(new_rows)
    tmp_path = f"/tmp/fact_rates_staging.parquet"
    new_df_s3_key = f"silver/stori/{extracted_date.strftime('%Y-%m-%d')}/fact_rates_staging.parquet"
    new_df.to_parquet(tmp_path)

    print(f"Uploading {tmp_path} to {new_df_s3_key}")

    s3_client = boto3.client('s3')
    s3_client.upload_file(tmp_path, bucket_name, new_df_s3_key)
    print(f"Saved {len(new_df)} rows to {new_df_s3_key}")

    return {
        'statusCode': 200,
        'message': f'Stori extraidos correctamente: {len(new_df)} registros',
        'bucket_name': bucket_name,
        'csv_key': new_df_s3_key,
        'records_count': len(new_df)
    }

if __name__ == "__main__":
    event = {}
    context = {}
    result = lambda_handler(event, context)
    print(result)