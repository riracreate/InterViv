import React, { Suspense, lazy } from 'react';
import { Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing.jsx';
import Upload from './pages/Upload.jsx';
import Dashboard from './pages/Dashboard.tsx';
import GapAnalysis from './pages/GapAnalysis.jsx';
import Roadmap from './pages/Roadmap.jsx';
import Login from './pages/Login.jsx';
import Signup from './pages/Signup.jsx';
import Practice from './pages/Practice.jsx';
import Ats from './pages/Ats.jsx';
import Jobs from './pages/Jobs.jsx';
import Coach from './pages/Coach.jsx';
import Resources from './pages/Resources.jsx';

// Interview pulls face-api.js (lazy inside engagement.js). Keep the route
 // async so dashboard/home chunks do not pay that cost up front.
const Interview = lazy(() => import('./pages/Interview.jsx'));

function InterviewRoute() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen grid place-items-center bg-white text-sm text-slate-600">
          Loading interview…
        </div>
      }
    >
      <Interview />
    </Suspense>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/register" element={<Signup />} />
      <Route path="/upload" element={<Upload />} />
      <Route path="/practice" element={<Practice />} />
      <Route path="/ats" element={<Ats />} />
      <Route path="/jobs" element={<Jobs />} />
      <Route path="/coach" element={<Coach />} />
      <Route path="/resources" element={<Resources />} />
      <Route path="/interview/:sessionId" element={<InterviewRoute />} />
      <Route path="/dashboard/:sessionId" element={<Dashboard />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/gap-analysis/:userId/:roleId" element={<GapAnalysis />} />
      <Route path="/roadmap/:userId/:roleId" element={<Roadmap />} />
    </Routes>
  );
}
