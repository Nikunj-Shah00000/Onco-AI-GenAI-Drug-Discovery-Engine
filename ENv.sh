# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Application Configuration
REACT_APP_API_ENDPOINT=https://your-api-gateway-url.amazonaws.com/prod

# Model Paths
GENERATIVE_MODEL_PATH=s3://oncoai-models/generative_model.pth
PREDICTOR_MODEL_PATH=s3://oncoai-models/predictor_model.pth

# Database
CAMPAIGNS_TABLE=OncoAI-Campaigns
MEMORY_INDEX=failed-predictions

# OpenSearch
OPENSEARCH_ENDPOINT=https://your-opensearch-endpoint.us-east-1.aoss.amazonaws.com

# S3 Buckets
DATA_BUCKET=oncoai-data
MODEL_BUCKET=oncoai-models
RESULTS_BUCKET=oncoai-results