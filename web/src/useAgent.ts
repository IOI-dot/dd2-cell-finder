import { HttpAgent } from "@ag-ui/client";
import { useCallback, useRef, useState } from "react";

export type Revision = { id: string; status: string; sites: number; met1_nets: string[]; breaks: number; settings: Record<string, unknown>; report: string };
export type Kind = "you" | "step" | "model" | "thought" | "tool" | "check" | "guard" | "verdict" | "error";
export type Item = { id: string; kind: Kind; title: string; detail: string; state: "running" | "ok" | "bad"; started: number; ended?: number };
type Feed = { id: string; kind: Kind; title: string; state: Item["state"]; detail: string };
type AgentState = { stage?: string; expr?: string; stop?: string; revisions?: Revision[]; verdict?: { status?: string; run?: string }; intent?: { kind?: string } };

/** A session over AG-UI: one thread, so follow-ups see the cell. Graph steps drive the rail, CUSTOM events
    the activity feed, state snapshots the revisions, and the assistant's text is the page. */
export function useAgent() {
  const [active, setActive] = useState<string[]>([]);
  const [done, setDone] = useState<string[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [page, setPage] = useState("");
  const [state, setState] = useState<AgentState>({});
  const [running, setRunning] = useState(false);
  const [started, setStarted] = useState(0);
  const agent = useRef<HttpAgent | null>(null);

  /* A later event with the same id updates its line, so a step goes from running to its result in place. */
  const feed = (e: Feed) => setItems((list) => {
    const at = list.findIndex((x) => x.id === e.id);
    const now = Date.now();
    if (at < 0) return [...list, { ...e, started: now, ended: e.state === "running" ? undefined : now }];
    const next = [...list];
    next[at] = { ...next[at], ...e, detail: e.detail || next[at].detail, ended: e.state === "running" ? undefined : now };
    return next;
  });

  const run = useCallback(async (text: string) => {
    if (!agent.current) agent.current = new HttpAgent({ url: "/agent", threadId: crypto.randomUUID() });
    setActive([]); setDone([]); setRunning(true); setStarted(Date.now());
    feed({ id: crypto.randomUUID(), kind: "you", title: text, state: "ok", detail: "" });
    agent.current.addMessage({ id: crypto.randomUUID(), role: "user", content: text });
    try {
      await agent.current.runAgent({}, {
        onStepStartedEvent: ({ event }) => setActive((s) => [...s, event.stepName]),
        onStepFinishedEvent: ({ event }) => {
          setActive((s) => s.filter((x) => x !== event.stepName));
          setDone((s) => [...s, event.stepName]);
        },
        onCustomEvent: ({ event }) => { if (event.name === "atlas") feed(event.value as Feed); },
        onStateSnapshotEvent: ({ event }) => setState(event.snapshot as AgentState),
        onTextMessageContentEvent: ({ textMessageBuffer }) => setPage(textMessageBuffer),
        onMessagesSnapshotEvent: ({ event }) => {
          const last = [...event.messages].reverse().find((m) => m.role === "assistant");
          if (last && typeof last.content === "string" && last.content.includes("root =")) setPage(last.content);
        },
        onRunErrorEvent: ({ event }) => feed({ id: crypto.randomUUID(), kind: "error", title: event.message, state: "bad", detail: "" }),
      });
    } catch (e) {
      if (!String(e).includes("Abort")) feed({ id: crypto.randomUUID(), kind: "error", title: String(e), state: "bad", detail: "" });
    }
    setRunning(false);
    setActive([]);
    setItems((l) => l.map((x) => (x.state === "running" ? { ...x, state: "bad", detail: x.detail || "stopped", ended: Date.now() } : x)));
  }, []);

  /* Dropping the connection is the signal: the server stops the build, its containers and the model. */
  const stop = useCallback(() => {
    agent.current?.abortRun();
    feed({ id: crypto.randomUUID(), kind: "error", title: "Stopped by you. The build and its containers are being stopped.", state: "bad", detail: "" });
  }, []);

  return { run, stop, running, started, active, done, items, page, state };
}
