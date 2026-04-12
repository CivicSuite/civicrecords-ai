import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  variant?: "default" | "success" | "warning" | "danger";
  className?: string;
}

const VARIANT_STYLES = {
  default: "text-foreground",
  success: "text-success",
  warning: "text-warning",
  danger: "text-destructive",
};

export function StatCard({ label, value, icon: Icon, variant = "default", className }: StatCardProps) {
  return (
    <Card className={cn("shadow-none", className)}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-label uppercase text-muted-foreground">{label}</p>
            <p className={cn("text-page-title mt-1", VARIANT_STYLES[variant])}>
              {value}
            </p>
          </div>
          {Icon && (
            <div className="rounded-lg bg-muted p-3">
              <Icon className="h-5 w-5 text-muted-foreground" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
