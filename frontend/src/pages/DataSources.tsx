import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import FileUpload from "@/components/FileUpload";
import {
  Plus,
  FolderOpen,
  Upload,
  Mail,
  Database,
  Globe,
  RefreshCw,
  CheckCircle,
  Clock,
} from "lucide-react";

interface DataSource {
  id: string;
  name: string;
  source_type: string;
  connection_config: Record<string, string>;
  is_active: boolean;
  created_at: string;
  last_ingestion_at: string | null;
}

function SourceCard({ source, onIngest, ingesting }: { source: DataSource; onIngest: () => void; ingesting: boolean }) {
  return (
    <Card className="shadow-none">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            {source.source_type === "upload" ? (
              <Upload className="h-5 w-5 text-primary" />
            ) : (
              <FolderOpen className="h-5 w-5 text-primary" />
            )}
            <div>
              <p className="font-medium text-foreground">{source.name}</p>
              <p className="text-xs text-muted-foreground">{source.source_type}</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {source.is_active ? (
              <CheckCircle className="h-4 w-4 text-success" />
            ) : (
              <Clock className="h-4 w-4 text-muted-foreground" />
            )}
            <span className="text-xs text-muted-foreground">
              {source.is_active ? "Active" : "Inactive"}
            </span>
          </div>
        </div>
        <Separator className="my-3" />
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Last ingestion: {source.last_ingestion_at ? new Date(source.last_ingestion_at).toLocaleDateString() : "Never"}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={ingesting}
            onClick={onIngest}
          >
            <RefreshCw className={`h-3 w-3 mr-1 ${ingesting ? "animate-spin" : ""}`} />
            {ingesting ? "Ingesting..." : "Ingest Now"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ComingSoonCard({ icon: Icon, title, phase }: { icon: React.ElementType; title: string; phase: string }) {
  return (
    <Card className="shadow-none opacity-60">
      <CardContent className="p-5 text-center">
        <Icon className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
        <p className="font-medium text-muted-foreground">{title}</p>
        <p className="text-xs text-muted-foreground mt-1">Coming in {phase}</p>
      </CardContent>
    </Card>
  );
}

export default function DataSources({ token }: { token: string }) {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ name: "", path: "" });
  const [submitting, setSubmitting] = useState(false);
  const [ingesting, setIngesting] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const data = await apiFetch<DataSource[]>("/datasources/", { token });
      setSources(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiFetch("/datasources/", {
        token,
        method: "POST",
        body: JSON.stringify({
          name: formData.name,
          source_type: "directory",
          connection_config: { path: formData.path },
        }),
      });
      setShowForm(false);
      setFormData({ name: "", path: "" });
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setSubmitting(false);
    }
  };

  const handleIngest = async (id: string) => {
    setIngesting(id);
    try {
      await apiFetch(`/datasources/${id}/ingest`, { token, method: "POST" });
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingestion failed");
    } finally {
      setIngesting(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Data Sources"
        actions={
          <Dialog open={showForm} onOpenChange={setShowForm}>
            <DialogTrigger render={<Button><Plus className="h-4 w-4 mr-2" />Add Source</Button>} />
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Data Source</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Source Name</label>
                  <Input value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="e.g. Public Records Drive" required />
                </div>
                <div>
                  <label className="text-sm font-medium">Directory Path</label>
                  <Input value={formData.path} onChange={(e) => setFormData({ ...formData, path: e.target.value })} placeholder="e.g. C:\Records\Public or /mnt/records" required />
                  <p className="text-xs text-muted-foreground mt-1">The folder on the server where documents are stored.</p>
                </div>
                <div className="flex justify-end gap-3">
                  <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
                  <Button type="submit" disabled={submitting}>{submitting ? "Adding..." : "Add Source"}</Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {error && (
        <Card className="border-destructive">
          <CardContent className="p-4"><p className="text-destructive text-sm">{error}</p></CardContent>
        </Card>
      )}

      {/* Upload section */}
      <Card className="shadow-none">
        <CardHeader>
          <CardTitle className="text-lg">Upload Documents</CardTitle>
        </CardHeader>
        <CardContent>
          <FileUpload token={token} onUploadComplete={loadData} />
        </CardContent>
      </Card>

      {/* Connected sources */}
      <div>
        <h3 className="text-label uppercase text-muted-foreground mb-3">Connected Sources</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {sources.map((s) => (
            <SourceCard
              key={s.id}
              source={s}
              onIngest={() => handleIngest(s.id)}
              ingesting={ingesting === s.id}
            />
          ))}
          {sources.length === 0 && (
            <Card className="shadow-none md:col-span-3">
              <CardContent className="p-8 text-center">
                <p className="text-muted-foreground">No sources configured yet. Upload documents above or add a directory source.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Integration roadmap */}
      <div>
        <h3 className="text-label uppercase text-muted-foreground mb-3">Integrations</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="shadow-none">
            <CardContent className="p-5 text-center">
              <Mail className="h-6 w-6 text-primary mx-auto mb-2" />
              <p className="font-medium text-foreground">Email Archive</p>
              <p className="text-xs text-muted-foreground mt-1">Microsoft 365 / Google Workspace</p>
              <Button variant="outline" size="sm" className="mt-3" disabled>Configure Email</Button>
            </CardContent>
          </Card>
          <ComingSoonCard icon={Database} title="Database (ODBC)" phase="Phase 3" />
          <ComingSoonCard icon={Globe} title="API Endpoint" phase="Phase 3" />
        </div>
      </div>
    </div>
  );
}
