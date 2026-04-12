import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { apiFetch } from "@/lib/api";

interface RequestData {
  id: string;
  requester_name: string;
  requester_email: string | null;
  description: string;
  status: string;
  statutory_deadline: string | null;
  created_at: string;
  response_draft: string | null;
  review_notes: string | null;
}

interface AttachedDoc {
  id: string;
  document_id: string;
  relevance_note: string | null;
  inclusion_status: string;
  attached_at: string;
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

export default function RequestDetail({ token }: Props) {
  const { id } = useParams<{ id: string }>();
  const [req, setReq] = useState<RequestData | null>(null);
  const [docs, setDocs] = useState<AttachedDoc[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(true);

  const load = () => {
    if (!id) return;
    setLoadingDetail(true);
    Promise.all([
      apiFetch<RequestData>(`/requests/${id}`, { token }).then(setReq).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e))),
      apiFetch<AttachedDoc[]>(`/requests/${id}/documents`, { token }).then(setDocs).catch(() => {}),
    ]).finally(() => setLoadingDetail(false));
  };

  useEffect(load, [id, token]);

  const handleAction = async (action: string) => {
    setLoading(true);
    try {
      await apiFetch(`/requests/${id}/${action}`, { token, method: "POST" });
      load();
    } catch (err: unknown) { setError(err instanceof Error ? err.message : String(err)); }
    setLoading(false);
  };

  const handleStatusUpdate = async (status: string) => {
    setLoading(true);
    try {
      await apiFetch(`/requests/${id}`, { token, method: "PATCH", body: JSON.stringify({ status }) });
      load();
    } catch (err: unknown) { setError(err instanceof Error ? err.message : String(err)); }
    setLoading(false);
  };

  if (loadingDetail) return (
    <div className="flex items-center gap-2 text-gray-500 py-8" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>Loading request...</span>
    </div>
  );

  if (!req) return <p className="text-gray-500">Request not found.</p>;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Link to="/requests" className="text-sm text-gray-500 hover:text-gray-700" aria-label="Back to requests list">&larr; Back</Link>
        <h2 className="text-lg font-semibold text-gray-900">Request from {req.requester_name}</h2>
        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[req.status] || ""}`}>{req.status.replace("_", " ")}</span>
      </div>

      {error && <p className="text-red-600 mb-4" role="alert">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <div className="md:col-span-2 bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-600 mb-2">Request Details</h3>
          <div className="space-y-2 text-sm">
            <p><span className="text-gray-500">Requester:</span> {req.requester_name} {req.requester_email && `(${req.requester_email})`}</p>
            <p><span className="text-gray-500">Received:</span> {new Date(req.created_at).toLocaleDateString()}</p>
            {req.statutory_deadline && <p><span className="text-gray-500">Deadline:</span> <span className={new Date(req.statutory_deadline) < new Date() ? "text-red-600 font-bold" : ""}>{new Date(req.statutory_deadline).toLocaleDateString()}</span></p>}
            <p className="mt-3 text-gray-800">{req.description}</p>
          </div>
          {req.review_notes && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
              <p className="text-xs font-medium text-yellow-700 mb-1">Review Notes</p>
              <p className="text-sm text-yellow-800">{req.review_notes}</p>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-600 mb-3">Workflow</h3>
          <div className="space-y-2">
            {req.status === "received" && (
              <button onClick={() => handleStatusUpdate("searching")} disabled={loading} className="w-full bg-blue-600 text-white py-2 px-3 rounded-md text-sm hover:bg-blue-700 disabled:opacity-50">Start Searching</button>
            )}
            {(req.status === "searching" || req.status === "drafted") && (
              <button onClick={() => handleAction("submit-review")} disabled={loading} className="w-full bg-yellow-600 text-white py-2 px-3 rounded-md text-sm hover:bg-yellow-700 disabled:opacity-50">Submit for Review</button>
            )}
            {req.status === "in_review" && (
              <>
                <button onClick={() => handleStatusUpdate("drafted")} disabled={loading} className="w-full bg-purple-600 text-white py-2 px-3 rounded-md text-sm hover:bg-purple-700 disabled:opacity-50">Move to Drafted</button>
              </>
            )}
            {req.status === "drafted" && (
              <button onClick={() => handleAction("approve")} disabled={loading} className="w-full bg-green-600 text-white py-2 px-3 rounded-md text-sm hover:bg-green-700 disabled:opacity-50">Approve Response</button>
            )}
            {req.status === "approved" && (
              <button onClick={() => handleStatusUpdate("sent")} disabled={loading} className="w-full bg-emerald-600 text-white py-2 px-3 rounded-md text-sm hover:bg-emerald-700 disabled:opacity-50">Mark as Sent</button>
            )}
            {req.status === "in_review" && (
              <button onClick={() => handleAction("reject")} disabled={loading} className="w-full border border-red-300 text-red-600 py-2 px-3 rounded-md text-sm hover:bg-red-50 disabled:opacity-50">Reject (Return to Draft)</button>
            )}
          </div>
          <div className="mt-4">
            <Link to="/search" className="block text-center text-blue-600 hover:text-blue-800 text-sm font-medium py-2 border border-blue-200 rounded-md hover:bg-blue-50" aria-label="Go to search to find and attach documents">Search &amp; Attach Documents</Link>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-medium text-gray-600 mb-3">Attached Documents ({docs.length})</h3>
        {docs.length > 0 ? (
          <table className="w-full text-sm" aria-label="Attached documents">
            <thead><tr className="border-b border-gray-200">
              <th className="text-left px-3 py-2 font-medium text-gray-600">Document ID</th>
              <th className="text-left px-3 py-2 font-medium text-gray-600">Note</th>
              <th className="text-left px-3 py-2 font-medium text-gray-600">Status</th>
              <th className="text-left px-3 py-2 font-medium text-gray-600">Attached</th>
            </tr></thead>
            <tbody>{docs.map((d) => (
              <tr key={d.id} className="border-b border-gray-100">
                <td className="px-3 py-2 text-gray-600 font-mono text-xs">{d.document_id.slice(0, 8)}...</td>
                <td className="px-3 py-2 text-gray-600">{d.relevance_note || "—"}</td>
                <td className="px-3 py-2"><span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{d.inclusion_status}</span></td>
                <td className="px-3 py-2 text-gray-500 text-xs">{new Date(d.attached_at).toLocaleDateString()}</td>
              </tr>
            ))}</tbody>
          </table>
        ) : <p className="text-gray-400 text-sm">No documents attached yet. Use Search to find and attach documents.</p>}
      </div>
    </div>
  );
}
