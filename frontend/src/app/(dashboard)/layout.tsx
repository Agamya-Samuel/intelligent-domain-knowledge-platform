import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { SidebarUser } from "@/components/layout/sidebar-user";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";
import {
  MessageSquare,
  FolderOpen,
  Bot,
  Wrench,
  Scale,
  BarChart3,
  Settings,
  ListChecks,
} from "lucide-react";

const navItems = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/datasets", label: "Datasets", icon: FolderOpen },
  { href: "/models", label: "Models", icon: Bot },
  { href: "/fine-tune", label: "Fine-tune", icon: Wrench },
  { href: "/jobs", label: "Jobs", icon: ListChecks },
  { href: "/compare", label: "Compare", icon: Scale },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

/**
 * Dashboard layout — persistent sidebar + main content area.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="hidden md:flex w-56 flex-col border-r bg-muted/30 px-3 py-4">
        <Link
          href="/"
          className="mb-6 flex items-center gap-2 px-2 text-lg font-semibold tracking-tight"
        >
          IDKP
        </Link>

        <nav className="flex flex-1 flex-col gap-1">
          {navItems.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                buttonVariants({ variant: "ghost", size: "default" }),
                "justify-start gap-2 font-normal"
              )}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          ))}
        </nav>

        {/* Footer: user info from session */}
        <SidebarUser />
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
