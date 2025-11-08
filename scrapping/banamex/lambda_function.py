import asyncio
import gzip
import os
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

import boto3


async def download_page_content(url):
    async with async_playwright() as p:
        # Launch the browser with all necessary parameters
        print("Launching browser...")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--single-process",
                "--disable-dev-shm-usage",
                "--no-zygote",
                "--disable-setuid-sandbox",
                "--disable-accelerated-2d-canvas",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-client-side-phishing-detection",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-domain-reliability",
                "--disable-features=AudioServiceOutOfProcess",
                "--disable-hang-monitor",
                "--disable-ipc-flooding-protection",
                "--disable-popup-blocking",
                "--disable-prompt-on-repost",
                "--disable-renderer-backgrounding",
                "--disable-sync",
                "--force-color-profile=srgb",
                "--metrics-recording-only",
                "--mute-audio",
                "--no-pings",
                "--use-gl=swiftshader",
                "--window-size=1280,1696"
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = await context.new_page()

        # Set headers
        await page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })

        await page.set_content("<meta http-equiv='X-Content-Type-Options' content='nosniff'>")

        # Navigate to URL
        print(f"Navigating to URL: {url}")
        try:
            await page.goto(url, timeout=60000, wait_until='domcontentloaded')
            print("Page loaded, waiting for content...")
            await page.wait_for_selector("p[ndivisa]", timeout=30000)
            
            print("Extracting currency data...")
            # Extraer todos los elementos con atributo ndivisa
            divisas_elements = await page.query_selector_all("p[ndivisa]")
            
            if not divisas_elements:
                raise ValueError("No currency elements found on page")
            
            data = {}
            for el in divisas_elements:
                name = await el.get_attribute("ndivisa")
                value = (await el.inner_text()).strip()
                data[name] = value
            
            print(f"Extracted {len(data)} data points")
            
            # Estructurar la información
            rows = []
            for base in ["usd", "euro", "libra", "yen"]:
                compra = data.get(f"{base}_com")
                venta = data.get(f"{base}_ven")
                if compra or venta:
                    rows.append({
                        "divisa": base.upper(),
                        "compra": float(compra) if compra else None,
                        "venta": float(venta) if venta else None
                    })
            
            if not rows:
                raise ValueError("No currency data could be parsed")
            
            df = pd.DataFrame(rows)
            df["fetched_at"] = datetime.now().isoformat()
            df["source_url"] = url
            
            # Guardar HTML renderizado (capa bronze)
            print("Saving HTML content...")
            html = await page.content()
            
            print("Page content extracted successfully.")
            
        except Exception as e:
            print(f"Failed to load page: {e}")
            raise
        
        await browser.close()
        print("Browser closed.")
        
        return html, df


async def main(event):
    # Extract parameters from the event payload
    url = event.get('url', 'https://www.banamex.com/economia-finanzas/es/mercado-de-divisas/index.html')
    bucket_name = event.get('bucket', 'scrapping-divisas')
    
    if not url:
        raise ValueError('Error: Missing required parameter (url).')

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Run the async function to download and process the content
    html, df = await download_page_content(url)

    # Save CSV file
    print("Saving CSV file...")
    csv_path = f"/tmp/banamex_divisas_{timestamp}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # Compress HTML file
    print("Compressing HTML file...")
    html_path = f"/tmp/banamex_raw_{timestamp}.html.gz"
    with gzip.open(html_path, "wt", encoding="utf-8") as f:
        f.write(html)

    # Upload files to S3
    try:
        print("### Uploading files to S3...")
        print("Bucket name: ", bucket_name)
        
        csv_key = f"banamex/banamex_divisas_{timestamp}.csv"
        html_key = f"banamex/banamex_raw_{timestamp}.html.gz"
        
        s3_client = boto3.client('s3')
        
        # Upload CSV
        s3_client.upload_file(csv_path, bucket_name, csv_key)
        print(f"Uploaded {csv_key} to S3")
        
        # Upload compressed HTML
        s3_client.upload_file(html_path, bucket_name, html_key)
        print(f"Uploaded {html_key} to S3")
        
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        raise

    # Clean up temporary files
    try:
        os.remove(csv_path)
        os.remove(html_path)
        print("Temporary files cleaned up")
    except Exception as e:
        print(f"Warning: Could not clean up temp files: {e}")

    print(f"✓ {len(df)} divisas extraídas correctamente")
    
    return {
        'statusCode': 200,
        'message': f'Divisas BANAMEX extraídas correctamente: {len(df)} divisas',
        'bucket_name': bucket_name,
        'csv_key': csv_key,
        'html_key': html_key
    }


def handler(event, context):
    return asyncio.run(main(event))
