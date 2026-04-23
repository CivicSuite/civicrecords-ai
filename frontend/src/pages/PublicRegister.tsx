import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login, apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

/**
 * T5D — resident self-registration page (public mode only).
 *
 * POSTs to ``/auth/register``; the backend pins the new user's role to
 * ``UserRole.PUBLIC`` server-side regardless of what the client sends.
 * On success, logs the new resident in and routes them to the
 * submission form.
 *
 * Surface states:
 * * empty    — initial load, form untouched.
 * * partial  — some fields filled but not yet submitted.
 * * loading  — submit button pressed, request in flight.
 * * success  — redirected to ``/public/submit`` on 201.
 * * error    — ``role="alert"`` message + ``aria-invalid`` on offending
 *              inputs; always actionable (what's wrong and how to fix).
 */

interface PublicRegisterProps {
  onLogin: (token: string) => void;
}

export default function PublicRegister({ onLogin }: PublicRegisterProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Enter the email address you want to sign in with.");
      return;
    }
    if (password.length < 8) {
      setError(
        "Password must be at least 8 characters. Longer is safer — " +
          "we recommend a passphrase you'll remember."
      );
      return;
    }

    setLoading(true);
    try {
      await apiFetch("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim(),
          password,
          full_name: fullName.trim(),
        }),
      });
      // Auto-sign-in so the resident can immediately submit a request
      const token = await login(email.trim(), password);
      onLogin(token);
      navigate("/public/submit", { replace: true });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Registration failed.";
      // If fastapi-users returns "REGISTER_USER_ALREADY_EXISTS", rewrite
      // the message so it is actionable for a non-technical resident.
      if (msg.toUpperCase().includes("ALREADY_EXISTS")) {
        setError(
          "An account with that email already exists. Sign in instead, " +
            "or use a different email."
        );
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center min-h-screen bg-background px-4 py-10">
      <Card className="w-full max-w-md shadow-md">
        <CardHeader className="text-center pb-2">
          <h1 className="text-section-head text-foreground">
            Create a resident account
          </h1>
          <p className="text-sm text-muted-foreground">
            Needed once, so your records requests are tied to a verified
            email.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {error && (
              <div
                role="alert"
                className="rounded-md bg-destructive/10 border border-destructive/40 p-3"
              >
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <div className="space-y-1">
              <label
                htmlFor="public-register-email"
                className="text-sm font-medium text-foreground"
              >
                Email
              </label>
              <Input
                id="public-register-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-required="true"
                required
              />
            </div>

            <div className="space-y-1">
              <label
                htmlFor="public-register-name"
                className="text-sm font-medium text-foreground"
              >
                Full name
              </label>
              <Input
                id="public-register-name"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Shown to records-office staff on every request you submit.
              </p>
            </div>

            <div className="space-y-1">
              <label
                htmlFor="public-register-password"
                className="text-sm font-medium text-foreground"
              >
                Password
              </label>
              <Input
                id="public-register-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-required="true"
                required
              />
              <p className="text-xs text-muted-foreground">
                At least 8 characters. A passphrase you can remember is
                usually stronger than a short complex string.
              </p>
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating account…" : "Create account"}
            </Button>

            <p className="text-sm text-muted-foreground text-center pt-2">
              Already have an account?{" "}
              <Link to="/login" className="text-primary underline">
                Sign in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
