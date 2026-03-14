import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import MoleculeViewer from './components/MoleculeViewer';
import ResultsTable from './components/ResultsTable';
import './App.css';

function App() {
  const [apiEndpoint, setApiEndpoint] = useState(process.env.REACT_APP_API_ENDPOINT);

  return (
    <Router>
      <div className="App">
        <nav className="navbar navbar-dark bg-primary">
          <div className="container">
            <a className="navbar-brand" href="/">
              <img src="/logo.png" alt="OncoAI" height="30" className="d-inline-block align-top" />
              OncoAI - Cancer Drug Discovery Platform
            </a>
          </div>
        </nav>
        
        <div className="container mt-4">
          <Routes>
            <Route path="/" element={<Dashboard apiEndpoint={apiEndpoint} />} />
            <Route path="/campaign/:id" element={<ResultsTable apiEndpoint={apiEndpoint} />} />
            <Route path="/molecule/:smiles" element={<MoleculeViewer />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;