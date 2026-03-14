import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

function Dashboard({ apiEndpoint }) {
  const [proteinTarget, setProteinTarget] = useState('EGFR');
  const [campaignName, setCampaignName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [campaignId, setCampaignId] = useState(null);
  const [progress, setProgress] = useState(0);
  const [recentCampaigns, setRecentCampaigns] = useState([]);
  const navigate = useNavigate();

  const proteinOptions = [
    'EGFR', 'BRAF', 'KRAS', 'TP53', 'PIK3CA', 'ALK', 'ROS1', 'MET', 'RET', 'NTRK'
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      const response = await axios.post(`${apiEndpoint}/campaign`, {
        protein_target: proteinTarget,
        name: campaignName || `Campaign_${new Date().toISOString()}`
      });
      
      setCampaignId(response.data.campaign_id);
      
      // Poll for progress
      const interval = setInterval(async () => {
        const statusResponse = await axios.get(`${apiEndpoint}/campaign/${response.data.campaign_id}`);
        setProgress(calculateProgress(statusResponse.data.campaign));
        
        if (statusResponse.data.campaign.status === 'COMPLETED') {
          clearInterval(interval);
          setIsLoading(false);
          navigate(`/campaign/${response.data.campaign_id}`);
        }
      }, 5000);
      
    } catch (error) {
      console.error('Error starting campaign:', error);
      setIsLoading(false);
    }
  };

  const calculateProgress = (campaign) => {
    const stages = ['INITIATED', 'GENERATING', 'SCREENING', 'DOCKING', 'COMPLETED'];
    const currentIndex = stages.indexOf(campaign.status);
    return (currentIndex / (stages.length - 1)) * 100;
  };

  // Fetch recent campaigns
  useEffect(() => {
    // In production, fetch from API
    setRecentCampaigns([
      { id: '1', name: 'EGFR Screening', status: 'COMPLETED', date: '2024-01-15' },
      { id: '2', name: 'BRAF Discovery', status: 'COMPLETED', date: '2024-01-14' },
      { id: '3', name: 'KRAS Inhibitors', status: 'IN_PROGRESS', date: '2024-01-13' }
    ]);
  }, []);

  const chartData = {
    labels: ['Generate', 'Screen', 'Validate', 'Complete'],
    datasets: [
      {
        label: 'Current Campaign Progress',
        data: [25, 50, 75, 100],
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
      }
    ]
  };

  return (
    <div className="row">
      <div className="col-md-6">
        <div className="card">
          <div className="card-header">
            <h3>Start New Discovery Campaign</h3>
          </div>
          <div className="card-body">
            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label className="form-label">Protein Target</label>
                <select 
                  className="form-select" 
                  value={proteinTarget}
                  onChange={(e) => setProteinTarget(e.target.value)}
                >
                  {proteinOptions.map(protein => (
                    <option key={protein} value={protein}>{protein}</option>
                  ))}
                </select>
              </div>
              
              <div className="mb-3">
                <label className="form-label">Campaign Name (Optional)</label>
                <input 
                  type="text" 
                  className="form-control"
                  value={campaignName}
                  onChange={(e) => setCampaignName(e.target.value)}
                  placeholder="e.g., EGFR Inhibitor Discovery"
                />
              </div>
              
              <button 
                type="submit" 
                className="btn btn-primary btn-lg w-100"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                    Starting Campaign...
                  </>
                ) : 'Start AI-Driven Discovery'}
              </button>
            </form>
            
            {isLoading && (
              <div className="mt-4">
                <div className="progress">
                  <div 
                    className="progress-bar progress-bar-striped progress-bar-animated" 
                    role="progressbar" 
                    style={{ width: `${progress}%` }}
                    aria-valuenow={progress} 
                    aria-valuemin="0" 
                    aria-valuemax="100"
                  >
                    {Math.round(progress)}%
                  </div>
                </div>
                <p className="text-center mt-2">
                  {campaignId && `Campaign ID: ${campaignId}`}
                </p>
              </div>
            )}
          </div>
        </div>
        
        <div className="card mt-4">
          <div className="card-header">
            <h3>System Performance</h3>
          </div>
          <div className="card-body">
            <Line data={chartData} />
          </div>
        </div>
      </div>
      
      <div className="col-md-6">
        <div className="card">
          <div className="card-header">
            <h3>Recent Campaigns</h3>
          </div>
          <div className="card-body">
            <div className="list-group">
              {recentCampaigns.map(campaign => (
                <a 
                  key={campaign.id} 
                  href={`/campaign/${campaign.id}`}
                  className="list-group-item list-group-item-action"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(`/campaign/${campaign.id}`);
                  }}
                >
                  <div className="d-flex w-100 justify-content-between">
                    <h5 className="mb-1">{campaign.name}</h5>
                    <small>{campaign.date}</small>
                  </div>
                  <p className="mb-1">
                    Status: 
                    <span className={`badge ${
                      campaign.status === 'COMPLETED' ? 'bg-success' : 
                      campaign.status === 'IN_PROGRESS' ? 'bg-warning' : 'bg-secondary'
                    } ms-2`}>
                      {campaign.status}
                    </span>
                  </p>
                </a>
              ))}
            </div>
          </div>
        </div>
        
        <div className="card mt-4">
          <div className="card-header">
            <h3>Memory Bank Statistics</h3>
          </div>
          <div className="card-body">
            <div className="row text-center">
              <div className="col-4">
                <h1 className="display-6">1.2M</h1>
                <p className="text-muted">Memories Stored</p>
              </div>
              <div className="col-4">
                <h1 className="display-6">94%</h1>
                <p className="text-muted">Accuracy</p>
              </div>
              <div className="col-4">
                <h1 className="display-6">3.4K</h1>
                <p className="text-muted">Campaigns</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;