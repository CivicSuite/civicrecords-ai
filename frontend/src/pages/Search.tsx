import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { LoadingRegion } from "@/components/loading-region";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Download, Search as SearchIcon, FileText, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

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
  departments: { id: string; name: string }[];
  date_range: { min: string; max: string } | null;
}

function normalizeScore(score: number): number {
  // RRF scores are typically 0.01-0.02 range; normalize to 0-100
  return Math.min(100, Math.round(score * 5000));
}

function highlightMatch(text: string, query: string): string {
  if (!query) return text;
  const words = query.split(/\s+/).filter(w => w.length > 2);
  if (words.length === 0) return text;
  const pattern = new RegExp(`(${words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
  return text.replace(pattern, '**$1**');
}

export default function Search({ token }: { token: string }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [filters, setFilters] = useState<FilterOptions | null>(null);
  const [selectedFileType, setSelectedFileType] = useState("all");
  const [selectedDepartment, setSelectedDepartment] = useState("all");
  const [synthesize, setSynthesize] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

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
    setHasSearched(true);
    try {
      const body: Record<string, unknown> = {
        query: query.trim(),
        synthesize,
        limit: 20,
      };
      if (sessionId) body.session_id = sessionId;
      const searchFilters: Record<string, string> = {};
      if (selectedFileType !== "all") searchFilters.file_type = selectedFileType;
      if (selectedDepartment !== "all") searchFilters.department_id = selectedDepartment;
      if (Object.keys(searchFilters).length > 0) body.filters = searchFilters;

      const res = await apiFetch<SearchResponse>("/search/query", {
        token,
        method: "POST",
        body: JSON.stringify(body),
      });
      setResults(res);
      if (res.session_id) setSessionId(res.session_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Search Records" />

      {/* Search form */}
      <form onSubmit={handleSearch} className="space-y-4">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search documents... e.g. 'water quality reports 2025'"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-10 h-11"
            />
          </div>
          <Button type="submit" disabled={loading || !query.trim()} className="h-11 px-6">
            {loading ? "Searching..." : "Search"}
          </Button>
        </div>

        <div className="flex items-center gap-4">
          <Select value={selectedFileType} onValueChange={(v) => setSelectedFileType(v ?? "all")}>
            <SelectTrigger className="w-[180px]" aria-label="File type filter">
              <SelectValue placeholder="All file types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All file types</SelectItem>
              {filters?.file_types.map((ft) => (
                <SelectItem key={ft} value={ft}>{ft.toUpperCase()}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={selectedDepartment} onValueChange={(v) => setSelectedDepartment(v ?? "all")}>
            <SelectTrigger className="w-[180px]" aria-label="Department filter">
              <SelectValue placeholder="All departments" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All departments</SelectItem>
              {filters?.departments.map((d) => (
                <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex items-center gap-2">
            <Checkbox
              id="synthesize"
              checked={synthesize}
              onCheckedChange={(checked) => setSynthesize(checked === true)}
            />
            <label htmlFor="synthesize" className="text-sm text-muted-foreground cursor-pointer">
              Generate AI summary
            </label>
          </div>
        </div>
      </form>

      {/* Error */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="p-4">
            <p className="text-destructive text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Empty state — before first search */}
      {!hasSearched && !loading && (
        <EmptyState
          icon={SearchIcon}
          title="Search across all ingested documents"
          description="Enter a query above to search. Try: 'water quality 2025' or 'police incident reports' or 'council budget'"
        />
      )}

      {/* Loading */}
      {loading && (
        <div className="space-y-4" role="status" aria-label="Searching, please wait">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      )}

      {/* Results */}
      {results && !loading && (
        <LoadingRegion loading={loading} label="Search results">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {results.results_count} result{results.results_count !== 1 ? "s" : ""} found
            </p>
            {results.results_count > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  try {
                    const params = new URLSearchParams({ query: results.query_text, format: "csv" });
                    if (selectedFileType !== "all") params.set("file_type", selectedFileType);
                    if (selectedDepartment !== "all") params.set("department_id", selectedDepartment);
                    const res = await fetch(`/api/search/export?${params}`, {
                      headers: { Authorization: `Bearer ${token}` },
                    });
                    if (!res.ok) throw new Error(`Export failed: ${res.status}`);
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement("a");
                    link.href = url;
                    link.download = "search-results.csv";
                    link.click();
                    URL.revokeObjectURL(url);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Export failed");
                  }
                }}
              >
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            )}
          </div>

          {/* AI Summary */}
          {results.synthesized_answer && (
            <Card className="border-primary/30 bg-primary/5">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <Badge variant="outline" className="text-xs border-primary/30 text-primary">
                    AI-generated draft — requires human review
                  </Badge>
                </div>
                <p className="text-sm text-foreground">
                  {results.synthesized_answer.split(/(\[Doc:\s*[^\]]+\])/).map((part, i) => {
                    const citationMatch = part.match(/^\[Doc:\s*(.+?)(?:,\s*Page:\s*(\d+))?\]$/);
                    if (citationMatch) {
                      return (
                        <span key={i} className="inline-flex items-center gap-0.5 mx-0.5 px-1.5 py-0.5 rounded bg-primary/10 text-primary text-xs font-medium">
                          <FileText className="h-3 w-3" />
                          {citationMatch[1]}{citationMatch[2] ? `, p.${citationMatch[2]}` : ""}
                        </span>
                      );
                    }
                    return part;
                  })}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Result cards */}
          {results.results.length === 0 && hasSearched && (
            <EmptyState
              icon={FileText}
              title="No results found"
              description="Try different keywords or broaden your search terms."
            />
          )}

          {results.results.map((r) => {
            const normalized = normalizeScore(r.similarity_score);
            const displayName = r.filename.replace(/^[a-f0-9]{32}_/, "");
            const highlighted = highlightMatch(
              r.content_text.substring(0, 500),
              query
            );

            return (
              <Card key={r.chunk_id} className="shadow-none hover:shadow-sm transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium text-foreground">{displayName}</span>
                      <Badge variant="outline" className="text-xs">{r.file_type}</Badge>
                      {r.page_number && (
                        <span className="text-xs text-muted-foreground">Page {r.page_number}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full",
                            normalized >= 70 ? "bg-success" : normalized >= 40 ? "bg-warning" : "bg-muted-foreground"
                          )}
                          style={{ width: `${normalized}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground w-8 text-right">{normalized}%</span>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {highlighted.split('**').map((part, i) =>
                      i % 2 === 1 ? <mark key={i} className="bg-warning-light px-0.5 rounded">{part}</mark> : part
                    )}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
        </LoadingRegion>
      )}
    </div>
  );
}
