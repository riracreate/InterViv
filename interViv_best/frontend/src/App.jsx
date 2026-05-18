import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing.jsx';
import Upload from './pages/Upload.jsx';
import Interview from './pages/Interview.jsx';
import Dashboard from './pages/Dashboard.tsx';
import GapAnalysis from './pages/GapAnalysis.jsx';
import Roadmap from './pages/Roadmap.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/upload" element={<Upload />} />
      <Route path="/interview/:sessionId" element={<Interview />} />
      <Route path="/dashboard/:sessionId" element={<Dashboard />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/gap-analysis/:userId/:roleId" element={<GapAnalysis />} />
      <Route path="/roadmap/:userId/:roleId" element={<Roadmap />} />
    </Routes>
  );
}
