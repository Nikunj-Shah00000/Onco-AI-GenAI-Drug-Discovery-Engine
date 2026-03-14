import json
import numpy as np
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski

def lambda_handler(event, context):
    """
    Check toxicity and drug-likeness of molecules
    """
    molecules = event.get('molecules', [])
    
    safe_molecules = []
    
    for mol_data in molecules:
        smiles = mol_data.get('smiles')
        score = mol_data.get('score', 0)
        
        # Convert to RDKit molecule
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
            
        # Lipinski's Rule of Five
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd = Lipinski.NumHDonors(mol)
        hba = Lipinski.NumHAcceptors(mol)
        
        lipinski_violations = 0
        if mw > 500: lipinski_violations += 1
        if logp > 5: lipinski_violations += 1
        if hbd > 5: lipinski_violations += 1
        if hba > 10: lipinski_violations += 1
        
        # Toxicity prediction (simplified)
        # In production, use a pre-trained toxicity model
        toxicity_score = predict_toxicity(smiles)
        
        # Combined safety score
        safety_score = 1.0 - (lipinski_violations / 4.0) - (toxicity_score * 0.5)
        
        if safety_score > 0.3:  # Threshold for safe molecules
            safe_molecules.append({
                'smiles': smiles,
                'binding_score': score,
                'safety_score': safety_score,
                'lipinski_violations': lipinski_violations,
                'toxicity_score': toxicity_score,
                'properties': {
                    'mw': mw,
                    'logp': logp,
                    'hbd': hbd,
                    'hba': hba
                }
            })
            
    # Sort by combined score
    safe_molecules.sort(
        key=lambda x: x['binding_score'] * x['safety_score'], 
        reverse=True
    )
    
    return {
        'statusCode': 200,
        'safe_molecules': safe_molecules[:100]  # Top 100 safe molecules
    }

def predict_toxicity(smiles):
    """
    Predict toxicity probability (0-1)
    Simplified version - in production use a neural network
    """
    # Use molecular properties as features
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return 0.5
        
    # Simple heuristic based on functional groups
    toxic_groups = ['[N+](=O)[O-]', 'c1ccccc1N', 'C#N']
    toxicity = 0.0
    
    for group in toxic_groups:
        pattern = Chem.MolFromSmarts(group)
        if mol.HasSubstructMatch(pattern):
            toxicity += 0.3
            
    return min(toxicity, 1.0)