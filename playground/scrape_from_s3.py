import boto3
import re
from datetime import datetime

# Initialize S3 client
s3_client = boto3.client('s3')

# Specify the bucket name and folder
bucket_name = 'scrapping-divisas' 
parent_folder = 'html/klar/' 

try:
    # List objects in the specific folder
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=parent_folder)
    
    # Check if the folder contains any objects
    if 'Contents' in response:
        print(f"Contents of folder '{parent_folder}' in bucket '{bucket_name}':")
        for obj in response['Contents']:
            file_key = obj['Key']
            # Extract date in YYYY-MM-DD format using regex
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', file_key)
            extracted_date = None
            if date_match:
                extracted_date = date_match.group()
                extracted_date = datetime.strptime(extracted_date, "%Y-%m-%d")
                print(f"  - {extracted_date.strftime('%Y-%m-%d')} (Size: {obj['Size']} bytes, Last Modified: {obj['LastModified']})")
            else:
                print(f"  - {file_key} (Size: {obj['Size']} bytes, Last Modified: {obj['LastModified']})")
    else:
        print(f"Folder '{parent_folder}' in bucket '{bucket_name}' is empty or does not exist.")
        
except Exception as e:
    print(f"Error accessing folder '{parent_folder}' in bucket '{bucket_name}': {e}")
