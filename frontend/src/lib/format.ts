export function fmtMs(v?: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  if (v < 1000) return `${v.toFixed(1)} ms`;
  return `${(v / 1000).toFixed(2)} s`;
}

export function fmtTps(v?: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  if (v >= 1000) return `${(v / 1000).toFixed(2)} k`;
  return v.toFixed(1);
}

export function fmtNum(v?: number | null, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  return v.toFixed(digits);
}

export function fmtPct(v?: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  return `${(v * 100).toFixed(2)}%`;
}

export function fmtElapsed(s?: number | null): string {
  if (s === null || s === undefined || Number.isNaN(s)) return "-";
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m${Math.round(s % 60)}s`;
}

export function timeAgo(
  iso: string | null | undefined,
  lang: string = "en",
): string {
  if (!iso) return "-";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "-";
  const diff = t - Date.now();
  const abs = Math.abs(diff);
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31536000000],
    ["month", 2592000000],
    ["day", 86400000],
    ["hour", 3600000],
    ["minute", 60000],
    ["second", 1000],
  ];
  for (const [unit, ms] of units) {
    if (abs >= ms || unit === "second") {
      return rtf.format(Math.round(diff / ms), unit);
    }
  }
  return "-";
}
