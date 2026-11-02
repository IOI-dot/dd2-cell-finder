import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Renderer } from "@openuidev/react-lang";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Activity, NowPanel } from "./Activity";
import { Evidence } from "./Evidence";
import { library } from "./library";
import { SendContext, Status } from "./panels";
import { useAgent } from "./useAgent";

const STAGES: [string, string][] = [
  ["intent_parser", "Request"], ["invoke_allowed_tool", "Network, layout, DRC, LVS, RC-LVS, SPICE"], ["assess_retry", "Score revisions"],
  ["plan_one_bounded_action", "Model: one next step"], ["validate_action", "Guardrails"], ["finish", "Verdict from the checks"], ["explain_evidence", "Report page"],
];
const EXAMPLES = ["!((A & B) | C)", "(A & !C) | (B & C)", "A ^ B", "a 3-input majority gate"];

export function App() {
  const [tab, setTab] = useState("work");
  const [model, setModel] = useState("");
  const [text, setText] = useState("");
  const { run, stop, running, started, active, done, items, page, state } = useAgent();

  useEffect(() => {
    fetch("/api/overview").then((r) => r.json()).then((o) => setModel(o.model)).catch(() => setModel("back end offline"));
  }, []);

  /* A pressed Choice shows its prompt in the box, then sends it, so the person sees what was asked. */
  const send = useCallback((prompt: string) => {
    setText(prompt);
    setTimeout(() => { setText(""); run(prompt); }, 450);
  }, [run]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const ask = text.trim();
    setText("");
    if (ask && !running) run(ask);
  };
  const stateOf = (n: string) => (active.includes(n) ? "running" : done.includes(n) ? "done" : "waiting");

  return (
    <SendContext.Provider value={send}>
      <div className="flex h-full flex-col">
        <header className="flex h-14 flex-none items-center gap-6 border-b bg-sidebar px-4">
          <strong className="font-semibold">Atlas <span className="font-normal text-info">Cell Studio</span></strong>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList><TabsTrigger value="work">Workbench</TabsTrigger><TabsTrigger value="evidence">Evidence</TabsTrigger></TabsList>
          </Tabs>
          <Badge variant="outline" className="ml-auto hidden font-mono text-[11px] md:inline-flex">{model}</Badge>
        </header>
        {tab === "evidence" ? <main className="flex-1 overflow-auto p-6"><Evidence /></main> : (
          <div className="grid min-h-0 flex-1 grid-cols-1 overflow-auto lg:grid-cols-[250px_minmax(0,1fr)_340px] lg:overflow-hidden">
            <aside className="flex flex-col gap-3 border-r bg-sidebar p-4" aria-label="Pipeline">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Pipeline</h2>
              <ol className="flex flex-col gap-0.5">
                {STAGES.map(([n, label]) => {
                  const s = stateOf(n);
                  return (
                    <li key={n} data-state={s} className={`flex items-baseline gap-2.5 rounded-md px-2 py-1.5 text-[13px] ${s === "running" ? "bg-sidebar-accent text-foreground" : s === "done" ? "text-foreground" : "text-muted-foreground"}`}>
                      <i aria-hidden className={`size-2 flex-none translate-y-[-1px] rounded-full ${s === "running" ? "pulse-dot bg-info" : s === "done" ? "bg-success" : "bg-muted"}`} />
                      {label}<span className="sr-only">{s}</span>
                    </li>
                  );
                })}
              </ol>
              {!!state.revisions?.length && (
                <>
                  <Separator />
                  <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Revisions</h2>
                  <ul className="flex flex-col gap-1">
                    {state.revisions.map((r) => <li key={r.id} className="flex items-center gap-2 text-xs"><code className="font-mono">{r.id}</code><Status value={r.status} /><span className="text-muted-foreground">{r.sites ?? "no"} sites</span></li>)}
                  </ul>
                </>
              )}
            </aside>
            <main className="grid-paper min-w-0 overflow-auto p-6" aria-live="polite">
              {running ? <NowPanel items={items} started={started} running={running} /> : page ? <Renderer response={page} library={library} isStreaming={false} /> : (
                <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center gap-2 text-center">
                  <h1 className="text-xl font-semibold">Describe a cell</h1>
                  <p className="text-sm text-muted-foreground">Give a Boolean function of up to 4 inputs, or describe one in your own words. Every result here comes from a check script, never from the model.</p>
                </div>
              )}
            </main>
            <aside className="flex min-h-0 flex-col gap-3 border-l bg-sidebar p-4" aria-label="Agent activity">
              <Activity items={items} running={running} started={started} />
              <form onSubmit={submit} className="flex flex-col gap-2">
                <label htmlFor="ask" className="text-xs text-muted-foreground">Function or request</label>
                <Textarea id="ask" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Type a function, or describe a cell" className="font-mono text-[13px]"
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }} />
                <div className="flex flex-wrap gap-1">
                  {EXAMPLES.map((x) => <Button key={x} type="button" variant="outline" size="sm" className="h-6 px-1.5 font-mono text-[11px] text-muted-foreground" onClick={() => setText(x)}>{x}</Button>)}
                </div>
                {running ? <Button type="button" variant="destructive" onClick={stop}>Stop the agent</Button>
                  : <Button type="submit" disabled={!text.trim()}>Send</Button>}
              </form>
            </aside>
          </div>
        )}
      </div>
    </SendContext.Provider>
  );
}
