import { auth } from "@/lib/auth";

/**
 * Next.js middleware — protects dashboard routes.
 * Redirects unauthenticated users to /login.
 *
 * Auth.js v5's `auth()` wrapper handles session validation
 * and token refresh automatically.
 */
export default auth((req) => {
  const isAuthenticated = !!req.auth;
  const isLoginPage = req.nextUrl.pathname === "/login";
  const isAuthApi = req.nextUrl.pathname.startsWith("/api/auth");

  // Allow auth API routes through
  if (isAuthApi) return;

  // Redirect unauthenticated users to login
  if (!isAuthenticated && !isLoginPage) {
    const loginUrl = new URL("/login", req.nextUrl.origin);
    loginUrl.searchParams.set("callbackUrl", req.nextUrl.pathname);
    return Response.redirect(loginUrl);
  }

  // Redirect authenticated users away from login
  if (isAuthenticated && isLoginPage) {
    return Response.redirect(new URL("/chat", req.nextUrl.origin));
  }
});

export const config = {
  matcher: [
    // Protect all dashboard routes
    "/chat/:path*",
    "/datasets/:path*",
    "/models/:path*",
    "/login",
    // Protect root
    "/",
  ],
};
