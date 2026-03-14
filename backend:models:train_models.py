#!/usr/bin/env python3
"""
Training script for OncoAI models
"""
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
import boto3
import json
import os
import argparse
from generative_model import MoleculeGenerator
from gnn_predictor import GraphNeuralNetwork

class MoleculeDataset(Dataset):
    def __init__(self, smiles_list, protein_targets, affinities):
        self.smiles_list = smiles_list
        self.protein_targets = protein_targets
        self.affinities = affinities
        
    def __len__(self):
        return len(self.smiles_list)
        
    def __getitem__(self, idx):
        return {
            'smiles': self.smiles_list[idx],
            'protein': self.protein_targets[idx],
            'affinity': self.affinities[idx]
        }

def train_generative_model(train_data, val_data, epochs=100):
    """Train the generative model"""
    model = MoleculeGenerator()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss()
    
    best_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        
        for batch in train_data:
            optimizer.zero_grad()
            
            # Forward pass
            logits, mu, log_var = model(
                batch['protein_features'],
                batch['smiles_sequences']
            )
            
            # Reconstruction loss
            recon_loss = criterion(
                logits.view(-1, logits.size(-1)),
                batch['smiles_sequences'].view(-1)
            )
            
            # KL divergence
            kl_loss = -0.5 * torch.sum(1 + log_var - mu.pow(2) - log_var.exp())
            
            # Total loss
            loss = recon_loss + 0.001 * kl_loss
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        avg_loss = total_loss / len(train_data)
        
        # Validation
        val_loss = validate_generative(model, val_data)
        
        print(f"Epoch {epoch}: Train Loss = {avg_loss:.4f}, Val Loss = {val_loss:.4f}")
        
        if val_loss < best_loss:
            best_loss = val_loss
            torch.save(model.state_dict(), 'generative_model_best.pth')
            
    return model

def train_predictor(train_data, val_data, epochs=100):
    """Train the binding affinity predictor"""
    model = GraphNeuralNetwork()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()
    
    best_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        
        for batch in train_data:
            optimizer.zero_grad()
            
            # Forward pass
            predictions = model(
                batch['ligand_graphs'],
                batch['protein_graphs']
            )
            
            # Loss
            loss = criterion(predictions, batch['affinities'])
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        avg_loss = total_loss / len(train_data)
        
        # Validation
        val_loss = validate_predictor(model, val_data)
        
        print(f"Epoch {epoch}: Train Loss = {avg_loss:.4f}, Val Loss = {val_loss:.4f}")
        
        if val_loss < best_loss:
            best_loss = val_loss
            torch.save(model.state_dict(), 'predictor_model_best.pth')
            
    return model

def validate_generative(model, val_data):
    """Validate generative model"""
    model.eval()
    total_loss = 0
    criterion = nn.CrossEntropyLoss()
    
    with torch.no_grad():
        for batch in val_data:
            logits, mu, log_var = model(
                batch['protein_features'],
                batch['smiles_sequences']
            )
            
            recon_loss = criterion(
                logits.view(-1, logits.size(-1)),
                batch['smiles_sequences'].view(-1)
            )
            
            total_loss += recon_loss.item()
            
    return total_loss / len(val_data)

def validate_predictor(model, val_data):
    """Validate predictor model"""
    model.eval()
    total_loss = 0
    criterion = nn.MSELoss()
    
    with torch.no_grad():
        for batch in val_data:
            predictions = model(
                batch['ligand_graphs'],
                batch['protein_graphs']
            )
            loss = criterion(predictions, batch['affinities'])
            total_loss += loss.item()
            
    return total_loss / len(val_data)

def generate_synthetic_data(num_samples=10000):
    """Generate synthetic training data"""
    data = []
    
    common_proteins = ['EGFR', 'BRAF', 'KRAS', 'TP53', 'PIK3CA']
    common_smiles = [
        'CCO',  # Ethanol
        'CCN',  # Ethylamine
        'c1ccccc1',  # Benzene
        'CC(=O)O',  # Acetic acid
        'CN1C=NC2=C1C(=O)N(C(=O)N2C)C'  # Caffeine
    ]
    
    for _ in range(num_samples):
        smiles = np.random.choice(common_smiles)
        protein = np.random.choice(common_proteins)
        affinity = np.random.random()  # Random binding affinity
        
        data.append({
            'smiles': smiles,
            'protein': protein,
            'affinity': affinity
        })
        
    return data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--save-path', type=str, default='/tmp/models/')
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()
    
    # Generate synthetic data
    print("Generating synthetic training data...")
    train_data = generate_synthetic_data(8000)
    val_data = generate_synthetic_data(2000)
    
    # Create data loaders
    train_dataset = MoleculeDataset(
        [d['smiles'] for d in train_data],
        [d['protein'] for d in train_data],
        [d['affinity'] for d in train_data]
    )
    val_dataset = MoleculeDataset(
        [d['smiles'] for d in val_data],
        [d['protein'] for d in val_data],
        [d['affinity'] for d in val_data]
    )
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size)
    
    # Train generative model
    print("\nTraining generative model...")
    generative_model = train_generative_model(train_loader, val_loader, epochs=args.epochs)
    
    # Train predictor model
    print("\nTraining predictor model...")
    predictor_model = train_predictor(train_loader, val_loader, epochs=args.epochs)
    
    # Save models
    os.makedirs(args.save_path, exist_ok=True)
    
    torch.save(generative_model.state_dict(), os.path.join(args.save_path, 'generative_model.pth'))
    torch.save(predictor_model.state_dict(), os.path.join(args.save_path, 'predictor_model.pth'))
    
    print(f"\nModels saved to {args.save_path}")

if __name__ == '__main__':
    main()