#!/bin/bash
# Deployment script for Weekly Account-News Automation

set -e  # Exit on error

echo "======================================"
echo "Weekly News Automation - Deployment"
echo "======================================"

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo "Error: AWS SAM CLI is not installed."
    echo "Install it from: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS CLI is not configured."
    echo "Run: aws configure"
    exit 1
fi

echo ""
echo "Step 1: Validating template..."
sam validate --lint

echo ""
echo "Step 2: Building application..."
sam build

echo ""
echo "Step 3: Deploying to AWS..."

# Check if this is first deployment
if [ "$1" == "--guided" ]; then
    echo "Running guided deployment..."
    sam deploy --guided
else
    echo "Using existing samconfig.toml..."
    sam deploy
fi

echo ""
echo "======================================"
echo "Deployment complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Verify secrets in AWS Secrets Manager"
echo "2. Test with: aws lambda invoke --function-name WeeklyNewsFunction --payload '{\"dry_run\": true}' response.json"
echo "3. Check CloudWatch Logs: aws logs tail /aws/lambda/WeeklyNewsFunction --follow"
echo ""
