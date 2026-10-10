"use client";

import * as React from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import * as PopoverPrimitive from "@radix-ui/react-popover";

import { Input } from "@/components/ui/input";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const Popover = PopoverPrimitive.Root;
const PopoverTrigger = PopoverPrimitive.Trigger;

const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(({ className, align = "start", ...props }, ref) => (
  <PopoverPrimitive.Portal>
    <PopoverPrimitive.Content
      ref={ref}
      align={align}
      sideOffset={6}
      className={cn(
        "z-50 min-w-[var(--radix-popover-trigger-width)] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md outline-none",
        className,
      )}
      {...props}
    />
  </PopoverPrimitive.Portal>
));
PopoverContent.displayName = "PopoverContent";

interface ModelComboboxProps {
  value: string;
  options: string[];
  onSelect: (value: string) => void;
  placeholder?: string;
}

export function ModelCombobox({
  value,
  options,
  onSelect,
  placeholder,
}: ModelComboboxProps) {
  const { t } = useI18n();
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.toLowerCase().includes(q));
  }, [options, query]);

  const commit = (v: string) => {
    const trimmed = v.trim();
    if (trimmed) onSelect(trimmed);
    setOpen(false);
    setQuery("");
  };

  const hasQuery = query.trim().length > 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger className="inline-flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm font-normal transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50">
        <span className={cn("truncate", !value && "text-muted-foreground")}>
          {value || placeholder || t("model.placeholder")}
        </span>
        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
      </PopoverTrigger>
      <PopoverContent>
        <div className="p-1">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("model.search")}
            className="h-8"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commit(query);
              }
            }}
          />
        </div>
        <div className="max-h-56 overflow-y-auto">
          {filtered.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => commit(m)}
              className="flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-sm transition-colors hover:bg-accent"
            >
              <span className="truncate">{m}</span>
              {m === value ? <Check className="h-4 w-4 shrink-0" /> : null}
            </button>
          ))}
          {!filtered.length && hasQuery ? (
            <button
              type="button"
              onClick={() => commit(query)}
              className="flex w-full items-center rounded-sm px-2 py-1.5 text-left text-sm text-primary transition-colors hover:bg-accent"
            >
              {t("model.use", { name: query.trim() })}
            </button>
          ) : null}
          {!filtered.length && !hasQuery ? (
            <div className="px-2 py-6 text-center text-xs text-muted-foreground">
              {t("model.empty")}
            </div>
          ) : null}
        </div>
      </PopoverContent>
    </Popover>
  );
}