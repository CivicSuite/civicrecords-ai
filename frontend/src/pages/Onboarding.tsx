import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Building2,
  ChevronRight,
  ChevronLeft,
  CheckCircle,
  AlertTriangle,
  MapPin,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface CityProfile {
  cityName: string;
  state: string;
  county: string;
  populationBand: string;
  emailPlatform: string;
  hasDedicatedIT: string;
  monthlyRequestVolume: string;
  systems: Record<string, { vendor: string; notes: string }>;
}

const STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
  "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
  "VA","WA","WV","WI","WY",
];

const POPULATION_BANDS = [
  "Under 5,000",
  "5,000 - 25,000",
  "25,000 - 100,000",
  "100,000 - 500,000",
  "Over 500,000",
];

const DOMAINS = [
  { key: "finance", label: "Finance & Budgeting", hint: "Tyler Munis, Caselle, OpenGov, SAP" },
  { key: "public_safety", label: "Public Safety", hint: "Mark43, Spillman, Axon, Tyler New World" },
  { key: "permitting", label: "Land Use & Permitting", hint: "Accela, CityWorks, EnerGov" },
  { key: "hr", label: "Human Resources", hint: "NEOGOV, Workday, ADP, Paylocity" },
  { key: "document_mgmt", label: "Document Management", hint: "Laserfiche, OnBase, SharePoint" },
  { key: "utilities", label: "Utilities & Public Works", hint: "CIS Infinity, Cartegraph, Lucity" },
  { key: "courts", label: "Courts & Legal", hint: "Tyler Odyssey, Journal Technologies" },
  { key: "parks", label: "Parks & Recreation", hint: "RecTrac, CivicRec, ActiveNet" },
];

const STEPS = [
  { phase: 1, label: "City Profile", icon: Building2 },
  { phase: 2, label: "Systems", icon: MapPin },
  { phase: 3, label: "Gap Map", icon: AlertTriangle },
];

function loadSavedProfile(): CityProfile {
  try {
    const saved = localStorage.getItem("civicrecords_city_profile");
    if (saved) return JSON.parse(saved);
  } catch {}
  return {
    cityName: "", state: "CO", county: "", populationBand: "",
    emailPlatform: "", hasDedicatedIT: "", monthlyRequestVolume: "",
    systems: {},
  };
}

