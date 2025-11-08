import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import os
import boto3
import re
from datetime import datetime

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

def scrape_klar_rates():
    """
    Core business logic for scraping Klar rates from S3-stored HTML
    and saving results to S3.
    
    Returns:
        dict: Response dictionary with statusCode, body, and optional error details
    """
    source_url = "https://www.klar.mx/inversion"
    bucket_name = 'scrapping-divisas'
    parent_folder = 'html/klar/'
    
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
        html_content = response['Body'].read().decode('utf-8')

        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        chart_component = soup.find("div", class_="layout508_component")
        if not chart_component:
            error_msg = "No se pudo encontrar el componente principal de la tabla (div.layout508_component)."
            print(f"Error: {error_msg}")
            return {
                "statusCode": 404,
                "body": {"error": error_msg}
            }

        desktop_chart = chart_component.find("div", class_="chart-wrapper is-desktop is-3-col")
        if not desktop_chart:
            error_msg = "No se pudo encontrar la tabla de escritorio (div.chart-wrapper.is-desktop.is-3-col)."
            print(f"Error: {error_msg}")
            return {
                "statusCode": 404,
                "body": {"error": error_msg}
            }

        # Extract columns
        columns = desktop_chart.find_all("div", class_="long-detail", recursive=False)
        if len(columns) != 3:
            error_msg = f"Se esperaban 3 columnas, pero se encontraron {len(columns)}."
            print(f"Error: {error_msg}")
            return {
                "statusCode": 404,
                "body": {"error": error_msg}
            }
        
        col_products = columns[0]
        col_klar_rates = columns[1]
        col_klar_plus_rates = columns[2]

        # Extract data
        product_names = [
            div.text.strip() for div in col_products.find_all("div", class_="is-title")
        ][1:]
        
        klar_rates = [
            div.text.strip() for div in col_klar_rates.find_all("div", class_="is-chart-details")
        ]
        klar_plus_rates = [
            div.text.strip() for div in col_klar_plus_rates.find_all("div", class_="is-chart-details")
        ]

        # Validate data
        if not (len(product_names) == len(klar_rates) == len(klar_plus_rates)):
            error_msg = "Las columnas no tienen el mismo número de filas."
            print(f"Error: {error_msg}")
            return {
                "statusCode": 404,
                "body": {"error": error_msg}
            }

        # Prepare CSV data
        data_to_csv = []
        fetched_at_timestamp = datetime.now().isoformat()
        
        for i in range(len(product_names)):
            data_to_csv.append({
                "producto": f"Klar - {product_names[i]}",
                "tasa_anual_fija": klar_rates[i],
                "fetched_at": fetched_at_timestamp,
                "source_url": source_url
            })
            data_to_csv.append({
                "producto": f"Klar Plus y Platino - {product_names[i]}",
                "tasa_anual_fija": klar_plus_rates[i],
                "fetched_at": fetched_at_timestamp,
                "source_url": source_url
            })

        # Write CSV to /tmp
        csv_write_path = "/tmp/klar_tasas.csv"
        fieldnames = data_to_csv[0].keys()

        with open(csv_write_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data_to_csv)

        print(f"Se guardó el archivo CSV en: '{csv_write_path}'.")

        # Upload to S3
        s3_destination = f"klar/{extracted_date.strftime('%Y-%m-%d')}/data.csv"
        s3_client.upload_file(csv_write_path, bucket_name, s3_destination)
        print(f"Se guardó el archivo CSV en S3: '{s3_destination}'.")

        # Return success response
        return {
            "statusCode": 200,
            "body": {
                "message": "Scraping completado exitosamente",
                "records_processed": len(data_to_csv),
                "s3_path": f"s3://{bucket_name}/{s3_destination}",
                "source_date": extracted_date.strftime('%Y-%m-%d'),
                "fetched_at": fetched_at_timestamp
            }
        }

    except requests.exceptions.RequestException as e:
        error_msg = f"Error al hacer la petición HTTP: {str(e)}"
        print(error_msg)
        return {
            "statusCode": 500,
            "body": {"error": error_msg}
        }
    except Exception as e:
        error_msg = f"Ocurrió un error inesperado: {str(e)}"
        print(error_msg)
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
    
    result = scrape_klar_rates()
    
    print(f"Lambda function completed with status: {result.get('statusCode')}")
    return result


# For local testing
if __name__ == "__main__":
    # Simulate Lambda execution locally
    test_event = {}
    test_context = {}
    result = lambda_handler(test_event, test_context)
    print(f"\nResult: {result}")