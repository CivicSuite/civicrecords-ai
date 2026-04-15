import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import {
  Search,
  FileText,
  Shield,
  FolderOpen,
  HardDrive,
  LayoutDashboard,
  Users,
  Building2,
  ClipboardList,
  Settings,
  ScrollText,
  type LucideIcon,
} from "lucide-react";

interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
}

const WORKFLOW_ITEMS: NavItem[] = [
  { path: "/search", label: "Search", icon: Search },
  { path: "/requests", label: "Requests", icon: FileText },
  { path: "/exemptions", label: "Exemptions", icon: Shield },
];

const SETUP_ITEMS: NavItem[] = [
  { path: "/onboarding", label: "Onboarding", icon: ClipboardList },
  { path: "/city-profile", label: "City Profile", icon: Building2 },
];

const ADMIN_ITEMS: NavItem[] = [
  { path: "/sources", label: "Sources", icon: FolderOpen },
  { path: "/ingestion", label: "Ingestion", icon: HardDrive },
  // Discovery deferred to v1.2 — no backend; nav item removed to avoid dead UI
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/users", label: "Users", icon: Users },
  { path: "/settings", label: "Settings", icon: Settings },
  { path: "/audit-log", label: "Audit Log", icon: ScrollText },
];

function NavLink({ item }: { item: NavItem }) {
  const location = useLocation();
  const isActive =
    item.path === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(item.path);

  return (
    <Link
      to={item.path}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
        "min-h-[44px]",
        isActive
          ? "bg-primary/10 text-primary border-l-2 border-primary -ml-px"
          : "text-muted-foreground hover:text-foreground hover:bg-muted"
      )}
      aria-current={isActive ? "page" : undefined}
    >
      <item.icon className="h-4 w-4 shrink-0" />
      {item.label}
    </Link>
  );
}

const LIAISON_HIDDEN_PATHS = new Set(["/users", "/audit-log", "/onboarding"]);

export function SidebarNav({ userRole }: { userRole?: string }) {
  const isLiaison = userRole === "liaison";

  const visibleSetupItems = isLiaison
    ? SETUP_ITEMS.filter((item) => !LIAISON_HIDDEN_PATHS.has(item.path))
    : SETUP_ITEMS;

  const visibleAdminItems = isLiaison
    ? ADMIN_ITEMS.filter((item) => !LIAISON_HIDDEN_PATHS.has(item.path))
    : ADMIN_ITEMS;

  return (
    <nav
      className="flex flex-col gap-1 px-3 py-4"
      role="navigation"
      aria-label="Main navigation"
    >
      <p className="px-3 mb-1 text-label uppercase text-muted-foreground">
        Workflow
      </p>
      {WORKFLOW_ITEMS.map((item) => (
        <NavLink key={item.path} item={item} />
      ))}

      <Separator className="my-3" />

      <p className="px-3 mb-1 text-label uppercase text-muted-foreground">
        Setup
      </p>
      {visibleSetupItems.map((item) => (
        <NavLink key={item.path} item={item} />
      ))}

      <Separator className="my-3" />

      <p className="px-3 mb-1 text-label uppercase text-muted-foreground">
        Administration
      </p>
      {visibleAdminItems.map((item) => (
        <NavLink key={item.path} item={item} />
      ))}
    </nav>
  );
}
