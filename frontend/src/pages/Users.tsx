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

export default function Users({ token }: Props) {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<User[]>("/users", { token })
      .then(setUsers)
      .catch((e) => setError(e.message));
  }, [token]);

  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Users</h2>
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
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
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
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
      </div>
    </div>
  );
}
