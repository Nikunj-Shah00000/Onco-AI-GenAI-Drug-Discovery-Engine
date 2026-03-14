import json
import boto3
import uuid
import time
from datetime import datetime
import os

dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')
s3 = boto3.client('s3')

CAMPAIGNS_TABLE = os.environ['CAMPAIGNS_TABLE']
BUCKET_NAME = os.environ['BUCKET_NAME']
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN', 'arn:aws:states:us-east-1:123456789012:stateMachine:OncoAIWorkflow')

def lambda_handler(event, context):
    """
    Main orchestrator for OncoAI
    Handles API requests and workflow coordination
    """
    http_method = event.get('httpMethod', 'POST')
    path = event.get('path', '')
    
    if http_method == 'POST' and path == '/campaign':
        return start_campaign(event)
    elif http_method == 'GET' and path.startswith('/campaign/'):
        campaign_id = path.split('/')[-1]
        return get_campaign_status(campaign_id)
    elif event.get('action') == 'notify':
        return notify_completion(event)
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid request'})
        }

def start_campaign(event):
    """Start a new drug discovery campaign"""
    try:
        body = json.loads(event.get('body', '{}'))
        protein_target = body.get('protein_target')
        campaign_name = body.get('name', f"Campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        if not protein_target:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'protein_target is required'})
            }
        
        # Generate campaign ID
        campaign_id = str(uuid.uuid4())
        
        # Store initial campaign data
        table = dynamodb.Table(CAMPAIGNS_TABLE)
        table.put_item(Item={
            'campaignId': campaign_id,
            'name': campaign_name,
            'protein_target': protein_target,
            'status': 'INITIATED',
            'createdAt': datetime.now().isoformat(),
            'parameters': body
        })
        
        # Start Step Functions execution
        response = stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"campaign_{campaign_id}",
            input=json.dumps({
                'campaign_id': campaign_id,
                'protein_target': protein_target,
                'parameters': body
            })
        )
        
        # Update with execution ARN
        table.update_item(
            Key={'campaignId': campaign_id},
            UpdateExpression='SET executionArn = :arn',
            ExpressionAttributeValues={':arn': response['executionArn']}
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'campaign_id': campaign_id,
                'status': 'INITIATED',
                'message': 'Campaign started successfully'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_campaign_status(campaign_id):
    """Get status of a campaign"""
    try:
        table = dynamodb.Table(CAMPAIGNS_TABLE)
        response = table.get_item(Key={'campaignId': campaign_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Campaign not found'})
            }
            
        campaign = response['Item']
        
        # Get results from S3 if available
        results = None
        if campaign.get('status') == 'COMPLETED':
            try:
                result_key = f"results/{campaign_id}/top_candidates.json"
                result_obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                results = json.loads(result_obj['Body'].read())
            except:
                pass
                
        return {
            'statusCode': 200,
            'body': json.dumps({
                'campaign': campaign,
                'results': results
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def notify_completion(event):
    """Handle workflow completion notification"""
    campaign_id = event.get('campaign_id')
    results = event.get('results', {})
    
    # Update DynamoDB
    table = dynamodb.Table(CAMPAIGNS_TABLE)
    table.update_item(
        Key={'campaignId': campaign_id},
        UpdateExpression='SET #status = :status, completedAt = :completedAt',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':status': 'COMPLETED',
            ':completedAt': datetime.now().isoformat()
        }
    )
    
    # Store results in S3
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"results/{campaign_id}/top_candidates.json",
        Body=json.dumps(results)
    )
    
    # In production, send notification via SNS/SES
    print(f"Campaign {campaign_id} completed with {len(results.get('candidates', []))} candidates")
    
    return {'status': 'notified'}