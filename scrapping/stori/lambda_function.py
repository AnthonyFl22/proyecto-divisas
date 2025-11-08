from bs4 import BeautifulSoup
from datetime import datetime
import gzip
import re
import boto3
import csv
from io import BytesIO

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
    date_match = re.search(r'\d{4}-\d{2}-\d{2}', object_key)
    if date_match:
        extracted_date = date_match.group()
        extracted_date = datetime.strptime(extracted_date, "%Y-%m-%d")
        return extracted_date, object_key
    else:
        return None

def scrape_stori_cuentamas():
    """
    Core business logic for scraping Stori Cuenta Más from S3-stored HTML
    and saving results to S3.
    
    Returns:
        dict: Response dictionary with statusCode, body, and optional error details
    """
    source_url = "https://www.storicard.com/stori-cuentamas"
    bucket_name = 'scrapping-divisas'
    parent_folder = 'html/stori/'
    
    try:
        # Get most recent HTML file from S3
        file_data = get_most_recent_file_from_s3(bucket_name, parent_folder)
        if not file_data:
            error_msg = "No se encontró el archivo más reciente en S3."
            print(f"Error: {error_msg}")
            return {
                "statusCode": 404,
                "body": {"error": error_msg}
            }

        extracted_date, object_key = file_data
        print(f"Processing file: {object_key} (date: {extracted_date})")

        # Download HTML from S3
        s3_client = boto3.client('s3')
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        
        # Handle gzipped content if the file is compressed
        if object_key.endswith('.gz'):
            with gzip.open(BytesIO(response['Body'].read()), 'rt', encoding='utf-8') as f:
                html_content = f.read()
        else:
            html_content = response['Body'].read().decode('utf-8')

        print("Parsing HTML content...")
        soup = BeautifulSoup(html_content, "html.parser")

        # Buscar los bloques de "plazo" y "rendimiento"
        filas = soup.find_all("div", class_=re.compile("flex justify-between border-b"))
        if not filas:
            error_msg = "No se encontraron filas de rendimientos en la página."
            print(f"Error: {error_msg}")
            return {
                "statusCode": 404,
                "body": {"error": error_msg}
            }

        # Extract data
        data = []
        fetched_at_timestamp = datetime.now().isoformat()
        
        for fila in filas:
            # El primer div de la fila tiene el plazo
            plazo_tag = fila.find("div", class_=re.compile("md:w-1/4"))
            # El segundo div tiene el rendimiento
            rendimiento_tag = fila.find("div", class_=re.compile("md:w-3/4"))

            if not (plazo_tag and rendimiento_tag):
                continue

            plazo = plazo_tag.get_text(strip=True)
            rendimiento_text = rendimiento_tag.get_text(strip=True)

            # Extraer solo el número de porcentaje
            match = re.search(r"([\d.]+)\s*%", rendimiento_text)
            if not match:
                continue
            rendimiento = float(match.group(1))

            data.append({
                "producto": plazo,
                "tasa_anual_fija": rendimiento,
                "fetched_at": fetched_at_timestamp,
                "source_url": source_url
            })

        if not data:
            error_msg = "No se pudo extraer ningún dato de rendimiento."
            print(f"Error: {error_msg}")
            return {
                "statusCode": 404,
                "body": {"error": error_msg}
            }

        print(f"Extracted {len(data)} products successfully.")

        # Write CSV to /tmp
        csv_write_path = "/tmp/stori_cuentamas.csv"
        fieldnames = data[0].keys()

        with open(csv_write_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        print(f"Se guardó el archivo CSV en: '{csv_write_path}'.")

        # Upload to S3
        s3_destination = f"stori/{extracted_date.strftime('%Y-%m-%d')}/data.csv"
        s3_client.upload_file(csv_write_path, bucket_name, s3_destination)
        print(f"Se guardó el archivo CSV en S3: '{s3_destination}'.")

        # Return success response
        return {
            "statusCode": 200,
            "body": {
                "message": "Scraping completado exitosamente",
                "records_processed": len(data),
                "s3_path": f"s3://{bucket_name}/{s3_destination}",
                "source_date": extracted_date.strftime('%Y-%m-%d'),
                "fetched_at": fetched_at_timestamp
            }
        }

    except Exception as e:
        error_msg = f"Ocurrió un error inesperado: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": {"error": error_msg}
        }


def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    
    Args:
        event: The event data passed to the Lambda function
        context: The runtime information provided by AWS Lambda
    
    Returns:
        dict: Response dictionary with statusCode and body
    """
    print("Lambda function started")
    print(f"Event: {event}")
    
    result = scrape_stori_cuentamas()
    
    print(f"Lambda function completed with status: {result.get('statusCode')}")
    return result


# For local testing
if __name__ == "__main__":
    # Simulate Lambda execution locally
    test_event = {}
    test_context = {}
    result = lambda_handler(test_event, test_context)
    print(f"\nResult: {result}")