import json
import sys
import os

# Add models to path
sys.path.append('/opt')
from models.generative_model import GenerativeModel, lambda_handler as model_handler

def lambda_handler(event, context):
    """
    Wrapper for generative model
    """
    # Extract parameters
    protein_target = event.get('protein_target')
    num_molecules = event.get('num_molecules', 10000)
    
    # Get protein sequence (in production, fetch from database)
    protein_sequence = f"SEQUENCE_FOR_{protein_target}"
    
    # Call the model
    result = model_handler({
        'protein_sequence': protein_sequence,
        'num_molecules': num_molecules,
        'model_path': os.environ.get('MODEL_PATH')
    }, context)
    
    return result