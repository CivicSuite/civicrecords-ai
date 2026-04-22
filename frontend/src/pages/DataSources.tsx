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

// Field-level validation — keys match state keys in formData.
// Messages are actionable: they say what is wrong AND how to fix it.
type FormData = {
  name: string;
  sourceType: string;
  host: string; port: string; path: string; username: string; password: string;
  base_url: string; endpoint_path: string; auth_method: string;
  api_key: string; key_location: string; key_header: string;
  token: string; client_id: string; client_secret: string; token_url: string;
  rest_username: string; rest_password: string;
  pagination_style: string; max_records: string;
  connection_string: string; table_name: string; pk_column: string;
  modified_column: string; batch_size: string;
  schedule_enabled: boolean; sync_schedule: string; schedule_preset: string;
};

type FieldErrors = Partial<Record<keyof FormData, string>>;

function validateStep(step: number, data: FormData): FieldErrors {
  const errors: FieldErrors = {};
  if (step === 1) {
    if (!data.name.trim()) {
      errors.name = "Enter a name for this source — this is how you will identify it later.";
    }
  } else if (step === 2) {
    if (data.sourceType === "file_system" || data.sourceType === "manual_drop") {
      if (!data.path.trim()) {
        errors.path = "Enter the full directory path where documents live (for example, /mnt/records).";
      }
    } else if (data.sourceType === "rest_api") {
      if (!data.base_url.trim()) {
        errors.base_url = "Enter the API base URL (for example, https://api.example.gov).";
      } else if (!/^https?:\/\//i.test(data.base_url.trim())) {
        errors.base_url = "Base URL must start with http:// or https://.";
      }
      if (data.auth_method === "api_key" && !data.api_key.trim()) {
        errors.api_key = "API key is required for API Key authentication.";
      }
      if (data.auth_method === "bearer" && !data.token.trim()) {
        errors.token = "Bearer token is required for Bearer Token authentication.";
      }
      if (data.auth_method === "oauth2") {
        if (!data.client_id.trim()) errors.client_id = "Client ID is required for OAuth 2.0.";
        if (!data.client_secret.trim()) errors.client_secret = "Client secret is required for OAuth 2.0.";
        if (!data.token_url.trim()) {
          errors.token_url = "Token URL is required for OAuth 2.0.";
        } else if (!/^https?:\/\//i.test(data.token_url.trim())) {
          errors.token_url = "Token URL must start with http:// or https://.";
        }
      }
      if (data.auth_method === "basic") {
        if (!data.rest_username.trim()) errors.rest_username = "Username is required for Basic Auth.";
        if (!data.rest_password.trim()) errors.rest_password = "Password is required for Basic Auth.";
      }
    } else if (data.sourceType === "odbc") {
      if (!data.connection_string.trim()) {
        errors.connection_string = "Enter the ODBC connection string (for example, DSN=MyDSN;UID=user;PWD=...).";
      }
      if (!data.table_name.trim()) {
        errors.table_name = "Enter the name of the table to read records from.";
      }
      if (!data.pk_column.trim()) {
        errors.pk_column = "Enter the primary key column — needed to track which records have been ingested.";
      }
    }
  } else if (step === 3) {
    if (data.schedule_enabled && data.sync_schedule.trim()) {
      try {
        parseExpression(data.sync_schedule.trim(), { utc: true });
      } catch {
        errors.sync_schedule = "Sync schedule must be a valid 5-field cron expression (for example, 0 2 * * *).";
      }
    }
  }
  return errors;
}


