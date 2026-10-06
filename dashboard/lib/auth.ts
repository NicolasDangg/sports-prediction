// One shared password (DASHBOARD_PASSWORD env var) guards the whole site.
// After login the browser holds a cookie containing a SHA-256 of the password, so the
// password itself is never stored client-side, and changing it signs everyone out.
export const SESSION_COOKIE = "sp_session";
export const SESSION_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

export async function sessionToken(password: string): Promise<string> {
  const bytes = new TextEncoder().encode(`sports-prediction:v1:${password}`);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Constant-time string comparison, so response timing leaks nothing about the secret. */
export function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** Only allow redirects back to our own pages (never to another site). */
export function safeNext(next: unknown): string {
  return typeof next === "string" && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}
