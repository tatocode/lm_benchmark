"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, History } from "lucide-react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import type { TKey } from "@/lib/i18n";

const NAV_ITEMS: { href: string; labelKey: TKey; icon: typeof Activity }[] = [
  { href: "/", labelKey: "common.nav.new", icon: Activity },
  { href: "/history", labelKey: "common.nav.history", icon: History },
];

export function SiteNav() {
  const pathname = usePathname();
  const { t } = useI18n();
  return (
    <nav
      className="flex items-center gap-0.5 rounded-lg bg-muted p-0.5 text-sm"
      aria-label={t("common.nav.aria")}
    >
      {NAV_ITEMS.map((item) => {
        const active =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {t(item.labelKey)}
          </Link>
        );
      })}
    </nav>
  );
}
