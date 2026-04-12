import { Badge } from "@/components/ui/badge";
import {
  Inbox,
  MessageCircle,
  UserCheck,
  Search,
  Eye,
  CheckCircle,
  FileText,
  ShieldCheck,
  Send,
  Archive,
  AlertTriangle,
  XCircle,
  Clock,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

type StatusVariant = "info" | "warning" | "success" | "danger" | "neutral";

interface StatusConfig {
  label: string;
  variant: StatusVariant;
  icon: LucideIcon;
}

const REQUEST_STATUS_MAP: Record<string, StatusConfig> = {
  received: { label: "Received", variant: "info", icon: Inbox },
  clarification_needed: { label: "Clarification Needed", variant: "warning", icon: MessageCircle },
  assigned: { label: "Assigned", variant: "info", icon: UserCheck },
  searching: { label: "Searching", variant: "info", icon: Search },
  in_review: { label: "In Review", variant: "warning", icon: Eye },
  ready_for_release: { label: "Ready for Release", variant: "success", icon: CheckCircle },
  drafted: { label: "Drafted", variant: "info", icon: FileText },
  approved: { label: "Approved", variant: "success", icon: ShieldCheck },
  fulfilled: { label: "Fulfilled", variant: "success", icon: Send },
  sent: { label: "Fulfilled", variant: "success", icon: Send },
  closed: { label: "Closed", variant: "neutral", icon: Archive },
};

const DOCUMENT_STATUS_MAP: Record<string, StatusConfig> = {
  pending: { label: "Pending", variant: "warning", icon: Clock },
  completed: { label: "Completed", variant: "success", icon: CheckCircle },
  failed: { label: "Failed", variant: "danger", icon: XCircle },
  processing: { label: "Processing", variant: "info", icon: Clock },
};

const EXEMPTION_STATUS_MAP: Record<string, StatusConfig> = {
  flagged: { label: "Flagged", variant: "warning", icon: AlertTriangle },
  reviewed: { label: "Reviewed", variant: "info", icon: Eye },
  accepted: { label: "Accepted", variant: "success", icon: CheckCircle },
  rejected: { label: "Rejected", variant: "neutral", icon: XCircle },
};

const VARIANT_CLASSES: Record<StatusVariant, string> = {
  info: "badge-info",
  warning: "badge-warning",
  success: "badge-success",
  danger: "badge-danger",
  neutral: "badge-neutral",
};

type StatusDomain = "request" | "document" | "exemption";

interface StatusBadgeProps {
  status: string;
  domain?: StatusDomain;
  className?: string;
}

function getStatusConfig(status: string, domain: StatusDomain): StatusConfig {
  const maps: Record<StatusDomain, Record<string, StatusConfig>> = {
    request: REQUEST_STATUS_MAP,
    document: DOCUMENT_STATUS_MAP,
    exemption: EXEMPTION_STATUS_MAP,
  };
  return maps[domain][status] ?? {
    label: status.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
    variant: "neutral" as StatusVariant,
    icon: Clock,
  };
}

export function StatusBadge({ status, domain = "request", className }: StatusBadgeProps) {
  const config = getStatusConfig(status, domain);
  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 border-0 font-medium",
        VARIANT_CLASSES[config.variant],
        className
      )}
    >
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}
