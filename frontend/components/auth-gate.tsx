"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { isAuthConfigured, useSession } from "@/lib/auth";

export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const session = useSession();
  const configured = isAuthConfigured();

  useEffect(() => {
    if (configured && !session) {
      router.replace("/");
    }
  }, [configured, router, session]);

  if (configured && !session) {
    return null;
  }

  return <>{children}</>;
}
