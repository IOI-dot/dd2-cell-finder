import { Badge } from "./ui";
import { Button } from "./ui";
import { useEffect, useMemo, useRef, useState } from "react";
import { stage, stageOf } from "./stages";
import { LogView, StepBody } from "./stepviews";
import { pretty } from "./text";
import { Mark, inStage, span, stateOf } from "./Steps";
import { took, useNow } from "./time";
import type { Revision, Step } from "./useAgent";

type Section = { key: string; id: string; revision: string; items: Step[] };

/** The run in the order it happened: one section per stage, per revision, and one per model decision. */
function sections(steps: Step[]): Section[] {
  const out = new Map<string, Section>();
  let decision = "";
  for (const s of steps) {
    if (s.kind === "thought") continue;
    const id = s.kind === "tool" ? "build" : stageOf(s.stage);
    if (!id) continue;
    if (id === "model" && s.kind === "model") decision = s.id;
    const key = id === "model" ? `model:${decision || s.id}` : `${s.revision ?? ""}:${id}`;
    if (!out.has(key)) out.set(key, { key, id, revision: s.revision ?? "", items: [] });
    out.get(key)!.items.push(s);
  }
  return [...out.values()];
}

/** The gate order a revision's layout really used. */
const chosenOrder = (steps: Step[], revision: string) => steps.find((x) => x.revision === revision && x.data?.gate_order)?.data.gate_order.join(" ");

export const cellHandle = (revisions: Revision[] | undefined, id: string) => {
  const m = revisions?.find((r) => r.id === id)?.report?.match(/runs\/([^/]+)\/cells\/([^/]+)\//);
  return m ? `cell:${m[1]}/${m[2]}` : undefined;
};

function Build({ s }: { s: Section }) {
  const first = s.items[0];
  const args = first.data?.args as Record<string, unknown> | undefined;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-muted/50 px-3 py-2 text-sm">
      <span className="grid size-5 place-items-center"><Mark state={first.state} /></span>
      <strong className="font-medium">Build <span className="font-mono">{s.revision}</span></strong>
      {args && <span className="font-mono text-xs text-muted-foreground">sizing {String(args.sizing ?? "hd")}, order index {String(args.order_index ?? "any")}{args.no_met1 ? ", no met1" : ""}</span>}
      {first.state !== "running" && <span className="ml-auto font-mono text-xs text-muted-foreground">{pretty(first.detail)}</span>}
    </div>
  );
}

function Overview({ steps, revisions, onPick, now, running }: { steps: Step[]; revisions?: Revision[]; onPick: (id: string, revision: string) => void; now: number; running: boolean }) {
  const list = useMemo(() => sections(steps), [steps]);
  const latest = list.findLast((s) => s.revision)?.revision;       // earlier revisions fold, and stay one click away
  const box = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  const active = list.findLast((s) => s.id !== "build" && stateOf(s.items) === "running")?.key;
  /* The page goes to the step that is working now, and stays out of the way once you scroll yourself. */
  useEffect(() => {
    const b = box.current, at = b?.querySelector<HTMLElement>(`[data-key="${CSS.escape(active ?? "")}"]`);
    if (b && at && follow) b.scrollTo({ top: at.offsetTop - 12, behavior: "smooth" });
  }, [active, follow]);
  return (
    <div ref={box} onWheel={() => setFollow(false)} onTouchMove={() => setFollow(false)} className="relative flex min-h-0 flex-1 flex-col gap-2 overflow-auto p-3 lg:p-4" aria-live="polite">
      {running && (
        <div className="sticky top-0 z-10 flex h-0 justify-end">
          <Button size="sm" variant="outline" aria-pressed={follow} className={`bg-card ${follow ? "border-primary" : ""}`} onClick={() => setFollow(!follow)}>{follow ? "Following live" : "Follow live"}</Button>
        </div>
      )}
      {list.map((s) => {
        if (s.id === "build") return <Build key={s.key} s={s} />;
        const info = stage(s.id);
        const state = stateOf(s.items);
        return (
          <details key={s.key} data-key={s.key} open={!s.revision || s.revision === latest} data-state={state} className="rounded-md border bg-card">
            <summary className="flex cursor-pointer list-none flex-col gap-0.5 px-3 py-2 text-sm">
              <span className="flex items-center gap-2.5">
                <span className="grid size-5 flex-none place-items-center"><Mark state={state} /></span>
                <button className="text-left font-medium hover:underline" onClick={(e) => { e.preventDefault(); onPick(s.id, s.revision); }}>{info?.name}</button>
                <span className="font-mono text-xs text-muted-foreground">{info?.tool}</span>
                <span className="ml-auto flex-none font-mono text-xs text-muted-foreground">{took(span(s.items, now))}</span>
              </span>
              <span className="break-words pl-7 font-mono text-xs text-muted-foreground">{pretty([...s.items].reverse().find((x) => x.detail)?.detail ?? "")}</span>
            </summary>
            <div className="border-t p-3"><StepBody id={s.id} items={s.items} chosen={chosenOrder(steps, s.revision)} cell={cellHandle(revisions, s.revision)} full={false} /></div>
          </details>
        );
      })}
      {running && <div aria-hidden className="h-[80%] flex-none" />}
    </div>
  );
}

