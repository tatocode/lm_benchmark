"use client";

import * as React from "react";
import { HelpCircle } from "lucide-react";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function InfoTip({
  children,
  className,
  side = "bottom",
}: {
  children: React.ReactNode;
  className?: string;
  side?: "top" | "bottom";
}) {
  const { t } = useI18n();
  return (
    <span
      tabIndex={0}
      className={cn(
        "group/tip relative inline-flex cursor-help items-center align-middle outline-none",
        className,
      )}
      aria-label={t("common.tip.aria")}
    >
      <HelpCircle className="h-3.5 w-3.5 text-muted-foreground/60 transition-colors group-hover/tip:text-foreground group-focus/tip:text-foreground" />
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none invisible absolute z-50 w-60 rounded-md border bg-popover p-2.5 text-xs font-normal leading-relaxed text-popover-foreground opacity-0 shadow-md transition group-hover/tip:visible group-hover/tip:opacity-100 group-focus/tip:visible group-focus/tip:opacity-100",
          side === "bottom"
            ? "left-1/2 top-full mt-1.5 -translate-x-1/2"
            : "bottom-full left-1/2 mb-1.5 -translate-x-1/2",
        )}
      >
        {children}
      </span>
    </span>
  );
}
