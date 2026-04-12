import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "@/lib/api";

interface Request {
  id: string;
  requester_name: string;
  requester_email: string | null;
  description: string;
  status: string;
  statutory_deadline: string | null;
  assigned_to: string | null;
  created_at: string;
}

interface Stats {
  total_requests: number;
  by_status: Record<string, number>;
  approaching_deadline: number;
  overdue: number;
}

interface Props { token: string; }

const STATUS_COLORS: Record<string, string> = {
  received: "bg-gray-100 text-gray-700",
  searching: "bg-blue-100 text-blue-700",
  in_review: "bg-yellow-100 text-yellow-700",
  drafted: "bg-purple-100 text-purple-700",
  approved: "bg-green-100 text-green-700",
  sent: "bg-emerald-100 text-emerald-700",
};

export default function Requests({ token }: Props) {
  const [requests, setRequests] = useState<Request[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");
  const [loadingData, setLoadingData] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [desc, setDesc] = useState("");
  const [deadline, setDeadline] = useState("");

  const load = () => {
    setLoadingData(true);
    Promise.all([
      apiFetch<Request[]>("/requests/", { token }).then(setRequests).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e))),
      apiFetch<Stats>("/requests/stats", { token }).then(setStats).catch(() => {}),
    ]).finally(() => setLoadingData(false));
  };

  useEffect(load, [token]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const body: Record<string, unknown> = { requester_name: name, description: desc };
      if (email) body.requester_email = email;
      if (deadline) body.statutory_deadline = new Date(deadline).toISOString();
      await apiFetch("/requests/", { token, method: "POST", body: JSON.stringify(body) });
      setName(""); setEmail(""); setDesc(""); setDeadline(""); setShowForm(false); load();
    } catch (err: unknown) { setError(err instanceof Error ? err.message : String(err)); }
  };

  const isOverdue = (d: string | null) => d && new Date(d) < new Date();
  const isApproaching = (d: string | null) => {
    if (!d) return false;
    const dl = new Date(d);
    const now = new Date();
    const diff = (dl.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
    return diff > 0 && diff <= 3;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Records Requests</h2>
        <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">
          {showForm ? "Cancel" : "New Request"}
        </button>
      </div>

      {error && <p className="text-red-600 mb-4" role="alert">{error}</p>}

      {loadingData && (
        <div className="flex items-center gap-2 text-gray-500 mb-4" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <span>Loading requests...</span>
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Total</p>
            <p className="text-2xl font-semibold text-gray-900">{stats.total_requests}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">In Review</p>
            <p className="text-2xl font-semibold text-yellow-600">{stats.by_status.in_review || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Approaching Deadline</p>
            <p className="text-2xl font-semibold text-orange-600">{stats.approaching_deadline}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Overdue</p>
            <p className="text-2xl font-semibold text-red-600">{stats.overdue}</p>
          </div>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white p-4 rounded-lg border border-gray-200 mb-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-sm font-medium text-gray-700 mb-1">Requester Name</label><input value={name} onChange={(e) => setName(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" required /></div>
            <div><label className="block text-sm font-medium text-gray-700 mb-1">Email</label><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" /></div>
          </div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1">Description</label><textarea value={desc} onChange={(e) => setDesc(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" rows={3} required /></div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1">Statutory Deadline</label><input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" /></div>
          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">Create Request</button>
        </form>
      )}

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm" aria-label="Records requests">
          <thead><tr className="border-b border-gray-200 bg-gray-50">
            <th className="text-left px-4 py-3 font-medium text-gray-600">Requester</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Description</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Deadline</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Created</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
          </tr></thead>
          <tbody>{requests.map((r) => (
            <tr key={r.id} className="border-b border-gray-100">
              <td className="px-4 py-3 text-gray-900">{r.requester_name}</td>
              <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{r.description}</td>
              <td className="px-4 py-3"><span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[r.status] || "bg-gray-100 text-gray-700"}`}>{r.status.replace("_", " ")}</span></td>
              <td className="px-4 py-3">
                {r.statutory_deadline ? (
                  <span className={`text-xs ${isOverdue(r.statutory_deadline) ? "text-red-600 font-bold" : isApproaching(r.statutory_deadline) ? "text-orange-600 font-medium" : "text-gray-500"}`}>
                    {new Date(r.statutory_deadline).toLocaleDateString()}
                    {isOverdue(r.statutory_deadline) && " OVERDUE"}
                  </span>
                ) : <span className="text-xs text-gray-400">None</span>}
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">{new Date(r.created_at).toLocaleDateString()}</td>
              <td className="px-4 py-3"><Link to={`/requests/${r.id}`} className="text-blue-600 hover:text-blue-800 text-sm font-medium" aria-label={`View request from ${r.requester_name}`}>View</Link></td>
            </tr>
          ))}</tbody>
        </table>
        {!loadingData && requests.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="font-medium">No requests yet</p>
            <p className="text-sm mt-1">Use the "New Request" button above to create your first open records request.</p>
          </div>
        )}
      </div>
    </div>
  );
}
