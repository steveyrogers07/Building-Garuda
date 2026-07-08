/** Numbers in Indian grouping — every data cell goes through here. */
export function fmt(n?: number | null): string {
  return n == null ? "–" : Number(n).toLocaleString("en-IN")
}

/** First 10 chars of an ISO timestamp (the date part). */
export function d10(s?: string | null): string {
  return String(s ?? "").slice(0, 10)
}

export function istNow(): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date())
}

export function pct(x?: number | null, digits = 0): string {
  return x == null ? "–" : (x * 100).toFixed(digits) + "%"
}
