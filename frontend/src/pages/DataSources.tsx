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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [ingesting, setIngesting] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadSources = () => {
    setLoading(true);
    apiFetch<DataSource[]>("/datasources/", { token })
      .then(setSources)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(loadSources, [token]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiFetch("/datasources/", {
        token,
        method: "POST",
        body: JSON.stringify({ name, source_type: "directory", connection_config: { path } }),
      });
      setName("");
      setPath("");
      setShowForm(false);
      loadSources();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleIngest = async (sourceId: string) => {
    setIngesting(sourceId);
    try {
      await apiFetch(`/datasources/${sourceId}/ingest`, { token, method: "POST" });
    } catch (err: any) {
      setError(err.message);
    }
    setIngesting(null);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Data Sources</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn btn-primary"
          aria-expanded={showForm}
          aria-controls="add-source-form"
        >
          {showForm ? "Cancel" : "Add Source"}
        </button>
      </div>

      {error && (
        <div className="error-banner mb-4" role="alert" aria-live="assertive">
          {error}
        </div>
      )}

      {showForm && (
        <form
          id="add-source-form"
          onSubmit={handleCreate}
          className="bg-white p-4 rounded-lg border border-gray-200 mb-4 space-y-3"
          aria-label="Add new data source"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="source-name" className="form-label">
                Name
              </label>
              <input
                id="source-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="form-input"
                aria-label="Data source name"
                required
              />
            </div>
            <div>
              <label htmlFor="source-path" className="form-label">
                Directory Path
              </label>
              <input
                id="source-path"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="/data/city-documents"
                className="form-input"
                aria-label="Directory path"
                required
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="btn btn-primary"
            aria-busy={submitting}
          >
            {submitting ? (
              <span className="flex items-center gap-2">
                <span className="spinner" aria-hidden="true" />
                Creating…
              </span>
            ) : (
              "Create Source"
            )}
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center gap-3 py-12 text-gray-500">
            <span className="spinner" aria-hidden="true" />
            <span>Loading data sources…</span>
          </div>
        ) : sources.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            <p className="font-medium text-gray-700 mb-1">No data sources configured yet.</p>
            <p className="text-sm">Add a directory to start indexing documents.</p>
          </div>
        ) : (
          <table className="w-full text-sm" aria-label="Data sources">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-600" scope="col">Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600" scope="col">Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600" scope="col">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600" scope="col">Last Ingestion</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600" scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id} className="border-b border-gray-100">
                  <td className="px-4 py-3 text-gray-900">{s.name}</td>
                  <td className="px-4 py-3 text-gray-600">{s.source_type}</td>
                  <td className="px-4 py-3">
                    <span className={`badge ${s.is_active ? "badge-green" : "badge-red"}`}>
                      {s.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {s.last_ingestion_at ? new Date(s.last_ingestion_at).toLocaleString() : "Never"}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleIngest(s.id)}
                      disabled={ingesting === s.id}
                      className="text-blue-600 hover:text-blue-800 text-sm font-medium disabled:opacity-50"
                      aria-label={`Ingest documents from ${s.name}`}
                      aria-busy={ingesting === s.id}
                    >
                      {ingesting === s.id ? (
                        <span className="flex items-center gap-1">
                          <span className="spinner spinner-sm" aria-hidden="true" />
                          Ingesting…
                        </span>
                      ) : (
                        "Ingest Now"
                      )}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
