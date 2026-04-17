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
import FileUpload from "@/components/FileUpload";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Plus,
  FolderOpen,
  Upload,
  Mail,
  Database,
  Globe,
} from "lucide-react";
import { SourceCard, type DataSource } from "@/components/SourceCard";
import { Checkbox } from "@/components/ui/checkbox";
import { parseExpression } from "cron-parser";

export function formatNextRun(cron: string): string {
  try {
    const interval = parseExpression(cron, { utc: true });
    const next = interval.next().toDate();
    const utcPart = next.toLocaleString("en-US", {
      timeZone: "UTC",
      month: "short", day: "numeric",
      hour: "numeric", minute: "2-digit",
      hour12: true,
    });
    const localPart = next.toLocaleString("en-US", {
      hour: "numeric", minute: "2-digit",
      hour12: true, timeZoneName: "short",
    });
    return `Next: ${utcPart} UTC (${localPart})`;
  } catch {
    return "";
  }
}

const SCHEDULE_PRESETS: { label: string; cron: string | null }[] = [
  { label: "Every 15 minutes", cron: "*/15 * * * *" },
  { label: "Every 30 minutes", cron: "*/30 * * * *" },
  { label: "Every hour",       cron: "0 * * * *" },
  { label: "Every 6 hours",    cron: "0 */6 * * *" },
  { label: "Every 12 hours",   cron: "0 */12 * * *" },
  { label: "Nightly at 2am UTC", cron: "0 2 * * *" },
  { label: "Weekly (Mon 2am UTC)", cron: "0 2 * * 1" },
  { label: "Custom…", cron: null },
];


