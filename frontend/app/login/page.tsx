'use client';

import { useEffect } from 'react';
import { useAuth } from 'react-oidc-context';

export default function LoginPage() {
  const auth = useAuth();

  useEffect(() => {
    auth.signinRedirect();
  }, [auth]);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p className="text-slate-600">Redirecting to login...</p>
    </main>
  );
}
