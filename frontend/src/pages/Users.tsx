import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { DataTable, type Column } from "@/components/data-table";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import { Plus, Users as UsersIcon } from "lucide-react";

interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
  department_id: string | null;
}

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-purple-100 text-purple-800",
  staff: "bg-green-100 text-green-800",
  reviewer: "bg-blue-100 text-blue-800",
  read_only: "bg-gray-100 text-gray-600",
  liaison: "bg-amber-100 text-amber-800",
  public: "bg-slate-100 text-slate-600",
};

function formatLastLogin(dateStr: string | null): string {
  if (!dateStr) return "Never logged in";
  const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / (1000 * 60 * 60 * 24));
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return new Date(dateStr).toLocaleDateString();
}

export default function Users({ token }: { token: string }) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ email: "", password: "", fullName: "", role: "read_only" });
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadData = async () => {
    try {
      const data = await apiFetch<User[]>("/admin/users", { token });
      setUsers(data);
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
    setFormError("");
    try {
      await apiFetch("/auth/register", {
        token,
        method: "POST",
        body: JSON.stringify({
          email: formData.email,
          password: formData.password,
          full_name: formData.fullName,
          role: formData.role,
        }),
      });
      setShowForm(false);
      setFormData({ email: "", password: "", fullName: "", role: "read_only" });
      await loadData();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setSubmitting(false);
    }
  };

  const columns: Column<User & Record<string, unknown>>[] = [
    {
      key: "full_name",
      header: "Name",
      render: (u) => <span className="font-medium">{u.full_name || u.email}</span>,
    },
    {
      key: "email",
      header: "Email",
      render: (u) => <span className="text-sm text-muted-foreground">{u.email}</span>,
    },
    {
      key: "role",
      header: "Role",
      render: (u) => (
        <Badge variant="outline" className={`text-xs border-0 ${ROLE_COLORS[u.role] || ROLE_COLORS.read_only}`}>
          {u.role}
        </Badge>
      ),
    },
    {
      key: "department_id",
      header: "Department",
      render: (u) => (
        <span className="text-sm text-muted-foreground">
          {u.department_id ? u.department_id.toString().slice(0, 8) + "..." : "None"}
        </span>
      ),
    },
    {
      key: "is_active",
      header: "Status",
      render: (u) => (
        <span className={`text-sm ${u.is_active ? "text-success" : "text-muted-foreground"}`}>
          {u.is_active ? "Active" : "Inactive"}
        </span>
      ),
    },
    {
      key: "last_login",
      header: "Last Active",
      render: (u) => (
        <span className="text-sm text-muted-foreground">{formatLastLogin(u.last_login)}</span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        actions={
          <Dialog open={showForm} onOpenChange={setShowForm}>
            <DialogTrigger render={<Button />}>
              <Plus className="h-4 w-4 mr-2" />
              Create User
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create User</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                {formError && (
                  <Card className="border-destructive">
                    <CardContent className="p-3"><p className="text-destructive text-sm">{formError}</p></CardContent>
                  </Card>
                )}
                <div>
                  <label className="text-sm font-medium">Full Name</label>
                  <Input value={formData.fullName} onChange={(e) => setFormData({ ...formData, fullName: e.target.value })} required />
                </div>
                <div>
                  <label className="text-sm font-medium">Email</label>
                  <Input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} required />
                </div>
                <div>
                  <label className="text-sm font-medium">Password</label>
                  <Input type="password" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} required minLength={8} />
                </div>
                <div>
                  <label className="text-sm font-medium">Role</label>
                  <Select value={formData.role} onValueChange={(v) => setFormData({ ...formData, role: v ?? "read_only" })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="read_only">Read Only</SelectItem>
                      <SelectItem value="liaison">Liaison</SelectItem>
                      <SelectItem value="staff">Staff</SelectItem>
                      <SelectItem value="reviewer">Reviewer</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="public">Public</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex justify-end gap-3">
                  <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
                  <Button type="submit" disabled={submitting}>{submitting ? "Creating..." : "Create User"}</Button>
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

      {users.length === 0 ? (
        <EmptyState
          icon={UsersIcon}
          title="No users found"
          description="Create user accounts for staff members who need access to the system."
          action={<Button onClick={() => setShowForm(true)}><Plus className="h-4 w-4 mr-2" /> Create First User</Button>}
        />
      ) : (
        <DataTable
          columns={columns}
          data={users as (User & Record<string, unknown>)[]}
          rowKey={(u) => u.id as string}
          ariaLabel="System users"
        />
      )}
    </div>
  );
}