export default function DataSources({ token }: { token: string }) {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [formData, setFormData] = useState({
    // common
    name: "", sourceType: "manual_drop",
    // imap / file_share
    host: "", port: "", path: "", username: "", password: "",
    // rest_api
    base_url: "", endpoint_path: "/", auth_method: "none",
    api_key: "", key_location: "header", key_header: "X-API-Key",
    token: "", client_id: "", client_secret: "", token_url: "",
    rest_username: "", rest_password: "",
    pagination_style: "none", max_records: "1000",
    // odbc
    connection_string: "", table_name: "", pk_column: "", modified_column: "", batch_size: "500",
    // schedule
    schedule_enabled: true, sync_schedule: "0 2 * * *", schedule_preset: "Nightly at 2am UTC",
  });
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [submitting, setSubmitting] = useState(false);

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
    setFormData({
      name: "", sourceType: "manual_drop",
      host: "", port: "", path: "", username: "", password: "",
      base_url: "", endpoint_path: "/", auth_method: "none",
      api_key: "", key_location: "header", key_header: "X-API-Key",
      token: "", client_id: "", client_secret: "", token_url: "",
      rest_username: "", rest_password: "",
      pagination_style: "none", max_records: "1000",
      connection_string: "", table_name: "", pk_column: "", modified_column: "", batch_size: "500",
      schedule_enabled: true, sync_schedule: "0 2 * * *", schedule_preset: "Nightly at 2am UTC",
    });
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
          sync_schedule: formData.schedule_enabled ? formData.sync_schedule : null,
          schedule_enabled: formData.schedule_enabled,
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


  if (loading) {
    return (
      <div className="space-y-6" role="status" aria-label="Loading data sources">
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
                          { type: "rest_api", icon: Globe, label: "REST API" },
                          { type: "odbc", icon: Database, label: "ODBC / Database" },
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

                    {/* REST API config */}
                    {formData.sourceType === "rest_api" && (
                      <div className="space-y-3">
                        <div>
                          <label className="text-sm font-medium">Base URL <span className="text-destructive">*</span></label>
                          <Input value={formData.base_url} onChange={(e) => setFormData({ ...formData, base_url: e.target.value })} placeholder="https://api.example.gov" />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Endpoint Path</label>
                          <Input value={formData.endpoint_path} onChange={(e) => setFormData({ ...formData, endpoint_path: e.target.value })} placeholder="/records" />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Authentication</label>
                          <Select value={formData.auth_method} onValueChange={(v) => setFormData({ ...formData, auth_method: v ?? "" })}>
                            <SelectTrigger className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">None</SelectItem>
                              <SelectItem value="api_key">API Key</SelectItem>
                              <SelectItem value="bearer">Bearer Token</SelectItem>
                              <SelectItem value="oauth2">OAuth 2.0 Client Credentials</SelectItem>
                              <SelectItem value="basic">Basic Auth</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Conditional auth fields */}
                        {formData.auth_method === "api_key" && (
                          <div className="space-y-2 pl-3 border-l-2 border-muted">
                            <div>
                              <label className="text-sm font-medium">API Key <span className="text-destructive">*</span></label>
                              <Input type="password" value={formData.api_key} onChange={(e) => setFormData({ ...formData, api_key: e.target.value })} placeholder="Enter API key" />
                            </div>
                            <div>
                              <label className="text-sm font-medium">Key Location</label>
                              <Select value={formData.key_location} onValueChange={(v) => setFormData({ ...formData, key_location: v ?? "" })}>
                                <SelectTrigger className="mt-1">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="header">Header</SelectItem>
                                  <SelectItem value="query">Query Parameter</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <label className="text-sm font-medium">Header / Parameter Name</label>
                              <Input value={formData.key_header} onChange={(e) => setFormData({ ...formData, key_header: e.target.value })} placeholder="X-API-Key" />
                            </div>
                          </div>
                        )}

                        {formData.auth_method === "bearer" && (
                          <div className="pl-3 border-l-2 border-muted">
                            <label className="text-sm font-medium">Bearer Token <span className="text-destructive">*</span></label>
                            <Input type="password" value={formData.token} onChange={(e) => setFormData({ ...formData, token: e.target.value })} placeholder="Enter bearer token" />
                          </div>
                        )}

                        {formData.auth_method === "oauth2" && (
                          <div className="space-y-2 pl-3 border-l-2 border-muted">
                            <div>
                              <label className="text-sm font-medium">Client ID <span className="text-destructive">*</span></label>
                              <Input value={formData.client_id} onChange={(e) => setFormData({ ...formData, client_id: e.target.value })} placeholder="OAuth client ID" />
                            </div>
                            <div>
                              <label className="text-sm font-medium">Client Secret <span className="text-destructive">*</span></label>
                              <Input type="password" value={formData.client_secret} onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })} placeholder="OAuth client secret" />
                            </div>
                            <div>
                              <label className="text-sm font-medium">Token URL <span className="text-destructive">*</span></label>
                              <Input value={formData.token_url} onChange={(e) => setFormData({ ...formData, token_url: e.target.value })} placeholder="https://auth.example.gov/oauth/token" />
                            </div>
                          </div>
                        )}

                        {formData.auth_method === "basic" && (
                          <div className="space-y-2 pl-3 border-l-2 border-muted">
                            <div>
                              <label className="text-sm font-medium">Username <span className="text-destructive">*</span></label>
                              <Input value={formData.rest_username} onChange={(e) => setFormData({ ...formData, rest_username: e.target.value })} placeholder="Username" />
                            </div>
                            <div>
                              <label className="text-sm font-medium">Password <span className="text-destructive">*</span></label>
                              <Input type="password" value={formData.rest_password} onChange={(e) => setFormData({ ...formData, rest_password: e.target.value })} placeholder="Password" />
                            </div>
                          </div>
                        )}

                        <div>
                          <label className="text-sm font-medium">Pagination Style</label>
                          <Select value={formData.pagination_style} onValueChange={(v) => setFormData({ ...formData, pagination_style: v ?? "" })}>
                            <SelectTrigger className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">None (single response)</SelectItem>
                              <SelectItem value="page">Page-based (?page=N)</SelectItem>
                              <SelectItem value="offset">Offset-based (?offset=N)</SelectItem>
                              <SelectItem value="cursor">Cursor-based</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <label className="text-sm font-medium">Max Records</label>
                          <Input type="number" value={formData.max_records} onChange={(e) => setFormData({ ...formData, max_records: e.target.value })} placeholder="1000" />
                        </div>
                      </div>
                    )}

                    {/* ODBC config */}
                    {formData.sourceType === "odbc" && (
                      <div className="space-y-3">
                        <div>
                          <label className="text-sm font-medium">Connection String <span className="text-destructive">*</span></label>
                          <Input type="password" value={formData.connection_string} onChange={(e) => setFormData({ ...formData, connection_string: e.target.value })} placeholder="DSN=MyDSN;UID=user;PWD=..." />
                          <p className="text-xs text-muted-foreground mt-1">Stored securely. Contains credentials — never logged or echoed.</p>
                        </div>
                        <div>
                          <label className="text-sm font-medium">Table Name <span className="text-destructive">*</span></label>
                          <Input value={formData.table_name} onChange={(e) => setFormData({ ...formData, table_name: e.target.value })} placeholder="public_records" />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Primary Key Column <span className="text-destructive">*</span></label>
                          <Input value={formData.pk_column} onChange={(e) => setFormData({ ...formData, pk_column: e.target.value })} placeholder="id" />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Modified Timestamp Column <span className="text-muted-foreground text-xs">(optional)</span></label>
                          <Input value={formData.modified_column} onChange={(e) => setFormData({ ...formData, modified_column: e.target.value })} placeholder="updated_at" />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Batch Size</label>
                          <Input type="number" value={formData.batch_size} onChange={(e) => setFormData({ ...formData, batch_size: e.target.value })} placeholder="500" />
                        </div>
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
                    <div className="space-y-2 border rounded-md p-3">
                      <label className="flex items-center gap-2 text-sm font-medium">
                        <Checkbox
                          checked={formData.schedule_enabled}
                          onCheckedChange={(checked) =>
                            setFormData({ ...formData, schedule_enabled: Boolean(checked) })
                          }
                        />
                        Enable automatic sync
                      </label>
                      {formData.schedule_enabled && (
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Sync schedule (UTC)</label>
                          <select
                            className="w-full border rounded-md px-2 py-1.5 text-sm bg-background"
                            value={formData.schedule_preset}
                            onChange={(e) => {
                              const preset = SCHEDULE_PRESETS.find((p) => p.label === e.target.value);
                              setFormData({
                                ...formData,
                                schedule_preset: e.target.value,
                                sync_schedule: preset?.cron ?? formData.sync_schedule,
                              });
                            }}
                          >
                            {SCHEDULE_PRESETS.map((p) => (
                              <option key={p.label} value={p.label}>{p.label}</option>
                            ))}
                          </select>
                          {formData.schedule_preset === "Custom…" && (
                            <Input
                              value={formData.sync_schedule}
                              onChange={(e) => setFormData({ ...formData, sync_schedule: e.target.value })}
                              placeholder="0 2 * * * (5-field cron, UTC)"
                            />
                          )}
                          <p className="text-xs text-muted-foreground font-mono">
                            {formData.sync_schedule}
                          </p>
                          {formData.sync_schedule && (
                            <p
                              data-testid="cron-preview"
                              className="text-xs text-muted-foreground"
                            >
                              {formatNextRun(formData.sync_schedule)}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                    <Card className="shadow-none">
                      <CardContent className="p-4 space-y-2 text-sm">
                        <p><span className="font-medium">Name:</span> {formData.name}</p>
                        <p><span className="font-medium">Type:</span> {formData.sourceType}</p>
                        {formData.host && <p><span className="font-medium">Server:</span> {formData.host}:{formData.port || "993"}</p>}
                        {formData.path && <p><span className="font-medium">Path:</span> {formData.path}</p>}
                        {formData.username && <p><span className="font-medium">Username:</span> {formData.username}</p>}
                        {formData.sourceType === "rest_api" && (
                          <>
                            {formData.base_url && <p><span className="font-medium">Base URL:</span> {formData.base_url}</p>}
                            <p><span className="font-medium">Endpoint:</span> {formData.endpoint_path}</p>
                            <p><span className="font-medium">Auth:</span> {formData.auth_method}</p>
                            <p><span className="font-medium">Pagination:</span> {formData.pagination_style}</p>
                            <p><span className="font-medium">Max Records:</span> {formData.max_records}</p>
                          </>
                        )}
                        {formData.sourceType === "odbc" && (
                          <>
                            <p><span className="font-medium">Connection String:</span> ••••••••</p>
                            {formData.table_name && <p><span className="font-medium">Table:</span> {formData.table_name}</p>}
                            {formData.pk_column && <p><span className="font-medium">PK Column:</span> {formData.pk_column}</p>}
                            {formData.modified_column && <p><span className="font-medium">Modified Column:</span> {formData.modified_column}</p>}
                            <p><span className="font-medium">Batch Size:</span> {formData.batch_size}</p>
                          </>
                        )}
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
        <Card role="alert" className="border-destructive">
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
              onRefresh={loadData}
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
          <Card className="shadow-none">
            <CardContent className="p-5 text-center">
              <Database className="h-6 w-6 text-primary mx-auto mb-2" />
              <p className="font-medium text-foreground">ODBC / Database</p>
              <p className="text-xs text-muted-foreground mt-1">Connect any ODBC-compatible database</p>
              <Button variant="outline" size="sm" className="mt-3" onClick={() => { setFormData((f) => ({ ...f, sourceType: "odbc" })); setShowForm(true); }}>Configure ODBC</Button>
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardContent className="p-5 text-center">
              <Globe className="h-6 w-6 text-primary mx-auto mb-2" />
              <p className="font-medium text-foreground">REST API</p>
              <p className="text-xs text-muted-foreground mt-1">Fetch records from any REST endpoint</p>
              <Button variant="outline" size="sm" className="mt-3" onClick={() => { setFormData((f) => ({ ...f, sourceType: "rest_api" })); setShowForm(true); }}>Configure API</Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
