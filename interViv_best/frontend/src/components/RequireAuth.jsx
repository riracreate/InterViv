import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { hasAuthToken } from '../lib/api';
import { loginHref } from '../lib/authRedirect';

export default function RequireAuth({ children }) {
  const location = useLocation();
  if (hasAuthToken()) return children;
  const here = `${location.pathname}${location.search}${location.hash}`;
  return <Navigate to={loginHref(here, window.location.origin)} replace />;
}
