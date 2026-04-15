import { SidebarNav } from "@/components/sidebar-nav";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { LogOut, HelpCircle } from "lucide-react";

interface AppShellProps {
  children: React.ReactNode;
  onSignOut: () => void;
  userEmail?: string;
  userRole?: string;
}

export function AppShell({ children, onSignOut, userEmail, userRole }: AppShellProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md"
      >
        Skip to main content
      </a>
      {/* Sidebar */}
      <aside
        className="flex flex-col border-r bg-card"
        style={{ width: "var(--sidebar-width)" }}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-6" style={{ height: "var(--header-height)" }}>
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-sm font-bold text-primary-foreground">CR</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground leading-tight">CivicRecords</p>
            <p className="text-xs text-muted-foreground leading-tight">AI</p>
          </div>
        </div>

        <Separator />

        {/* Navigation */}
        <div className="flex-1 overflow-y-auto">
          <SidebarNav userRole={userRole} />
        </div>

        {/* Footer */}
        <div className="border-t p-4">
          <p className="text-xs text-muted-foreground truncate mb-2">{userEmail}</p>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 text-muted-foreground"
            onClick={onSignOut}
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header
          className="flex items-center justify-end gap-3 border-b px-6 bg-background"
          style={{ height: "var(--header-height)" }}
        >
          <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground">
            <HelpCircle className="h-4 w-4" />
            Help
          </Button>
        </header>

        {/* Scrollable content */}
        <main id="main-content" className="flex-1 overflow-y-auto p-6" role="main">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>

        {/* Footer */}
        <footer className="border-t px-6 py-2 text-xs text-muted-foreground flex items-center justify-between">
          <span>CivicRecords AI v1.1.0 &middot; Apache 2.0</span>
          <span>Help &middot; Audit Log</span>
        </footer>
      </div>
    </div>
  );
}
