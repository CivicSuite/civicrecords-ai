import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { DataTable, type Column } from "@/components/data-table";
import { LoadingRegion } from "@/components/loading-region";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Shield, AlertTriangle, CheckCircle, Plus } from "lucide-react";

interface Rule extends Record<string, unknown> {
  id: string;
  state_code: string;
  category: string;
  rule_type: string;
  rule_definition: string;
  description?: string;
  enabled: boolean;
}

interface DashboardData {
  total_flags: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  acceptance_rate: number;
  total_rules: number;
  active_rules: number;
}

export default function Exemptions({ token }: { token: string }) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ stateCode: "CO", category: "", ruleType: "keyword", definition: "" });
  const [submitting, setSubmitting] = useState(false);

  const loadData = async () => {
    try {
      const [rulesData, dashData] = await Promise.all([
        apiFetch<Rule[]>("/exemptions/rules/", { token }),
        apiFetch<DashboardData>("/exemptions/dashboard", { token }),
      ]);
      setRules(rulesData);
      setDashboard(dashData);
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
      await apiFetch("/exemptions/rules/", {
        token,
        method: "POST",
        body: JSON.stringify({
          state_code: formData.stateCode,
          category: formData.category,
          rule_type: formData.ruleType,
          rule_definition: formData.definition,
        }),
      });
      setShowForm(false);
      setFormData({ stateCode: "CO", category: "", ruleType: "keyword", definition: "" });
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (rule: Rule) => {
    try {
      await apiFetch(`/exemptions/rules/${rule.id}`, {
        token,
        method: "PATCH",
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to toggle");
    }
  };

  const ruleColumns: Column<Rule & Record<string, unknown>>[] = [
    { key: "state_code", header: "State", className: "w-16" },
    { key: "category", header: "Category" },
    {
      key: "rule_type",
      header: "Type",
      render: (r) => (
        <Badge variant="outline" className="text-xs font-mono">{r.rule_type}</Badge>
      ),
    },
    {
      key: "rule_definition",
      header: "Definition",
      render: (r) => (
        <span className="text-sm text-muted-foreground font-mono">
          {r.rule_definition.length > 50 ? r.rule_definition.substring(0, 50) + "..." : r.rule_definition}
        </span>
      ),
    },
    {
      key: "enabled",
      header: "Status",
      render: (r) => (
        <span className={r.enabled ? "text-success font-medium text-sm" : "text-muted-foreground text-sm"}>
          {r.enabled ? "Active" : "Disabled"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      render: (r) => (
        <Button variant="ghost" size="sm" onClick={() => handleToggle(r)}>
          {r.enabled ? "Disable" : "Enable"}
        </Button>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
      </div>
    );
  }

  const totalReviewed = (dashboard?.by_status?.accepted ?? 0) + (dashboard?.by_status?.rejected ?? 0);
  const acceptanceDisplay = totalReviewed === 0
    ? "No flags reviewed yet"
    : `${dashboard?.acceptance_rate?.toFixed(1)}%`;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Exemption Detection"
        actions={
          <Dialog open={showForm} onOpenChange={setShowForm}>
            <DialogTrigger>
              <Button onClick={() => setShowForm(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Rule
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Exemption Rule</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-sm font-medium">State Code</label>
                  <Input value={formData.stateCode} onChange={(e) => setFormData({ ...formData, stateCode: e.target.value })} required />
                </div>
                <div>
                  <label className="text-sm font-medium">Category</label>
                  <Input value={formData.category} onChange={(e) => setFormData({ ...formData, category: e.target.value })} placeholder="e.g. CORA - Trade Secrets" required />
                </div>
                <div>
                  <label className="text-sm font-medium">Rule Type</label>
                  <Select value={formData.ruleType} onValueChange={(v) => setFormData({ ...formData, ruleType: v ?? "keyword" })}>
                    <SelectTrigger aria-label="Exemption category"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="keyword">Keyword</SelectItem>
                      <SelectItem value="regex">Regex</SelectItem>
                      <SelectItem value="llm_prompt">LLM Prompt</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-sm font-medium">Definition</label>
                  <Input value={formData.definition} onChange={(e) => setFormData({ ...formData, definition: e.target.value })} placeholder="e.g. trade secret,proprietary,confidential" required />
                </div>
                <div className="flex justify-end gap-3">
                  <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
                  <Button type="submit" disabled={submitting}>{submitting ? "Adding..." : "Add Rule"}</Button>
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

      {/* Stat cards */}
      {dashboard && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            label="Pending Review"
            value={dashboard.by_status?.flagged ?? dashboard.total_flags}
            icon={AlertTriangle}
            variant={(dashboard.by_status?.flagged ?? dashboard.total_flags) > 0 ? "warning" : "default"}
          />
          <StatCard label="Accepted" value={dashboard.by_status?.accepted ?? 0} icon={CheckCircle} variant="success" />
          <StatCard label="Rejected" value={dashboard.by_status?.rejected ?? 0} />
          <StatCard label="Active Rules" value={`${dashboard.active_rules}/${dashboard.total_rules}`} icon={Shield} />
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="rules">
        <TabsList>
          <TabsTrigger value="rules">Rules</TabsTrigger>
          <TabsTrigger value="flags">Flags for Review</TabsTrigger>
        </TabsList>

        <TabsContent value="rules" className="mt-4">
          {rules.length === 0 ? (
            <EmptyState
              icon={Shield}
              title="No exemption rules configured"
              description="Add rules to automatically flag sensitive content in ingested documents."
              action={<Button onClick={() => setShowForm(true)}><Plus className="h-4 w-4 mr-2" /> Add First Rule</Button>}
            />
          ) : (
            <LoadingRegion loading={loading} label="Exemptions list">
              <DataTable
                columns={ruleColumns}
                data={rules}
                rowKey={(r) => r.id}
                ariaLabel="Exemption rules"
              />
            </LoadingRegion>
          )}
        </TabsContent>

        <TabsContent value="flags" className="mt-4">
          <EmptyState
            icon={AlertTriangle}
            title={acceptanceDisplay === "No flags reviewed yet" ? "No flags reviewed yet" : "Flag review"}
            description="Exemption flags from ingested documents will appear here for review. Accept or reject each flag to build your review record."
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
