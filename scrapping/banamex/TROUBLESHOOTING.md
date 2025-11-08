# Banamex Scraper - Lambda Troubleshooting Guide

## Issue: Browser.new_page: Target page, context or browser has been closed

### Root Cause
This error occurs when Playwright's Chromium browser fails to launch properly in AWS Lambda's containerized environment. The browser may launch but immediately close due to:

1. Missing critical launch arguments for containerized environments
2. Incorrect or missing Chromium executable path
3. Missing system dependencies
4. Memory/resource constraints

### Solutions Implemented

#### 1. Critical Browser Launch Arguments

Added essential flags for Lambda compatibility:

- `--no-sandbox` - Required for containerized environments
- `--disable-setuid-sandbox` - Disables SUID sandbox
- `--disable-dev-shm-usage` - Prevents shared memory issues (/dev/shm size limitation)
- `--no-zygote` - Disables zygote process
- `--single-process` - **CRITICAL** - Runs Chromium in single process mode
- `--disable-gpu` - Disables GPU hardware acceleration
- `--disable-features=IsolateOrigins,site-per-process` - Disables site isolation

#### 2. Environment Variables

Set in both Dockerfile and Python code:

```bash
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
HOME=/tmp
```

#### 3. Dynamic Chromium Path Detection

Implemented `find_chromium_executable()` function that:
- Searches multiple possible Chromium locations
- Uses glob patterns to find version-specific paths
- Falls back gracefully if not found

#### 4. Dockerfile Improvements

- Explicitly install Playwright browsers in both build stages
- Install browser dependencies with `playwright install-deps chromium`
- Use Microsoft's Playwright Python base image
- Set environment variables at container level

### Debugging Steps

If the error persists, check CloudWatch logs for:

1. **Python version**: Should match container expectations
```
Python version: 3.12.x
```

2. **Chromium path**: Should find executable
```
Found Chromium at: /ms-playwright/chromium-XXXX/chrome-linux/chrome
```

3. **Browser launch**: Should succeed
```
Browser launched successfully
```

### Common Additional Issues

#### Issue: Timeout during browser launch
**Solution**: Increase timeout in launch_options:
```python
'timeout': 60000,  # Increase to 60 seconds
```

#### Issue: Memory limit exceeded
**Solution**: 
- Increase Lambda memory allocation (minimum 1024MB recommended, 2048MB better)
- Use `--single-process` flag (already implemented)

#### Issue: Chromium crashes immediately
**Solution**:
- Check CloudWatch logs for missing dependencies
- Verify Playwright installation in container
- Test locally with Docker first:
```bash
docker build -t banamex-scraper .
docker run -it banamex-scraper bash
# Inside container:
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.launch())"
```

#### Issue: /dev/shm too small
**Solution**: Already handled with `--disable-dev-shm-usage` flag

### Testing Locally with Docker

```bash
# Build the container
cd scrapping/banamex
docker build -t banamex-scraper .

# Run interactively
docker run -it banamex-scraper bash

# Inside container, test Playwright
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    print('Browser launched successfully!')
    browser.close()
"
```

### Lambda Configuration Requirements

**Memory**: 2048 MB (minimum 1024 MB)
**Timeout**: 300 seconds (5 minutes) - scraping can take time
**Ephemeral storage**: 512 MB default should be sufficient

### Environment Variables to Set in Lambda

If still having issues, add these to Lambda configuration:

```
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
HOME=/tmp
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
```

### Architecture Considerations

- **Container Size**: ~1.5-2 GB (Playwright + Chromium)
- **Cold Start**: 10-20 seconds due to container size
- **Warm Start**: 2-5 seconds
- **Execution Time**: 30-60 seconds typical

### Alternative Solutions (If Issues Persist)

1. **Use Playwright AWS Lambda Layer**
   - Pre-built layer with Chromium
   - Reduces deployment package size
   
2. **Use Selenium with Chrome for Lambda**
   - Alternative browser automation
   - More Lambda deployment examples

3. **Use HTTP-only scraping**
   - If JavaScript rendering not critical
   - Much lighter weight
   - Faster execution

4. **Use AWS Fargate**
   - More resources available
   - Better for long-running scrapes
   - No execution time limit

### Additional Debugging Commands

Add these to lambda_function.py for more debug info:

```python
# Check available memory
import resource
print(f"Memory limit: {resource.getrlimit(resource.RLIMIT_AS)}")

# Check disk space
import shutil
print(f"Disk usage: {shutil.disk_usage('/tmp')}")

# List Playwright installation
import subprocess
result = subprocess.run(['playwright', 'install', '--dry-run'], capture_output=True)
print(result.stdout.decode())
```

### References

- [Playwright in Docker](https://playwright.dev/python/docs/docker)
- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Chromium Command Line Switches](https://peter.sh/experiments/chromium-command-line-switches/)


