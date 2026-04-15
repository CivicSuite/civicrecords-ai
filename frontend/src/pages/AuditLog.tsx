import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { DataTable, type Column } from "@/components/data-table";
import { LoadingRegion } from "@/components/loading-region";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollText, Download } from "lucide-react";

interface AuditEntry {
  id: string;
  timestamp: string;
  user_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ai_generated: boolean;
}

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString();
}

export default function AuditLog({ token }: { token: string }) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<AuditEntry[]>("/audit/logs?limit=100", { token })
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [token]);

  const columns: Column<AuditEntry & Record<string, unknown>>[] = [
    {
      key: "timestamp",
      header: "Timestamp",
      render: (e) => (
        <span className="text-sm text-muted-foreground">
          {formatTimestamp(e.timestamp as string)}
        </span>
      ),
    },
    {
      key: "user_email",
      header: "User",
      render: (e) => (
        <span className="text-sm font-medium">
          {(e.user_email as string | null) || "System"}
        </span>
      ),
    },
    {
      key: "action",
      header: "Action",
      render: (e) => (
        <Badge variant="outline" className="text-xs">
          {e.action as string}
        </Badge>
      ),
    },
    {
      key: "resource_type",
      header: "Resource Type",
      render: (e) => (
        <span className="text-sm text-muted-foreground">
          {(e.resource_type as string | null) || "-"}
        </span>
      ),
    },
    {
      key: "resource_id",
      header: "Resource ID",
      render: (e) => (
        <span className="text-sm text-muted-foreground font-mono">
          {(e.resource_id as string | null)
            ? (e.resource_id as string).slice(0, 12) + "..."
            : "-"}
        </span>
      ),
    },
    {
      key: "ai_generated",
      header: "AI Generated",
      render: (e) => (
        <span
          className={`text-sm ${e.ai_generated ? "text-primary" : "text-muted-foreground"}`}
        >
          {e.ai_generated ? "Yes" : "No"}
        </span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Log"
        description="Recent system activity (last 100 entries)"
        actions={
          <Button
            variant="outline"
            onClick={async () => {
              try {
                const res = await fetch(`/api/audit/export?format=csv`, {
                  headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok) throw new Error(`Export failed: ${res.status}`);
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = "audit-log.csv";
                link.click();
                URL.revokeObjectURL(url);
              } catch (e) {
                setError(e instanceof Error ? e.message : "Export failed");
              }
            }}
          >
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        }
      />

      {error && (
        <Card className="border-destructive">
          <CardContent className="p-4">
            <p className="text-destructive text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      {entries.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="No audit entries"
          description="Audit log entries will appear here as system activity occurs."
        />
      ) : (
        <LoadingRegion loading={loading} label="Audit log entries">
          <DataTable
            columns={columns}
            data={entries as (AuditEntry & Record<string, unknown>)[]}
            rowKey={(e) => e.id as string}
            ariaLabel="Audit log entries"
          />
        </LoadingRegion>
      )}
    </div>
  );
}
