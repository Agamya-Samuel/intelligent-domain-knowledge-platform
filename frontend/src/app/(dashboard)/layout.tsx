import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/chat", label: "Chat", icon: "💬" },
  { href: "/datasets", label: "Datasets", icon: "📁" },
  { href: "/models", label: "Models", icon: "🤖" },
  { href: "/fine-tune", label: "Fine-tune", icon: "🔧" },
] as const;

/**
 * Dashboard layout — persistent sidebar + main content area.
 * Auth session provider wrapper added in Task 4.
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
          {navItems.map(({ href, label, icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                buttonVariants({ variant: "ghost", size: "default" }),
                "justify-start gap-2 font-normal"
              )}
            >
              <span>{icon}</span>
              {label}
            </Link>
          ))}
        </nav>

        {/* Footer: user info placeholder */}
        <div className="mt-auto border-t pt-3">
          <p className="px-2 text-xs text-muted-foreground">
            Signed in as <span className="font-medium">—</span>
          </p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
