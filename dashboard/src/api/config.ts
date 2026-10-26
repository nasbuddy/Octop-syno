declare const BASE_URL: string;

export const APP_BASE_PATH = import.meta.env.BASE_URL.replace(/\/$/, "");
export const DSM_NATIVE = import.meta.env.VITE_DSM_AUTH === "1";

/** Prefix application URLs without changing external URLs or already-prefixed paths. */
export function getAppUrl(path: string): string {
  if (
    !APP_BASE_PATH ||
    !path.startsWith("/") ||
    path.startsWith("//") ||
    path === APP_BASE_PATH ||
    path.startsWith(`${APP_BASE_PATH}/`)
  )
    return path;
  return `${APP_BASE_PATH}${path}`;
}

/**
 * Get the full API URL with /api prefix
 * @param path - API path (e.g., "/models", "/skills")
 * @returns Full API URL (e.g., "http://localhost:8088/api/models" or "/api/models")
 */
export function getApiUrl(path: string): string {
  const base = BASE_URL || APP_BASE_PATH;
  const apiPrefix = "/api";
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${apiPrefix}${normalizedPath}`;
}

/**
 * Get a WebSocket URL derived from the same origin as the API.
 * Converts http:// → ws:// and https:// → wss://.
 * If BASE_URL is empty (same-origin), uses the current page location.
 * @param path - API path (e.g., "/browser-stream/ws")
 * @returns Full WebSocket URL
 */
export function getWsUrl(path: string): string {
  const base = BASE_URL || APP_BASE_PATH;
  const apiPrefix = "/api";
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const httpUrl = `${base}${apiPrefix}${normalizedPath}`;

  if (httpUrl.startsWith("http://")) {
    return httpUrl.replace("http://", "ws://");
  }
  if (httpUrl.startsWith("https://")) {
    return httpUrl.replace("https://", "wss://");
  }

  // Relative URL — derive from current page location
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${httpUrl}`;
}
