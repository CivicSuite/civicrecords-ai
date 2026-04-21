import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { DataTable, type Column } from "@/components/data-table";
import { LoadingRegion } from "@/components/loading-region";
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
import { Pencil, Plus, UserX, Users as UsersIcon } from "lucide-react";

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

interface Department {
  id: string;
  name: string;
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
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ email: "", password: "", fullName: "", role: "read_only" });
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editData, setEditData] = useState({ fullName: "", role: "", departmentId: "" });
  const [editError, setEditError] = useState("");

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

  useEffect(() => {
    loadData();
    apiFetch<Department[]>("/departments/", { token })
      .then(setDepartments)
      .catch(() => setDepartments([]));
  }, [token]);

  const deptMap = new Map(departments.map((d) => [d.id, d.name]));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError("");
    try {
      await apiFetch("/admin/users", {
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

  const openEditDialog = (u: User) => {
    setEditUser(u);
    setEditData({
      fullName: u.full_name || "",
      role: u.role,
      departmentId: u.department_id || "",
    });
    setEditError("");
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editUser) return;
    setSubmitting(true);
    setEditError("");
    try {
      const body: Record<string, unknown> = {};
      if (editData.fullName !== (editUser.full_name || "")) body.full_name = editData.fullName;
      if (editData.role !== editUser.role) body.role = editData.role;
      if (editData.departmentId !== (editUser.department_id || "")) {
        body.department_id = editData.departmentId || null;
      }
      await apiFetch(`/admin/users/${editUser.id}`, {
        token,
        method: "PATCH",
        body: JSON.stringify(body),
      });
      setEditUser(null);
      await loadData();
    } catch (e) {
      setEditError(e instanceof Error ? e.message : "Failed to update");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (u: User) => {
    if (!confirm(`Deactivate ${u.full_name || u.email}? They will lose access.`)) return;
    try {
      await apiFetch(`/admin/users/${u.id}`, {
        token,
        method: "PATCH",
        body: JSON.stringify({ is_active: false }),
      });
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to deactivate");
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
          {u.department_id ? deptMap.get(u.department_id) || "Unknown" : "Unassigned"}
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
    {
      key: "actions",
      header: "Actions",
      render: (u) => (
        <div className="flex gap-1">
          <Button size="icon-xs" variant="ghost" onClick={() => openEditDialog(u as unknown as User)} title="Edit user">
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          {u.is_active && (
            <Button size="icon-xs" variant="ghost" onClick={() => handleDeactivate(u as unknown as User)} title="Deactivate user" className="text-destructive hover:text-destructive">
              <UserX className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
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
                  <Card role="alert" className="border-destructive">
                    <CardContent className="p-3"><p className="text-destructive text-sm">{formError}</p></CardContent>
                  </Card>
                )}
                <div>
                  <label htmlFor="create-user-fullname" className="text-sm font-medium">Full Name</label>
                  <Input id="create-user-fullname" value={formData.fullName} onChange={(e) => setFormData({ ...formData, fullName: e.target.value })} required />
                </div>
                <div>
                  <label htmlFor="create-user-email" className="text-sm font-medium">Email</label>
                  <Input id="create-user-email" type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} required />
                </div>
                <div>
                  <label htmlFor="create-user-password" className="text-sm font-medium">Password</label>
                  <Input id="create-user-password" type="password" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} required minLength={8} />
                </div>
                <div>
                  <label className="text-sm font-medium">Role</label>
                  <Select value={formData.role} onValueChange={(v) => setFormData({ ...formData, role: v ?? "read_only" })}>
                    <SelectTrigger aria-label="User role"><SelectValue /></SelectTrigger>
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
        <Card role="alert" className="border-destructive">
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
        <LoadingRegion loading={loading} label="Users list">
          <DataTable
            columns={columns}
            data={users as (User & Record<string, unknown>)[]}
            rowKey={(u) => u.id as string}
            ariaLabel="System users"
          />
        </LoadingRegion>
      )}

      {/* Edit User Dialog */}
      <Dialog open={!!editUser} onOpenChange={(open) => { if (!open) setEditUser(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit User — {editUser?.email}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEdit} className="space-y-4">
            {editError && (
              <Card role="alert" className="border-destructive">
                <CardContent className="p-3"><p className="text-destructive text-sm">{editError}</p></CardContent>
              </Card>
            )}
            <div>
              <label className="text-sm font-medium">Full Name</label>
              <Input value={editData.fullName} onChange={(e) => setEditData({ ...editData, fullName: e.target.value })} />
            </div>
            <div>
              <label className="text-sm font-medium">Role</label>
              <Select value={editData.role} onValueChange={(v) => setEditData({ ...editData, role: v ?? editData.role })}>
                <SelectTrigger aria-label="User role"><SelectValue /></SelectTrigger>
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
            <div>
              <label className="text-sm font-medium">Department</label>
              <Select value={editData.departmentId} onValueChange={(v) => setEditData({ ...editData, departmentId: v ?? "" })}>
                <SelectTrigger aria-label="Department"><SelectValue placeholder="Unassigned" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Unassigned</SelectItem>
                  {departments.map((d) => (
                    <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={() => setEditUser(null)}>Cancel</Button>
              <Button type="submit" disabled={submitting}>{submitting ? "Saving..." : "Save Changes"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
