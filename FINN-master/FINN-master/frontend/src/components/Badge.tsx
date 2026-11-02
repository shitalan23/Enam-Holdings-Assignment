import type { Feed, FeedStatus } from "../api";

const LABEL: Record<FeedStatus, string> = {
  LIVE: "Live", EOD: "EOD", DELAYED: "Delayed", CACHED: "Cached", MOCK: "Mock", UNAVAILABLE: "Unavailable",
};
// Each status looks different on purpose: EOD must never be mistaken for Live or Delayed.
const STYLE: Record<FeedStatus, string> = {
  LIVE: "bg-accent text-paper",
  EOD: "border border-ink/60 text-ink",
  DELAYED: "bg-accent-soft text-accent",
  CACHED: "border border-dashed border-faint text-mute",
  MOCK: "bg-warn-soft text-warn",
  UNAVAILABLE: "bg-down text-paper",
};
const shortDate = (d: string) =>
  new Date(d + "T00:00:00+05:30").toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short" });
const shortAge = (h: number) => (h < 1 ? "<1h" : h < 48 ? `${Math.round(h)}h` : `${Math.round(h / 24)}d`);

/** What the badge says after the status word: the date an EOD close is for, or how old a snapshot is. */
export function detail(f: Feed | undefined): string {
  if (!f) return "";
  if (f.status === "EOD" || (f.status === "CACHED" && f.feed === "prices")) return f.as_of ? shortDate(f.as_of) : "";
  if ((f.status === "DELAYED" || f.status === "CACHED") && f.age_hours != null) return shortAge(f.age_hours);
  return "";
}

export function Badge({ status, small = false, detail: d }: { status: FeedStatus; small?: boolean; detail?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-[3px] font-semibold leading-none ${small ? "px-1 py-[3px] text-[10.5px]" : "px-1.5 py-1 text-[11.5px]"} ${STYLE[status]}`}>
      {LABEL[status]}{d ? <span className="font-normal opacity-80">{d}</span> : null}
    </span>
  );
}
