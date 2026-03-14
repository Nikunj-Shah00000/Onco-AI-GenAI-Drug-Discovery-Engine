import json
import boto3
import numpy as np
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import os
import hashlib

region = os.environ.get('AWS_REGION', 'us-east-1')
service = 'aoss'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)

OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']

# Initialize OpenSearch client
client = OpenSearch(
    hosts=[{'host': OPENSEARCH_ENDPOINT.replace('https://', ''), 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

def lambda_handler(event, context):
    """
    Memory Bank for OncoAI
    Stores and retrieves embeddings of failed predictions
    """
    action = event.get('action')
    
    if action == 'query':
        return query_memory(event)
    elif action == 'store':
        return store_memory(event)
    else:
        return {'status': 'error', 'message': 'Invalid action'}

def query_memory(event):
    """Query memory bank for similar failed predictions"""
    candidates = event.get('candidates', [])
    protein_target = event.get('protein_target')
    
    if not candidates:
        return {'memory_context': None}
        
    memory_context = []
    
    for candidate in candidates[:100]:  # Limit to first 100 for performance
        smiles = candidate.get('smiles', '')
        
        # Generate embedding for query
        embedding = generate_embedding(smiles, protein_target)
        
        # Search for similar memories
        query = {
            "size": 10,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": embedding.tolist(),
                        "k": 10
                    }
                }
            }
        }
        
        try:
            response = client.search(
                index='failed-predictions',
                body=query
            )
            
            hits = response['hits']['hits']
            if hits:
                # Extract relevant memory features
                memories = [hit['_source'] for hit in hits]
                memory_context.append({
                    'smiles': smiles,
                    'similar_failures': memories,
                    'similarity_score': hits[0]['_score']
                })
        except Exception as e:
            print(f"Error querying memory: {e}")
            
    return {
        'memory_context': memory_context if memory_context else None
    }

def store_memory(event):
    """Store failed prediction in memory bank"""
    predictions = event.get('predictions', [])
    validation = event.get('validation', [])
    
    stored_count = 0
    
    # Compare predictions with validation to find failures
    for pred, valid in zip(predictions, validation):
        smiles = pred.get('smiles')
        pred_score = pred.get('score', 0)
        valid_score = valid.get('docking_score', 0)
        
        # If prediction was significantly wrong
        if abs(pred_score - valid_score) > 0.3:  # Threshold
            embedding = generate_embedding(smiles, valid.get('protein_target'))
            
            # Store in OpenSearch
            doc = {
                'smiles': smiles,
                'protein_target': valid.get('protein_target'),
                'predicted_score': pred_score,
                'actual_score': valid_score,
                'error_magnitude': abs(pred_score - valid_score),
                'timestamp': context.aws_request_id,
                'embedding': embedding.tolist()
            }
            
            try:
                client.index(
                    index='failed-predictions',
                    body=doc,
                    id=hashlib.md5(f"{smiles}_{valid.get('protein_target')}".encode()).hexdigest()
                )
                stored_count += 1
            except Exception as e:
                print(f"Error storing memory: {e}")
                
    return {
        'status': 'stored',
        'count': stored_count
    }

def generate_embedding(smiles, protein_target):
    """
    Generate embedding vector for molecule-protein pair
    Uses a combination of molecular fingerprints and protein features
    """
    # Generate molecular fingerprint (simplified)
    # In production, use a pre-trained model
    mol_fingerprint = np.random.randn(128)
    
    # Generate protein features
    protein_features = np.random.randn(128)
    
    # Combine
    combined = np.concatenate([mol_fingerprint, protein_features])
    
    # Normalize
    combined = combined / np.linalg.norm(combined)
    
    return combined