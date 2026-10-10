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

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "-";
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}秒前`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}小时前`;
  return new Date(iso).toLocaleString();
}