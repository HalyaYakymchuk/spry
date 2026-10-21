'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from 'react-oidc-context';

export function AuthHeader() {
  const auth = useAuth();
  const [authTimedOut, setAuthTimedOut] = useState(false);
  const [fallbackToken, setFallbackToken] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored =
        localStorage.getItem('token') ||
        localStorage.getItem('fallback_token') ||
        localStorage.getItem('id_token') ||
        process.env.NEXT_PUBLIC_FALLBACK_TOKEN;
      if (stored) {
        setFallbackToken(stored);
      }
    }
  }, []);

  useEffect(() => {
    if (!auth.isLoading) {
      setAuthTimedOut(false);
      return;
    }
    const timer = setTimeout(() => {
      setAuthTimedOut(true);
    }, 1500);
    return () => clearTimeout(timer);
  }, [auth.isLoading]);

  const handleLogout = () => {
    auth.removeUser();
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
      localStorage.removeItem('fallback_token');
      localStorage.removeItem('id_token');
    }
    setFallbackToken(null);

    const cognitoDomain = process.env.NEXT_PUBLIC_COGNITO_DOMAIN;
    const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
    const isLocal =
      typeof window !== 'undefined' &&
      (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
    const appUrl = isLocal
      ? window.location.origin
      : process.env.NEXT_PUBLIC_APP_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000');
    const logoutUri = encodeURIComponent(`${appUrl}/`);

    if (cognitoDomain && clientId) {
      window.location.href = `https://${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${logoutUri}`;
    } else {
      window.location.href = '/';
    }
  };

  const isChecking = auth.isLoading && !authTimedOut;

  if (isChecking) {
    return <span className="text-sm text-slate-500">Checking auth...</span>;
  }

  if (auth.isAuthenticated) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-slate-700">
          {(auth.user?.profile?.email as string) || 'Signed in'}
        </span>
        <button
          onClick={handleLogout}
          className="rounded bg-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-300"
        >
          Sign out
        </button>
      </div>
    );
  }

  if (fallbackToken) {
    return (
      <div className="flex items-center gap-3">
        <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
          Dev / Fallback Token
        </span>
        <button
          onClick={handleLogout}
          className="rounded bg-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-300"
        >
          Clear
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => auth.signinRedirect()}
        className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
      >
        Sign in
      </button>
      <button
        onClick={() => auth.signinRedirect({ extraQueryParams: { identity_provider: 'Google' } })}
        className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        Google
      </button>
    </div>
  );
}
