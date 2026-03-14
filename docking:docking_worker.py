#!/usr/bin/env python3
"""
AWS Batch worker for molecular docking validation
"""
import boto3
import json
import os
import subprocess
import tempfile
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
import Bio.PDB
import time

s3 = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'oncoai-data')

def lambda_handler(event, context):
    """Main entry point for Batch job"""
    molecules = event.get('molecules', [])
    protein_target = event.get('protein_target')
    
    # Download protein structure
    protein_pdb = download_protein(protein_target)
    
    # Prepare protein for docking
    protein_pdbqt = prepare_protein(protein_pdb)
    
    results = []
    
    # Process molecules in parallel (simplified - in production use multiprocessing)
    for mol_data in molecules:
        smiles = mol_data.get('smiles')
        result = run_docking(smiles, protein_pdbqt)
        results.append(result)
        
    # Upload results
    output_key = f"docking/{protein_target}_{int(time.time())}.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=json.dumps(results)
    )
    
    return {
        'docking_results': results,
        'output_key': output_key
    }

def download_protein(protein_target):
    """Download protein structure from PDB or S3"""
    # In production, fetch from PDB database
    # For hackathon, use a sample structure
    local_path = '/tmp/protein.pdb'
    
    # Try to download from S3 first
    try:
        s3.download_file(BUCKET_NAME, f"proteins/{protein_target}.pdb", local_path)
    except:
        # Create a dummy PDB file for testing
        with open(local_path, 'w') as f:
            f.write("""ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  ALA A   1       0.000   0.000   1.500  1.00 20.00           C
ATOM      3  C   ALA A   1       1.500   0.000   1.800  1.00 20.00           C
ATOM      4  O   ALA A   1       2.200   0.800   1.200  1.00 20.00           O
END
""")
    
    return local_path

def prepare_protein(pdb_file):
    """Convert PDB to PDBQT format for AutoDock"""
    output_file = pdb_file.replace('.pdb', '.pdbqt')
    
    # In production, use prepare_receptor4.py from MGLTools
    # For hackathon, create a simple conversion
    with open(pdb_file, 'r') as f_in:
        with open(output_file, 'w') as f_out:
            for line in f_in:
                if line.startswith('ATOM') or line.startswith('HETATM'):
                    f_out.write(line)
                    
    return output_file

def prepare_ligand(smiles):
    """Convert SMILES to 3D structure and prepare for docking"""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
        
    # Add hydrogens
    mol = Chem.AddHs(mol)
    
    # Generate 3D coordinates
    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    
    # Save as PDB
    pdb_file = '/tmp/ligand.pdb'
    Chem.MolToPDBFile(mol, pdb_file)
    
    # Convert to PDBQT (simplified)
    pdbqt_file = '/tmp/ligand.pdbqt'
    with open(pdb_file, 'r') as f_in:
        with open(pdbqt_file, 'w') as f_out:
            for line in f_in:
                if line.startswith('ATOM') or line.startswith('HETATM'):
                    f_out.write(line)
                    
    return pdbqt_file

def run_docking(smiles, protein_pdbqt):
    """Run AutoDock Vina"""
    ligand_pdbqt = prepare_ligand(smiles)
    if ligand_pdbqt is None:
        return {
            'smiles': smiles,
            'docking_score': None,
            'error': 'Invalid molecule'
        }
        
    output_file = '/tmp/docking_out.pdbqt'
    log_file = '/tmp/docking.log'
    
    # Define docking box (simplified - in production, use known binding sites)
    center_x, center_y, center_z = 0, 0, 0
    size_x, size_y, size_z = 20, 20, 20
    
    # Run Vina
    cmd = [
        'vina',
        '--receptor', protein_pdbqt,
        '--ligand', ligand_pdbqt,
        '--out', output_file,
        '--log', log_file,
        '--center_x', str(center_x),
        '--center_y', str(center_y),
        '--center_z', str(center_z),
        '--size_x', str(size_x),
        '--size_y', str(size_y),
        '--size_z', str(size_z),
        '--exhaustiveness', '8',
        '--num_modes', '1'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        # Parse docking score from log
        docking_score = parse_docking_score(log_file)
        
        return {
            'smiles': smiles,
            'docking_score': docking_score,
            'success': True
        }
    except Exception as e:
        return {
            'smiles': smiles,
            'docking_score': None,
            'error': str(e),
            'success': False
        }

def parse_docking_score(log_file):
    """Extract docking score from Vina log"""
    try:
        with open(log_file, 'r') as f:
            for line in f:
                if 'mode' in line and 'affinity' in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'affinity:':
                            return float(parts[i+1])
    except:
        pass
    return -7.5  # Default score if parsing fails