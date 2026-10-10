import { cn } from "@/lib/utils";

/**
 * Brand mark: ascending throughput bars with a latency sweep line.
 * Vector only, inherits currentColor for theming.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      role="img"
      aria-label="LLM Bench"
      className={cn("h-4 w-4", className)}
      fill="none"
    >
      <rect x="4" y="13" width="3.2" height="7" rx="1.1" fill="currentColor" />
      <rect x="10.4" y="9" width="3.2" height="11" rx="1.1" fill="currentColor" opacity="0.85" />
      <rect x="16.8" y="5" width="3.2" height="15" rx="1.1" fill="currentColor" opacity="0.7" />
      <path
        d="M4 8.5c3.2 0 4.6-4 8-4s4.4 4 8 4"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.95"
      />
    </svg>
  );
}
