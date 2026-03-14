import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { CSVLink } from 'react-csv';

function ResultsTable({ apiEndpoint }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedMolecule, setSelectedMolecule] = useState(null);

  useEffect(() => {
    fetchResults();
  }, [id]);

  const fetchResults = async () => {
    try {
      const response = await axios.get(`${apiEndpoint}/campaign/${id}`);
      setCampaign(response.data.campaign);
      setResults(response.data.results?.candidates || []);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching results:', error);
      setLoading(false);
    }
  };

  const viewMolecule = (smiles) => {
    navigate(`/molecule/${encodeURIComponent(smiles)}`);
  };

  const downloadSDF = (smiles) => {
    // Convert SMILES to SDF and download
    window.open(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/${smiles}/SDF?record_type=3d`, '_blank');
  };

  if (loading) {
    return (
      <div className="text-center">
        <div className="spinner-border" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  const csvData = results.map(r => ({
    'Rank': r.rank,
    'SMILES': r.smiles,
    'Binding Score': r.binding_score,
    'Docking Score': r.docking_score,
    'Safety Score': r.safety_score,
    'Lipinski Violations': r.lipinski_violations
  }));

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2>Campaign Results: {campaign?.name}</h2>
        <div>
          <CSVLink 
            data={csvData} 
            filename={`oncoai_results_${id}.csv`}
            className="btn btn-success me-2"
          >
            Download CSV
          </CSVLink>
          <button 
            className="btn btn-primary"
            onClick={() => window.print()}
          >
            Print Report
          </button>
        </div>
      </div>
      
      <div className="card">
        <div className="card-header">
          <h4>Top {results.length} Drug Candidates</h4>
        </div>
        <div className="card-body">
          <div className="table-responsive">
            <table className="table table-hover">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Structure</th>
                  <th>SMILES</th>
                  <th>Binding Score</th>
                  <th>Docking Score</th>
                  <th>Safety Score</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result, index) => (
                  <tr key={index}>
                    <td>{index + 1}</td>
                    <td>
                      <img 
                        src={`https://cactus.nci.nih.gov/chemical/structure/${result.smiles}/image`}
                        alt="Molecular structure"
                        style={{ maxHeight: '50px', maxWidth: '50px' }}
                      />
                    </td>
                    <td>
                      <code>{result.smiles.substring(0, 30)}...</code>
                    </td>
                    <td>
                      <span className="badge bg-primary">{result.binding_score?.toFixed(3)}</span>
                    </td>
                    <td>
                      <span className="badge bg-info">{result.docking_score?.toFixed(3)}</span>
                    </td>
                    <td>
                      <span className={`badge ${
                        result.safety_score > 0.7 ? 'bg-success' : 
                        result.safety_score > 0.4 ? 'bg-warning' : 'bg-danger'
                      }`}>
                        {result.safety_score?.toFixed(3)}
                      </span>
                    </td>
                    <td>
                      <button 
                        className="btn btn-sm btn-outline-primary me-2"
                        onClick={() => viewMolecule(result.smiles)}
                      >
                        View 3D
                      </button>
                      <button 
                        className="btn btn-sm btn-outline-success"
                        onClick={() => downloadSDF(result.smiles)}
                      >
                        Download SDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      
      {selectedMolecule && (
        <div className="modal" style={{ display: 'block' }}>
          <div className="modal-dialog modal-lg">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title">Molecule Details</h5>
                <button 
                  type="button" 
                  className="btn-close"
                  onClick={() => setSelectedMolecule(null)}
                ></button>
              </div>
              <div className="modal-body">
                <pre>{JSON.stringify(selectedMolecule, null, 2)}</pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ResultsTable;