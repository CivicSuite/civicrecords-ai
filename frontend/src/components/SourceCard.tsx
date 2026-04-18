import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { useState, useCallback } from "react";
import { useSyncNow } from "@/hooks/useSyncNow";
import { FailedRecordsPanel } from "./FailedRecordsPanel";

export interface DataSource {
  id: string;
  name: string;
  source_type: string;
  is_active: boolean;
  health_status: "healthy" | "degraded" | "circuit_open";
  last_sync_at: string | null;
  next_sync_at: string | null;
  sync_schedule: string | null;
  schedule_enabled: boolean;
  sync_paused: boolean;
  last_sync_status: string | null;
  active_failure_count: number;
  consecutive_failure_count: number;
}

const HEALTH_BADGE: Record<string, { dot: string; label: string }> = {
  healthy:      { dot: "bg-green-500",  label: "Healthy" },
  degraded:     { dot: "bg-amber-500",  label: "Degraded" },
  circuit_open: { dot: "bg-red-500",    label: "Paused" },
};

function formatDateTime(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  const utcStr = d.toUTCString().replace(" GMT", " UTC");
  const localStr = d.toLocaleString();
  return `${utcStr} (${localStr})`;
}

function ScheduleLabel({ source }: { source: DataSource }) {
  if (!source.sync_schedule || !source.schedule_enabled) {
    return <span className="text-muted-foreground text-sm">Manual only</span>;
  }
  if (source.sync_paused) {
    return (
      <span className="text-amber-600 text-sm font-medium">
        ⚠️ Paused — check failed records
      </span>
    );
  }
  return (
    <span className="text-sm">
      Next: {formatDateTime(source.next_sync_at)}
    </span>
  );
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function SourceCard({
  source,
  onRefresh,
  token,
}: {
  source: DataSource;
  onRefresh: () => void;
  token: string;
}) {
  const [failuresOpen, setFailuresOpen] = useState(false);
  const health = HEALTH_BADGE[source.health_status] ?? HEALTH_BADGE.healthy;

  const handleSyncComplete = useCallback(() => {
    onRefresh();
  }, [onRefresh]);

  const { isSyncing, elapsedSeconds, triggerSync } = useSyncNow(source.id, handleSyncComplete, token);

  return (
    <Card className="overflow-hidden">
      <div className="flex">
        {/* Left panel */}
        <div className="w-[90px] bg-[#EBF3FA] flex flex-col items-center justify-center gap-2 p-3">
          <div className="text-3xl">
            {source.source_type === "rest_api"    ? "🌐" :
             source.source_type === "odbc"        ? "🗄️" :
             source.source_type === "imap_email"  ? "📧" : "📁"}
          </div>
          <div className="flex items-center gap-1">
            <span
              className={`w-2 h-2 rounded-full ${health.dot}`}
              aria-label={`Health: ${health.label}`}
              role="img"
            />
            <span className="text-xs" aria-hidden="true">{health.label}</span>
          </div>
          <Badge variant="outline" className="text-xs">
            {source.source_type}
          </Badge>
        </div>

        {/* Right panel — min-w-0 lets flex-1 shrink below min-content at narrow widths */}
        <div className="flex-1 min-w-0 p-4 space-y-3">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-base">{source.name}</h3>
              <span className={`text-xs ${source.is_active ? "text-green-600" : "text-muted-foreground"}`}>
                {source.is_active ? "Active" : "Inactive"}
              </span>
            </div>
            {source.active_failure_count > 0 && (
              <Badge variant="destructive" className="text-xs">
                {source.active_failure_count} failed
              </Badge>
            )}
          </div>

          {/* Metadata grid */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <div>
              <span className="text-muted-foreground">Last sync:</span>{" "}
              {formatDateTime(source.last_sync_at)}
            </div>
            <div>
              <span className="text-muted-foreground">Schedule:</span>{" "}
              <ScheduleLabel source={source} />
            </div>
          </div>

          {/* Actions — wrap onto second row when card is narrow (1024px × 3-col grid) */}
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={isSyncing}
              onClick={triggerSync}
              aria-label={isSyncing
                ? (elapsedSeconds > 0 ? `Syncing, ${formatElapsed(elapsedSeconds)} elapsed` : "Syncing in progress")
                : "Sync Now"}
            >
              {isSyncing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" aria-hidden="true" />
                  <span aria-live="polite" aria-atomic="true">
                    {elapsedSeconds > 0 ? `Syncing for ${formatElapsed(elapsedSeconds)}…` : "Syncing…"}
                  </span>
                </>
              ) : (
                "Sync Now"
              )}
            </Button>
            <Button size="sm" variant="ghost">
              Edit
            </Button>
            {source.active_failure_count > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setFailuresOpen((o) => !o)}
              >
                {failuresOpen ? "Hide" : "View"} failures
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Failed records panel */}
      {failuresOpen && (
        <div role="region" aria-label={`Failed records for ${source.name}`} aria-live="polite">
          <FailedRecordsPanel sourceId={source.id} syncPaused={source.sync_paused} token={token} />
        </div>
      )}
    </Card>
  );
}
