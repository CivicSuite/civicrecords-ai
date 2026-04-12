import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface Stats { total_sources: number; active_sources: number; total_documents: number; documents_by_status: Record<string, number>; total_chunks: number; }
interface Document { id: string; filename: string; file_type: string; file_size: number; ingestion_status: string; ingestion_error: string | null; chunk_count: number; ingested_at: string | null; }
interface Props { token: string; }

export default function Ingestion({ token }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Stats>("/datasources/stats", { token }).then(setStats).catch((e) => setError(e.message));
    apiFetch<Document[]>("/documents/?limit=50", { token }).then(setDocs).catch((e) => setError(e.message));
  }, [token]);

  const statusColors: Record<string, string> = { completed: "text-green-600", processing: "text-blue-600", pending: "text-yellow-600", failed: "text-red-600" };

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Ingestion Dashboard</h2>
      {error && <p className="text-red-600 mb-4">{error}</p>}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg border border-gray-200"><p className="text-sm text-gray-500">Sources</p><p className="text-2xl font-semibold text-gray-900">{stats.active_sources}/{stats.total_sources}</p></div>
          <div className="bg-white p-4 rounded-lg border border-gray-200"><p className="text-sm text-gray-500">Documents</p><p className="text-2xl font-semibold text-gray-900">{stats.total_documents}</p></div>
          <div className="bg-white p-4 rounded-lg border border-gray-200"><p className="text-sm text-gray-500">Chunks</p><p className="text-2xl font-semibold text-gray-900">{stats.total_chunks}</p></div>
          <div className="bg-white p-4 rounded-lg border border-gray-200"><p className="text-sm text-gray-500">Completed</p><p className="text-2xl font-semibold text-green-600">{stats.documents_by_status.completed || 0}</p></div>
          <div className="bg-white p-4 rounded-lg border border-gray-200"><p className="text-sm text-gray-500">Failed</p><p className="text-2xl font-semibold text-red-600">{stats.documents_by_status.failed || 0}</p></div>
        </div>
      )}
      <h3 className="text-md font-semibold text-gray-900 mb-3">Recent Documents</h3>
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-gray-200 bg-gray-50">
            <th className="text-left px-4 py-3 font-medium text-gray-600">Filename</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Size</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Chunks</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Ingested</th>
          </tr></thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id} className="border-b border-gray-100">
                <td className="px-4 py-3 text-gray-900">{d.filename}</td>
                <td className="px-4 py-3 text-gray-600">{d.file_type}</td>
                <td className="px-4 py-3 text-gray-600">{(d.file_size / 1024).toFixed(1)} KB</td>
                <td className="px-4 py-3"><span className={`text-xs font-medium ${statusColors[d.ingestion_status] || "text-gray-600"}`}>{d.ingestion_status}</span>{d.ingestion_error && <span className="block text-xs text-red-400 truncate max-w-xs" title={d.ingestion_error}>{d.ingestion_error}</span>}</td>
                <td className="px-4 py-3 text-gray-600">{d.chunk_count}</td>
                <td className="px-4 py-3 text-gray-500">{d.ingested_at ? new Date(d.ingested_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
            {docs.length === 0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No documents ingested yet</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
