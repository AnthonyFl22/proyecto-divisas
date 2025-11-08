# Banamex Scraper - AWS Lambda Deployment Guide

## Prerequisites

- Docker installed and running
- AWS CLI configured with appropriate credentials
- AWS ECR repository created
- AWS Lambda function created (or will be created)
- Sufficient permissions to push to ECR and update Lambda

## Step 1: Create ECR Repository (if not exists)

```bash
aws ecr create-repository --repository-name banamex-scraper --region us-east-1
```

Save the repository URI from the output:
```
123456789012.dkr.ecr.us-east-1.amazonaws.com/banamex-scraper
```

## Step 2: Build Docker Image

Navigate to the banamex directory:

```bash
cd scrapping/banamex
```

Build the Docker image:

```bash
docker build -t banamex-scraper:latest .
```

**Note**: This build will take 5-10 minutes due to Playwright browser installation.

Expected output shows:
- Installing dependencies
- Installing Playwright
- Installing Chromium browser
- Verification steps

## Step 3: Test Locally (Recommended)

Before deploying, test the container locally:

```bash
# Run interactively to test
docker run -it --rm \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e AWS_DEFAULT_REGION=us-east-1 \
  banamex-scraper:latest \
  python lambda_function.py
```

Or test the Lambda handler directly:

```bash
docker run -it --rm \
  -p 9000:8080 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  banamex-scraper:latest

# In another terminal:
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{}'
```

## Step 4: Authenticate with ECR

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com
```

Replace `123456789012` with your AWS account ID and `us-east-1` with your region.

## Step 5: Tag and Push Image

```bash
# Tag the image
docker tag banamex-scraper:latest \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/banamex-scraper:latest

# Push to ECR
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/banamex-scraper:latest
```

## Step 6: Create/Update Lambda Function

### Option A: Create New Lambda Function

```bash
aws lambda create-function \
  --function-name banamex-scraper \
  --package-type Image \
  --code ImageUri=123456789012.dkr.ecr.us-east-1.amazonaws.com/banamex-scraper:latest \
  --role arn:aws:iam::123456789012:role/lambda-execution-role \
  --memory-size 2048 \
  --timeout 300 \
  --region us-east-1
```

### Option B: Update Existing Lambda Function

```bash
aws lambda update-function-code \
  --function-name banamex-scraper \
  --image-uri 123456789012.dkr.ecr.us-east-1.amazonaws.com/banamex-scraper:latest \
  --region us-east-1
```

## Step 7: Configure Lambda Settings

### Memory and Timeout

```bash
aws lambda update-function-configuration \
  --function-name banamex-scraper \
  --memory-size 2048 \
  --timeout 300 \
  --region us-east-1
```

**Recommended Settings:**
- **Memory**: 2048 MB (minimum 1024 MB, but 2048 MB for better performance)
- **Timeout**: 300 seconds (5 minutes)
- **Ephemeral Storage**: 512 MB (default is fine)

### Environment Variables (Optional)

If needed, set additional environment variables:

```bash
aws lambda update-function-configuration \
  --function-name banamex-scraper \
  --environment Variables={PLAYWRIGHT_BROWSERS_PATH=/ms-playwright,HOME=/tmp} \
  --region us-east-1
```

## Step 8: Set Up IAM Role

The Lambda execution role needs:

1. **Basic Lambda execution permissions**
2. **S3 write permissions** for the target bucket

Example policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::scrapping-divisas/banamex/*"
    }
  ]
}
```

## Step 9: Test Lambda Function

Test the deployed function:

```bash
aws lambda invoke \
  --function-name banamex-scraper \
  --region us-east-1 \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  response.json | base64 --decode

# View the response
cat response.json
```

## Step 10: Set Up CloudWatch Logging

Monitor the function:

```bash
# View recent logs
aws logs tail /aws/lambda/banamex-scraper --follow

# View logs from specific time
aws logs tail /aws/lambda/banamex-scraper --since 1h
```

## Step 11: Set Up Scheduled Execution (Optional)

Create an EventBridge rule to run the scraper on a schedule:

```bash
# Create rule (runs every day at 9 AM UTC)
aws events put-rule \
  --name banamex-scraper-daily \
  --schedule-expression "cron(0 9 * * ? *)" \
  --region us-east-1

# Add Lambda as target
aws events put-targets \
  --rule banamex-scraper-daily \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:123456789012:function:banamex-scraper" \
  --region us-east-1

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name banamex-scraper \
  --statement-id banamex-scraper-daily \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:123456789012:rule/banamex-scraper-daily \
  --region us-east-1
```

## Quick Update Script

Create a script for quick deployments (`deploy.sh`):

```bash
#!/bin/bash
set -e

REGION="us-east-1"
ACCOUNT_ID="123456789012"
REPO_NAME="banamex-scraper"
FUNCTION_NAME="banamex-scraper"

# Build
echo "Building Docker image..."
docker build -t ${REPO_NAME}:latest .

# Test locally (optional)
# echo "Testing locally..."
# docker run --rm ${REPO_NAME}:latest python -c "import playwright; print('OK')"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region ${REGION} | \
  docker login --username AWS --password-stdin \
  ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Tag and push
echo "Pushing to ECR..."
docker tag ${REPO_NAME}:latest \
  ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:latest
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:latest

# Update Lambda
echo "Updating Lambda function..."
aws lambda update-function-code \
  --function-name ${FUNCTION_NAME} \
  --image-uri ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:latest \
  --region ${REGION}

echo "Deployment complete!"
echo "Testing function..."
aws lambda invoke \
  --function-name ${FUNCTION_NAME} \
  --region ${REGION} \
  --log-type Tail \
  response.json

cat response.json
```

Make it executable:

```bash
chmod +x deploy.sh
```

## Troubleshooting Deployment

### Image Too Large
- Current image size: ~1.5-2 GB (normal for Playwright)
- Lambda supports up to 10 GB container images
- No action needed unless approaching limit

### Push Timeout
- ECR push can take 10-15 minutes
- Ensure stable internet connection
- Consider using AWS CodeBuild for CI/CD

### Lambda Update Pending
- Wait for update to complete before testing
- Check status:
  ```bash
  aws lambda get-function --function-name banamex-scraper
  ```

### Permission Denied
- Verify AWS credentials are correct
- Check IAM role has ECR and Lambda permissions
- Verify Lambda execution role has S3 permissions

## Monitoring and Alerts

Set up CloudWatch alarms for:

1. **Function Errors**
2. **Function Duration** (approaching timeout)
3. **Throttles**
4. **Concurrent Executions**

Example alarm for errors:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name banamex-scraper-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=banamex-scraper
```

## Cost Considerations

**Estimated monthly costs (with daily execution):**
- Lambda execution: ~$5-10/month (2048 MB, 60s avg execution)
- ECR storage: ~$1/month
- S3 storage: ~$0.50/month
- Data transfer: ~$1/month
- **Total**: ~$7-13/month

**Cost optimization:**
- Use scheduled execution instead of continuous
- Reduce memory if possible (test with 1024 MB)
- Set up S3 lifecycle policies for old data
- Use CloudWatch Logs retention policies

## Next Steps

1. Set up monitoring and alerting
2. Create data pipeline for scraped data
3. Set up data validation
4. Create dashboards for exchange rates
5. Implement error notifications (SNS/email)


