import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GATConv, global_mean_pool
from torch_geometric.data import Data, Batch
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
import boto3
import json

class GraphNeuralNetwork(nn.Module):
    """
    Graph Neural Network for predicting protein-ligand binding affinity
    """
    def __init__(self, node_features=78, hidden_dim=128, num_layers=4):
        super().__init__()
        
        # Node embedding
        self.node_embedding = nn.Linear(node_features, hidden_dim)
        
        # Graph convolution layers
        self.convs = nn.ModuleList()
        for i in range(num_layers):
            self.convs.append(GATConv(hidden_dim, hidden_dim, heads=4, concat=False))
            
        # Protein-ligand interaction layers
        self.interaction = nn.Sequential(
            nn.Linear(hidden_dim * 2, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 1)
        )
        
        # Memory attention mechanism
        self.memory_attention = nn.MultiheadAttention(embed_dim=hidden_dim, num_heads=4, batch_first=True)
        
    def forward(self, ligand_graphs, protein_graphs, memory_context=None):
        batch_size = len(ligand_graphs)
        
        # Process ligand graphs
        ligand_features = []
        for graph in ligand_graphs:
            x = self.node_embedding(graph.x)
            for conv in self.convs:
                x = F.relu(conv(x, graph.edge_index))
            # Global pooling
            graph_feat = global_mean_pool(x, graph.batch)
            ligand_features.append(graph_feat)
        ligand_features = torch.stack(ligand_features)
        
        # Process protein graphs
        protein_features = []
        for graph in protein_graphs:
            x = self.node_embedding(graph.x)
            for conv in self.convs:
                x = F.relu(conv(x, graph.edge_index))
            graph_feat = global_mean_pool(x, graph.batch)
            protein_features.append(graph_feat)
        protein_features = torch.stack(protein_features)
        
        # Apply memory attention if context provided
        if memory_context is not None:
            # Memory shapes: [batch, num_memories, hidden_dim]
            ligand_features, attention_weights = self.memory_attention(
                ligand_features.unsqueeze(1),
                memory_context,
                memory_context
            )
            ligand_features = ligand_features.squeeze(1)
        
        # Combine features
        combined = torch.cat([ligand_features, protein_features], dim=-1)
        
        # Predict binding affinity
        binding_scores = self.interaction(combined)
        
        return torch.sigmoid(binding_scores).squeeze(-1)

class BindingPredictor:
    def __init__(self, model_path=None):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = GraphNeuralNetwork().to(self.device)
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
            
    def smiles_to_graph(self, smiles):
        """Convert SMILES to PyTorch Geometric graph"""
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
            
        # Node features: atom type, degree, hybridization, etc.
        node_features = []
        for atom in mol.GetAtoms():
            features = [
                atom.GetAtomicNum() / 100.0,  # Normalize
                atom.GetDegree() / 10.0,
                atom.GetFormalCharge() / 5.0,
                atom.GetNumRadicalElectrons() / 5.0,
                atom.GetHybridization(),
                atom.GetIsAromatic(),
                atom.GetMass() / 200.0,
            ]
            # One-hot encoding for atom type (simplified)
            atom_types = [0] * 70
            if atom.GetAtomicNum() < 70:
                atom_types[atom.GetAtomicNum()] = 1
            features.extend(atom_types)
            
            node_features.append(features)
            
        # Edge indices
        edge_indices = []
        for bond in mol.GetBonds():
            i = bond.GetBeginAtomIdx()
            j = bond.GetEndAtomIdx()
            edge_indices.append([i, j])
            edge_indices.append([j, i])
            
        if not edge_indices:  # No bonds (single atom)
            edge_indices = [[0, 0]]
            
        x = torch.tensor(node_features, dtype=torch.float)
        edge_index = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()
        
        return Data(x=x, edge_index=edge_index)
    
    def get_protein_graph(self, pdb_id):
        """Fetch and convert protein structure to graph"""
        # In production, download from PDB and process
        # Simplified: Return placeholder graph
        num_nodes = 500  # Typical protein size
        x = torch.randn(num_nodes, 78)
        edge_index = torch.randint(0, num_nodes, (2, 2000))
        return Data(x=x, edge_index=edge_index)
    
    def predict_batch(self, smiles_list, protein_target, memory_context=None):
        """Predict binding affinity for multiple molecules"""
        # Convert to graphs
        ligand_graphs = []
        valid_indices = []
        
        for i, smiles in enumerate(smiles_list):
            graph = self.smiles_to_graph(smiles)
            if graph is not None:
                ligand_graphs.append(graph)
                valid_indices.append(i)
                
        if not ligand_graphs:
            return []
            
        # Get protein graph (same for all)
        protein_graph = self.get_protein_graph(protein_target)
        protein_graphs = [protein_graph] * len(ligand_graphs)
        
        # Batch graphs
        ligand_batch = Batch.from_data_list(ligand_graphs).to(self.device)
        protein_batch = Batch.from_data_list(protein_graphs).to(self.device)
        
        # Prepare memory context if provided
        memory_tensors = None
        if memory_context:
            memory_tensors = torch.tensor(memory_context).to(self.device)
            
        # Predict
        self.model.eval()
        with torch.no_grad():
            scores = self.model(
                [ligand_batch],  # Wrap in list for batch processing
                [protein_batch],
                memory_tensors
            )
            
        # Map back to original indices
        results = [{'smiles': smiles_list[idx], 'score': float(scores[i])} 
                   for i, idx in enumerate(valid_indices)]
        
        return sorted(results, key=lambda x: x['score'], reverse=True)

# Lambda handler
def lambda_handler(event, context):
    predictor = BindingPredictor(model_path=event.get('model_path', 's3://oncoai-models/gnn_predictor.pth'))
    
    results = predictor.predict_batch(
        smiles_list=event['molecules'],
        protein_target=event['protein_target'],
        memory_context=event.get('memory_context')
    )
    
    # Return top 1000
    top_results = results[:1000]
    
    return {
        'statusCode': 200,
        'predictions': top_results
    }