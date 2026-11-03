import { useEffect, useState } from "react";

/** Seconds under a minute, minutes under an hour, then hours. */
export function fmt(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${s % 60} s`;
  return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
}

/** Short steps need a decimal: 0.4 s is a real duration, "0 s" is not. */
export const took = (ms: number) => (ms < 100 ? "<0.1 s" : ms < 10000 ? `${(ms / 1000).toFixed(1)} s` : fmt(ms));

/** An estimate, plainly an estimate. */
export const about = (ms: number) => (ms < 1000 ? "<1 s" : `~${fmt(ms)}`);

/** Ticks while anything runs, so a long step visibly counts up. */
export function useNow(on: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!on) return;
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, [on]);
  return now;
}
