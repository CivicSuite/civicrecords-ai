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

export default function Dashboard({ token }: Props) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<SystemStatus>("/admin/status", { token })
      .then(setStatus)
      .catch((e) => setError(e.message));
  }, [token]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!status) return <p className="text-gray-500">Loading...</p>;

  const services = [
    { name: "Database", status: status.database },
    { name: "Ollama (LLM)", status: status.ollama },
    { name: "Redis (Queue)", status: status.redis },
  ];

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">System Dashboard</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {services.map((s) => (
          <div key={s.name} className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">{s.name}</p>
            <p className={`text-lg font-medium ${s.status === "connected" ? "text-green-600" : "text-red-600"}`}>
              {s.status}
            </p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <p className="text-sm text-gray-500">Version</p>
          <p className="text-lg font-medium text-gray-900">{status.version}</p>
        </div>
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <p className="text-sm text-gray-500">Users</p>
          <p className="text-lg font-medium text-gray-900">{status.user_count}</p>
        </div>
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <p className="text-sm text-gray-500">Audit Log Entries</p>
          <p className="text-lg font-medium text-gray-900">{status.audit_log_count}</p>
        </div>
      </div>
    </div>
  );
}
