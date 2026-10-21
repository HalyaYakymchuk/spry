/**
 * API client configuration and helper functions.
 *
 * Uses `process.env.NEXT_PUBLIC_API_URL` as the absolute base URL for the backend API.
 * Uses `process.env.NEXT_PUBLIC_PARSER_URL` for the agenda parser Function URL.
 */

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.VITE_API_URL ||
  "http://localhost:8000"
).replace(/\/+$/, "");

export const PARSER_URL = (
  process.env.NEXT_PUBLIC_PARSER_URL ||
  process.env.PARSER_URL ||
  "https://gcvzj3jhh5aya5news2ypxlalm0wzmvb.lambda-url.eu-north-1.on.aws/"
).replace(/\/+$/, "") + "/";

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

export interface AgendaItem {
  topic: string;
  owner?: string | null;
  minutes?: number | null;
}

export interface ActionItem {
  task: string;
  owner?: string | null;
  due?: string | null;
}

export interface ParsedAgendaData {
  title?: string | null;
  starts_at?: string | null;
  duration_minutes?: number | null;
  items: AgendaItem[];
  action_items: ActionItem[];
  language?: string;
}

export interface ParserResponse {
  agenda: ParsedAgendaData;
  model: string;
  prompt_version: string;
}

export interface Agenda {
  id: number;
  meeting_id: number;
  title?: string | null;
  items: AgendaItem[];
  action_items: ActionItem[];
  ai_suggestion?: Record<string, unknown> | null;
  model?: string | null;
  prompt_version?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface SaveAgendaPayload {
  title?: string | null;
  items: AgendaItem[];
  action_items: ActionItem[];
  ai_suggestion?: Record<string, unknown> | null;
  model?: string | null;
  prompt_version?: string | null;
}

export interface Meeting {
  id: number;
  title: string;
  starts_at: string;
  ends_at: string;
  attendee_count: number;
  agenda?: Agenda | null;
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

export async function fetchMeetingAgenda(
  meetingId: number,
  token?: string
): Promise<Agenda | null> {
  try {
    const url = getApiUrl(`/api/meetings/${meetingId}/agenda`);
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(url, { headers });
    if (res.status === 404) {
      return null;
    }
    if (!res.ok) {
      return null;
    }
    const data = await res.json().catch(() => null);
    if (!data) return null;
    if (data.agenda !== undefined) {
      return data.agenda;
    }
    return data;
  } catch (err) {
    console.warn(`Could not fetch agenda for meeting ${meetingId}:`, err);
    return null;
  }
}

export async function saveMeetingAgenda(
  meetingId: number,
  payload: SaveAgendaPayload,
  token?: string
): Promise<Agenda> {
  const url = getApiUrl(`/api/meetings/${meetingId}/agenda`);
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
      `Error ${res.status}: Failed to save agenda`;
    throw new Error(errorDetail);
  }

  return res.json();
}

/**
 * Call the Agenda Parser Function URL.
 * STRICTLY READ-ONLY: never writes to the database.
 */
export async function parseAgendaText(
  text: string,
  token: string,
  signal?: AbortSignal
): Promise<ParserResponse> {
  const clientTz =
    typeof Intl !== "undefined" && Intl.DateTimeFormat
      ? Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
      : "UTC";
  const todayStr = new Date().toISOString().slice(0, 10);

  let res: Response;
  try {
    res = await fetch(PARSER_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        text,
        today: todayStr,
        tz: clientTz,
      }),
      signal,
    });
  } catch (err: unknown) {
    if (
      (err instanceof DOMException && err.name === "AbortError") ||
      (err instanceof Error && err.name === "AbortError")
    ) {
      throw err;
    }
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
      throw new Error(
        "Unable to connect to the agenda parser service. Please check your network connection or CORS configuration."
      );
    }
    throw new Error(`Parser network error: ${msg}`);
  }

  if (!res.ok) {
    if (res.status === 401) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(
        errJson.error || "Authentication failed. Please sign in again."
      );
    }
    if (res.status === 413) {
      throw new Error(
        "Text exceeds the 10,000 character limit. Please shorten your input."
      );
    }
    if (res.status === 422) {
      throw new Error(
        "The model could not find a clear agenda in the provided text."
      );
    }
    if (res.status === 429 || res.status === 503) {
      throw new Error(
        "Service is busy. Please try again in a few moments or enter manually."
      );
    }
    const errJson = await res.json().catch(() => ({}));
    const errorMsg =
      errJson.error ||
      errJson.message ||
      errJson.detail ||
      `Parser failed with status code ${res.status}: ${res.statusText || "Error"}`;
    throw new Error(errorMsg);
  }

  return res.json();
}
