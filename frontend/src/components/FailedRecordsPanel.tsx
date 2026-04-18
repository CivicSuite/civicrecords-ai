import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

interface SyncFailure {
  id: string;
  source_path: string;
  error_message: string | null;
  error_class: string | null;
  retry_count: number;
  status: string;
  first_failed_at: string;
}

type PanelState = "loading" | "empty" | "populated" | "error";

export function FailedRecordsPanel({
  sourceId,
  syncPaused,
}: {
  sourceId: string;
  syncPaused: boolean;
}) {
  const [panelState, setPanelState] = useState<PanelState>("loading");
  const [failures, setFailures] = useState<SyncFailure[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function loadFailures() {
    setPanelState("loading");
    try {
      const resp = await fetch(
        `/datasources/${sourceId}/sync-failures?status=retrying&limit=50`
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: SyncFailure[] = await resp.json();
      setFailures(data);
      setPanelState(data.length === 0 ? "empty" : "populated");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Unknown error");
      setPanelState("error");
    }
  }

  useEffect(() => {
    void loadFailures();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId]);

  async function handleRetryAll() {
    await fetch(
      `/datasources/${sourceId}/sync-failures/retry-all?status=permanently_failed`,
      { method: "POST" }
    );
    void loadFailures();
  }

  async function handleDismissAll() {
    await fetch(
      `/datasources/${sourceId}/sync-failures/dismiss-all?status=permanently_failed`,
      { method: "POST" }
    );
    void loadFailures();
  }

  async function handleRetry(failureId: string) {
    await fetch(`/datasources/${sourceId}/sync-failures/${failureId}/retry`, { method: "POST" });
    void loadFailures();
  }

  async function handleDismiss(failureId: string) {
    await fetch(`/datasources/${sourceId}/sync-failures/${failureId}/dismiss`, { method: "POST" });
    void loadFailures();
  }

  async function handleUnpause() {
    await fetch(`/datasources/${sourceId}/unpause`, { method: "POST" });
    void loadFailures();
  }

  return (
    <div className="border-t p-4 bg-muted/30 space-y-3" aria-live="polite" aria-atomic="false">
      {/* Circuit open banner */}
      {syncPaused && (
        <div className="flex items-center justify-between rounded border border-amber-300 bg-amber-50 px-3 py-2">
          <span className="text-sm text-amber-800">
            ⚠️ This source is paused after repeated failures.
          </span>
          <Button size="sm" variant="outline" onClick={() => void handleUnpause()}>
            Unpause →
          </Button>
        </div>
      )}

      {/* Loading state */}
      {panelState === "loading" && (
        <p className="text-sm text-muted-foreground">Loading failed records…</p>
      )}

      {/* Zero state */}
      {panelState === "empty" && (
        <p className="text-sm text-muted-foreground italic">
          No failed records — this source is syncing cleanly.
        </p>
      )}

      {/* Error state */}
      {panelState === "error" && (
        <div className="flex items-center gap-2" role="alert">
          <p className="text-sm text-destructive">
            Failed to load sync failures. {errorMsg}
          </p>
          <Button size="sm" variant="ghost" onClick={() => void loadFailures()}>
            Retry?
          </Button>
        </div>
      )}

      {/* Populated state */}
      {panelState === "populated" && (
        <>
          {/* Bulk actions */}
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => void handleRetryAll()}>
              Retry all permanently failed
            </Button>
            <Button size="sm" variant="ghost" onClick={() => void handleDismissAll()}>
              Dismiss all permanently failed
            </Button>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left py-1 pr-3">Record path</th>
                  <th className="text-left py-1 pr-3">Error</th>
                  <th className="text-left py-1 pr-3">Retries</th>
                  <th className="text-left py-1 pr-3">Status</th>
                  <th className="text-left py-1 pr-3">First failed</th>
                  <th className="text-left py-1">Actions</th>
                </tr>
              </thead>
              <tbody>
                {failures.map((f) => (
                  <tr key={f.id} className="border-b hover:bg-muted/20">
                    <td className="py-1 pr-3 font-mono truncate max-w-[200px]" title={f.source_path}>
                      {f.source_path}
                    </td>
                    <td className="py-1 pr-3 truncate max-w-[150px]" title={f.error_message ?? ""}>
                      {f.error_class}: {f.error_message?.slice(0, 60)}
                    </td>
                    <td className="py-1 pr-3">{f.retry_count}</td>
                    <td className="py-1 pr-3">
                      <span className={
                        f.status === "permanently_failed" ? "text-destructive" :
                        f.status === "tombstone"          ? "text-muted-foreground" :
                        "text-amber-600"
                      }>
                        {f.status}
                      </span>
                    </td>
                    <td className="py-1 pr-3">{new Date(f.first_failed_at).toLocaleDateString()}</td>
                    <td className="py-1 flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => void handleRetry(f.id)}>
                        Retry
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => void handleDismiss(f.id)}>
                        Dismiss
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
