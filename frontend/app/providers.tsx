'use client';

import React from 'react';
import { AuthProvider, AuthProviderProps } from 'react-oidc-context';

const cognitoRegion = process.env.NEXT_PUBLIC_COGNITO_REGION || 'eu-north-1';
const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID;
const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
const redirectUri = process.env.NEXT_PUBLIC_COGNITO_REDIRECT_URI || `${appUrl}/auth/callback`;

const oidcConfig: AuthProviderProps = {
  authority: `https://cognito-idp.${cognitoRegion}.amazonaws.com/${userPoolId}`,
  client_id: clientId || '',
  redirect_uri: redirectUri,
  response_type: 'code',
  scope: 'openid email profile',
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname);
  },
};

export function AppProviders({ children }: { children: React.ReactNode }) {
  return <AuthProvider {...oidcConfig}>{children}</AuthProvider>;
}