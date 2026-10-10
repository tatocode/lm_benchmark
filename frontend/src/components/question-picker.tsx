"use client";

import * as React from "react";
import { Check, ListChecks, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface QuestionPickerProps {
  library: string[];
  value: string[];
  onChange: (questions: string[]) => void;
  className?: string;
}

function splitValue(value: string[], library: string[]) {
  const libSet = new Set(library);
  const selected: string[] = [];
  const custom: string[] = [];
  for (const q of value) {
    if (libSet.has(q) && !selected.includes(q)) selected.push(q);
    else if (!libSet.has(q)) custom.push(q);
  }
  return { selected, custom };
}

export function QuestionPicker({ library, value, onChange, className }: QuestionPickerProps) {
  const { t } = useI18n();
  const [selected, setSelected] = React.useState<string[]>(
    () => splitValue(value, library).selected,
  );
  const [custom, setCustom] = React.useState<string>(
    () => splitValue(value, library).custom.join("\n"),
  );

  // 只在本组件之外改动 value（默认题库异步载入、切换场景、恢复默认）时同步，
  // 避免覆盖用户正在输入的内容。
  const emitted = React.useRef<string[]>(value);
  React.useEffect(() => {
    if (emitted.current === value) return;
    const parsed = splitValue(value, library);
    setSelected(parsed.selected);
    setCustom(parsed.custom.join("\n"));
    emitted.current = value;
  }, [value, library]);

  const emit = (nextSelected: string[], nextCustom: string) => {
    const customArr = nextCustom
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    // 明确表达选择结果：空数组就代表“没有选择任何问题”（由上层校验拦截），
    // 不再把空数组偷偷当成“使用全部题库”。
    const next = [...nextSelected, ...customArr];
    emitted.current = next;
    onChange(next);
  };

  const toggle = (q: string) => {
    const next = selected.includes(q)
      ? selected.filter((x) => x !== q)
      : [...selected, q];
    setSelected(next);
    emit(next, custom);
  };

  const toggleAll = () => {
    const next = selected.length === library.length ? [] : library;
    setSelected(next);
    emit(next, custom);
  };

  const onCustomChange = (text: string) => {
    setCustom(text);
    emit(selected, text);
  };

  const customArr = custom.split("\n").map((s) => s.trim()).filter(Boolean);
  const total = selected.length + customArr.length;
  const invalid = total === 0;

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-sm font-medium">
          <ListChecks className="h-4 w-4 text-muted-foreground" />
          {t("picker.title")}
          <Badge
            variant={invalid ? "destructive" : "default"}
            className="font-normal"
          >
            {invalid ? t("picker.none") : t("picker.selected", { n: total })}
          </Badge>
        </div>
        <button
          type="button"
          onClick={toggleAll}
          className="cursor-pointer text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          {selected.length === library.length ? t("picker.unselect") : t("picker.all")}
        </button>
      </div>

      <div className="max-h-52 divide-y overflow-y-auto rounded-lg border">
        {library.map((q, i) => {
          const on = selected.includes(q);
          return (
            <button
              key={`${i}-${q.slice(0, 8)}`}
              type="button"
              onClick={() => toggle(q)}
              className="flex w-full cursor-pointer items-start gap-2.5 px-3 py-2 text-left transition-colors hover:bg-accent/60"
            >
              <span
                className={cn(
                  "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                  on ? "border-primary bg-primary text-primary-foreground" : "border-input",
                )}
              >
                {on ? <Check className="h-3 w-3" /> : null}
              </span>
              <span className="text-xs leading-relaxed">
                <span className="mr-1.5 tabular-nums text-muted-foreground">{i + 1}.</span>
                {q}
              </span>
            </button>
          );
        })}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Plus className="h-3.5 w-3.5" />
          {t("picker.custom")}
          <span className="font-normal">{t("picker.customHint")}</span>
        </div>
        <Textarea
          value={custom}
          onChange={(e) => onCustomChange(e.target.value)}
          placeholder={t("picker.placeholder")}
          rows={3}
          className="min-h-[64px] text-xs"
        />
      </div>

      <p className={cn("text-xs", invalid ? "text-destructive" : "text-muted-foreground")}>
        {invalid
          ? t("picker.invalid")
          : t("picker.valid", { total, bank: selected.length, custom: customArr.length })}
      </p>
    </div>
  );
}