export default function Onboarding({ token }: { token: string }) {
  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState<CityProfile>(loadSavedProfile);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const navigate = useNavigate();

  const updateProfile = (updates: Partial<CityProfile>) => {
    setProfile((prev) => ({ ...prev, ...updates }));
  };

  const updateSystem = (domain: string, vendor: string, notes: string) => {
    setProfile((prev) => ({
      ...prev,
      systems: { ...prev.systems, [domain]: { vendor, notes } },
    }));
  };

  const saveAndContinue = async () => {
    // Always persist draft to localStorage between steps
    localStorage.setItem("civicrecords_city_profile", JSON.stringify(profile));

    if (step < 3) {
      setStep(step + 1);
      return;
    }

    // Final step: POST to API
    setSubmitting(true);
    setSubmitError(null);
    try {
      await apiFetch("/city-profile", {
        token,
        method: "POST",
        body: JSON.stringify({
          city_name: profile.cityName,
          state: profile.state,
          county: profile.county || undefined,
          population_band: profile.populationBand || undefined,
          email_platform: profile.emailPlatform || undefined,
          has_dedicated_it: profile.hasDedicatedIT === "yes" ? true : profile.hasDedicatedIT === "no" ? false : undefined,
          monthly_request_volume: profile.monthlyRequestVolume || undefined,
          gap_map: profile.systems,
        }),
      });
      localStorage.setItem("civicrecords_onboarding_complete", "true");
      navigate("/city-profile");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to save profile. Please try again.");
      setSubmitting(false);
    }
  };

  const domainsWithoutSystems = DOMAINS.filter(
    (d) => !profile.systems[d.key]?.vendor
  );

  return (
    <div className="space-y-6 max-w-3xl">
      <PageHeader
        title="Welcome to CivicRecords AI"
        description="Let's set up your city profile. This takes about 15-20 minutes."
      />

      {/* Progress steps */}
      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const isActive = step === s.phase;
          const isDone = step > s.phase;
          return (
            <div key={s.phase} className="flex items-center gap-2">
              {i > 0 && <div className={cn("w-8 h-px", isDone ? "bg-primary" : "bg-border")} />}
              <div
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-full text-sm",
                  isActive ? "bg-primary text-primary-foreground" :
                  isDone ? "bg-primary/10 text-primary" :
                  "bg-muted text-muted-foreground"
                )}
              >
                {isDone ? <CheckCircle className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                {s.label}
              </div>
            </div>
          );
        })}
      </div>

      {/* Phase 1: City Profile */}
      {step === 1 && (
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Tell us about your city</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">City Name *</label>
                <Input
                  value={profile.cityName}
                  onChange={(e) => updateProfile({ cityName: e.target.value })}
                  placeholder="e.g. City of Lakewood"
                />
              </div>
              <div>
                <label className="text-sm font-medium">State *</label>
                <Select value={profile.state} onValueChange={(v) => updateProfile({ state: v ?? "CO" })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {STATES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">County</label>
                <Input
                  value={profile.county}
                  onChange={(e) => updateProfile({ county: e.target.value })}
                  placeholder="e.g. Jefferson County"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Population *</label>
                <Select value={profile.populationBand} onValueChange={(v) => updateProfile({ populationBand: v ?? "" })}>
                  <SelectTrigger><SelectValue placeholder="Select range" /></SelectTrigger>
                  <SelectContent>
                    {POPULATION_BANDS.map((b) => <SelectItem key={b} value={b}>{b}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Separator />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Email Platform *</label>
                <Select value={profile.emailPlatform} onValueChange={(v) => updateProfile({ emailPlatform: v ?? "" })}>
                  <SelectTrigger><SelectValue placeholder="Select platform" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="microsoft365">Microsoft 365</SelectItem>
                    <SelectItem value="google">Google Workspace</SelectItem>
                    <SelectItem value="exchange">On-premise Exchange</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">Dedicated IT Department?</label>
                <Select value={profile.hasDedicatedIT} onValueChange={(v) => updateProfile({ hasDedicatedIT: v ?? "" })}>
                  <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="yes">Yes — dedicated IT staff</SelectItem>
                    <SelectItem value="no">No — IT is a shared role</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">Monthly Records Requests</label>
                <Select value={profile.monthlyRequestVolume} onValueChange={(v) => updateProfile({ monthlyRequestVolume: v ?? "" })}>
                  <SelectTrigger><SelectValue placeholder="Approximate volume" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1-5">1-5 per month</SelectItem>
                    <SelectItem value="5-20">5-20 per month</SelectItem>
                    <SelectItem value="20-50">20-50 per month</SelectItem>
                    <SelectItem value="50+">50+ per month</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Phase 2: System Identification */}
      {step === 2 && (
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>What systems does your city use?</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              For each department, tell us the software system name. Skip any you don't know — you can add them later.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {DOMAINS.map((domain) => {
              const existing = profile.systems[domain.key];
              return (
                <div key={domain.key} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                  <div>
                    <p className="text-sm font-medium">{domain.label}</p>
                    <p className="text-xs text-muted-foreground">{domain.hint}</p>
                  </div>
                  <Input
                    value={existing?.vendor || ""}
                    onChange={(e) => updateSystem(domain.key, e.target.value, existing?.notes || "")}
                    placeholder="System name or vendor"
                  />
                  <Input
                    value={existing?.notes || ""}
                    onChange={(e) => updateSystem(domain.key, existing?.vendor || "", e.target.value)}
                    placeholder="Notes (cloud/on-prem, version, etc.)"
                  />
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Phase 3: Gap Map */}
      {step === 3 && (
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Gap Map</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              These are functional areas where your city should have data but you haven't identified a system yet.
              This is normal — you can connect sources later from the Sources page.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {domainsWithoutSystems.length === 0 ? (
              <div className="flex items-center gap-2 text-success py-4">
                <CheckCircle className="h-5 w-5" />
                <p className="font-medium">All domains have an identified system. Great coverage!</p>
              </div>
            ) : (
              domainsWithoutSystems.map((domain) => (
                <div key={domain.key} className="flex items-center justify-between py-3 border-b last:border-0">
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="h-4 w-4 text-warning" />
                    <div>
                      <p className="text-sm font-medium">{domain.label}</p>
                      <p className="text-xs text-muted-foreground">No system identified</p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => { setStep(2); }}
                  >
                    Identify System
                  </Button>
                </div>
              ))
            )}

            {/* Show identified systems */}
            {Object.entries(profile.systems).filter(([, v]) => v.vendor).length > 0 && (
              <>
                <Separator className="my-4" />
                <p className="text-label uppercase text-muted-foreground">Identified Systems</p>
                {Object.entries(profile.systems)
                  .filter(([, v]) => v.vendor)
                  .map(([key, val]) => {
                    const domain = DOMAINS.find((d) => d.key === key);
                    return (
                      <div key={key} className="flex items-center gap-3 py-2">
                        <CheckCircle className="h-4 w-4 text-success" />
                        <span className="text-sm font-medium">{domain?.label}</span>
                        <Badge variant="outline" className="text-xs">{val.vendor}</Badge>
                      </div>
                    );
                  })}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Navigation */}
      {submitError && (
        <p className="text-sm text-destructive text-right">{submitError}</p>
      )}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={() => setStep(step - 1)}
          disabled={step === 1 || submitting}
        >
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
        <Button onClick={saveAndContinue} disabled={submitting}>
          {step === 3 ? (submitting ? "Saving…" : "Complete Setup") : "Continue"}
          {step < 3 && <ChevronRight className="h-4 w-4 ml-1" />}
        </Button>
      </div>
    </div>
  );
}
