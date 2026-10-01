export type UserSession = {
  name: string;
  email: string;
};

const TOKEN_KEY = "peach_id_token";
const USER_KEY = "peach_user";

export const MOCK_USER: UserSession = {
  name: "User",
  email: "user@example.com",
};

export const MOCK_TOKEN = "mock-dev-token";

/**
 * Returns true if Cognito authentication environment variables are configured.
 */
export function isAuthConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID &&
      process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID.trim() !== ""
  );
}

export const isConfigured = isAuthConfigured;

/**
 * Retrieve the active ID token.
 * When Cognito is not configured, gracefully falls back to a mock dev token.
 */
export async function getIdToken(): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    return token;
  }
  if (!isAuthConfigured()) {
    return MOCK_TOKEN;
  }
  return null;
}

/**
 * Sign out the current user by removing stored tokens and session.
 */
export function signOut(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
}

/**
 * Hook to retrieve the current session.
 * When Cognito is not configured, gracefully falls back to a mock user session.
 */
export function useSession(): UserSession | null {
  if (!isAuthConfigured()) {
    return MOCK_USER;
  }

  if (typeof window === "undefined") {
    return null;
  }

  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    return null;
  }

  const storedUser = localStorage.getItem(USER_KEY);
  if (storedUser) {
    try {
      return JSON.parse(storedUser) as UserSession;
    } catch {
      // fallback
    }
  }

  return MOCK_USER;
}
