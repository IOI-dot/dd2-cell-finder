import { Button } from "./ui";
import { Spinner } from "./ui";
import { Textarea } from "./ui";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useSend } from "./panels";
import { Mark } from "./Steps";
import { Rich, pretty } from "./text";
import { took, useNow } from "./time";
import type { Message, Step } from "./useAgent";
import { useMic } from "./useMic";

const TAG: Record<string, string> = { model: "Model", tool: "Tool", guard: "Guardrail", verdict: "Verdict" };
const LINE: Record<string, string> = { model: "border-info", tool: "border-primary", guard: "border-warning", verdict: "border-success" };

/** Reveals a reply as a stream of characters, and only the new part when an update adds to it. */
function Typed({ text }: { text: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { setN(text.length); return; }
    const id = setInterval(() => setN((c) => { if (c >= text.length) clearInterval(id); return Math.min(text.length, c + 3); }), 16);
    return () => clearInterval(id);
  }, [text]);
  return <Rich text={text.slice(0, n)} />;
}

const NEAR_END = 120;          // scrolled up further than this, you are reading, and the chat stays put

/** One agent action as a single line. Its arguments, reply and thinking stay folded until asked for. */
function TraceRow({ item, thoughts, now }: { item: Step; thoughts: Step[]; now: number }) {
  const more = item.detail || thoughts.length || item.data?.reply || item.data?.action;
  return (
    <details data-kind={item.kind} data-state={item.state} className={`group border-l-2 pl-2.5 ${LINE[item.kind]}`}>
      <summary className={`flex min-h-7 list-none items-center gap-2 py-0.5 text-sm ${more ? "cursor-pointer" : ""}`}>
        <span className="grid size-4 flex-none place-items-center"><Mark state={item.state} /></span>
        <span className="flex-none text-xs text-muted-foreground">{TAG[item.kind]}</span>
        <span className={`min-w-0 flex-1 leading-tight ${item.state === "bad" ? "text-destructive" : ""}`}>{pretty(item.title.replace("Tool call: ", ""))}</span>
        <span className="flex-none font-mono text-xs text-muted-foreground">{took((item.ended ?? now) - item.started)}</span>
      </summary>
      {more && (
        <div className="flex flex-col gap-1.5 pb-2 pl-6 pt-1">
          {item.detail && <p className="break-words font-mono text-xs text-muted-foreground">{pretty(item.detail)}</p>}
          {item.data?.action && <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-xs"><dt className="text-muted-foreground">action</dt><dd className="font-mono">{item.data.action}</dd>
            {item.data.expected_effect && <><dt className="text-muted-foreground">expects</dt><dd>{item.data.expected_effect}</dd></>}</dl>}
          {thoughts.map((t) => <p key={t.id} className="text-xs italic text-muted-foreground">{pretty(t.title)}</p>)}
        </div>
      )}
    </details>
  );
}

