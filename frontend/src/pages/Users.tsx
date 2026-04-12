import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

interface Props {
  token: string;
}

const ROLES = ["admin", "staff", "reviewer", "read_only"] as const;
type Role = typeof ROLES[number];

export default function Users({ token }: Props) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Create user form state
  const [showForm, setShowForm] = useState(false);
  const [formEmail, setFormEmail] = useState("");
  const [formPassword, setFormPassword] = useState("");
  const [formFullName, setFormFullName] = useState("");
  const [formRole, setFormRole] = useState<Role>("read_only");
  const [formError, setFormError] = useState("");
  const [formSubmitting, setFormSubmitting] = useState(false);

  const loadUsers = () => {
    setLoading(true);
    setError("");
    apiFetch<User[]>("/admin/users", { token })
      .then(setUsers)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadUsers();
  }, [token]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    setFormSubmitting(true);
    try {
      await apiFetch("/auth/register", {
        token,
        method: "POST",
        body: JSON.stringify({
          email: formEmail,
          password: formPassword,
          full_name: formFullName,
          role: formRole,
        }),
      });
      setFormEmail("");
      setFormPassword("");
      setFormFullName("");
      setFormRole("read_only");
      setShowForm(false);
      loadUsers();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to create user");
    } finally {
      setFormSubmitting(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Users</h2>
        <button
          onClick={() => { setShowForm(!showForm); setFormError(""); }}
          className="btn btn-primary"
        >
          {showForm ? "Cancel" : "+ Create User"}
        </button>
      </div>

      {error && (
        <p role="alert" className="error-banner mb-4">
          {error}
        </p>
      )}

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">Create User</h3>
          {formError && (
            <p role="alert" className="error-banner mb-3">
              {formError}
            </p>
          )}
          <form onSubmit={handleCreateUser} className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="form-label">Email *</label>
              <input
                type="email"
                required
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                className="form-input"
                placeholder="user@example.com"
                aria-label="Email address"
              />
            </div>
            <div>
              <label className="form-label">Password *</label>
              <input
                type="password"
                required
                value={formPassword}
                onChange={(e) => setFormPassword(e.target.value)}
                className="form-input"
                placeholder="Min 8 characters"
                aria-label="Password"
              />
            </div>
            <div>
              <label className="form-label">Full Name</label>
              <input
                type="text"
                value={formFullName}
                onChange={(e) => setFormFullName(e.target.value)}
                className="form-input"
                placeholder="Jane Smith"
                aria-label="Full name"
              />
            </div>
            <div>
              <label className="form-label">Role *</label>
              <select
                value={formRole}
                onChange={(e) => setFormRole(e.target.value as Role)}
                className="form-input"
                aria-label="User role"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={formSubmitting}
                className="btn btn-primary disabled:opacity-50"
              >
                {formSubmitting ? "Creating..." : "Create User"}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <span className="spinner" aria-label="Loading users" />
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm" aria-label="User accounts">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Email</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Role</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Last Login</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-gray-100">
                  <td className="px-4 py-3 text-gray-900">{u.full_name || "—"}</td>
                  <td className="px-4 py-3 text-gray-600">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`badge ${
                      u.role === "admin" ? "bg-purple-100 text-purple-700" :
                      u.role === "reviewer" ? "bg-blue-100 text-blue-700" :
                      u.role === "staff" ? "bg-green-100 text-green-700" :
                      "bg-gray-100 text-gray-700"
                    }`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs ${u.is_active ? "text-green-600" : "text-red-600"}`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {u.last_login ? new Date(u.last_login).toLocaleDateString() : "Never"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && (
            <p className="text-center py-8 text-gray-400">No users found.</p>
          )}
        </div>
      )}
    </div>
  );
}
