import { HttpAgent } from "@ag-ui/client";
import { useCallback, useMemo, useRef, useState } from "react";

export type FeedEvent = { id: string; kind: string; title: string; state: "running" | "ok" | "bad"; detail: string; stage: string; revision?: string; data?: any };
export type Revision = { id: string; status: string; sites: number; met1_nets: string[]; breaks: number; settings: Record<string, unknown>; report: string };
export type Step = FeedEvent & { started: number; ended?: number; run?: string; turn: number };
export type Choice = { label: string; expression: string };
export type Message = { id: string; who: "you" | "agent"; text: string; at: number; options?: Choice[] };
type AgentState = { stage?: string; expr?: string; stop?: string; revisions?: Revision[]; verdict?: { status?: string; run?: string; best?: string | { id: string } } };

/** A session over AG-UI: one thread, so follow-ups see the cell. CUSTOM events are the live feed: a "reply"
    goes to the chat, everything else to the steps. `log` keeps every turn for the trace, and `steps` is the
    latest turn. The assistant's text is the report page. */
export function useAgent(onFocus: (stage: string) => void) {
  const [log, setLog] = useState<Step[]>([]);
  const [turn, setTurn] = useState(0);
  const [messages, setMessages] = useState<Message[]>([]);
  const [page, setPage] = useState("");
  const [state, setState] = useState<AgentState>({});
  const [running, setRunning] = useState(false);
  const [started, setStarted] = useState(0);
  const agent = useRef<HttpAgent | null>(null);

  const turnNow = useRef(0);

  const feed = (e: FeedEvent) => setLog((list) => {
    const at = list.findIndex((x) => x.id === e.id);
    const now = Date.now();
    if (at < 0) return [...list, { ...e, turn: turnNow.current, started: now, ended: e.state === "running" ? undefined : now }];
    const next = [...list];
    next[at] = { ...next[at], ...e, started: next[at].started, detail: e.detail || next[at].detail, data: e.data ?? next[at].data, ended: e.state === "running" ? undefined : now };
    return next;
  });
  const say = (who: Message["who"], text: string, id: string = crypto.randomUUID(), options?: Choice[]) =>
    setMessages((m) => (m.some((x) => x.id === id) ? m.map((x) => (x.id === id ? { ...x, text } : x)) : [...m, { id, who, text, at: Date.now(), options }]));

  const run = useCallback(async (text: string) => {
    if (!agent.current) agent.current = new HttpAgent({ url: "/agent", threadId: crypto.randomUUID() });
    turnNow.current += 1;
    setTurn(turnNow.current); setRunning(true); setStarted(Date.now());
    say("you", text);
    agent.current.addMessage({ id: crypto.randomUUID(), role: "user", content: text });
    try {
      await agent.current.runAgent({}, {
        onCustomEvent: ({ event }) => {
          if (event.name !== "atlas") return;
          const e = event.value as FeedEvent;
          if (e.kind === "reply") say("agent", e.title, e.id, e.data?.options);
          else if (e.kind === "focus") onFocus(e.data.stage);
          else {
            if (e.kind === "check") setPage("");       // a new build replaces the old report
            feed(e);
          }
        },
        onStateSnapshotEvent: ({ event }) => setState(event.snapshot as AgentState),
        onTextMessageContentEvent: ({ textMessageBuffer }) => setPage(textMessageBuffer),
        onMessagesSnapshotEvent: ({ event }) => {
          const last = [...event.messages].reverse().find((m) => m.role === "assistant");
          if (last && typeof last.content === "string" && last.content.includes("root =")) setPage(last.content);
        },
        onRunErrorEvent: ({ event }) => say("agent", `The run failed: ${event.message}`),
      });
    } catch (e) {
      if (!String(e).includes("Abort")) say("agent", /fetch|network|HTTP/i.test(String(e)) ? `I could not reach the back end, so nothing ran. Start it with make agent-server. (${e})` : `The run failed: ${e}`);
    }
    setRunning(false);
    setLog((l) => l.map((x) => (x.state === "running" ? { ...x, state: "bad", detail: x.detail || "stopped", ended: Date.now() } : x)));
  }, [onFocus]);

  /* Dropping the connection is the signal: the server stops the build, its containers and the model. */
  const stop = useCallback(() => {
    agent.current?.abortRun();
    say("agent", "Stopped. The build and its containers are being shut down.");
  }, []);

  /* A question about a finished run keeps that run on screen: the view moves on only when a new build does. */
  const steps = useMemo(() => {
    const shown = log.findLast((x) => x.kind === "check")?.turn ?? turn;
    return log.filter((x) => x.turn === shown);
  }, [log, turn]);
  return { run, stop, running, started, steps, log, messages, page, state };
}
