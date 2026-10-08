'use client';

import { useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import { useRouter } from 'next/navigation';

export default function CallbackPage() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.isAuthenticated) {
      router.push('/');
    }
  }, [auth.isAuthenticated, router]);

  if (auth.error) {
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <div className="rounded border border-red-300 bg-red-50 p-4 text-red-700">
          <p className="font-semibold">Authentication failed</p>
          <p className="text-sm">{auth.error.message}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p className="text-slate-600">Completing sign-in...</p>
    </main>
  );
}
