import { NextResponse } from "next/server";
import { SESSION_COOKIE, SESSION_MAX_AGE, safeEqual, safeNext, sessionToken } from "@/lib/auth";

export async function POST(request: Request) {
  const expected = process.env.DASHBOARD_PASSWORD;
  if (!expected) return NextResponse.json({ error: "Login is not configured on the server." }, { status: 503 });

  const body = await request.json().catch(() => ({}));
  const password = typeof body.password === "string" ? body.password : "";

  // A small fixed delay makes password guessing slow without hurting a real login.
  await new Promise((r) => setTimeout(r, 350));

  const [given, wanted] = await Promise.all([sessionToken(password), sessionToken(expected)]);
  if (!safeEqual(given, wanted)) {
    return NextResponse.json({ error: "That password isn't right. Check it and try again." }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true, next: safeNext(body.next) });
  response.cookies.set(SESSION_COOKIE, wanted, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
  return response;
}
