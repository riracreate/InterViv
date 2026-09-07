import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing.jsx';
import Upload from './pages/Upload.jsx';
import Dashboard from './pages/Dashboard.tsx';
import GapAnalysis from './pages/GapAnalysis.jsx';
import Roadmap from './pages/Roadmap.jsx';
import Login from './pages/Login.jsx';
import Signup from './pages/Signup.jsx';
import Practice from './pages/Practice.jsx';
import Problems from './pages/Problems.jsx';
import Learn from './pages/Learn.jsx';
import Ats from './pages/Ats.jsx';
import Jobs from './pages/Jobs.jsx';
import Coach from './pages/Coach.jsx';
import Resources from './pages/Resources.jsx';
import Home from './pages/Home.jsx';
import Progress from './pages/Progress.jsx';
import InterviewRoute from './components/InterviewRoute.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/register" element={<Signup />} />
      <Route path="/home" element={<Home />} />
      <Route path="/upload" element={<Upload />} />
      <Route path="/practice" element={<Practice />} />
      <Route path="/problems" element={<Problems />} />
      <Route path="/learn" element={<Learn />} />
      <Route path="/ats" element={<Ats />} />
      <Route path="/jobs" element={<Jobs />} />
      <Route path="/coach" element={<Coach />} />
      <Route path="/resources" element={<Resources />} />
      <Route path="/interview/:sessionId" element={<InterviewRoute />} />
      <Route path="/dashboard/:sessionId" element={<Dashboard />} />
      <Route path="/dashboard" element={<Progress />} />
      <Route path="/gap-analysis/:userId/:roleId" element={<GapAnalysis />} />
      <Route path="/roadmap/:userId/:roleId" element={<Roadmap />} />
    </Routes>
  );
}
