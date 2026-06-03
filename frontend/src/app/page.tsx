import { redirect } from "next/navigation";

/**
 * Root page — redirects authenticated users to /chat,
 * unauthenticated users to /login.
 * Auth check is handled by middleware (added in Task 4).
 * For now, redirect to /chat.
 */
export default function Home() {
  redirect("/chat");
}
