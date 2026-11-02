import { useEffect, useState } from "react";
import { api, type Scoring, type Status } from "../api";
import { Badge, detail } from "./Badge";
import { ago, day } from "../format";

const MEANING: [string, string][] = [
  ["EOD", "The official end-of-day close for the last completed session. Not intraday, not live."],
  ["Delayed", "Filings fetched from NSE within the last 6 hours. NSE publishes in near real time; FINN catches up only when ingest runs."],
  ["Cached", "A saved snapshot that is out of date: filings fetched more than 6 hours ago, or prices missing recent sessions."],
  ["Live", "A real-time stream. FINN has none yet, so you will not see this label."],
  ["Mock", "Synthetic data for testing. Never real prices or filings."],
  ["Unavailable", "The source could not be reached. Nothing is guessed."],
];

export function StatusSheet({ status, onClose }: { status: Status; onClose: () => void }) {
  const [rules, setRules] = useState<Scoring | null>(null);
  useEffect(() => { api.scoring().then(setRules).catch(() => {}); }, []);
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  const rows = [{ name: "Prices", f: status.prices }, { name: "Filings", f: status.announcements }];
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 md:items-center md:p-6" onClick={onClose}>
      <div role="dialog" aria-label="Data sources and ranking" onClick={(e) => e.stopPropagation()}
        className="max-h-[88vh] w-full max-w-[640px] overflow-y-auto rounded-t-xl md:rounded-lg bg-raised px-4 pb-[calc(1.25rem+env(safe-area-inset-bottom))] pt-4 md:px-6">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[17px] font-semibold">Where this data comes from</h2>
          <button onClick={onClose} className="text-sm text-mute underline underline-offset-2">Close</button>
        </div>
        <div className="mt-3 divide-y divide-rule border-y border-rule">
          {rows.map(({ name, f }) => (
            <div key={name} className="py-3">
              <div className="flex items-center justify-between">
                <span className="font-medium">{name}</span><Badge status={f.status} detail={detail(f)} />
              </div>
              <p className="mt-1 text-[13px] text-mute">
                {f.as_of && f.feed === "prices" ? `Close for ${day(f.as_of)}. ` : ""}
                {f.fetched_at ? `Fetched ${ago(f.fetched_at)}. ` : ""}{f.note}
              </p>
            </div>
          ))}
        </div>
        <dl className="mt-3 space-y-1.5 text-[13px]">
          {MEANING.map(([k, v]) => (
            <div key={k} className="flex gap-2"><dt className="w-[78px] shrink-0 font-semibold">{k}</dt><dd className="text-mute">{v}</dd></div>
          ))}
        </dl>

        <h2 className="mt-6 text-[17px] font-semibold">How filings are ranked</h2>
        <p className="mt-1 text-[13px] text-mute">
          Each filing's score is the sum of itemised parts: what the filing is, how much of your portfolio it touches
          (up to +8), and how the stock reacted (up to +16). Open any filing to see its own sum. No AI model sets the rank.
        </p>
        {rules && (<>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-mute">
            {rules.gates.map((g) => <li key={g}>{g}</li>)}
          </ul>
          <p className="mt-3 text-[13px] font-semibold">Starting score by type</p>
          <ul className="mt-1 grid grid-cols-1 sm:grid-cols-2 gap-x-6 text-[13px]">
            {rules.examples.map((e) => (
              <li key={e.label} className="flex justify-between border-b border-rule/60 py-1"><span>{e.label}</span><span className="font-medium">{e.base}</span></li>
            ))}
          </ul>
          <p className="mt-2 text-[12.5px] text-faint">{rules.market_note} Unusual means a move beyond ±{status.thresholds.price_move_pct}% or volume above {status.thresholds.volume_mult}× its 20-day average.</p>
        </>)}
      </div>
    </div>
  );
}
