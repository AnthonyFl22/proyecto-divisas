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
    """
    Get the most recent file from S3 bucket.
    
    Args:
        bucket_name: S3 bucket name
        parent_folder: Folder prefix in S3
    
    Returns:
        tuple: (extracted_date, object_key) or None if no files found
    """
    s3_client = boto3.client('s3')
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=parent_folder)
    
    # Sort objects by LastModified in descending order (most recent first)
    if not 'Contents' in response:
        return None
        
    response['Contents'] = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
    object_key = response['Contents'][0]['Key']
    extracted_date = None
    # Match YYYYMMDD in the object key, e.g., banxico/divisas/banxico_divisas_20251108_020959.csv
    date_match = re.search(r'(\d{8})_\d{6}', object_key)
    if date_match:
        date_str = date_match.group(1)  # e.g. "20251108"
        extracted_date = datetime.strptime(date_str, "%Y%m%d")
        return extracted_date, object_key
    else:
        return None

def lambda_handler(event, context):
    ENTITY_ID = 1
    PRODUCT_ID_MAP = {
        'SF60633': 26,
        'SF60634': 27,
        'SF60635': 28,
        'SF60636': 29,
    }

    bucket_name = 'scrapping-divisas'
    parent_folder = 'banxico/cetes/'

    file_data = get_most_recent_file_from_s3(bucket_name, parent_folder)

    if not file_data:
        return {
            'statusCode': 404,
            'body': 'No se encontró el archivo más reciente en S3.'
        }

    extracted_date, object_key = file_data

    df = read_csv_from_s3(bucket_name, object_key)

    new_rows = []
    
    for _, row in df.iterrows():
        serie_id = row['serie_id']
        product_id = PRODUCT_ID_MAP.get(serie_id, None)
        entity_id = ENTITY_ID
        rate = float(row['tasa']) if not pd.isna(row['tasa']) else None
        ingestion_ts = datetime.now().isoformat()
        source_file = f"s3://{bucket_name}/{object_key}"
        date = datetime.strptime(row['fecha'], "%d/%m/%Y")

        new_rows.append({
            'date': date.strftime("%Y-%m-%d"),
            'entity__id': entity_id,
            'product__id': product_id,
            'rate': rate,
            'ingestion_ts': ingestion_ts,
            'source_file': source_file
        })
        
    new_df = pd.DataFrame(new_rows)
    tmp_path = f"/tmp/fact_rates_staging.parquet"
    new_df_s3_key = f"silver/banxico/{extracted_date.strftime('%Y-%m-%d')}/fact_rates_staging.parquet"
    new_df.to_parquet(tmp_path)

    print(f"Uploading {tmp_path} to {new_df_s3_key}")

    s3_client = boto3.client('s3')
    s3_client.upload_file(tmp_path, bucket_name, new_df_s3_key)
    print(f"Saved {len(new_df)} rows to {new_df_s3_key}")

    return {
        'statusCode': 200,
        'message': f'CETES Banxico extraidos correctamente: {len(new_df)} registros',
        'bucket_name': bucket_name,
        'csv_key': new_df_s3_key,
        'records_count': len(new_df)
    }

if __name__ == "__main__":
    event = {}
    context = {}
    result = lambda_handler(event, context)
    print(result)