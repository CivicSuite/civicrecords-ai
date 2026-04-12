import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Radar,
  CheckCircle,
  HelpCircle,
  AlertTriangle,
  Sparkles,
  Lock,
} from "lucide-react";

export default function Discovery({ token: _token }: { token: string }) {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Discovery Dashboard"
        description="Network discovery and automatic source identification"
        actions={
          <Button disabled>
            <Radar className="h-4 w-4 mr-2" />
            Run Discovery Scan
          </Button>
        }
      />

      {/* Coming soon notice */}
      <Card className="shadow-none border-primary/20 bg-primary/5">
        <CardContent className="p-4 flex items-start gap-3">
          <Lock className="h-5 w-5 text-primary mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground">
              Network Discovery — Coming in v1.1
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              The discovery engine will scan your city's network (with IT authorization) to automatically
              find and identify data sources. It cross-references findings against the Municipal Systems
              Catalog and presents them for your review — nothing connects without your approval.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Preview of what the dashboard will look like */}
      <div className="opacity-60 pointer-events-none">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard label="High Confidence" value={0} icon={CheckCircle} />
          <StatCard label="Needs Review" value={0} icon={HelpCircle} />
          <StatCard label="Unknown" value={0} icon={AlertTriangle} />
          <StatCard label="New Since Last Scan" value={0} icon={Sparkles} />
        </div>
      </div>

      <EmptyState
        icon={Radar}
        title="No discovery scans yet"
        description="When network discovery is enabled in v1.1, this page will show discovered data sources with confidence scores, one-click confirmation, and coverage gap alerts."
      />

      {/* What it will do */}
      <Card className="shadow-none">
        <CardContent className="p-6">
          <h3 className="text-lg font-semibold mb-3">What Discovery Will Do</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-medium">
                <Radar className="h-4 w-4 text-primary" />
                Network Scanning
              </div>
              <p className="text-muted-foreground">
                Scan for database servers, file shares, email servers, and web applications on your city network.
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-medium">
                <CheckCircle className="h-4 w-4 text-primary" />
                Auto-Identification
              </div>
              <p className="text-muted-foreground">
                Cross-reference discovered services against the Municipal Systems Catalog to identify vendors and data types.
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-medium">
                <AlertTriangle className="h-4 w-4 text-primary" />
                Coverage Gaps
              </div>
              <p className="text-muted-foreground">
                Compare connected sources against request patterns to find data that people ask for but isn't indexed.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
