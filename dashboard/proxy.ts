import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, safeEqual, sessionToken } from "@/lib/auth";

// Runs before every page (static ones included). No valid session cookie -> login page.
export async function proxy(request: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) {
    // Fail closed: a missing password must never mean "public".
    return new NextResponse("Dashboard locked: DASHBOARD_PASSWORD is not configured.", { status: 503 });
  }
  const cookie = request.cookies.get(SESSION_COOKIE)?.value ?? "";
  if (safeEqual(cookie, await sessionToken(password))) return NextResponse.next();

  const login = new URL("/login", request.url);
  if (request.nextUrl.pathname !== "/") login.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!login|api/login|_next/static|_next/image|favicon.ico|robots.txt).*)"],
};
