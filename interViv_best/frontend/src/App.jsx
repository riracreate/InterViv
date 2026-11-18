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
import CareerProfile from './pages/CareerProfile.jsx';
import Home from './pages/Home.jsx';
import Progress from './pages/Progress.jsx';
import BundleReview from './pages/BundleReview.jsx';
import InterviewRoute from './components/InterviewRoute.jsx';
import RequireAuth from './components/RequireAuth.jsx';
import ScrollManager from './components/ScrollManager.jsx';

function guarded(page) {
  return <RequireAuth>{page}</RequireAuth>;
}

export default function App() {
  return (
    <><ScrollManager /><Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/register" element={<Signup />} />
      <Route path="/home" element={guarded(<Home />)} />
      <Route path="/upload" element={guarded(<Upload />)} />
      <Route path="/practice" element={guarded(<Practice />)} />
      <Route path="/problems" element={guarded(<Problems />)} />
      <Route path="/learn" element={guarded(<Learn />)} />
      <Route path="/ats" element={guarded(<Ats />)} />
      <Route path="/jobs" element={guarded(<Jobs />)} />
      <Route path="/coach" element={guarded(<Coach />)} />
      <Route path="/resources" element={guarded(<Resources />)} />
      <Route path="/career" element={guarded(<CareerProfile />)} />
      <Route path="/interview/:sessionId" element={guarded(<InterviewRoute />)} />
      <Route path="/dashboard/:sessionId" element={guarded(<Dashboard />)} />
      <Route path="/dashboard" element={guarded(<Progress />)} />
      <Route path="/gap-analysis/:userId/:roleId" element={guarded(<GapAnalysis />)} />
      <Route path="/roadmap/:userId/:roleId" element={guarded(<Roadmap />)} />
      <Route path="/admin/bundles" element={guarded(<BundleReview />)} />
    </Routes></>
  );
}
