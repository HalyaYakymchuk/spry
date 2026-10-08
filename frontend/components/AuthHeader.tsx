'use client';

import React from 'react';
import { useAuth } from 'react-oidc-context';

export function AuthHeader() {
  const auth = useAuth();

  const handleLogout = () => {
    auth.removeUser();
    const cognitoDomain = process.env.NEXT_PUBLIC_COGNITO_DOMAIN;
    const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
    const logoutUri = encodeURIComponent(`${appUrl}/`);

    if (cognitoDomain && clientId) {
      window.location.href = `https://${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${logoutUri}`;
    } else {
      window.location.href = '/';
    }
  };

  if (auth.isLoading) {
    return <span className="text-sm text-slate-500">Checking auth...</span>;
  }

  if (auth.isAuthenticated) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-slate-700">
          {auth.user?.profile?.email as string}
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
