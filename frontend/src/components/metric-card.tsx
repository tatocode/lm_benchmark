"use client";

import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "success" | "warning" | "danger";
  icon?: ReactNode;
  primary?: boolean;
}

export default function MetricCard({
  label,
  value,
  hint,
  tone = "default",
  icon,
  primary,
}: MetricCardProps) {
  const tones = {
    default: "text-foreground",
    success: "text-success",
    warning: "text-warning",
    danger: "text-destructive",
  };
  return (
    <Card
      className={cn(
        "flex flex-col gap-1 px-4 py-3",
        primary && "border-primary/30 bg-primary/5",
      )}
    >
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{label}</span>
        {icon}
      </div>
      <div
        className={cn(
          "num text-2xl font-semibold tracking-tight",
          tones[tone],
        )}
      >
        {value}
      </div>
      {hint ? <div className="text-xs text-muted-foreground">{hint}</div> : null}
    </Card>
  );
}
