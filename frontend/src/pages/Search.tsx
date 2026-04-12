import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface SearchResult {
  chunk_id: string;
  document_id: string;
  filename: string;
  file_type: string;
  source_path: string;
  page_number: number | null;
  content_text: string;
  similarity_score: number;
  rank: number;
}

interface SearchResponse {
  query_id: string;
  session_id: string;
  query_text: string;
  results: SearchResult[];
  results_count: number;
  synthesized_answer: string | null;
  ai_generated: boolean;
}

interface FilterOptions {
  file_types: string[];
  source_names: string[];
  date_range: { min: string; max: string } | null;
}

interface Props {
  token: string;
}

export default function Search({ token }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [filters, setFilters] = useState<FilterOptions | null>(null);
  const [selectedFileType, setSelectedFileType] = useState<string>("");
  const [synthesize, setSynthesize] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [queryHistory, setQueryHistory] = useState<string[]>([]);

  useEffect(() => {
    apiFetch<FilterOptions>("/search/filters", { token })
      .then(setFilters)
      .catch(() => {});
  }, [token]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    try {
      const body: Record<string, unknown> = {
        query: query.trim(),
        synthesize,
        limit: 10,
      };
      if (sessionId) body.session_id = sessionId;
      if (selectedFileType) body.filters = { file_type: selectedFileType };

      const resp = await apiFetch<SearchResponse>("/search/query", {
        token,
        method: "POST",
        body: JSON.stringify(body),
      });
      setResults(resp);
      setSessionId(resp.session_id);
      setQueryHistory((prev) => [...prev, query.trim()]);
      setQuery("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const highlightMatch = (text: string, q: string) => {
    if (!q) return text;
    const words = q.split(/\s+/).filter((w) => w.length > 2);
    if (!words.length) return text;
    const regex = new RegExp(`(${words.join("|")})`, "gi");
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="bg-yellow-200 px-0.5 rounded">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  const lastQuery = queryHistory[queryHistory.length - 1] || "";

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Search Records</h2>

      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documents... e.g. 'water quality reports 2025'"
            aria-label="Search query"
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            aria-label="Submit search"
            className="bg-blue-600 text-white px-6 py-3 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 sm:w-auto w-full"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-4 mt-3">
          {filters && filters.file_types.length > 0 && (
            <select
              value={selectedFileType}
              onChange={(e) => setSelectedFileType(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded-md text-sm"
            >
              <option value="">All file types</option>
              {filters.file_types.map((ft) => (
                <option key={ft} value={ft}>{ft.toUpperCase()}</option>
              ))}
            </select>
          )}
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={synthesize}
              onChange={(e) => setSynthesize(e.target.checked)}
              className="rounded"
            />
            Generate AI summary
          </label>
          {sessionId && (
            <button
              type="button"
              onClick={() => { setSessionId(null); setQueryHistory([]); setResults(null); }}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              New session
            </button>
          )}
        </div>
      </form>

      {error && <p className="text-red-600 mb-4" role="alert">{error}</p>}

      {loading && (
        <div className="flex items-center gap-2 text-gray-500 mb-4" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <span>Searching records...</span>
        </div>
      )}

      {queryHistory.length > 1 && (
        <div className="mb-4 flex gap-2 flex-wrap">
          <span className="text-xs text-gray-400">Session:</span>
          {queryHistory.map((q, i) => (
            <span key={i} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{q}</span>
          ))}
        </div>
      )}

      {results && results.synthesized_answer && (
        <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-medium bg-blue-100 text-blue-700 px-2 py-0.5 rounded">AI-Generated Draft</span>
            <span className="text-xs text-gray-400">Requires human review</span>
          </div>
          <p className="text-sm text-gray-800 whitespace-pre-wrap">{results.synthesized_answer}</p>
        </div>
      )}

      {results && (
        <div aria-label="Search results">
          <p className="text-sm text-gray-500 mb-3">
            {results.results_count} result{results.results_count !== 1 ? "s" : ""} for "{results.query_text}"
          </p>
          <div className="space-y-3">
            {results.results.map((r) => (
              <div key={r.chunk_id} className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <div className="flex flex-wrap items-center gap-2 min-w-0">
                    <span className="text-sm font-medium text-gray-900 truncate max-w-xs">{r.filename}</span>
                    <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{r.file_type}</span>
                    {r.page_number && (
                      <span className="text-xs text-gray-400">Page {r.page_number}</span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 shrink-0">
                    Score: {(r.similarity_score * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-sm text-gray-700 leading-relaxed">
                  {highlightMatch(
                    r.content_text.length > 500 ? r.content_text.slice(0, 500) + "..." : r.content_text,
                    lastQuery
                  )}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {results && results.results_count === 0 && (
        <div className="text-center py-12 text-gray-400">
          <p>No documents match your query.</p>
          <p className="text-sm mt-1">Try different search terms or broaden your filters.</p>
        </div>
      )}
    </div>
  );
}
