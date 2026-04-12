import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface SystemStatus {
  version: string;
  database: string;
  ollama: string;
  redis: string;
  user_count: number;
  audit_log_count: number;
}

interface Props {
  token: string;
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full mr-2 ${ok ? "bg-green-500" : "bg-red-500"}`}
      aria-label={ok ? "Connected" : "Disconnected"}
    />
  );
}

export default function Dashboard({ token }: Props) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<SystemStatus>("/admin/status", { token })
      .then(setStatus)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load system status"))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="spinner" aria-label="Loading dashboard" />
        <span className="ml-3 text-gray-500">Loading system status...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-banner" role="alert">
        <strong>Unable to load dashboard:</strong> {error}
      </div>
    );
  }

  if (!status) return null;

  const services = [
    { name: "Database (PostgreSQL)", status: status.database, icon: "🗄️" },
    { name: "Ollama (LLM Engine)", status: status.ollama, icon: "🤖" },
    { name: "Redis (Task Queue)", status: status.redis, icon: "⚡" },
  ];

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-900">System Dashboard</h2>
        <p className="text-sm text-gray-500 mt-1">CivicRecords AI v{status.version}</p>
      </div>

      <section aria-label="Service health">
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">Services</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          {services.map((s) => (
            <div
              key={s.name}
              className="bg-white p-5 rounded-lg border border-gray-200 flex items-center gap-3"
            >
              <span className="text-2xl" role="img" aria-hidden="true">{s.icon}</span>
              <div>
                <p className="text-sm text-gray-600">{s.name}</p>
                <p className="flex items-center text-sm font-medium">
                  <StatusDot ok={s.status === "connected"} />
                  {s.status === "connected" ? "Connected" : s.status}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section aria-label="System statistics">
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">Overview</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white p-5 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Registered Users</p>
            <p className="text-3xl font-semibold text-gray-900 mt-1">{status.user_count}</p>
          </div>
          <div className="bg-white p-5 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Audit Log Entries</p>
            <p className="text-3xl font-semibold text-gray-900 mt-1">{status.audit_log_count}</p>
          </div>
          <div className="bg-white p-5 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">System Version</p>
            <p className="text-3xl font-semibold text-gray-900 mt-1">{status.version}</p>
          </div>
        </div>
      </section>
    </div>
  );
}
