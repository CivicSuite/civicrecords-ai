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
  const [wizardStep, setWizardStep] = useState(1);
  const [formData, setFormData] = useState({
    name: "", sourceType: "manual_drop", host: "", port: "", path: "", username: "", password: "",
  });
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);
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

  const resetWizard = () => {
    setWizardStep(1);
    setFormData({ name: "", sourceType: "manual_drop", host: "", port: "", path: "", username: "", password: "" });
    setTestResult(null);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await apiFetch<{ success: boolean; message: string }>("/datasources/test-connection", {
        token,
        method: "POST",
        body: JSON.stringify({
          source_type: formData.sourceType,
          host: formData.host || undefined,
          port: formData.port ? parseInt(formData.port) : undefined,
          path: formData.path || undefined,
          username: formData.username || undefined,
          password: formData.password || undefined,
        }),
      });
      setTestResult(result);
    } catch (e) {
      setTestResult({ success: false, message: e instanceof Error ? e.message : "Test failed" });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const config: Record<string, string> = {};
      if (formData.path) config.path = formData.path;
      if (formData.host) config.host = formData.host;
      if (formData.port) config.port = formData.port;
      if (formData.username) config.username = formData.username;
      // Never persist password in connection_config — handle via secure vault in production
      await apiFetch("/datasources/", {
        token,
        method: "POST",
        body: JSON.stringify({
          name: formData.name,
          source_type: formData.sourceType,
          connection_config: config,
        }),
      });
      setShowForm(false);
      resetWizard();
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
          <Dialog open={showForm} onOpenChange={(open) => { setShowForm(open); if (!open) resetWizard(); }}>
            <DialogTrigger render={<Button><Plus className="h-4 w-4 mr-2" />Add Source</Button>} />
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Data Source — Step {wizardStep} of 3</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                {/* Step indicators */}
                <div className="flex gap-2">
                  {[1, 2, 3].map((s) => (
                    <div key={s} className={`h-1.5 flex-1 rounded-full ${s <= wizardStep ? "bg-primary" : "bg-muted"}`} />
                  ))}
                </div>

                {/* Step 1: Source type + name */}
                {wizardStep === 1 && (
                  <>
                    <div>
                      <label className="text-sm font-medium">Source Name</label>
                      <Input value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="e.g. City Clerk Email Archive" />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Source Type</label>
                      <div className="grid grid-cols-3 gap-2 mt-2">
                        {[
                          { type: "imap", icon: Mail, label: "IMAP Email" },
                          { type: "file_share", icon: FolderOpen, label: "File Share" },
                          { type: "manual_drop", icon: Upload, label: "Manual Drop" },
                        ].map(({ type, icon: Icon, label }) => (
                          <button
                            key={type}
                            type="button"
                            onClick={() => setFormData({ ...formData, sourceType: type })}
                            className={`p-3 rounded-lg border text-center transition-colors ${formData.sourceType === type ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"}`}
                          >
                            <Icon className="h-5 w-5 mx-auto mb-1" />
                            <span className="text-xs font-medium">{label}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="flex justify-end gap-3">
                      <Button type="button" variant="outline" onClick={() => { setShowForm(false); resetWizard(); }}>Cancel</Button>
                      <Button type="button" disabled={!formData.name.trim()} onClick={() => setWizardStep(2)}>Next</Button>
                    </div>
                  </>
                )}

                {/* Step 2: Connection config */}
                {wizardStep === 2 && (
                  <>
                    {formData.sourceType === "imap" && (
                      <>
                        <div>
                          <label className="text-sm font-medium">IMAP Server</label>
                          <Input value={formData.host} onChange={(e) => setFormData({ ...formData, host: e.target.value })} placeholder="imap.gmail.com" />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Port</label>
                          <Input value={formData.port} onChange={(e) => setFormData({ ...formData, port: e.target.value })} placeholder="993" />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Username</label>
                          <Input value={formData.username} onChange={(e) => setFormData({ ...formData, username: e.target.value })} placeholder="records@city.gov" />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Password</label>
                          <Input type="password" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} />
                        </div>
                      </>
                    )}
                    {(formData.sourceType === "file_share" || formData.sourceType === "manual_drop") && (
                      <div>
                        <label className="text-sm font-medium">Directory Path</label>
                        <Input value={formData.path} onChange={(e) => setFormData({ ...formData, path: e.target.value })} placeholder="/mnt/records or C:\Records\Public" />
                        <p className="text-xs text-muted-foreground mt-1">The folder on the server where documents are stored.</p>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <Button type="button" variant="outline" onClick={() => setWizardStep(1)}>Back</Button>
                      <Button type="button" onClick={() => setWizardStep(3)}>Next</Button>
                    </div>
                  </>
                )}

                {/* Step 3: Review + test connection */}
                {wizardStep === 3 && (
                  <>
                    <Card className="shadow-none">
                      <CardContent className="p-4 space-y-2 text-sm">
                        <p><span className="font-medium">Name:</span> {formData.name}</p>
                        <p><span className="font-medium">Type:</span> {formData.sourceType}</p>
                        {formData.host && <p><span className="font-medium">Server:</span> {formData.host}:{formData.port || "993"}</p>}
                        {formData.path && <p><span className="font-medium">Path:</span> {formData.path}</p>}
                        {formData.username && <p><span className="font-medium">Username:</span> {formData.username}</p>}
                      </CardContent>
                    </Card>

                    <Button type="button" variant="outline" className="w-full" onClick={handleTestConnection} disabled={testing}>
                      {testing ? "Testing..." : "Test Connection"}
                    </Button>

                    {testResult && (
                      <Card className={`shadow-none ${testResult.success ? "border-success" : "border-destructive"}`}>
                        <CardContent className="p-3">
                          <p className={`text-sm ${testResult.success ? "text-success" : "text-destructive"}`}>
                            {testResult.success ? "✓" : "✗"} {testResult.message}
                          </p>
                        </CardContent>
                      </Card>
                    )}

                    <div className="flex justify-between">
                      <Button type="button" variant="outline" onClick={() => setWizardStep(2)}>Back</Button>
                      <Button type="button" onClick={handleSubmit} disabled={submitting}>
                        {submitting ? "Creating..." : "Create Source"}
                      </Button>
                    </div>
                  </>
                )}
              </div>
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
