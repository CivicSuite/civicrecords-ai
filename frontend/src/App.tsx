import { useState, useEffect, useCallback } from "react";
import { Routes, Route, Navigate, Link, useLocation } from "react-router-dom";
import { isTokenValid } from "./lib/api";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Users from "./pages/Users";
import DataSources from "./pages/DataSources";
import Ingestion from "./pages/Ingestion";
import Search from "./pages/Search";
import Requests from "./pages/Requests";
import RequestDetail from "./pages/RequestDetail";
import Exemptions from "./pages/Exemptions";

const NAV_ITEMS = [
  { path: "/search", label: "Search" },
  { path: "/requests", label: "Requests" },
  { path: "/exemptions", label: "Exemptions" },
  { path: "/", label: "Dashboard" },
  { path: "/sources", label: "Sources" },
  { path: "/ingestion", label: "Ingestion" },
  { path: "/users", label: "Users" },
];

function NavLink({ to, label }: { to: string; label: string }) {
  const location = useLocation();
  const isActive = to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
  return (
    <Link
      to={to}
      className={`text-sm transition-colors ${
        isActive
          ? "text-blue-700 font-medium"
          : "text-gray-600 hover:text-gray-900"
      }`}
      aria-current={isActive ? "page" : undefined}
    >
      {label}
    </Link>
  );
}

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

  const logout = useCallback(() => setToken(null), []);

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

  if (!token) return <Login onLogin={setToken} />;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center justify-between" role="navigation" aria-label="Main navigation">
        <div className="flex items-center gap-3 sm:gap-6 overflow-x-auto">
          <Link to="/" className="text-lg font-semibold text-gray-900 whitespace-nowrap">
            CivicRecords AI
          </Link>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.path} to={item.path} label={item.label} />
          ))}
        </div>
        <button
          onClick={logout}
          className="text-sm text-gray-500 hover:text-gray-700 whitespace-nowrap ml-4"
          aria-label="Sign out of your account"
        >
          Sign out
        </button>
      </nav>
      <main className="p-4 sm:p-6 max-w-7xl mx-auto" role="main">
        <Routes>
          <Route path="/" element={<Dashboard token={token} />} />
          <Route path="/search" element={<Search token={token} />} />
          <Route path="/requests" element={<Requests token={token} />} />
          <Route path="/requests/:id" element={<RequestDetail token={token} />} />
          <Route path="/exemptions" element={<Exemptions token={token} />} />
          <Route path="/sources" element={<DataSources token={token} />} />
          <Route path="/ingestion" element={<Ingestion token={token} />} />
          <Route path="/users" element={<Users token={token} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