export default function DataSources({ token }: { token: string }) {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [formData, setFormData] = useState<FormData>({
    // common
    name: "", sourceType: "file_system",
    // file_system / manual_drop
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
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState("");
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const updateField = <K extends keyof FormData>(key: K, value: FormData[K]) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    // Clear this field's error as soon as the user corrects it — don't make them
    // hit Next again just to see the red go away.
    if (fieldErrors[key]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

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
    setFieldErrors({});
    setSubmitError("");
    setFormData({
      name: "", sourceType: "file_system",
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

  const tryAdvance = (toStep: number) => {
    const errs = validateStep(wizardStep, formData);
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }
    setFieldErrors({});
    setSubmitError("");
    setWizardStep(toStep);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const body: Record<string, unknown> = { source_type: formData.sourceType };

      if (formData.sourceType === "rest_api") {
        const cfg: Record<string, unknown> = {
          base_url: formData.base_url,
          endpoint_path: formData.endpoint_path,
          auth_method: formData.auth_method,
          pagination_style: formData.pagination_style,
          max_records: parseInt(formData.max_records) || 1000,
        };
        if (formData.auth_method === "api_key") {
          cfg.api_key = formData.api_key;
          cfg.key_location = formData.key_location;
          cfg.key_header = formData.key_header;
        } else if (formData.auth_method === "bearer") {
          cfg.token = formData.token;
        } else if (formData.auth_method === "oauth2") {
          cfg.client_id = formData.client_id;
          cfg.client_secret = formData.client_secret;
          cfg.token_url = formData.token_url;
        } else if (formData.auth_method === "basic") {
          cfg.username = formData.rest_username;
          cfg.password = formData.rest_password;
        }
        body.rest_api_config = cfg;
      } else if (formData.sourceType === "odbc") {
        body.odbc_config = {
          connection_string: formData.connection_string,
          table_name: formData.table_name,
          pk_column: formData.pk_column,
          ...(formData.modified_column ? { modified_column: formData.modified_column } : {}),
          batch_size: parseInt(formData.batch_size) || 500,
        };
      } else {
        body.path = formData.path || undefined;
      }

      const result = await apiFetch<{ success: boolean; message: string }>("/datasources/test-connection", {
        token,
        method: "POST",
        body: JSON.stringify(body),
      });
      setTestResult(result);
    } catch (e) {
      setTestResult({ success: false, message: e instanceof Error ? e.message : "Test failed" });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async () => {
    // Revalidate step 3 (schedule) before sending — belt and suspenders.
    const errs = validateStep(3, formData);
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    try {
      let config: Record<string, unknown> = {};
      if (formData.sourceType === "file_system") {
        config = { path: formData.path };
      } else if (formData.sourceType === "manual_drop") {
        config = { drop_path: formData.path };
      } else if (formData.sourceType === "rest_api") {
        config = {
          base_url: formData.base_url,
          endpoint_path: formData.endpoint_path,
          auth_method: formData.auth_method,
          pagination_style: formData.pagination_style,
          max_records: parseInt(formData.max_records) || 1000,
        };
        if (formData.auth_method === "api_key") {
          config.api_key = formData.api_key;
          config.key_location = formData.key_location;
          config.key_header = formData.key_header;
        } else if (formData.auth_method === "bearer") {
          config.token = formData.token;
        } else if (formData.auth_method === "oauth2") {
          config.client_id = formData.client_id;
          config.client_secret = formData.client_secret;
          config.token_url = formData.token_url;
        } else if (formData.auth_method === "basic") {
          config.username = formData.rest_username;
          config.password = formData.rest_password;
        }
      } else if (formData.sourceType === "odbc") {
        config = {
          connection_string: formData.connection_string,
          table_name: formData.table_name,
          pk_column: formData.pk_column,
          batch_size: parseInt(formData.batch_size) || 500,
        };
        if (formData.modified_column) config.modified_column = formData.modified_column;
      }
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
      setSubmitError(e instanceof Error ? e.message : "Failed to create source. Check the fields above and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  // Reusable label + error pair.
  // Labels are associated via htmlFor → id. Errors get role="alert" so screen
  // readers announce them as soon as they appear. Inputs reference both the
  // hint (if any) and the error via aria-describedby, and get aria-invalid.
  const FieldLabel = ({ htmlFor, children, required }: { htmlFor: string; children: React.ReactNode; required?: boolean }) => (
    <label htmlFor={htmlFor} className="text-sm font-medium">
      {children}
      {required && <span className="text-destructive" aria-hidden="true"> *</span>}
      {required && <span className="sr-only"> (required)</span>}
    </label>
  );
  const FieldError = ({ id, message }: { id: string; message: string | undefined }) =>
    message ? (
      <p id={id} role="alert" className="text-xs text-destructive mt-1">
        {message}
      </p>
    ) : null;
  const describedBy = (hintId: string | null, errorShown: boolean, errorId: string): string | undefined => {
    const parts = [];
    if (hintId) parts.push(hintId);
    if (errorShown) parts.push(errorId);
    return parts.length ? parts.join(" ") : undefined;
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
                <div className="flex gap-2" aria-hidden="true">
                  {[1, 2, 3].map((s) => (
                    <div key={s} className={`h-1.5 flex-1 rounded-full ${s <= wizardStep ? "bg-primary" : "bg-muted"}`} />
                  ))}
                </div>

                {/* Step 1: Source type + name */}
                {wizardStep === 1 && (
                  <>
                    <div>
                      <FieldLabel htmlFor="ds-name" required>Source Name</FieldLabel>
                      <Input
                        id="ds-name"
                        value={formData.name}
                        onChange={(e) => updateField("name", e.target.value)}
                        placeholder="e.g. City Clerk Email Archive"
                        aria-required="true"
                        aria-invalid={fieldErrors.name ? "true" : undefined}
                        aria-describedby={describedBy(null, !!fieldErrors.name, "ds-name-error")}
                      />
                      <FieldError id="ds-name-error" message={fieldErrors.name} />
                    </div>
                    <div>
                      <span id="ds-type-label" className="text-sm font-medium">Source Type</span>
                      <div
                        role="radiogroup"
                        aria-labelledby="ds-type-label"
                        className="grid grid-cols-3 gap-2 mt-2"
                      >
                        {[
                          { type: "file_system", icon: FolderOpen, label: "File System" },
                          { type: "manual_drop", icon: Upload, label: "Manual Drop" },
                          { type: "rest_api", icon: Globe, label: "REST API" },
                          { type: "odbc", icon: Database, label: "ODBC / Database" },
                        ].map(({ type, icon: Icon, label }) => {
                          const selected = formData.sourceType === type;
                          return (
                            <button
                              key={type}
                              type="button"
                              role="radio"
                              aria-checked={selected}
                              tabIndex={selected ? 0 : -1}
                              onClick={() => setFormData({ ...formData, sourceType: type })}
                              className={`p-3 rounded-lg border text-center transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ${selected ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"}`}
                            >
                              <Icon className="h-5 w-5 mx-auto mb-1" />
                              <span className="text-xs font-medium">{label}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    <div className="flex justify-end gap-3">
                      <Button type="button" variant="outline" onClick={() => { setShowForm(false); resetWizard(); }}>Cancel</Button>
                      <Button type="button" onClick={() => tryAdvance(2)}>Next</Button>
                    </div>
                  </>
                )}

                {/* Step 2: Connection config */}
                {wizardStep === 2 && (
                  <>
                    {(formData.sourceType === "file_system" || formData.sourceType === "manual_drop") && (
                      <div>
                        <FieldLabel htmlFor="ds-path" required>Directory Path</FieldLabel>
                        <Input
                          id="ds-path"
                          value={formData.path}
                          onChange={(e) => updateField("path", e.target.value)}
                          placeholder="/mnt/records or C:\Records\Public"
                          aria-required="true"
                          aria-invalid={fieldErrors.path ? "true" : undefined}
                          aria-describedby={describedBy("ds-path-hint", !!fieldErrors.path, "ds-path-error")}
                        />
                        <p id="ds-path-hint" className="text-xs text-muted-foreground mt-1">The folder on the server where documents are stored.</p>
                        <FieldError id="ds-path-error" message={fieldErrors.path} />
                      </div>
                    )}

                    {/* REST API config */}
                    {formData.sourceType === "rest_api" && (
                      <div className="space-y-3">
                        <div>
                          <FieldLabel htmlFor="ds-base-url" required>Base URL</FieldLabel>
                          <Input
                            id="ds-base-url"
                            value={formData.base_url}
                            onChange={(e) => updateField("base_url", e.target.value)}
                            placeholder="https://api.example.gov"
                            aria-required="true"
                            aria-invalid={fieldErrors.base_url ? "true" : undefined}
                            aria-describedby={describedBy(null, !!fieldErrors.base_url, "ds-base-url-error")}
                          />
                          <FieldError id="ds-base-url-error" message={fieldErrors.base_url} />
                        </div>
                        <div>
                          <FieldLabel htmlFor="ds-endpoint-path">Endpoint Path</FieldLabel>
                          <Input
                            id="ds-endpoint-path"
                            value={formData.endpoint_path}
                            onChange={(e) => updateField("endpoint_path", e.target.value)}
                            placeholder="/records"
                          />
                        </div>
                        <div>
                          <FieldLabel htmlFor="ds-auth-method">Authentication</FieldLabel>
                          <Select value={formData.auth_method} onValueChange={(v) => updateField("auth_method", v ?? "")}>
                            <SelectTrigger id="ds-auth-method" className="mt-1">
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
                              <FieldLabel htmlFor="ds-api-key" required>API Key</FieldLabel>
                              <Input
                                id="ds-api-key"
                                type="password"
                                value={formData.api_key}
                                onChange={(e) => updateField("api_key", e.target.value)}
                                placeholder="Enter API key"
                                aria-required="true"
                                aria-invalid={fieldErrors.api_key ? "true" : undefined}
                                aria-describedby={describedBy(null, !!fieldErrors.api_key, "ds-api-key-error")}
                              />
                              <FieldError id="ds-api-key-error" message={fieldErrors.api_key} />
                            </div>
                            <div>
                              <FieldLabel htmlFor="ds-key-location">Key Location</FieldLabel>
                              <Select value={formData.key_location} onValueChange={(v) => updateField("key_location", v ?? "")}>
                                <SelectTrigger id="ds-key-location" className="mt-1">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="header">Header</SelectItem>
                                  <SelectItem value="query">Query Parameter</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <FieldLabel htmlFor="ds-key-header">Header / Parameter Name</FieldLabel>
                              <Input
                                id="ds-key-header"
                                value={formData.key_header}
                                onChange={(e) => updateField("key_header", e.target.value)}
                                placeholder="X-API-Key"
                              />
                            </div>
                          </div>
                        )}

                        {formData.auth_method === "bearer" && (
                          <div className="pl-3 border-l-2 border-muted">
                            <FieldLabel htmlFor="ds-bearer-token" required>Bearer Token</FieldLabel>
                            <Input
                              id="ds-bearer-token"
                              type="password"
                              value={formData.token}
                              onChange={(e) => updateField("token", e.target.value)}
                              placeholder="Enter bearer token"
                              aria-required="true"
                              aria-invalid={fieldErrors.token ? "true" : undefined}
                              aria-describedby={describedBy(null, !!fieldErrors.token, "ds-bearer-token-error")}
                            />
                            <FieldError id="ds-bearer-token-error" message={fieldErrors.token} />
                          </div>
                        )}

                        {formData.auth_method === "oauth2" && (
                          <div className="space-y-2 pl-3 border-l-2 border-muted">
                            <div>
                              <FieldLabel htmlFor="ds-client-id" required>Client ID</FieldLabel>
                              <Input
                                id="ds-client-id"
                                value={formData.client_id}
                                onChange={(e) => updateField("client_id", e.target.value)}
                                placeholder="OAuth client ID"
                                aria-required="true"
                                aria-invalid={fieldErrors.client_id ? "true" : undefined}
                                aria-describedby={describedBy(null, !!fieldErrors.client_id, "ds-client-id-error")}
                              />
                              <FieldError id="ds-client-id-error" message={fieldErrors.client_id} />
                            </div>
                            <div>
                              <FieldLabel htmlFor="ds-client-secret" required>Client Secret</FieldLabel>
                              <Input
                                id="ds-client-secret"
                                type="password"
                                value={formData.client_secret}
                                onChange={(e) => updateField("client_secret", e.target.value)}
                                placeholder="OAuth client secret"
                                aria-required="true"
                                aria-invalid={fieldErrors.client_secret ? "true" : undefined}
                                aria-describedby={describedBy(null, !!fieldErrors.client_secret, "ds-client-secret-error")}
                              />
                              <FieldError id="ds-client-secret-error" message={fieldErrors.client_secret} />
                            </div>
                            <div>
                              <FieldLabel htmlFor="ds-token-url" required>Token URL</FieldLabel>
                              <Input
                                id="ds-token-url"
                                value={formData.token_url}
                                onChange={(e) => updateField("token_url", e.target.value)}
                                placeholder="https://auth.example.gov/oauth/token"
                                aria-required="true"
                                aria-invalid={fieldErrors.token_url ? "true" : undefined}
                                aria-describedby={describedBy(null, !!fieldErrors.token_url, "ds-token-url-error")}
                              />
                              <FieldError id="ds-token-url-error" message={fieldErrors.token_url} />
                            </div>
                          </div>
                        )}

                        {formData.auth_method === "basic" && (
                          <div className="space-y-2 pl-3 border-l-2 border-muted">
                            <div>
                              <FieldLabel htmlFor="ds-basic-username" required>Username</FieldLabel>
                              <Input
                                id="ds-basic-username"
                                value={formData.rest_username}
                                onChange={(e) => updateField("rest_username", e.target.value)}
                                placeholder="Username"
                                aria-required="true"
                                aria-invalid={fieldErrors.rest_username ? "true" : undefined}
                                aria-describedby={describedBy(null, !!fieldErrors.rest_username, "ds-basic-username-error")}
                              />
                              <FieldError id="ds-basic-username-error" message={fieldErrors.rest_username} />
                            </div>
                            <div>
                              <FieldLabel htmlFor="ds-basic-password" required>Password</FieldLabel>
                              <Input
                                id="ds-basic-password"
                                type="password"
                                value={formData.rest_password}
                                onChange={(e) => updateField("rest_password", e.target.value)}
                                placeholder="Password"
                                aria-required="true"
                                aria-invalid={fieldErrors.rest_password ? "true" : undefined}
                                aria-describedby={describedBy(null, !!fieldErrors.rest_password, "ds-basic-password-error")}
                              />
                              <FieldError id="ds-basic-password-error" message={fieldErrors.rest_password} />
                            </div>
                          </div>
                        )}

                        <div>
                          <FieldLabel htmlFor="ds-pagination-style">Pagination Style</FieldLabel>
                          <Select value={formData.pagination_style} onValueChange={(v) => updateField("pagination_style", v ?? "")}>
                            <SelectTrigger id="ds-pagination-style" className="mt-1">
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
                          <FieldLabel htmlFor="ds-max-records">Max Records</FieldLabel>
                          <Input
                            id="ds-max-records"
                            type="number"
                            value={formData.max_records}
                            onChange={(e) => updateField("max_records", e.target.value)}
                            placeholder="1000"
                          />
                        </div>
                      </div>
                    )}

                    {/* ODBC config */}
                    {formData.sourceType === "odbc" && (
                      <div className="space-y-3">
                        <div>
                          <FieldLabel htmlFor="ds-conn-string" required>Connection String</FieldLabel>
                          <Input
                            id="ds-conn-string"
                            type="password"
                            value={formData.connection_string}
                            onChange={(e) => updateField("connection_string", e.target.value)}
                            placeholder="DSN=MyDSN;UID=user;PWD=..."
                            aria-required="true"
                            aria-invalid={fieldErrors.connection_string ? "true" : undefined}
                            aria-describedby={describedBy("ds-conn-string-hint", !!fieldErrors.connection_string, "ds-conn-string-error")}
                          />
                          <p id="ds-conn-string-hint" className="text-xs text-muted-foreground mt-1">Stored securely. Contains credentials — never logged or echoed.</p>
                          <FieldError id="ds-conn-string-error" message={fieldErrors.connection_string} />
                        </div>
                        <div>
                          <FieldLabel htmlFor="ds-table-name" required>Table Name</FieldLabel>
                          <Input
                            id="ds-table-name"
                            value={formData.table_name}
                            onChange={(e) => updateField("table_name", e.target.value)}
                            placeholder="public_records"
                            aria-required="true"
                            aria-invalid={fieldErrors.table_name ? "true" : undefined}
                            aria-describedby={describedBy(null, !!fieldErrors.table_name, "ds-table-name-error")}
                          />
                          <FieldError id="ds-table-name-error" message={fieldErrors.table_name} />
                        </div>
                        <div>
                          <FieldLabel htmlFor="ds-pk-column" required>Primary Key Column</FieldLabel>
                          <Input
                            id="ds-pk-column"
                            value={formData.pk_column}
                            onChange={(e) => updateField("pk_column", e.target.value)}
                            placeholder="id"
                            aria-required="true"
                            aria-invalid={fieldErrors.pk_column ? "true" : undefined}
                            aria-describedby={describedBy(null, !!fieldErrors.pk_column, "ds-pk-column-error")}
                          />
                          <FieldError id="ds-pk-column-error" message={fieldErrors.pk_column} />
                        </div>
                        <div>
                          <FieldLabel htmlFor="ds-modified-column">
                            Modified Timestamp Column <span className="text-muted-foreground text-xs">(optional)</span>
                          </FieldLabel>
                          <Input
                            id="ds-modified-column"
                            value={formData.modified_column}
                            onChange={(e) => updateField("modified_column", e.target.value)}
                            placeholder="updated_at"
                          />
                        </div>
                        <div>
                          <FieldLabel htmlFor="ds-batch-size">Batch Size</FieldLabel>
                          <Input
                            id="ds-batch-size"
                            type="number"
                            value={formData.batch_size}
                            onChange={(e) => updateField("batch_size", e.target.value)}
                            placeholder="500"
                          />
                        </div>
                      </div>
                    )}

                    <div className="flex justify-between">
                      <Button type="button" variant="outline" onClick={() => { setFieldErrors({}); setWizardStep(1); }}>Back</Button>
                      <Button type="button" onClick={() => tryAdvance(3)}>Next</Button>
                    </div>
                  </>
                )}

                {/* Step 3: Review + test connection */}
                {wizardStep === 3 && (
                  <>
                    <div className="space-y-2 border rounded-md p-3">
                      <label htmlFor="ds-schedule-enabled" className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                        <Checkbox
                          id="ds-schedule-enabled"
                          checked={formData.schedule_enabled}
                          onCheckedChange={(checked) =>
                            updateField("schedule_enabled", Boolean(checked))
                          }
                        />
                        Enable automatic sync
                      </label>
                      {formData.schedule_enabled && (
                        <div className="space-y-1">
                          <FieldLabel htmlFor="ds-schedule-preset">Sync schedule (UTC)</FieldLabel>
                          <select
                            id="ds-schedule-preset"
                            className="w-full border rounded-md px-2 py-1.5 text-sm bg-background"
                            value={formData.schedule_preset}
                            onChange={(e) => {
                              const preset = SCHEDULE_PRESETS.find((p) => p.label === e.target.value);
                              setFormData({
                                ...formData,
                                schedule_preset: e.target.value,
                                sync_schedule: preset?.cron ?? formData.sync_schedule,
                              });
                              if (fieldErrors.sync_schedule) {
                                setFieldErrors((prev) => {
                                  const next = { ...prev };
                                  delete next.sync_schedule;
                                  return next;
                                });
                              }
                            }}
                          >
                            {SCHEDULE_PRESETS.map((p) => (
                              <option key={p.label} value={p.label}>{p.label}</option>
                            ))}
                          </select>
                          {formData.schedule_preset === "Custom…" && (
                            <>
                              <FieldLabel htmlFor="ds-sync-schedule">Custom cron expression</FieldLabel>
                              <Input
                                id="ds-sync-schedule"
                                value={formData.sync_schedule}
                                onChange={(e) => updateField("sync_schedule", e.target.value)}
                                placeholder="0 2 * * * (5-field cron, UTC)"
                                aria-invalid={fieldErrors.sync_schedule ? "true" : undefined}
                                aria-describedby={describedBy(null, !!fieldErrors.sync_schedule, "ds-sync-schedule-error")}
                              />
                            </>
                          )}
                          <FieldError id="ds-sync-schedule-error" message={fieldErrors.sync_schedule} />
                          <p className="text-xs text-muted-foreground font-mono">
                            {formData.sync_schedule}
                          </p>
                          {formData.sync_schedule && !fieldErrors.sync_schedule && (
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
                          <p
                            role="alert"
                            className={`text-sm ${testResult.success ? "text-success" : "text-destructive"}`}
                          >
                            {testResult.success ? "✓" : "✗"} {testResult.message}
                          </p>
                        </CardContent>
                      </Card>
                    )}

                    {submitError && (
                      <Card className="shadow-none border-destructive">
                        <CardContent className="p-3">
                          <p role="alert" className="text-sm text-destructive">{submitError}</p>
                        </CardContent>
                      </Card>
                    )}

                    <div className="flex justify-between">
                      <Button type="button" variant="outline" onClick={() => { setFieldErrors({}); setWizardStep(2); }}>Back</Button>
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
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {sources.map((s) => (
            <SourceCard
              key={s.id}
              source={s}
              onRefresh={loadData}
              token={token}
            />
          ))}
          {sources.length === 0 && (
            <Card className="shadow-none md:col-span-2 xl:col-span-3">
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
