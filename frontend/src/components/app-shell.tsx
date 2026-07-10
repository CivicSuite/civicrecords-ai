import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { AuditDrawer } from "@/components/audit-drawer";
import { CommandPalette } from "@/components/command-palette";
import { SidebarNav } from "@/components/sidebar-nav";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { VersionFooter } from "@/components/version-footer";
import { FileSearch, HelpCircle, Keyboard, LogOut, Menu, PanelsTopLeft, X } from "lucide-react";

const suiteLauncherUrl =
  (import.meta.env.VITE_CIVICSUITE_LAUNCHER_URL as string | undefined)?.trim() ||
  "http://127.0.0.1:18082/";

interface AppShellProps {
  children: React.ReactNode;
  onSignOut: () => void;
  userEmail?: string;
  userRole?: string;
}

/**
 * Shared sidebar contents — rendered twice:
 *   • Inside the desktop `<aside>` at `md:` and up.
 *   • Inside the mobile slide-in drawer below `md:`.
 * Extracted so the two contexts stay in lockstep and the nav order,
 * styling, and sign-out controls never drift between viewports.
 */
function SidebarContents({
  userRole,
  userEmail,
  onSignOut,
}: {
  userRole?: string;
  userEmail?: string;
  onSignOut: () => void;
}) {
  return (
    <>
      {/* Logo */}
      <div
        className="flex items-center gap-2 px-6 shrink-0"
        style={{ height: "var(--header-height)" }}
      >
        <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
          <span className="text-sm font-bold text-primary-foreground">CS</span>
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground leading-tight">CivicSunshine</p>
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
    </>
  );
}

export function AppShell({ children, onSignOut, userEmail, userRole }: AppShellProps) {
  // Mobile drawer open state. Always closed on route change so users aren't
  // stuck with a drawer covering the content they just navigated to.
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const location = useLocation();
  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-16 md:focus:left-2 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md"
      >
        Skip to main content
      </a>

      {/* Desktop sidebar — visible at md (768px) and above */}
      <aside
        className="hidden md:flex flex-col border-r bg-card"
        style={{ width: "var(--sidebar-width)" }}
        aria-label="Primary navigation"
      >
        <SidebarContents userRole={userRole} userEmail={userEmail} onSignOut={onSignOut} />
      </aside>

      {/* Mobile slide-in drawer — Base UI Dialog gives us focus trap + ESC close */}
      <DialogPrimitive.Root open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Backdrop
            className="fixed inset-0 z-40 bg-black/40 md:hidden data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0"
          />
          <DialogPrimitive.Popup
            id="app-mobile-nav"
            aria-label="Primary navigation"
            className="fixed inset-y-0 left-0 z-50 flex flex-col w-[280px] max-w-[85vw] bg-card border-r outline-none md:hidden data-open:animate-in data-open:slide-in-from-left data-closed:animate-out data-closed:slide-out-to-left"
          >
            <DialogPrimitive.Title className="sr-only">
              Primary navigation
            </DialogPrimitive.Title>
            <div className="absolute right-2 top-2 z-10">
              <DialogPrimitive.Close
                render={
                  <Button variant="ghost" size="icon-sm" aria-label="Close navigation" />
                }
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </DialogPrimitive.Close>
            </div>
            <SidebarContents userRole={userRole} userEmail={userEmail} onSignOut={onSignOut} />
          </DialogPrimitive.Popup>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        {/* Header */}
        <header
          className="flex items-center gap-2 border-b px-4 md:px-6 bg-background"
          style={{ height: "var(--header-height)" }}
        >
          {/* Mobile-only hamburger + compact logo (desktop gets full logo in sidebar) */}
          <Button
            variant="ghost"
            size="icon-sm"
            className="md:hidden"
            aria-label="Open navigation"
            aria-expanded={mobileNavOpen}
            aria-controls="app-mobile-nav"
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </Button>
          <div className="md:hidden flex items-center gap-2">
            <div className="h-7 w-7 rounded-md bg-primary flex items-center justify-center">
              <span className="text-xs font-bold text-primary-foreground">CS</span>
            </div>
            <span className="text-sm font-semibold text-foreground">CivicSunshine</span>
          </div>

          <div className="ml-auto flex items-center gap-1">
            <a
              href={suiteLauncherUrl}
              aria-label="Suite launcher"
              className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg px-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <PanelsTopLeft className="h-4 w-4" aria-hidden="true" />
              <span className="ml-1 hidden lg:inline">Suite launcher</span>
            </a>
            <Button
              variant="ghost"
              size="sm"
              className="gap-2 text-muted-foreground"
              aria-label="Show audit"
              onClick={() => setAuditOpen(true)}
            >
              <FileSearch className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Audit</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="gap-2 text-muted-foreground"
              aria-label="Open command palette"
              onClick={() => setCommandOpen(true)}
            >
              <Keyboard className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Command</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="gap-2 text-muted-foreground"
              aria-label="Help"
            >
              <HelpCircle className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Help</span>
            </Button>
          </div>
        </header>

        {/* Scrollable content */}
        <main id="main-content" className="flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6" role="main">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>

        {/* Footer */}
        <footer className="border-t px-4 md:px-6 py-2 text-xs text-muted-foreground flex items-center justify-between gap-2">
          <VersionFooter />
          <span className="whitespace-nowrap hidden sm:inline">Help &middot; Audit Log</span>
        </footer>
      </div>
      <AuditDrawer open={auditOpen} onOpenChange={setAuditOpen} />
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  );
}