/** The conversation, with what the agent did between the messages. Individual checks live in the pipeline. */
export function Chat({ messages, log, running, status, onSend, onStop, draft }: {
  messages: Message[]; log: Step[]; running: boolean; status: string; onSend: (t: string) => void; onStop: () => void; draft: string }) {
  const [text, setText] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const reading = useRef(false);
  const choose = useSend();
  const now = useNow(running);
  const addText = useCallback((t: string) => setText((x) => (x.trim() ? `${x.trim()} ${t}` : t)), []);
  const mic = useMic(addText);
  const { toggle } = mic;
  /* Right Option on its own opens the mic. It acts on release, so Option shortcuts and typed symbols still work. */
  useEffect(() => {
    let alone = false;
    const down = (e: KeyboardEvent) => { if (!e.repeat) alone = e.code === "AltRight"; };
    const up = (e: KeyboardEvent) => {
      if (e.code === "AltRight" && alone && box.current?.offsetParent) toggle();
      alone = false;
    };
    addEventListener("keydown", down);
    addEventListener("keyup", up);
    return () => { removeEventListener("keydown", down); removeEventListener("keyup", up); };
  }, [toggle]);
  const trace = log.filter((x) => TAG[x.kind]);
  const thoughtsOf = (m: Step) => log.filter((x) => x.kind === "thought" && x.stage === m.stage && x.started >= m.started && x.started <= (m.ended ?? now));
  const entries: { at: number; m?: Message; t?: Step }[] = [...messages.map((m) => ({ at: m.at, m })), ...trace.map((t) => ({ at: t.started, t }))].sort((a, b) => a.at - b.at);
  /* Only your own scrolling can pause the chat: a tall new message must not look like you scrolled up. */
  const scrolled = () => requestAnimationFrame(() => {
    const b = box.current;
    if (b) reading.current = b.scrollHeight - b.scrollTop - b.clientHeight > NEAR_END;
  });
  /* Whatever makes the chat taller, a new message or a reply still streaming, follows to the end. */
  useEffect(() => {
    const follow = new ResizeObserver(() => { if (box.current && !reading.current) box.current.scrollTop = box.current.scrollHeight; });
    if (body.current) follow.observe(body.current);
    return () => follow.disconnect();
  }, []);
  useEffect(() => { if (box.current && !reading.current) box.current.scrollTop = box.current.scrollHeight; }, [entries.length]);
  useEffect(() => { setText(draft); }, [draft]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const ask = text.trim();
    if (ask && !running) { onSend(ask); setText(""); }
  };
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div ref={box} onWheel={scrolled} onTouchMove={scrolled} onPointerUp={scrolled} onKeyUp={scrolled}
        className="min-h-0 flex-1 overflow-auto pr-1" aria-live="polite" role="log" aria-label="Conversation and agent trace">
        <div ref={body} className="flex min-h-full flex-col gap-2">
        {!entries.length && (
          <p className="m-auto text-center text-sm text-muted-foreground">Describe a cell or type a function</p>
        )}
        {entries.map((e) => e.m ? (
          <div key={e.m.id} className={`my-1 flex max-w-[88%] flex-col gap-1.5 ${e.m.who === "you" ? "self-end" : "self-start"}`}>
            <div data-who={e.m.who} className={`whitespace-pre-line rounded-lg px-3 py-2 text-sm leading-snug ${e.m.who === "you" ? "bg-primary text-primary-foreground" : "border bg-card"}`}>
              {e.m.who === "you" ? e.m.text : <Typed text={e.m.text} />}
            </div>
            {e.m.options?.map((o) => <Button key={o.expression} size="sm" variant="outline" disabled={running} className="h-auto justify-start whitespace-normal py-1.5 text-left" onClick={() => choose(o.expression)}>{o.label}</Button>)}
          </div>
        ) : e.t && <TraceRow key={e.t.id} item={e.t} thoughts={thoughtsOf(e.t)} now={now} />)}
        {running && <p className="flex items-center gap-2 px-1 text-sm text-muted-foreground"><span className="pulse-dot">●</span>{status}</p>}
        {mic.error && mic.state === "idle" && <p role="alert" className="my-1 rounded-lg border border-destructive/40 px-3 py-2 text-sm text-destructive">{mic.error}</p>}
        </div>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-2">
        <label htmlFor="ask" className="sr-only">Message</label>
        {/* The mic takes over the box in place: the box keeps its size, so nothing around it moves. */}
        <div className="relative">
          <Textarea id="ask" rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="Describe a cell or type a function"
            className={`block resize-none text-sm ${mic.state === "idle" ? "" : "invisible"}`}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }} />
          {mic.state !== "idle" && (
            <div role="status" className="absolute inset-0 flex items-center gap-3 rounded-md border border-info/50 px-3 text-xs text-muted-foreground">
              {mic.state === "listening" ? (
                <>
                  <span aria-hidden className="flex h-8 min-w-0 flex-1 items-center justify-end gap-0.5 overflow-hidden">
                    {mic.levels.map((l, i) => <i key={i} className="w-0.5 flex-none rounded-full bg-info" style={{ height: `${Math.max(6, l * 100)}%` }} />)}
                  </span>
                  <span className="flex-none">Listening</span>
                  <button type="button" onClick={mic.cancel} className="flex-none cursor-pointer underline">Cancel</button>
                </>
              ) : <><Spinner className="size-3.5" />Writing it out</>}
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" aria-label={mic.state === "listening" ? "Finish speaking" : "Speak your message"} aria-pressed={mic.state === "listening"} disabled={mic.state === "transcribing"}
            size="icon" className={`flex-none ${mic.state === "listening" ? "border-info text-info" : ""}`} onClick={mic.toggle}>
            <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
          </Button>
          {running ? <Button type="button" variant="destructive" className="min-h-11 flex-1" onClick={onStop}>Stop the agent</Button>
            : <Button type="submit" className="min-h-11 flex-1" disabled={!text.trim()}>Send</Button>}
        </div>
      </form>
    </div>
  );
}
