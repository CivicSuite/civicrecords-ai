import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";
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
  Activity,
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

interface AuditLogEntry {
  id: string;
  action: string;
  actor_email?: string;
  target_type?: string;
  target_id?: string;
  created_at: string;
  details?: string;
}

interface DeadlineRequest {
  id: string;
  requester_name: string;
  description: string;
  status: string;
  statutory_deadline: string;
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
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [approachingDeadlines, setApproachingDeadlines] = useState<DeadlineRequest[]>([]);
  const [coverageGaps, setCoverageGaps] = useState<{
    jurisdictions_without_rules: string[];
    departments_without_staff: { id: string; name: string }[];
    uncovered_categories: string[];
    total_gaps: number;
  } | null>(null);

  useEffect(() => {
    apiFetch<SystemStatus>("/admin/status", { token })
      .then(setStatus)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));

    apiFetch<OperationalMetrics>("/analytics/operational", { token })
      .then(setAnalytics)
      .catch(() => {
        setAnalytics(null);
      });

    // Recent activity: fetch last 10 audit log entries
    apiFetch<AuditLogEntry[]>("/admin/audit-log?limit=10", { token })
      .then(setAuditLog)
      .catch(() => setAuditLog([]));

    // Coverage gaps
    apiFetch<typeof coverageGaps>("/admin/coverage-gaps", { token })
      .then(setCoverageGaps)
      .catch(() => setCoverageGaps(null));

    // Approaching deadlines: fetch open requests, filter client-side for deadlines within 3 days
    apiFetch<DeadlineRequest[]>("/requests/?limit=100", { token })
      .then((reqs) => {
        const now = Date.now();
        const threeDays = 3 * 24 * 60 * 60 * 1000;
        const approaching = reqs.filter((r) => {
          if (!r.statutory_deadline) return false;
          const deadline = new Date(r.statutory_deadline).getTime();
          const diff = deadline - now;
          return diff >= 0 && diff <= threeDays;
        });
        setApproachingDeadlines(approaching);
      })
      .catch(() => setApproachingDeadlines([]));
  }, [token]);

  if (loading) {
    return (
      <div className="space-y-6" role="status" aria-label="Loading dashboard data">
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
            value={`${analytics.deadline_compliance_rate.toFixed(1)}%`}
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

      {/* Requests by Status */}
      {analytics && Object.keys(analytics.requests_by_status).length > 0 && (
        <Card className="shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="text-label uppercase text-muted-foreground">Requests by Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(analytics.requests_by_status).map(([statusKey, count]) => {
                const total = Object.values(analytics.requests_by_status).reduce((a, b) => a + b, 0);
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                return (
                  <div key={statusKey} className="flex items-center gap-3">
                    <StatusBadge status={statusKey} domain="request" className="w-32 justify-start" />
                    <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium w-12 text-right">{count}</span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Approaching Deadlines */}
      <Card className="shadow-none">
        <CardHeader className="pb-3">
          <CardTitle className="text-label uppercase text-muted-foreground flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Approaching Deadlines (within 3 days)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {approachingDeadlines.length === 0 ? (
            <p className="text-sm text-muted-foreground">No requests with upcoming deadlines.</p>
          ) : (
            <div className="space-y-3">
              {approachingDeadlines.map((r: DeadlineRequest) => {
                const days = Math.ceil(
                  (new Date(r.statutory_deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
                );
                return (
                  <div
                    key={r.id}
                    className="flex items-center justify-between p-3 rounded-lg border cursor-pointer hover:bg-muted/50 transition-colors"
                    onClick={() => (window.location.href = `/requests/${r.id}`)}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{r.requester_name}</p>
                      <p className="text-xs text-muted-foreground truncate">{r.description}</p>
                    </div>
                    <div className="ml-3 flex items-center gap-2">
                      <StatusBadge status={r.status} domain="request" />
                      <span className={`text-xs font-semibold px-2 py-1 rounded ${days === 0 ? "bg-destructive/10 text-destructive" : "bg-warning/10 text-warning"}`}>
                        {days === 0 ? "Due today" : `${days}d left`}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Activity Timeline */}
      <Card className="shadow-none">
        <CardHeader className="pb-3">
          <CardTitle className="text-label uppercase text-muted-foreground flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Recent Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {auditLog.length === 0 ? (
            <p className="text-sm text-muted-foreground">No recent activity recorded.</p>
          ) : (
            <div className="relative">
              <div className="absolute left-3 top-0 bottom-0 w-px bg-border" />
              <div className="space-y-4">
                {auditLog.map((entry: AuditLogEntry) => (
                  <div key={entry.id} className="flex items-start gap-4 relative">
                    <div className="w-6 h-6 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center flex-shrink-0 z-10">
                      <FileText className="h-3 w-3 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0 pt-0.5">
                      <p className="text-sm">
                        <span className="font-medium">{entry.actor_email ?? "System"}</span>
                        {" "}
                        <span className="text-muted-foreground">{entry.action.replace(/_/g, " ")}</span>
                        {entry.target_type && (
                          <span className="text-muted-foreground"> on {entry.target_type}</span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(entry.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Coverage Gaps */}
      {coverageGaps && coverageGaps.total_gaps > 0 && (
        <Card className="shadow-none border-warning">
          <CardHeader className="pb-3">
            <CardTitle className="text-label uppercase text-muted-foreground flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" />
              Coverage Gaps ({coverageGaps.total_gaps})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {coverageGaps.uncovered_categories.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Exemption categories without rules</p>
                  <div className="flex flex-wrap gap-1">
                    {coverageGaps.uncovered_categories.map((c) => (
                      <span key={c} className="text-xs px-2 py-0.5 rounded-full bg-warning-light text-warning">{c}</span>
                    ))}
                  </div>
                </div>
              )}
              {coverageGaps.departments_without_staff.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Departments without assigned staff</p>
                  <div className="flex flex-wrap gap-1">
                    {coverageGaps.departments_without_staff.map((d) => (
                      <span key={d.id} className="text-xs px-2 py-0.5 rounded-full bg-warning-light text-warning">{d.name}</span>
                    ))}
                  </div>
                </div>
              )}
              {coverageGaps.jurisdictions_without_rules.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">
                    Jurisdictions without exemption rules ({coverageGaps.jurisdictions_without_rules.length} of 51)
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {coverageGaps.jurisdictions_without_rules.slice(0, 10).join(", ")}
                    {coverageGaps.jurisdictions_without_rules.length > 10 && ` +${coverageGaps.jurisdictions_without_rules.length - 10} more`}
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

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
