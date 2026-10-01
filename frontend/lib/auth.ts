export type UserSession = {
  name: string;
  email: string;
};

const TOKEN_KEY = "peach_id_token";

export async function getIdToken(): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }
  return localStorage.getItem(TOKEN_KEY) ?? "mock-dev-token";
}

export function signOut(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function useSession(): UserSession | null {
  return {
    name: "User",
    email: "user@example.com",
  };
}
