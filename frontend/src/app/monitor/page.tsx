"use client";

import { Suspense } from "react";

import { useI18n } from "@/lib/i18n";
import MonitorInner from "./monitor-inner";

export default function MonitorPage() {
  const { t } = useI18n();
  return (
    <Suspense
      fallback={<div className="p-8 text-center text-muted-foreground">{t("common.loading")}</div>}
    >
      <MonitorInner />
    </Suspense>
  );
}
