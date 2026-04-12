import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface DataSource {
  id: string;
  name: string;
  source_type: string;
  connection_config: Record<string, string>;
  is_active: boolean;
  created_at: string;
  last_ingestion_at: string | null;
}

interface Props {
  token: string;
}

export default function DataSources({ token }: Props) {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [ingesting, setIngesting] = useState<string | null>(null);

  const loadSources = () => {
    apiFetch<DataSource[]>("/datasources/", { token }).then(setSources).catch((e) => setError(e.message));
  };

  useEffect(loadSources, [token]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/datasources/", { token, method: "POST", body: JSON.stringify({ name, source_type: "directory", connection_config: { path } }) });
      setName(""); setPath(""); setShowForm(false); loadSources();
    } catch (err: any) { setError(err.message); }
  };

  const handleIngest = async (sourceId: string) => {
    setIngesting(sourceId);
    try { await apiFetch(`/datasources/${sourceId}/ingest`, { token, method: "POST" }); } catch (err: any) { setError(err.message); }
    setIngesting(null);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Data Sources</h2>
        <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">{showForm ? "Cancel" : "Add Source"}</button>
      </div>
      {error && <p className="text-red-600 mb-4">{error}</p>}
      {showForm && (
        <form onSubmit={handleCreate} className="bg-white p-4 rounded-lg border border-gray-200 mb-4 space-y-3">
          <div><label className="block text-sm font-medium text-gray-700 mb-1">Name</label><input value={name} onChange={(e) => setName(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" required /></div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1">Directory Path</label><input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/data/city-documents" className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" required /></div>
          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">Create Source</button>
        </form>
      )}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-gray-200 bg-gray-50">
            <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Last Ingestion</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
          </tr></thead>
          <tbody>{sources.map((s) => (
            <tr key={s.id} className="border-b border-gray-100">
              <td className="px-4 py-3 text-gray-900">{s.name}</td>
              <td className="px-4 py-3 text-gray-600">{s.source_type}</td>
              <td className="px-4 py-3"><span className={`text-xs ${s.is_active ? "text-green-600" : "text-red-600"}`}>{s.is_active ? "Active" : "Inactive"}</span></td>
              <td className="px-4 py-3 text-gray-500">{s.last_ingestion_at ? new Date(s.last_ingestion_at).toLocaleString() : "Never"}</td>
              <td className="px-4 py-3"><button onClick={() => handleIngest(s.id)} disabled={ingesting === s.id} className="text-blue-600 hover:text-blue-800 text-sm font-medium disabled:opacity-50">{ingesting === s.id ? "Ingesting..." : "Ingest Now"}</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
