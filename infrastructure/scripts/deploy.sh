#!/bin/bash
set -e

echo "=== Zotta Deployment Script ==="

# Check prerequisites
command -v aws >/dev/null 2>&1 || { echo "AWS CLI required. Install: pip install awscli"; exit 1; }
command -v cdk >/dev/null 2>&1 || { echo "AWS CDK required. Install: npm install -g aws-cdk"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Docker required."; exit 1; }

# Build frontend
echo "Building frontend..."
cd "$(dirname "$0")/../../frontend"
npm ci
npm run build

# Deploy CDK stack
echo "Deploying AWS infrastructure..."
cd "$(dirname "$0")/../aws"
pip install -r requirements.txt
cdk deploy --require-approval never

# Get outputs
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ZottaStack --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' --output text)
CF_URL=$(aws cloudformation describe-stacks --stack-name ZottaStack --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontURL`].OutputValue' --output text)

# Upload frontend to S3
echo "Uploading frontend to S3..."
aws s3 sync "$(dirname "$0")/../../frontend/dist" "s3://${BUCKET_NAME}" --delete

echo ""
echo "=== Deployment Complete ==="
echo "Application URL: ${CF_URL}"
echo "Frontend Bucket: ${BUCKET_NAME}"
