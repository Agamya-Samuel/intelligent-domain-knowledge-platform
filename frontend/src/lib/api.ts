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

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = document.cookie
    .split("; ")
    .find((row) => row.startsWith("next-auth.session-token="))
    ?.split("=")[1];

  if (!token) {
    throw new Error("Not authenticated");
  }

  const fullUrl = url.startsWith("http") ? url : `${getApiUrl()}${url}`;

  return fetch(fullUrl, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-CSRF-Token": token,
    },
    credentials: "include",
  });
}