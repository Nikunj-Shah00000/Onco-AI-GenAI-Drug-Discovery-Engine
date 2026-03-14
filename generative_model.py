import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
import boto3
import json

class MoleculeGenerator(nn.Module):
    """
    Conditional Variational Autoencoder (CVAE) for generating novel molecules
    conditioned on target protein features
    """
    def __init__(self, latent_dim=128, max_smiles_len=100, vocab_size=64):
        super().__init__()
        self.latent_dim = latent_dim
        self.max_len = max_smiles_len
        self.vocab_size = vocab_size
        
        # Protein encoder (conditioning)
        self.protein_encoder = nn.Sequential(
            nn.Linear(1024, 512),  # Input: protein fingerprint
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU()
        )
        
        # Molecule encoder (SMILES)
        self.encoder_lstm = nn.LSTM(
            input_size=64,
            hidden_size=256,
            num_layers=2,
            batch_first=True,
            bidirectional=True
        )
        self.encoder_fc = nn.Linear(512, 2 * latent_dim)  # mean and log_var
        
        # Decoder
        self.decoder_fc = nn.Linear(latent_dim + 256, 512)
        self.decoder_lstm = nn.LSTM(512, 256, 2, batch_first=True)
        self.decoder_output = nn.Linear(256, vocab_size)
        
    def reparameterize(self, mu, log_var):
        std = torch.exp(0.5 * log_var)
        eps = torch.randn_like(std)
        return mu + eps * std
    
    def forward(self, protein_features, smiles_sequences=None):
        # Encode protein condition
        protein_encoded = self.protein_encoder(protein_features)
        
        if self.training and smiles_sequences is not None:
            # Encode SMILES
            lstm_out, (h, c) = self.encoder_lstm(smiles_sequences)
            encoded = lstm_out[:, -1, :]  # Last timestep
            stats = self.encoder_fc(encoded)
            mu, log_var = stats.chunk(2, dim=-1)
            z = self.reparameterize(mu, log_var)
            
            # Decode with conditioning
            decoder_input = torch.cat([z, protein_encoded], dim=-1)
            decoder_hidden = self.decoder_fc(decoder_input).unsqueeze(0).repeat(2, 1, 1)
            
            # Teacher forcing
            output, _ = self.decoder_lstm(smiles_sequences, 
                                          (decoder_hidden, torch.zeros_like(decoder_hidden)))
            logits = self.decoder_output(output)
            
            return logits, mu, log_var
        else:
            # Generation mode
            z = torch.randn(protein_features.size(0), self.latent_dim).to(protein_features.device)
            decoder_input = torch.cat([z, protein_encoded], dim=-1)
            decoder_hidden = self.decoder_fc(decoder_input).unsqueeze(0).repeat(2, 1, 1)
            
            generated = []
            current_token = torch.zeros(protein_features.size(0), 1, self.vocab_size).to(protein_features.device)
            current_token[:, :, self.vocab_size-1] = 1  # Start token
            
            for _ in range(self.max_len):
                output, (decoder_hidden, _) = self.decoder_lstm(current_token, 
                                                                (decoder_hidden, 
                                                                 torch.zeros_like(decoder_hidden)))
                logits = self.decoder_output(output)
                probs = torch.softmax(logits, dim=-1)
                next_token = torch.multinomial(probs.squeeze(1), 1)
                
                # Convert to one-hot
                next_onehot = torch.zeros(protein_features.size(0), 1, self.vocab_size).to(protein_features.device)
                next_onehot.scatter_(2, next_token.unsqueeze(-1), 1)
                current_token = next_onehot
                generated.append(next_token)
            
            return torch.cat(generated, dim=1)

class GenerativeModel:
    def __init__(self, model_path=None):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = MoleculeGenerator().to(self.device)
        if model_path:
            self.load_model(model_path)
        self.s3 = boto3.client('s3')
        
    def load_model(self, path):
        if path.startswith('s3://'):
            bucket, key = path.replace('s3://', '').split('/', 1)
            local_path = '/tmp/model.pth'
            self.s3.download_file(bucket, key, local_path)
            self.model.load_state_dict(torch.load(local_path, map_location=self.device))
        else:
            self.model.load_state_dict(torch.load(path, map_location=self.device))
            
    def generate_molecules(self, protein_sequence, num_molecules=10000, temperature=1.0):
        """Generate novel molecules for target protein"""
        # Convert protein sequence to features
        protein_features = self.encode_protein(protein_sequence)
        protein_tensor = torch.FloatTensor(protein_features).unsqueeze(0).to(self.device)
        protein_tensor = protein_tensor.repeat(min(num_molecules, 100), 1)  # Batch generation
        
        generated = []
        batch_size = 100
        num_batches = (num_molecules + batch_size - 1) // batch_size
        
        for i in range(num_batches):
            current_batch_size = min(batch_size, num_molecules - i * batch_size)
            batch_protein = protein_tensor[:current_batch_size]
            
            with torch.no_grad():
                smiles_indices = self.model(batch_protein)
                
            # Convert indices to SMILES strings
            for j in range(current_batch_size):
                smiles = self.indices_to_smiles(smiles_indices[j])
                if self.validate_smiles(smiles):
                    generated.append({
                        'smiles': smiles,
                        'generation_params': {
                            'temperature': temperature,
                            'batch': i,
                            'index': j
                        }
                    })
                    
            if len(generated) >= num_molecules:
                break
                
        return generated[:num_molecules]
    
    def encode_protein(self, sequence):
        """Convert protein sequence to numerical features"""
        # Simplified: Use precomputed features or ESM embeddings
        # In production, use a pre-trained protein language model
        np.random.seed(hash(sequence) % 2**32)
        return np.random.randn(1024)  # Placeholder
        
    def validate_smiles(self, smiles):
        """Check if SMILES string is valid"""
        try:
            mol = Chem.MolFromSmiles(smiles)
            return mol is not None
        except:
            return False
            
    def indices_to_smiles(self, indices):
        """Convert token indices back to SMILES string"""
        # Placeholder - implement actual tokenizer
        return "CCO"  # Example: Ethanol

# Lambda handler
def lambda_handler(event, context):
    model = GenerativeModel(model_path=event.get('model_path', 's3://oncoai-models/generative_model.pth'))
    
    molecules = model.generate_molecules(
        protein_sequence=event['protein_sequence'],
        num_molecules=event.get('num_molecules', 10000)
    )
    
    return {
        'statusCode': 200,
        'generated_molecules': molecules
    }