function Calls({ items, cell, now }: { items: Step[]; cell?: string; now: number }) {
  const [open, setOpen] = useState("");
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-sm font-medium">Calls</h3>
      <ol className="flex flex-col gap-1">
        {items.map((x) => (
          <li key={x.id} className="rounded-md border px-3 py-1.5">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="grid size-5 place-items-center"><Mark state={x.state} /></span>
              <span className="min-w-0 flex-1">{pretty(x.title)}</span>
              <span className="font-mono text-xs text-muted-foreground">{took((x.ended ?? now) - x.started)}</span>
              {x.data?.log && cell && <Button size="sm" variant="outline" className="min-h-11 lg:min-h-7" aria-expanded={open === x.id} onClick={() => setOpen(open === x.id ? "" : x.id)}>Log</Button>}
            </div>
            {x.data?.command && <code className="block break-all font-mono text-xs text-muted-foreground">{x.data.command}</code>}
            {!x.data?.command && x.detail && <p className="break-words font-mono text-xs text-muted-foreground">{pretty(x.detail)}</p>}
            {open === x.id && cell && <div className="pt-2"><LogView cell={cell} name={x.data.log} /></div>}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Detail({ id, steps, revision, revisions, onBack, now }: { id: string; steps: Step[]; revision: string; revisions?: Revision[]; onBack: () => void; now: number }) {
  const info = stage(id);
  const items = inStage(steps, id, revision);
  const cell = cellHandle(revisions, revision);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-3 lg:p-5">
      <header className="flex flex-col gap-1.5">
        <button onClick={onBack} className="min-h-11 self-start text-xs text-muted-foreground hover:text-foreground lg:min-h-0">← Run overview</button>
        <div className="flex flex-wrap items-center gap-2">
          <span className="grid size-5 place-items-center"><Mark state={stateOf(items)} /></span>
          <h2 className="text-lg font-semibold">{info?.name}</h2>
          <Badge variant="outline" className="font-mono text-xs">{info?.tool}</Badge>
          {revision && <Badge variant="outline" className="font-mono text-xs">{revision}</Badge>}
          {items.length > 0 && <span className="ml-auto font-mono text-xs text-muted-foreground">{took(span(items, now))}</span>}
        </div>
        <p className="max-w-[75ch] text-sm text-muted-foreground">{info?.about}</p>
      </header>
      <StepBody id={id} items={items} chosen={chosenOrder(steps, revision)} cell={cell} full />
      <Calls items={items} cell={cell} now={now} />
    </div>
  );
}

export function RunView({ steps, running, picked, revision, revisions, onPick, onRevision }: {
  steps: Step[]; running: boolean; picked: string | null; revision: string; revisions?: Revision[]; onPick: (id: string | null) => void; onRevision: (r: string) => void }) {
  const now = useNow(running);
  if (picked) return <Detail id={picked} steps={steps} revision={revision} revisions={revisions} onBack={() => onPick(null)} now={now} />;
  if (!steps.length) {
    return (
      <p className="m-auto p-6 text-center text-sm text-muted-foreground">Each step appears here as it runs, with its real output.</p>
    );
  }
  return <Overview key={steps[0].turn} steps={steps} revisions={revisions} now={now} running={running} onPick={(id, r) => { if (r) onRevision(r); onPick(id); }} />;
}
