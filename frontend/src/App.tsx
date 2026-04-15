import { useState, useEffect, useCallback } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

function LiaisonGuard({ userRole, children }: { userRole: string; children: React.ReactNode }) {
  if (userRole === "liaison") return <Navigate to="/" replace />;
  return <>{children}</>;
}
import { isTokenValid, apiFetch } from "@/lib/api";
import { AppShell } from "@/components/app-shell";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Search from "@/pages/Search";
import Requests from "@/pages/Requests";
import RequestDetail from "@/pages/RequestDetail";
import Exemptions from "@/pages/Exemptions";
import DataSources from "@/pages/DataSources";
import Ingestion from "@/pages/Ingestion";
import Users from "@/pages/Users";
import Onboarding from "@/pages/Onboarding";
import CityProfile from "@/pages/CityProfile";
import Discovery from "@/pages/Discovery";
import Settings from "@/pages/Settings";
import AuditLog from "@/pages/AuditLog";

export default function App() {
  const [token, setToken] = useState<string | null>(() => {
    const stored = localStorage.getItem("token");
    // Clear expired tokens on load
    if (stored && !isTokenValid(stored)) {
      localStorage.removeItem("token");
      return null;
    }
    return stored;
  });

  const [userEmail, setUserEmail] = useState("");
  const [userRole, setUserRole] = useState<string>("");

  const logout = useCallback(() => {
    setToken(null);
    setUserEmail("");
    setUserRole("");
  }, []);

  useEffect(() => {
    if (token) localStorage.setItem("token", token);
    else localStorage.removeItem("token");
  }, [token]);

  // Check token expiration every 30 seconds
  useEffect(() => {
    if (!token) return;
    const interval = setInterval(() => {
      if (!isTokenValid(token)) {
        setToken(null);
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [token]);

  // Fetch real user info from API instead of decoding JWT sub (which is a UUID)
  useEffect(() => {
    if (token) {
      apiFetch<{ email: string; full_name: string | null; role: string }>("/users/me", { token })
        .then(data => {
          setUserEmail(data.full_name || data.email);
          setUserRole(data.role);
        })
        .catch(() => {
          // Fallback to JWT decode
          try {
            const payload = JSON.parse(atob(token.split(".")[1]));
            setUserEmail(payload.email || payload.sub || "");
          } catch { setUserEmail(""); }
          setUserRole("");
        });
    } else {
      setUserEmail("");
      setUserRole("");
    }
  }, [token]);

  if (!token) return <Login onLogin={setToken} />;

  return (
    <AppShell onSignOut={logout} userEmail={userEmail} userRole={userRole}>
      <Routes>
        <Route path="/" element={<Dashboard token={token} />} />
        <Route path="/search" element={<Search token={token} />} />
        <Route path="/requests" element={<Requests token={token} />} />
        <Route path="/requests/:id" element={<RequestDetail token={token} />} />
        <Route path="/exemptions" element={<Exemptions token={token} />} />
        <Route path="/sources" element={<DataSources token={token} />} />
        <Route path="/ingestion" element={<Ingestion token={token} />} />
        <Route path="/users" element={<LiaisonGuard userRole={userRole}><Users token={token} /></LiaisonGuard>} />
        <Route path="/onboarding" element={<LiaisonGuard userRole={userRole}><Onboarding token={token} /></LiaisonGuard>} />
        <Route path="/city-profile" element={<CityProfile token={token} />} />
        <Route path="/discovery" element={<Discovery token={token} />} />
        <Route path="/settings" element={<Settings token={token} />} />
        <Route path="/audit-log" element={<LiaisonGuard userRole={userRole}><AuditLog token={token} /></LiaisonGuard>} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </AppShell>
  );
}
