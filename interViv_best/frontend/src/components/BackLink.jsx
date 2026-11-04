import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { backDestination } from '../lib/backNavigation';

/**
 * Back that never strands the user: one step back when the app put an
 * entry there, otherwise the page's fallback (Home for preparation pages,
 * Progress for reports). Never a hard-coded destructive jump.
 */
export default function BackLink({ fallback = '/home', label = 'Back', className = 'hub-button' }) {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <button
      type="button"
      data-testid="back-link"
      className={className}
      onClick={() => navigate(backDestination(location, fallback))}
    >
      ← {label}
    </button>
  );
}
