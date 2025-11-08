# Banamex Exchange Rates Scraper

AWS Lambda function that scrapes exchange rates from Banamex using Playwright and stores the data in S3.

## Quick Start

```bash
# Build Docker image
docker build -t banamex-scraper .

# Deploy to AWS Lambda
./deploy.sh  # See DEPLOYMENT.md for setup
```

## Files

- `lambda_function.py` - Main Lambda handler with Playwright scraper
- `Dockerfile` - Container image definition for AWS Lambda
- `requirements.txt` - Python dependencies
- `DEPLOYMENT.md` - Complete deployment guide
- `TROUBLESHOOTING.md` - Issue resolution guide
- `CHANGES.md` - Detailed changelog

## Features

- 🔄 Scrapes USD, EUR, GBP, and JPY exchange rates
- 📦 Stores CSV data and raw HTML in S3
- 🐳 Containerized for AWS Lambda
- ⚡ Optimized for Lambda environment
- 📊 Comprehensive logging
- 🛡️ Error handling and recovery

## Data Output

### CSV Format
```csv
divisa,compra,venta,fetched_at,source_url
USD,17.50,18.00,2025-11-05T10:00:00,https://...
EURO,19.20,19.80,2025-11-05T10:00:00,https://...
```

### S3 Structure
```
scrapping-divisas/
└── banamex/
    ├── banamex_divisas_20251105_100000.csv
    └── banamex_raw_20251105_100000.html.gz
```

## Lambda Configuration

**Memory**: 2048 MB  
**Timeout**: 300 seconds  
**Runtime**: Python 3.12 (Container)  

## Usage

### Manual Invocation
```bash
aws lambda invoke \
  --function-name banamex-scraper \
  --region us-east-1 \
  response.json
```

### Scheduled Execution
Configured via EventBridge (see DEPLOYMENT.md)

## Dependencies

- Python 3.12
- Playwright (with Chromium)
- Pandas
- Boto3

## Documentation

- 📘 **[DEPLOYMENT.md](DEPLOYMENT.md)** - How to deploy to AWS
- 🔧 **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- 📝 **[CHANGES.md](CHANGES.md)** - What changed and why

## Troubleshooting

If you encounter browser launch errors, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## License

Internal use only.


