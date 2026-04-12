import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Users,
  FileText,
  Shield,
  Search,
  Plus,
  Database,
  Cpu,
  Zap,
  CheckCircle,
  XCircle,
  Inbox,
  AlertTriangle,
  Clock,
  CalendarCheck,
} from "lucide-react";

interface SystemStatus {
  version: string;
  database: { status: string };
  ollama: { status: string };
  redis: { status: string };
  user_count: number;
  audit_log_count: number;
}

interface OperationalMetrics {
  average_response_time_days: number | null;
  median_response_time_days: number | null;
  requests_by_status: Record<string, number>;
  requests_by_department: Record<string, number>;
  deadline_compliance_rate: number;
  total_open: number;
  total_closed: number;
  total_overdue: number;
  clarification_frequency: number;
  top_request_topics: string[];
}

function ServiceIndicator({ name, status, icon: Icon }: { name: string; status: string; icon: React.ElementType }) {
  const isConnected = status === "connected" || status === "ok" || status === "healthy";
  return (
    <div className="flex items-center gap-2 text-sm">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <span className="text-foreground">{name}</span>
      {isConnected ? (
        <CheckCircle className="h-3.5 w-3.5 text-success" />
      ) : (
        <XCircle className="h-3.5 w-3.5 text-destructive" />
      )}
    </div>
  );
}

export default function Dashboard({ token }: { token: string }) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analytics, setAnalytics] = useState<OperationalMetrics | null>(null);

  useEffect(() => {
    apiFetch<SystemStatus>("/admin/status", { token })
      .then(setStatus)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));

    apiFetch<OperationalMetrics>("/analytics/operational", { token })
      .then(setAnalytics)
      .catch(() => {
        // Analytics are non-critical — silently suppress errors
        setAnalytics(null);
      });
  }, [token]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="Dashboard" />
        <Card className="border-destructive">
          <CardContent className="p-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!status) return null;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        description={`CivicRecords AI v${status.version}`}
      />

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Registered Users" value={status.user_count} icon={Users} />
        <StatCard label="Audit Log Entries" value={status.audit_log_count} icon={FileText} />
        <StatCard label="System Version" value={status.version} icon={Shield} />
      </div>

      {/* Operational analytics — shown only when the call succeeds */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            label="Open Requests"
            value={analytics.total_open}
            icon={Inbox}
          />
          <StatCard
            label="Overdue Requests"
            value={analytics.total_overdue}
            icon={AlertTriangle}
            variant={analytics.total_overdue > 0 ? "danger" : undefined}
          />
          <StatCard
            label="Avg Response Time"
            value={
              analytics.average_response_time_days != null
                ? `${analytics.average_response_time_days.toFixed(1)} days`
                : "N/A"
            }
            icon={Clock}
          />
          <StatCard
            label="Deadline Compliance"
            value={`${(analytics.deadline_compliance_rate * 100).toFixed(1)}%`}
            icon={CalendarCheck}
          />
        </div>
      )}

      {/* Service health — compact inline */}
      <Card className="shadow-none">
        <CardHeader className="pb-3">
          <CardTitle className="text-label uppercase text-muted-foreground">Services</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-6">
            <ServiceIndicator name="Database (PostgreSQL)" status={status.database?.status} icon={Database} />
            <ServiceIndicator name="Ollama (LLM Engine)" status={status.ollama?.status} icon={Cpu} />
            <ServiceIndicator name="Redis (Task Queue)" status={status.redis?.status} icon={Zap} />
          </div>
        </CardContent>
      </Card>

      {/* Quick actions */}
      <Card className="shadow-none">
        <CardHeader className="pb-3">
          <CardTitle className="text-label uppercase text-muted-foreground">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => window.location.href = "/requests"}>
              <Plus className="h-4 w-4 mr-2" />
              New Request
            </Button>
            <Button variant="outline" onClick={() => window.location.href = "/search"}>
              <Search className="h-4 w-4 mr-2" />
              Search Records
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
