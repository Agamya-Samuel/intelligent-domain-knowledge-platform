"use client";

import { useSession } from "next-auth/react";
import { LogOut } from "lucide-react";
import { signOut } from "next-auth/react";

/**
 * Sidebar user info — client component that reads the Auth.js session
 * and displays the signed-in user's name and email.
 */
export function SidebarUser() {
  const { data: session, status } = useSession();

  if (status === "loading") {
    return (
      <div className="mt-auto border-t pt-3">
        <div className="flex items-center gap-2 px-2">
          <div className="size-7 animate-pulse rounded-full bg-muted" />
          <div className="flex flex-1 flex-col gap-1">
            <div className="h-3 w-20 animate-pulse rounded bg-muted" />
            <div className="h-2.5 w-28 animate-pulse rounded bg-muted" />
          </div>
        </div>
      </div>
    );
  }

  if (!session?.user) {
    return (
      <div className="mt-auto border-t pt-3">
        <p className="px-2 text-xs text-muted-foreground">Not signed in</p>
      </div>
    );
  }

  const { name, email } = session.user;
  const initials = name
    ? name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : email?.[0]?.toUpperCase() ?? "?";

  return (
    <div className="mt-auto border-t pt-3">
      <div className="flex items-center gap-2 px-2">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">
          {initials}
        </div>
        <div className="flex flex-1 flex-col overflow-hidden">
          <span className="truncate text-xs font-medium text-foreground">
            {name || "User"}
          </span>
          {email && (
            <span className="truncate text-[10px] text-muted-foreground">
              {email}
            </span>
          )}
        </div>
        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Sign out"
        >
          <LogOut className="size-3.5" />
        </button>
      </div>
    </div>
  );
}
