/** Same-origin API contract for the standalone review host. */
export const HTTP_OPTS = { withCredentials: true } as const;
export function apiUrl(path: string): string { return path; }
