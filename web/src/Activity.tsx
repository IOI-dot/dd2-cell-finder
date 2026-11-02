import { Spinner } from "@/components/ui/spinner";
import { useEffect, useRef, useState } from "react";
import type { Item, Kind } from "./useAgent";

const TAGS: Record<Kind, string> = { you: "You", step: "Step", model: "Model", thought: "Thinking", tool: "Tool", check: "Check", guard: "Guardrail", verdict: "Verdict", error: "Error" };
const LINE: Record<Kind, string> = { you: "border-primary", step: "border-border", model: "border-info", thought: "border-info/40", tool: "border-primary/70", check: "border-border", guard: "border-warning", verdict: "border-success", error: "border-destructive" };

function seconds(ms: number) { return `${(ms / 1000).toFixed(1)} s`; }

/** Ticks while anything runs, so a long step visibly counts up instead of looking stuck. */
export function useNow(on: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!on) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [on]);
  return now;
}

function Row({ item, now }: { item: Item; now: number }) {
  const live = item.state === "running";
  const took = (item.ended ?? now) - item.started;
  return (
    <li data-kind={item.kind} data-state={item.state} className={`border-l-2 pl-3 ${LINE[item.kind]} ${item.kind === "check" ? "ml-3" : ""}`}>
      <div className="flex items-baseline gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
        {live && <Spinner className="size-3 self-center" />}
        <span>{TAGS[item.kind]}</span>
        {item.kind !== "you" && item.kind !== "thought" && took > 200 && <span className="ml-auto font-mono normal-case">{seconds(took)}</span>}
      </div>
      <div className={`text-[13px] ${item.state === "bad" ? "text-destructive" : item.kind === "you" ? "font-medium" : item.kind === "thought" ? "italic text-muted-foreground" : ""}`}>
        {item.state === "ok" && !["you", "thought", "step", "model"].includes(item.kind) ? "✓ " : item.state === "bad" ? "✕ " : ""}{item.title}
      </div>
      {item.detail && <div className="break-words font-mono text-[11px] text-muted-foreground">{item.detail}</div>}
    </li>
  );
}

export function Activity({ items, running, started }: { items: Item[]; running: boolean; started: number }) {
  const end = useRef<HTMLLIElement>(null);
  const now = useNow(running);
  useEffect(() => { end.current?.scrollIntoView({ block: "end", behavior: "smooth" }); }, [items.length]);
  return (
    <>
      <div className="flex items-baseline gap-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Activity</h2>
        {running && <span className="ml-auto font-mono text-[11px] text-info">working {seconds(now - started)}</span>}
      </div>
      <ol className="flex min-h-0 flex-1 flex-col gap-2 overflow-auto pr-1" aria-live="polite">
        {items.map((it) => <Row key={it.id} item={it} now={now} />)}
        {!items.length && <li className="text-[13px] text-muted-foreground">Nothing has run in this session yet.</li>}
        <li ref={end} aria-hidden />
      </ol>
    </>
  );
}

/** While no page exists, the middle of the screen says what is happening right now. */
export function NowPanel({ items, started, running }: { items: Item[]; started: number; running: boolean }) {
  const now = useNow(running);
  const live = [...items].reverse().find((x) => x.state === "running" && x.kind === "check") ?? [...items].reverse().find((x) => x.state === "running");
  const passed = items.filter((x) => x.kind === "check" && x.state === "ok").length;
  return (
    <div className="mx-auto flex h-full max-w-lg flex-col items-center justify-center gap-3 text-center">
      <Spinner className="size-6 text-info" />
      <h1 data-testid="now" className="text-xl font-semibold">{live?.title ?? "Starting"}</h1>
      <p className="break-words font-mono text-xs text-muted-foreground">{live?.detail}</p>
      <p className="text-sm text-muted-foreground">{passed} steps done · {seconds(now - started)}</p>
    </div>
  );
}
