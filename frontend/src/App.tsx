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
import Settings from "@/pages/Settings";
import AuditLog from "@/pages/AuditLog";
import PublicLanding from "@/pages/PublicLanding";
import PublicRegister from "@/pages/PublicRegister";
import PublicSubmit from "@/pages/PublicSubmit";

type PortalMode = "public" | "private";

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
  // T5D — track whether the `/users/me` round-trip has settled. While a token
  // is present but this is false, we do NOT decide public-vs-staff routing —
  // otherwise a freshly-authenticated resident would briefly fall through
  // the `userRole === "public"` check (role is "" during the race) and see
  // the staff `AppShell` for a frame before the correct public-surface
  // render. Set true on success OR failure of /users/me.
  const [userInfoLoaded, setUserInfoLoaded] = useState(false);

  // T5D — deployment-wide portal mode, fetched once from the backend on
  // mount. Controls whether the /public/* route tree is reachable without
  // authentication. Null while the fetch is in flight; on fetch failure we
  // default to "private" (the safer choice — hides public surfaces rather
  // than exposing them on a flaky network).
  const [portalMode, setPortalMode] = useState<PortalMode | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<{ mode: PortalMode }>("/config/portal-mode")
      .then(data => {
        if (!cancelled) setPortalMode(data.mode);
      })
      .catch(() => {
        if (!cancelled) setPortalMode("private");
      });
    return () => { cancelled = true; };
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUserEmail("");
    setUserRole("");
    setUserInfoLoaded(false);
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
      setUserInfoLoaded(false);
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
        })
        .finally(() => setUserInfoLoaded(true));
    } else {
      setUserEmail("");
      setUserRole("");
      setUserInfoLoaded(false);
    }
  }, [token]);

  // T5D — posture/role mismatch guard. If an operator flips the deployment
  // to PORTAL_MODE=private while a resident's UserRole.PUBLIC token is still
  // in localStorage, sign them out. Private-mode deployments must not show
  // any public surface, not even for cached residents. The check waits for
  // /users/me to resolve so a transient empty userRole doesn't trigger it.
  useEffect(() => {
    if (
      token &&
      userInfoLoaded &&
      portalMode === "private" &&
      userRole === "public"
    ) {
      logout();
    }
  }, [token, userInfoLoaded, portalMode, userRole, logout]);

  // T5D — wait for the portal-mode fetch to resolve before deciding which
  // route tree to render. The delay is typically single-digit milliseconds;
  // a null-state splash avoids a flicker where the user sees Login render
  // and then redirect to /public.
  if (portalMode === null) {
    return (
      <div
        className="flex items-center justify-center min-h-screen text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        Loading…
      </div>
    );
  }

  // Unauthenticated:
  //   private mode → Login is the only reachable page.
  //   public  mode → /public, /public/register, /public/submit are all
  //                  reachable; /login remains the staff entry.
  if (!token) {
    if (portalMode === "public") {
      return (
        <Routes>
          <Route path="/public" element={<PublicLanding authenticated={false} />} />
          <Route path="/public/register" element={<PublicRegister onLogin={setToken} />} />
          <Route path="/public/submit" element={<PublicSubmit token={null} />} />
          <Route path="/login" element={<Login onLogin={setToken} />} />
          <Route path="*" element={<Navigate to="/public" replace />} />
        </Routes>
      );
    }
    return <Login onLogin={setToken} />;
  }

  // T5D — authenticated but /users/me hasn't resolved yet. Render the same
  // loading splash rather than falling through to the staff AppShell — a
  // resident whose role is briefly unknown must not see the staff UI,
  // even for a single frame. Once userInfoLoaded becomes true, this
  // guard releases and routing continues normally.
  if (!userInfoLoaded) {
    return (
      <div
        className="flex items-center justify-center min-h-screen text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        Loading…
      </div>
    );
  }

  // Authenticated as a resident (UserRole.PUBLIC) in a public-mode
  // deployment — show the public surface only. Do NOT mix them into the
  // staff AppShell; that would expose staff navigation.
  //
  // Private-mode with a UserRole.PUBLIC token is handled by the posture/
  // role mismatch useEffect above, which calls logout(). By the time this
  // branch runs with userRole === "public", portalMode must be "public" —
  // the explicit gate here is defense-in-depth against a render cycle
  // where the effect has not yet fired.
  if (userRole === "public" && portalMode === "public") {
    return (
      <Routes>
        <Route path="/public" element={<PublicLanding authenticated={true} onSignOut={logout} />} />
        <Route path="/public/submit" element={<PublicSubmit token={token} onSignOut={logout} />} />
        <Route path="*" element={<Navigate to="/public/submit" replace />} />
      </Routes>
    );
  }

  // Private-mode deployment with a resident token cached — render the
  // same loading splash while the logout effect tears the session down.
  // No public surface is rendered here, by design.
  if (userRole === "public" && portalMode === "private") {
    return (
      <div
        className="flex items-center justify-center min-h-screen text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        Signing out…
      </div>
    );
  }

  // Authenticated as staff / reviewer / liaison / admin / read_only —
  // existing staff dashboard. Unchanged from pre-T5D behavior.
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
        {/* /discovery deferred to v1.2 — route removed, nav item removed */}
        <Route path="/settings" element={<Settings token={token} />} />
        <Route path="/audit-log" element={<LiaisonGuard userRole={userRole}><AuditLog token={token} /></LiaisonGuard>} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </AppShell>
  );
}
