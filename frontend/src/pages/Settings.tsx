import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import type { components } from "@/generated/api";
import {
  Database,
  Cpu,
  Zap,
  CheckCircle,
  XCircle,
  Mail,
  Clock,
  ShieldCheck,
  Server,
  type LucideIcon,
} from "lucide-react";

interface HealthResponse {
  status: string;
  version: string;
}

// Backend /admin/status returns flat strings for each service
// (components["schemas"]["SystemStatus"]). The additional optional fields
// (smtp_configured, audit_retention_days, llm_model, data_sovereignty)
// are surfaced by the same endpoint but not yet in the OpenAPI schema;
// they are treated as optional client-side until the schema catches up.
type SystemStatus = components["schemas"]["SystemStatus"] & {
  smtp_configured?: boolean;
  audit_retention_days?: number;
  llm_model?: string;
  data_sovereignty?: boolean;
};

function isServiceHealthy(status: string | undefined): boolean {
  return status === "connected" || status === "ok" || status === "healthy";
}

function StatusRow({
  label,
  icon: Icon,
  status,
  detail,
}: {
  label: string;
  icon: LucideIcon;
  status: "ok" | "error" | "info";
  detail: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2 text-sm">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <span className="text-foreground font-medium">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">{detail}</span>
        {status === "ok" && <CheckCircle className="h-4 w-4 text-success" />}
        {status === "error" && <XCircle className="h-4 w-4 text-destructive" />}
      </div>
    </div>
  );
}

export default function Settings({ token }: { token: string }) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      apiFetch<HealthResponse>("/health", { token }),
      apiFetch<SystemStatus>("/admin/status", { token }),
    ])
      .then(([h, s]) => {
        setHealth(h);
        setStatus(s);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="Settings" />
        <Card className="border-destructive">
          <CardContent className="p-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!health || !status) return null;

  const dbOk = isServiceHealthy(status.database);
  const ollamaOk = isServiceHealthy(status.ollama);
  const redisOk = isServiceHealthy(status.redis);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Settings"
        description="System configuration and status overview"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* System Info */}
        <Card className="shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="text-label uppercase text-muted-foreground">
              System Info
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <StatusRow
              label="Version"
              icon={Server}
              status="info"
              detail={`v${health.version}`}
            />
            <StatusRow
              label="Database (PostgreSQL)"
              icon={Database}
              status={dbOk ? "ok" : "error"}
              detail={status.database ?? "unknown"}
            />
            <StatusRow
              label="Ollama (LLM Engine)"
              icon={Cpu}
              status={ollamaOk ? "ok" : "error"}
              detail={status.ollama ?? "unknown"}
            />
            <StatusRow
              label="Redis (Task Queue)"
              icon={Zap}
              status={redisOk ? "ok" : "error"}
              detail={status.redis ?? "unknown"}
            />
          </CardContent>
        </Card>

        {/* Email & Notifications */}
        <Card className="shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="text-label uppercase text-muted-foreground">
              Email & Notifications
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <StatusRow
              label="SMTP Configuration"
              icon={Mail}
              status={status.smtp_configured ? "ok" : "error"}
              detail={status.smtp_configured ? "Configured" : "Not configured"}
            />
          </CardContent>
        </Card>

        {/* Audit & Compliance */}
        <Card className="shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="text-label uppercase text-muted-foreground">
              Audit & Compliance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <StatusRow
              label="Audit Retention"
              icon={Clock}
              status="info"
              detail={
                status.audit_retention_days
                  ? `${status.audit_retention_days} days`
                  : "Default"
              }
            />
            <StatusRow
              label="Data Sovereignty"
              icon={ShieldCheck}
              status={status.data_sovereignty !== false ? "ok" : "error"}
              detail={
                status.data_sovereignty !== false ? "Verified" : "Not verified"
              }
            />
          </CardContent>
        </Card>

        {/* AI / LLM */}
        <Card className="shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="text-label uppercase text-muted-foreground">
              AI / LLM Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2 text-sm">
                <Cpu className="h-4 w-4 text-muted-foreground" />
                <span className="text-foreground font-medium">
                  Current Model
                </span>
              </div>
              <Badge variant="outline" className="text-xs">
                {status.llm_model || "Not configured"}
              </Badge>
            </div>
            <StatusRow
              label="Ollama Status"
              icon={Cpu}
              status={ollamaOk ? "ok" : "error"}
              detail={ollamaOk ? "Running" : "Offline"}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
