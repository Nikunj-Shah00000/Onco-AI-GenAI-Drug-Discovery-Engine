#!/bin/bash

# OncoAI Deployment Script
set -e

echo "🚀 Starting OncoAI Deployment..."

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
STACK_NAME=${STACK_NAME:-OncoAIStack}
S3_BUCKET=${S3_BUCKET:-oncoai-deployment-$(date +%s)}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

command -v aws >/dev/null 2>&1 || { echo -e "${RED}AWS CLI required but not installed. Aborting.${NC}" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo -e "${RED}Node.js required but not installed. Aborting.${NC}" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo -e "${RED}npm required but not installed. Aborting.${NC}" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker required but not installed. Aborting.${NC}" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Python3 required but not installed. Aborting.${NC}" >&2; exit 1; }

# Create deployment bucket
echo -e "${YELLOW}Creating deployment bucket: ${S3_BUCKET}${NC}"
aws s3 mb s3://${S3_BUCKET} --region ${AWS_REGION}

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"

# Backend dependencies
pip install -r infrastructure/docker/docking/requirements.txt -t /tmp/python/
pip install torch torch-geometric boto3 rdkit-pypi -t /tmp/python/

# Package Lambda layers
echo -e "${YELLOW}Packaging Lambda layers...${NC}"
cd /tmp
zip -r9 lambda-layer.zip python/
aws s3 cp lambda-layer.zip s3://${S3_BUCKET}/layers/
cd -

# Build Docker images
echo -e "${YELLOW}Building Docker images...${NC}"
cd infrastructure/docker/docking
docker build -t oncoai-docking .
docker tag oncoai-docking:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/oncoai-docking:latest
cd -

# Build frontend
echo -e "${YELLOW}Building frontend...${NC}"
cd frontend
npm install
npm run build
aws s3 sync build/ s3://${S3_BUCKET}/frontend/
cd -

# Package CloudFormation templates
echo -e "${YELLOW}Packaging CloudFormation...${NC}"
cd infrastructure/cdk
npm install
npm run build
cdk bootstrap
cdk synth --output=./dist

# Deploy CDK stack
echo -e "${YELLOW}Deploying CDK stack...${NC}"
cdk deploy --require-approval never \
  --parameters S3BucketName=${S3_BUCKET} \
  --outputs-file ./stack-outputs.json

# Get stack outputs
API_ENDPOINT=$(jq -r '."OncoAIStack".APIEndpoint' stack-outputs.json)
STATE_MACHINE_ARN=$(jq -r '."OncoAIStack".StateMachineArn' stack-outputs.json)

# Upload initial models
echo -e "${YELLOW}Uploading pre-trained models...${NC}"
python3 backend/models/train_models.py --save-path /tmp/models/
aws s3 sync /tmp/models/ s3://${S3_BUCKET}/models/

# Create OpenSearch index
echo -e "${YELLOW}Creating OpenSearch index...${NC}"
python3 -c "
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import json

region = '${AWS_REGION}'
service = 'aoss'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)

# Get OpenSearch endpoint from stack outputs
endpoint = '$(jq -r '."OncoAIStack".OpenSearchEndpoint' stack-outputs.json)'

client = OpenSearch(
    hosts=[{'host': endpoint, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

# Create index with mappings
index_body = {
    'settings': {
        'index.knn': True
    },
    'mappings': {
        'properties': {
            'embedding': {
                'type': 'knn_vector',
                'dimension': 256
            },
            'smiles': {'type': 'text'},
            'protein_target': {'type': 'keyword'},
            'predicted_score': {'type': 'float'},
            'actual_score': {'type': 'float'},
            'timestamp': {'type': 'date'}
        }
    }
}

client.indices.create(index='failed-predictions', body=index_body, ignore=400)
"

# Configure API Gateway
echo -e "${YELLOW}Configuring API Gateway...${NC}"
aws apigateway create-deployment \
  --rest-api-id $(echo ${API_ENDPOINT} | cut -d'/' -f3) \
  --stage-name prod

# Deploy frontend to Amplify or S3/CloudFront
echo -e "${YELLOW}Deploying frontend...${NC}"
cd frontend
REACT_APP_API_ENDPOINT=${API_ENDPOINT} npm run build
aws s3 sync build/ s3://${S3_BUCKET}-web/
aws s3 website s3://${S3_BUCKET}-web/ --index-document index.html --error-document error.html

# Create CloudFront distribution
DISTRIBUTION_ID=$(aws cloudfront create-distribution \
  --origin-domain-name ${S3_BUCKET}-web.s3-website-${AWS_REGION}.amazonaws.com \
  --default-root-object index.html \
  --query 'Distribution.Id' \
  --output text)

# Output deployment info
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${GREEN}=================================${NC}"
echo -e "API Endpoint: ${API_ENDPOINT}"
echo -e "Frontend URL: http://${S3_BUCKET}-web.s3-website-${AWS_REGION}.amazonaws.com"
echo -e "State Machine: ${STATE_MACHINE_ARN}"
echo -e "CloudFront: https://${DISTRIBUTION_ID}.cloudfront.net"
echo -e "${GREEN}=================================${NC}"

# Create test campaign
echo -e "${YELLOW}Creating test campaign...${NC}"
curl -X POST ${API_ENDPOINT}/campaign \
  -H "Content-Type: application/json" \
  -d '{
    "protein_target": "EGFR",
    "name": "Test Campaign",
    "num_molecules": 1000
  }'

echo -e "${GREEN}Test campaign started! Check the dashboard for results.${NC}"