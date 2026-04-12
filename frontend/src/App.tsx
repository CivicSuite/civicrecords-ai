import { useState, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Users from "./pages/Users";
import DataSources from "./pages/DataSources";
import Ingestion from "./pages/Ingestion";

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  useEffect(() => { if (token) localStorage.setItem("token", token); else localStorage.removeItem("token"); }, [token]);
  if (!token) return <Login onLogin={setToken} />;
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <h1 className="text-lg font-semibold text-gray-900">CivicRecords AI</h1>
          <a href="/" className="text-sm text-gray-600 hover:text-gray-900">Dashboard</a>
          <a href="/sources" className="text-sm text-gray-600 hover:text-gray-900">Sources</a>
          <a href="/ingestion" className="text-sm text-gray-600 hover:text-gray-900">Ingestion</a>
          <a href="/users" className="text-sm text-gray-600 hover:text-gray-900">Users</a>
        </div>
        <button onClick={() => setToken(null)} className="text-sm text-gray-500 hover:text-gray-700">Sign out</button>
      </nav>
      <main className="p-6 max-w-7xl mx-auto">
        <Routes>
          <Route path="/" element={<Dashboard token={token} />} />
          <Route path="/sources" element={<DataSources token={token} />} />
          <Route path="/ingestion" element={<Ingestion token={token} />} />
          <Route path="/users" element={<Users token={token} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
