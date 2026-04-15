import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { DataTable, type Column } from "@/components/data-table";
import { LoadingRegion } from "@/components/loading-region";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
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
import { Plus, FileText, AlertTriangle, Clock, ChevronLeft, ChevronRight } from "lucide-react";

interface Request {
  id: string;
  requester_name: string;
  requester_email: string;
  description: string;
  status: string;
  priority?: string;
  department?: string;
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

interface Department {
  id: string;
  name: string;
}

interface User {
  id: string;
  email: string;
  full_name?: string;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "No deadline set";
  return new Date(dateStr).toLocaleDateString();
}

function formatRelativeDeadline(dateStr: string | null): string {
  if (!dateStr) return "No deadline";
  const days = Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  if (days < 0) return `${Math.abs(days)} days overdue`;
  if (days === 0) return "Due today";
  if (days <= 3) return `${days} days left`;
  return formatDate(dateStr);
}

export default function Requests({ token }: { token: string }) {
  const [requests, setRequests] = useState<Request[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [assignedToFilter, setAssignedToFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [departments, setDepartments] = useState<Department[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [formData, setFormData] = useState({ name: "", email: "", description: "", deadline: "" });
  const [submitting, setSubmitting] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;
  const navigate = useNavigate();

  const loadData = async () => {
    try {
      // Build query params for server-side filtering where supported
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (assignedToFilter !== "all") params.set("assigned_to", assignedToFilter);
      params.set("offset", String(page * PAGE_SIZE));
      params.set("limit", String(PAGE_SIZE));
      const qs = params.toString();

      const [reqData, statsData] = await Promise.all([
        apiFetch<Request[]>(`/requests/?${qs}`, { token }),
        apiFetch<Stats>("/requests/stats", { token }),
      ]);
      setRequests(reqData);
      setStats(statsData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  // Load filter option data (departments, users)
  useEffect(() => {
    apiFetch<Department[]>("/departments/", { token })
      .then(setDepartments)
      .catch(() => setDepartments([]));
    apiFetch<User[]>("/admin/users", { token })
      .then(setUsers)
      .catch(() => setUsers([]));
  }, [token]);

  // Reload requests when filters or page change
  useEffect(() => { setLoading(true); loadData(); }, [token, statusFilter, assignedToFilter, page]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const body: Record<string, string> = {
        requester_name: formData.name,
        description: formData.description,
      };
      if (formData.email) body.requester_email = formData.email;
      if (formData.deadline) body.statutory_deadline = formData.deadline;

      await apiFetch("/requests/", {
        token,
        method: "POST",
        body: JSON.stringify(body),
      });
      setShowForm(false);
      setFormData({ name: "", email: "", description: "", deadline: "" });
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setSubmitting(false);
    }
  };

  // Status and assigned_to are filtered server-side via query params.
  // Department, priority, and date range are filtered client-side until the
  // backend adds support for those query parameters.
  const filtered = requests.filter((r) => {
    if (departmentFilter !== "all" && r.department !== departmentFilter) return false;
    if (priorityFilter !== "all" && (r.priority ?? "normal") !== priorityFilter) return false;
    if (dateFrom) {
      const created = new Date(r.created_at);
      if (created < new Date(dateFrom)) return false;
    }
    if (dateTo) {
      const created = new Date(r.created_at);
      if (created > new Date(dateTo + "T23:59:59")) return false;
    }
    return true;
  });

  const columns: Column<Request & Record<string, unknown>>[] = [
    { key: "requester_name", header: "Requester" },
    {
      key: "description",
      header: "Description",
      render: (r) => (
        <span className="text-sm text-muted-foreground">
          {r.description.length > 60 ? r.description.substring(0, 60) + "..." : r.description}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <StatusBadge status={r.status} domain="request" />,
    },
    {
      key: "priority",
      header: "Priority",
      render: (r) => {
        const p = (r.priority as string) || "normal";
        const colors: Record<string, string> = {
          urgent: "bg-red-100 text-red-800",
          expedited: "bg-amber-100 text-amber-800",
          normal: "bg-gray-100 text-gray-600",
          low: "bg-slate-100 text-slate-500",
        };
        return (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[p] || colors.normal}`}>
            {p}
          </span>
        );
      },
    },
    {
      key: "statutory_deadline",
      header: "Deadline",
      render: (r) => {
        const days = r.statutory_deadline
          ? Math.ceil((new Date(r.statutory_deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
          : null;
        return (
          <span className={days !== null && days < 0 ? "text-destructive font-medium" : days !== null && days <= 3 ? "text-warning font-medium" : "text-muted-foreground"}>
            {formatRelativeDeadline(r.statutory_deadline)}
          </span>
        );
      },
    },
    {
      key: "created_at",
      header: "Created",
      render: (r) => <span className="text-sm text-muted-foreground">{formatDate(r.created_at)}</span>,
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Records Requests"
        actions={
          <Dialog open={showForm} onOpenChange={setShowForm}>
            <DialogTrigger render={<Button />}>
              <Plus className="h-4 w-4 mr-2" />
              New Request
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>New Records Request</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Requester Name *</label>
                  <Input value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
                </div>
                <div>
                  <label className="text-sm font-medium">Email</label>
                  <Input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} />
                </div>
                <div>
                  <label className="text-sm font-medium">Description *</label>
                  <Input value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} required />
                </div>
                <div>
                  <label className="text-sm font-medium">Statutory Deadline</label>
                  <Input type="date" value={formData.deadline} onChange={(e) => setFormData({ ...formData, deadline: e.target.value })} />
                </div>
                <div className="flex justify-end gap-3">
                  <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
                  <Button type="submit" disabled={submitting}>{submitting ? "Creating..." : "Create Request"}</Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {error && (
        <Card role="alert" className="border-destructive">
          <CardContent className="p-4">
            <p className="text-destructive text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Stat cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard label="Total Open" value={stats.total_requests} icon={FileText} />
          <StatCard label="In Review" value={stats.by_status?.in_review ?? 0} icon={Clock} />
          <StatCard
            label="Approaching Deadline"
            value={stats.approaching_deadline}
            icon={AlertTriangle}
            variant={stats.approaching_deadline > 0 ? "warning" : "default"}
          />
          <StatCard
            label="Overdue"
            value={stats.overdue}
            icon={AlertTriangle}
            variant={stats.overdue > 0 ? "danger" : "default"}
          />
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v ?? "all"); setPage(0); }}>
          <SelectTrigger className="w-[160px]" aria-label="Status filter">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="received">Received</SelectItem>
            <SelectItem value="searching">Searching</SelectItem>
            <SelectItem value="in_review">In Review</SelectItem>
            <SelectItem value="drafted">Drafted</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="fulfilled">Fulfilled</SelectItem>
            <SelectItem value="closed">Closed</SelectItem>
          </SelectContent>
        </Select>

        <Select value={departmentFilter} onValueChange={(v) => { setDepartmentFilter(v ?? "all"); setPage(0); }}>
          <SelectTrigger className="w-[160px]" aria-label="Department filter">
            <SelectValue placeholder="All departments" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All departments</SelectItem>
            {departments.map((d) => (
              <SelectItem key={d.id} value={d.name}>{d.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={priorityFilter} onValueChange={(v) => { setPriorityFilter(v ?? "all"); setPage(0); }}>
          <SelectTrigger className="w-[140px]" aria-label="Priority filter">
            <SelectValue placeholder="All priorities" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All priorities</SelectItem>
            <SelectItem value="normal">Normal</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="urgent">Urgent</SelectItem>
          </SelectContent>
        </Select>

        <Select value={assignedToFilter} onValueChange={(v) => { setAssignedToFilter(v ?? "all"); setPage(0); }}>
          <SelectTrigger className="w-[160px]" aria-label="Assigned to filter">
            <SelectValue placeholder="All assignees" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All assignees</SelectItem>
            {users.map((u) => (
              <SelectItem key={u.id} value={u.id}>{u.full_name || u.email}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(0); }}
            className="w-[140px]"
            placeholder="From"
          />
          <span className="text-muted-foreground text-sm">to</span>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(0); }}
            className="w-[140px]"
            placeholder="To"
          />
        </div>
      </div>

      {/* Table */}
      {filtered.length === 0 && !loading ? (
        <EmptyState
          icon={FileText}
          title="No requests found"
          description={statusFilter !== "all" ? "No requests match the selected filter." : "No records requests have been submitted yet."}
          action={
            <Button onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create First Request
            </Button>
          }
        />
      ) : (
        <LoadingRegion loading={loading} label="Records requests">
          <DataTable<Request & Record<string, unknown>>
            columns={columns}
            data={filtered as (Request & Record<string, unknown>)[]}
            rowKey={(r) => r.id}
            onRowClick={(r) => navigate(`/requests/${r.id}`)}
            ariaLabel="Records requests"
            emptyMessage="No requests found."
          />
        </LoadingRegion>
      )}

      {/* Pagination controls */}
      <div className="flex items-center justify-between pt-2">
        <span className="text-sm text-muted-foreground">
          Showing {filtered.length === 0 ? 0 : page * PAGE_SIZE + 1}
          &ndash;{page * PAGE_SIZE + filtered.length}
          {stats ? ` of ${stats.total_requests}` : ""}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={requests.length < PAGE_SIZE}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  );
}
