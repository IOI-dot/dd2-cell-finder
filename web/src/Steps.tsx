import { Spinner } from "./ui";
import { STAGES, stageOf, type Estimates } from "./stages";
import { about, took, useNow } from "./time";
import type { Step } from "./useAgent";

export type Scoped = { revision: string; picked: string | null };

/** Which steps belong to a stage in a revision. Stages outside a build belong to the run. */
export const inStage = (steps: Step[], id: string, revision: string) =>
  steps.filter((x) => stageOf(x.stage) === id && x.kind !== "thought" && (!x.revision || !revision || x.revision === revision));

export const stateOf = (mine: Step[]) => (mine.some((x) => x.state === "running") ? "running" : !mine.length ? "waiting" : mine.some((x) => x.state === "bad") ? "bad" : "ok");

export function Mark({ state }: { state: string }) {
  if (state === "running") return <Spinner className="size-4 text-info" />;
  if (state === "waiting") return <i aria-hidden className="size-1.5 rounded-full bg-muted-foreground/40" />;
  return <span aria-hidden className={`text-xs font-semibold ${state === "ok" ? "text-success" : "text-destructive"}`}>{state === "ok" ? "✓" : "✕"}</span>;
}

export const span = (mine: Step[], now: number) => Math.max(...mine.map((x) => x.ended ?? now)) - Math.min(...mine.map((x) => x.started));

/** The pipeline. Pressing a step opens everything about it in the middle. */
/** The group a run's estimates come from, known once its network is. */
export const estimateFor = (estimates: Estimates, steps: Step[]) => estimates[(steps.find((x) => x.data?.stages)?.data.stages ?? 1) > 1 ? "multi" : "single"] ?? {};

export function Steps({ steps, running, picked, onPick, revision, revisions, best, onRevision, estimates }: {
  steps: Step[]; running: boolean; picked: string | null; onPick: (id: string | null) => void; revision: string; revisions: string[]; best: string; onRevision: (r: string) => void; estimates: Estimates }) {
  const now = useNow(running);
  const guess = estimateFor(estimates, steps);
  const row = "flex min-h-11 w-full items-center gap-2.5 rounded-md px-2 py-1 text-left text-sm lg:min-h-8";
  return (
    <nav aria-label="Pipeline" className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto pr-1">
      <button aria-current={picked === null} onClick={() => onPick(null)} className={`${row} ${picked === null ? "bg-sidebar-accent font-medium text-foreground" : "text-muted-foreground hover:bg-sidebar-accent/50"}`}>
        <span aria-hidden className="grid size-5 flex-none place-items-center text-xs">≡</span>Run overview
      </button>
      {revisions.length > 1 && (
        <section className="flex flex-col gap-1 px-2">
          <h3 className="text-xs font-medium text-muted-foreground">Builds</h3>
          <div role="group" aria-label="Build" className="flex flex-wrap gap-1">
            {revisions.map((r) => (
              <button key={r} aria-pressed={r === revision} onClick={() => onRevision(r)}
                className={`min-h-7 rounded-md border px-2 font-mono text-xs ${r === revision ? "border-primary text-foreground" : "text-muted-foreground"}`}>{r}{r === best ? " best" : ""}</button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">Each build runs the whole flow with different settings.</p>
        </section>
      )}
      {[...new Set(STAGES.map((s) => s.group))].map((g) => (
        <section key={g} className="flex flex-col gap-0.5">
          <h3 className="px-2 pb-0.5 text-xs font-medium text-muted-foreground">{g}</h3>
          <ol className="flex flex-col gap-0.5">
            {STAGES.filter((s) => s.group === g).map((s) => {
              const mine = inStage(steps, s.id, revision);
              const state = stateOf(mine);
              const on = picked === s.id;
              return (
                <li key={s.id} data-state={state}>
                  <button aria-current={on} disabled={state === "waiting"} onClick={() => onPick(s.id)}
                    className={`${row} ${on ? "bg-sidebar-accent font-medium text-foreground" : state === "waiting" ? "text-muted-foreground/70" : "text-foreground hover:bg-sidebar-accent/50"}`}>
                    <span className="grid size-5 flex-none place-items-center"><Mark state={state} /></span>
                    <span className="min-w-0 flex-1 leading-tight">{s.name}<span className="sr-only"> {state}</span></span>
                    <span title={guess[s.id] ? `Median of ${guess[s.id].runs} past runs` : undefined} className="flex-none font-mono text-xs text-muted-foreground">
                      {mine.length > 0 && took(span(mine, now))}{state === "running" && guess[s.id] && " / "}{(state === "waiting" || state === "running") && guess[s.id] && about(guess[s.id].seconds * 1000)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </nav>
  );
}
