const TZ = "Asia/Kolkata";

export function ago(ts: string): string {
  const h = (Date.now() - new Date(ts).getTime()) / 36e5;
  if (h < 0) return "just now";
  if (h < 1) return `${Math.max(1, Math.round(h * 60))}m ago`;
  if (h < 48) return `${Math.round(h)}h ago`;
  return new Date(ts).toLocaleDateString("en-IN", { timeZone: TZ, day: "numeric", month: "short" });
}
export function full(ts: string): string {
  return new Date(ts).toLocaleString("en-IN", { timeZone: TZ, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }) + " IST";
}
export function day(d: string): string {
  return new Date(d + "T00:00:00+05:30").toLocaleDateString("en-IN", { timeZone: TZ, weekday: "short", day: "numeric", month: "short" });
}
export const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;
export const price = (v: number) => v.toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
export const sign = (v: number | null | undefined) => (v == null || v === 0 ? "text-mute" : v > 0 ? "text-up" : "text-down");
export const confPct = (c: number) => `${Math.round(c * 100)}%`;
export const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "0");
