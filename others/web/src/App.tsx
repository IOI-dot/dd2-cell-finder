import { Badge } from "./ui";
import { Tabs, TabsList, TabsTrigger } from "./ui";
import { Renderer } from "@openuidev/react-lang";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Chat } from "./Chat";
import { Evidence } from "./Evidence";
import { library } from "./library";
import { SendContext } from "./panels";
import { Option2Nav, Option2View } from "./Option2";
import { RunView } from "./RunView";
import { STAGES, stage, type Estimates } from "./stages";
import { Steps, estimateFor, inStage, span, stateOf } from "./Steps";
import { fmt, useNow } from "./time";
import { useAgent } from "./useAgent";

type Pane = "steps" | "run" | "agent";

export function App() {
  const [tab, setTab] = useState("o1");
  const [section, setSection] = useState("o2-status");
  const [model, setModel] = useState("");
  const [view, setView] = useState("run");
  const [pane, setPane] = useState<Pane>("run");
  const [draft, setDraft] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  const [chosenRev, setChosenRev] = useState("");

  /* The agent can open a step, or a section of Option 2, when you ask about it. */
  const openSection = useCallback((id: string) => {
    setTab("o2"); setPane("run"); setSection(id);
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, []);
  const onFocus = useCallback((stage: string) => {
    if (stage.startsWith("o2-")) openSection(stage);
    else { setTab("o1"); setView("run"); setPane("run"); setPicked(stage); }
  }, [openSection]);
  const { run, stop, running, started, steps, log, messages, page, state } = useAgent(onFocus);
  const shownTurn = steps[0]?.turn;
  useEffect(() => { setView("run"); setPicked(null); setChosenRev(""); }, [shownTurn]);
  const now = useNow(running);
  const revisions = useMemo(() => [...new Set(steps.map((x) => x.revision).filter(Boolean) as string[])], [steps]);
  const bestRev = state.verdict?.best;
  const best = (typeof bestRev === "string" ? bestRev : bestRev?.id) ?? "";
  const revision = chosenRev || (!running && best) || revisions.at(-1) || "";
  const [estimates, setEstimates] = useState<Estimates>({});

  useEffect(() => {
    fetch("/api/overview").then((r) => r.json()).then((o) => setModel(o.model)).catch(() => setModel("back end offline"));
  }, []);

  useEffect(() => {
    if (!running) fetch("/api/estimates").then((r) => r.json()).then(setEstimates).catch(() => {});
  }, [running]);
  /* What is left, from the median of past runs. DRC and abutment run together, so they count once. */
  const left = useMemo(() => {
    const guess = estimateFor(estimates, steps);
    return running ? STAGES.filter((s) => s.id !== "abutment" && s.id !== "model" && s.id !== "request").reduce((sum, s) => {
      const mine = inStage(steps, s.id, revision);
      const done = mine.length > 0 && stateOf(mine) !== "running";
      return sum + (done ? 0 : Math.max(0, (guess[s.id]?.seconds ?? 0) * 1000 - (mine.length ? span(mine, now) : 0)));
    }, 0) : 0;
  }, [estimates, steps, running, revision, now]);

  const send = useCallback((prompt: string) => {
    setDraft(prompt);
    setTimeout(() => { setDraft(""); run(prompt); }, 450);
  }, [run]);
  const live = useMemo(() => [...steps].reverse().find((x) => x.state === "running" && x.stage), [steps]);
  const status = (live && stage(live.stage)?.name) ?? "Starting";
  const pick = useCallback((id: string | null) => { setPicked(id); setView("run"); setPane("run"); }, []);
  const panes: [Pane, string][] = [["steps", "Pipeline"], ["run", "Run"], ["agent", "Agent"]];

  return (
    <SendContext.Provider value={send}>
      <div className="flex h-dvh flex-col">
        <header className="flex min-h-14 flex-none items-center gap-3 border-b bg-sidebar px-3 lg:gap-6 lg:px-4">
          <strong className="font-semibold">Atlas <span className="hidden font-normal text-info sm:inline">Cell Studio</span></strong>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="h-auto"><TabsTrigger className="min-h-11 lg:min-h-8" value="o1">Option 1 · Cells</TabsTrigger><TabsTrigger className="min-h-11 lg:min-h-8" value="o2">Option 2 · Designs</TabsTrigger><TabsTrigger className="min-h-11 lg:min-h-8" value="evidence">Evidence</TabsTrigger></TabsList>
          </Tabs>
          {running && <span data-testid="clock" className="ml-auto font-mono text-sm text-info">{fmt(now - started)}{left >= 1000 && <span className="text-muted-foreground">, about {fmt(left)} left</span>}</span>}
          <Badge variant="outline" className={`hidden font-mono text-xs lg:inline-flex ${running ? "" : "ml-auto"}`} title={model}>{model.replace(/ effort by role:.*/, " · effort by role")}</Badge>
        </header>
        {tab === "evidence" && <main className="min-h-0 flex-1 overflow-auto p-4 lg:p-6"><Evidence /></main>}
        {/* Both options stay mounted behind Evidence and behind each other, so the chat, scroll positions and open step survive a tab switch. */}
        {(
          <div className={`min-h-0 flex-1 grid-cols-1 lg:grid-cols-[16rem_minmax(0,1fr)_22rem] ${tab === "evidence" ? "hidden" : "grid"}`}>
            <aside aria-label="Pipeline" className={`min-h-0 flex-col gap-3 border-r bg-sidebar p-3 ${pane === "steps" ? "flex" : "hidden"} ${tab === "o1" ? "lg:flex" : "lg:hidden"}`}>
              <Steps steps={steps} running={running} picked={picked} onPick={pick} revision={revision} revisions={revisions} best={best} onRevision={setChosenRev} estimates={estimates} />
            </aside>
            <aside aria-label="Option 2 sections" className={`min-h-0 flex-col gap-3 border-r bg-sidebar p-3 ${pane === "steps" ? "flex" : "hidden"} ${tab === "o2" ? "lg:flex" : "lg:hidden"}`}>
              <Option2Nav active={section} onPick={openSection} />
            </aside>
            <main className={`relative min-h-0 min-w-0 flex-col ${tab === "o2" && pane === "run" ? "flex" : "hidden"} ${tab === "o2" ? "lg:flex" : "lg:hidden"}`}>
              <Option2View />
            </main>
            <main className={`relative min-h-0 min-w-0 flex-col ${tab === "o1" && pane === "run" ? "flex" : "hidden"} ${tab === "o1" ? "lg:flex" : "lg:hidden"}`}>
              {page && (
                <div className="flex-none border-b p-2">
                  <Tabs value={view} onValueChange={setView}>
                    <TabsList className="h-auto"><TabsTrigger className="min-h-11 lg:min-h-8" value="run">Run</TabsTrigger><TabsTrigger className="min-h-11 lg:min-h-8" value="report">Report</TabsTrigger></TabsList>
                  </Tabs>
                </div>
              )}
              {view === "run" ? <RunView steps={steps} running={running} picked={picked} revision={revision} revisions={state.revisions} onPick={setPicked} onRevision={setChosenRev} />
                : page && <div className="min-h-0 flex-1 overflow-auto p-4 lg:p-6"><Renderer response={page} library={library} isStreaming={false} /></div>}
            </main>
            <aside aria-label="Agent" className={`min-h-0 flex-col gap-3 border-l bg-sidebar p-3 lg:flex ${pane === "agent" ? "flex" : "hidden"}`}>
              <h2 className="hidden text-sm font-semibold lg:block">Agent</h2>
              <Chat messages={messages} log={log} running={running} status={status} onSend={run} onStop={stop} draft={draft} />
            </aside>
          </div>
        )}
        {tab !== "evidence" && (
          <nav aria-label="Panels" className="grid flex-none grid-cols-3 border-t bg-sidebar lg:hidden">
            {panes.map(([id, name]) => (
              <button key={id} aria-current={pane === id} onClick={() => setPane(id)} className={`min-h-12 text-sm ${pane === id ? "font-semibold text-foreground" : "text-muted-foreground"}`}>{name}</button>
            ))}
          </nav>
        )}
      </div>
    </SendContext.Provider>
  );
}
