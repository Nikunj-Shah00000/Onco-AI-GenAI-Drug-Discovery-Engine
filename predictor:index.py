import json
import sys
import os

sys.path.append('/opt')
from models.gnn_predictor import BindingPredictor, lambda_handler as model_handler

def lambda_handler(event, context):
    """
    Wrapper for binding affinity predictor
    """
    molecules = event.get('molecules', [])
    protein_target = event.get('protein_target')
    memory_context = event.get('memory_context')
    
    # Extract SMILES strings
    smiles_list = [m.get('smiles') for m in molecules]
    
    # Call the model
    result = model_handler({
        'molecules': smiles_list,
        'protein_target': protein_target,
        'memory_context': memory_context,
        'model_path': os.environ.get('MODEL_PATH')
    }, context)
    
    return result