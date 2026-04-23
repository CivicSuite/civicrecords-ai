import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

/**
 * T5D — public-mode landing page.
 *
 * Reachable at ``/public`` in ``PORTAL_MODE=public`` deployments. Serves
 * as the resident-facing front door:
 *
 * * Explains what residents can do on this site (submit a records
 *   request).
 * * Steers unauthenticated visitors to either register or sign in.
 * * Steers authenticated residents to the submission form.
 *
 * Per Scott 2026-04-22 Option A, submission requires authentication;
 * copy makes that explicit — no anonymous-submission language anywhere.
 *
 * Out of T5D scope (explicit per locked B4): published-records search,
 * track-my-request suite, resident dashboard. Do not add them here.
 */

interface PublicLandingProps {
  authenticated: boolean;
  /** Only passed when `authenticated === true`. */
  onSignOut?: () => void;
}

export default function PublicLanding({ authenticated, onSignOut }: PublicLandingProps) {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center min-h-screen bg-background px-4 py-10">
      <Card className="w-full max-w-2xl shadow-md">
        <CardHeader className="text-center pb-2">
          <h1 className="text-section-head text-foreground">
            Records Request Portal
          </h1>
          <p className="text-sm text-muted-foreground">
            Submit a public records request to the city records office.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          <section>
            <h2 className="text-base font-medium text-foreground mb-2">
              What you can do here
            </h2>
            <ul className="list-disc pl-5 space-y-1 text-sm text-foreground">
              <li>Create a resident account.</li>
              <li>
                Sign in and submit a records request. The records office
                staff will review it and respond.
              </li>
              <li>
                Save the tracking ID you receive after submission so you
                can reference your request when contacting the office.
              </li>
            </ul>
          </section>

          <section className="bg-muted/50 rounded-md p-4 text-sm text-muted-foreground">
            <strong className="text-foreground">
              A resident account is required to submit a request.
            </strong>{" "}
            Registering creates a minimal public account — it lets the
            records office tie the submission to a verified email address.
            Staff users should sign in through the usual staff login.
          </section>

          {authenticated ? (
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Button
                onClick={() => navigate("/public/submit")}
                className="w-full sm:w-auto"
              >
                Submit a records request
              </Button>
              {onSignOut && (
                <Button
                  variant="outline"
                  onClick={onSignOut}
                  className="w-full sm:w-auto"
                >
                  Sign out
                </Button>
              )}
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Button
                onClick={() => navigate("/public/register")}
                className="w-full sm:w-auto"
              >
                Create a resident account
              </Button>
              <Button
                variant="outline"
                onClick={() => navigate("/login")}
                className="w-full sm:w-auto"
              >
                Sign in
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
