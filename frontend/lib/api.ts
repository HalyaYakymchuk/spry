/**
 * API client configuration and helper functions.
 *
 * Uses `process.env.NEXT_PUBLIC_API_URL` as the absolute base URL for the backend API.
 */

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  "https://qk4qzvxvcohv4evaf3rnaj7kui0duqut.lambda-url.eu-north-1.on.aws"
).replace(/\/+$/, "");

/**
 * Returns a fully qualified API URL.
 * Handles paths with or without leading slashes and prevents duplicate `/api` prefixes if
 * the base URL already includes `/api`.
 */
export function getApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!API_BASE_URL) {
    return normalizedPath;
  }
  if (API_BASE_URL.endsWith("/api") && normalizedPath.startsWith("/api/")) {
    return `${API_BASE_URL}${normalizedPath.slice(4)}`;
  }
  return `${API_BASE_URL}${normalizedPath}`;
}

export interface Meeting {
  id: number;
  title: string;
  starts_at: string;
  ends_at: string;
  attendee_count: number;
}

export interface CreateMeetingPayload {
  title: string;
  starts_at: string;
  ends_at: string;
  attendee_count: number;
}

export async function fetchMeetings(token?: string): Promise<Meeting[]> {
  const url = getApiUrl("/api/meetings");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Failed to fetch meetings: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function createMeeting(
  payload: CreateMeetingPayload,
  token?: string
): Promise<Meeting> {
  const url = getApiUrl("/api/meetings");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const errorDetail =
      errData?.detail?.[0]?.msg ||
      errData?.detail ||
      `Error ${res.status}: Failed to create meeting`;
    throw new Error(errorDetail);
  }

  return res.json();
}
