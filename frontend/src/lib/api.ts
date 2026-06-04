/**
 * Shared API client module — consolidates fetchWithAuth and provides safe API URL handling.
 */

export function getApiUrl(): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    if (process.env.NODE_ENV === "development") {
      return "http://localhost:8000";
    }
    throw new Error(
      "NEXT_PUBLIC_API_URL environment variable is not set. " +
      "This is required in production environments."
    );
  }
  return apiUrl;
}

export function getWsUrl(): string {
  const apiUrl = getApiUrl();
  return apiUrl.replace(/^http/, "ws");
}

export function getSessionToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const cookies = document.cookie.split("; ");

  // NextAuth v5 (Auth.js) - check both with and without __Secure prefix
  const v5Match = cookies.find((row) =>
    row.startsWith("authjs.session-token=") ||
    row.startsWith("__Secure-authjs.session-token=")
  );
  if (v5Match) return v5Match.split("=")[1];

  // NextAuth v4 (legacy)
  const v4Match = cookies.find((row) =>
    row.startsWith("next-auth.session-token=") ||
    row.startsWith("__Secure-next-auth.session-token=")
  );
  if (v4Match) return v4Match.split("=")[1];

  return undefined;
}

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  // Add CSRF token for state-changing requests
  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    const token = getSessionToken();
    if (token) {
      headers["X-CSRF-Token"] = token;
    }
  }

  const fullUrl = url.startsWith("http") ? url : `${getApiUrl()}${url}`;

  return fetch(fullUrl, {
    ...options,
    headers,
    credentials: "include",
  });
}