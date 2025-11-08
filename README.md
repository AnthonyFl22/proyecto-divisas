# Proyecto Divisas

A data pipeline project for collecting, cleaning, and processing foreign exchange rates from various Mexican financial institutions and data sources.

## Overview

This project implements an ETL (Extract, Transform, Load) pipeline that:
- **Scrapes** exchange rates from multiple financial institutions
- **Cleans** and standardizes the collected data
- **Transforms** the data into a fact table using AWS Glue/Spark
- **Exposes** data through APIs (Banxico integration)

## Project Structure

```
proyecto-divisas/
├── scrapping/          # Web scraping modules for each institution
│   ├── banamex/
│   ├── banregio/
│   ├── bbva/
│   ├── klar/
│   ├── nu/
│   ├── stori/
│   └── wise/
├── cleaning/           # Data cleaning and transformation scripts
│   ├── banxico/
│   ├── klar/
│   ├── nu/
│   └── stori/
├── fact-build/         # AWS Glue jobs for building fact tables
│   └── rates.py        # Spark job for processing rates
├── api/                # API integrations
│   ├── banxico-cetes/
│   └── banxico-divisas/
├── output/             # Output directory for processed data
└── playground/         # Development and testing scripts
```

## Technologies

- **Python 3.13+**
- **Web Scraping**: BeautifulSoup4, Playwright, Cloudscraper, Requests
- **Data Processing**: Pandas, PyArrow, FastParquet
- **Cloud Infrastructure**: AWS (Lambda, Glue, S3)
- **Orchestration**: PySpark for distributed processing

## Key Dependencies

```toml
- beautifulsoup4 >= 4.14.2
- boto3 >= 1.40.65
- cloudscraper >= 1.2.71
- pandas >= 2.3.3
- playwright >= 1.55.0
- pyarrow >= 22.0.0
- requests >= 2.32.5
- s3fs >= 0.4.2
```

## Data Sources

The project collects exchange rates from the following institutions:

- **Banamex**: Traditional banking institution
- **Banregio**: Regional bank
- **BBVA**: International banking group
- **Klar**: Digital bank
- **Nu**: Digital financial services
- **Stori**: Digital credit card provider
- **Wise**: International money transfer service
- **Banxico**: Central Bank of Mexico (official rates)

## Pipeline Architecture

### 1. Scraping Layer
Each institution has its own scraper module (typically Lambda functions) that:
- Extracts exchange rate data
- Handles institution-specific web scraping challenges
- Outputs raw data to staging

### 2. Cleaning Layer
Data cleaning scripts that:
- Standardize data formats
- Validate data quality
- Transform to a common schema

### 3. Fact Building Layer
AWS Glue job (`rates.py`) that:
- Reads silver-tier Parquet files
- Applies business validations
- Deduplicates records
- Creates fact table in gold tier
- Partitions by date for efficient querying

### 4. API Layer
Provides integration with external APIs:
- Banxico CETES rates
- Banxico foreign exchange rates

## Data Flow

```
Raw Data (Scraping) → Silver Layer (Cleaning) → Gold Layer (Fact Build) → Analytics/API
```

## Setup

1. **Install dependencies** (using uv):
```bash
uv sync
```

2. **Install Playwright browsers** (if needed):
```bash
playwright install
```

3. **Configure AWS credentials** for S3 and Glue access

## Usage

The main entry point is intentionally minimal. Each component is designed to run independently:

- **Scrapers**: Deploy as AWS Lambda functions or run locally
- **Cleaners**: Process staged data
- **Fact Builder**: Run as AWS Glue job
- **APIs**: Deploy as Lambda functions with API Gateway

## Development

This project uses:
- **uv** for dependency management
- **Python 3.13** as the runtime
- Docker for containerized deployments (Lambda functions)

## Output Format

The pipeline produces a partitioned fact table (`fact_rates`) with:
- `date`: Rate date
- `entity_id`: Financial institution identifier
- `product_id`: Product type identifier  
- `rate`: Exchange rate value
- `ingestion_ts`: Timestamp of data ingestion
- `source_file`: Original source file
- `business_hash`: SHA-256 hash for auditing
- `dt`: Partition key (YYYY-MM-DD)