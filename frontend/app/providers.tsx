'use client';

import React from 'react';
import { AuthProvider, AuthProviderProps } from 'react-oidc-context';

const cognitoRegion = process.env.NEXT_PUBLIC_COGNITO_REGION || 'eu-north-1';
const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID;
const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;

export function AppProviders({ children }: { children: React.ReactNode }) {
  const oidcConfig: AuthProviderProps = React.useMemo(() => {
    let redirectUri = process.env.NEXT_PUBLIC_COGNITO_REDIRECT_URI;
    if (typeof window !== 'undefined') {
      if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        redirectUri = `${window.location.origin}/auth/callback`;
      } else if (!redirectUri) {
        redirectUri = `${window.location.origin}/auth/callback`;
      }
    } else if (!redirectUri) {
      const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
      redirectUri = `${appUrl}/auth/callback`;
    }

    return {
      authority: `https://cognito-idp.${cognitoRegion}.amazonaws.com/${userPoolId}`,
      client_id: clientId || '',
      redirect_uri: redirectUri,
      response_type: 'code',
      scope: 'openid email profile',
      automaticSilentRenew: false,
      loadUserInfo: false,
      onSigninCallback: () => {
        window.history.replaceState({}, document.title, window.location.pathname);
      },
    };
  }, []);

  return <AuthProvider {...oidcConfig}>{children}</AuthProvider>;
}
