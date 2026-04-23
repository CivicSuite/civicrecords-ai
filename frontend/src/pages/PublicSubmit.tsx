import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

/**
 * T5D — authenticated records-request submission form (public mode only).
 *
 * POSTs to ``/public/requests`` as the signed-in ``UserRole.PUBLIC``
 * user. Backend pulls ``requester_name`` / ``requester_email`` from the
 * account record; this form collects only the description and optional
 * phone number.
 *
 * Surface states:
 * * unauthenticated — redirect to ``/public/register`` (form is not
 *                     viewable without a token; anonymous submission is
 *                     explicitly out of scope, Scott 2026-04-22 Option A).
 * * empty    — initial load, form untouched.
 * * partial  — description typed but below 10 chars; Submit button
 *              remains enabled but the backend 422 surfaces actionable
 *              copy if sent. (Client-side guard also catches this before
 *              sending.)
 * * loading  — submit button pressed, request in flight.
 * * success  — tracking id shown; form cleared; "Submit another" CTA.
 * * error    — ``role="alert"`` message; always actionable.
 */

interface PublicSubmitProps {
  token: string | null;
  onSignOut?: () => void;
}

interface SubmitResponse {
  request_id: string;
  status: string;
  submitted_at: string;
  message: string;
}

export default function PublicSubmit({ token, onSignOut }: PublicSubmitProps) {
  // Hard gate: no anonymous submission. Without a token, send the user
  // to the registration page. This is defense-in-depth — App.tsx should
  // not route to this page without a token in the standard flow.
  // Splitting authed/unauthed into two components lets the inner
  // component declare hooks freely (no rules-of-hooks violation) and
  // lets TypeScript narrow ``token`` to ``string`` in the inner scope.
  if (!token) {
    return <Navigate to="/public/register" replace />;
  }
  return <AuthenticatedSubmit token={token} onSignOut={onSignOut} />;
}

function AuthenticatedSubmit({
  token,
  onSignOut,
}: {
  token: string;
  onSignOut?: () => void;
}) {
  const navigate = useNavigate();
  const [description, setDescription] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SubmitResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const trimmed = description.trim();
    if (trimmed.length < 10) {
      setError(
        "Please describe your request in at least 10 characters so the " +
          "records-office reviewer can understand what you need."
      );
      return;
    }

    setLoading(true);
    try {
      const res = await apiFetch<SubmitResponse>("/public/requests", {
        method: "POST",
        token,
        body: JSON.stringify({
          description: trimmed,
          phone: phone.trim() || null,
        }),
      });
      setResult(res);
      setDescription("");
      setPhone("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Submission failed.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center min-h-screen bg-background px-4 py-10">
      <Card className="w-full max-w-2xl shadow-md">
        <CardHeader className="text-center pb-2">
          <h1 className="text-section-head text-foreground">
            Submit a records request
          </h1>
          <p className="text-sm text-muted-foreground">
            Describe the records you want as plainly as you can. Include
            dates, departments, or file types if you know them.
          </p>
        </CardHeader>
        <CardContent>
          {result ? (
            <div
              role="status"
              aria-live="polite"
              className="space-y-4"
            >
              <div className="rounded-md bg-emerald-500/10 border border-emerald-500/40 p-4">
                <p className="text-sm font-medium text-foreground">
                  Your request has been submitted.
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  Tracking ID:{" "}
                  <code className="bg-background px-1 py-0.5 rounded text-foreground">
                    {result.request_id}
                  </code>
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  {result.message}
                </p>
              </div>
              <div className="flex flex-col sm:flex-row gap-3">
                <Button onClick={() => setResult(null)} className="w-full sm:w-auto">
                  Submit another request
                </Button>
                <Button
                  variant="outline"
                  onClick={() => navigate("/public")}
                  className="w-full sm:w-auto"
                >
                  Back to the portal home
                </Button>
                {onSignOut && (
                  <Button variant="outline" onClick={onSignOut} className="w-full sm:w-auto">
                    Sign out
                  </Button>
                )}
              </div>
            </div>
          ) : (
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
                  htmlFor="public-submit-description"
                  className="text-sm font-medium text-foreground"
                >
                  Describe the records you want
                </label>
                <textarea
                  id="public-submit-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={6}
                  className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 outline-none"
                  aria-required="true"
                  required
                  minLength={10}
                  placeholder="Example: All City Council meeting minutes from January to March 2026."
                />
                <p className="text-xs text-muted-foreground">
                  At least 10 characters.
                </p>
              </div>

              <div className="space-y-1">
                <label
                  htmlFor="public-submit-phone"
                  className="text-sm font-medium text-foreground"
                >
                  Phone (optional)
                </label>
                <Input
                  id="public-submit-phone"
                  type="tel"
                  autoComplete="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Only if you'd like staff to call you with clarifying
                  questions. Your email will be used by default.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <Button type="submit" className="w-full sm:w-auto" disabled={loading}>
                  {loading ? "Submitting…" : "Submit request"}
                </Button>
                {onSignOut && (
                  <Button type="button" variant="outline" onClick={onSignOut} className="w-full sm:w-auto">
                    Sign out
                  </Button>
                )}
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
