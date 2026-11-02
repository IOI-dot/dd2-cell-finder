import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { createLibrary, defineComponent } from "@openuidev/react-lang";
import { useMemo, useState } from "react";
import { z } from "zod/v4";
import { Cell3D } from "./Layout3D";
import { LAYER_COLOURS, Panel, Status, useSend, Waiting } from "./panels";
import { TimeMachineView } from "./TimeMachine";
import { TimingView } from "./TimingSurface";
import { useEvidence } from "./useEvidence";

/* The closed set of panels a model can place. Each takes a handle and fetches its own numbers, so a
   page written by a model can arrange evidence but cannot state it. Keep the names in step with
   COMPONENTS in agent/dd2_agent/generative_ui.py; a test compares the two. */

type Check = { check: string; status: string; detail: string };
type CellView = {
  cell: string; status: string; failed: string[]; checks: Check[]; inputs: string[]; truth: { row: number; y: number }[];
  sites: number; width_um: number; gate_order: string[]; gate_pitch_um: number[]; breaks: { n: number; p: number }; met1_nets: string[];
  rows: { n: string[][]; p: string[][] }; network: { transistors: number; stages: number; stage_outputs: string[]; max_series: number };
  sizing: { policy: string };
};
type Revision = { id: string; status: string; sites: number; met1_nets: string[]; breaks: number; settings: Record<string, unknown>; failed: string[]; report: string };
type RunView = { run: string; function: string; status: string; stop: string; seconds: number; model: string; calls: { model: number; tool: number; in: number; out: number };
  revisions: Revision[]; best: Revision | null };
type Layout = { width_um: number; height_um: number; layers: Record<string, number[][][]>; labels: { text: string; x: number; y: number }[] };

const handle = z.string().describe("an evidence handle, copied exactly from the facts");
const handleOf = (r: Revision) => { const p = r.report.split("/"); return `cell:${p[1]}/${p[3]}`; };

const Report = defineComponent({
  name: "Report", description: "The page. Holds panels from top to bottom.",
  props: z.object({ children: z.array(z.any()).describe("the panels, in reading order") }),
  component: ({ props, renderNode }) => <div className="mx-auto flex max-w-5xl flex-col gap-4">{renderNode(props.children)}</div>,
});

const Section = defineComponent({
  name: "Section", description: "A titled group of panels, side by side when there is room.",
  props: z.object({ title: z.string().describe("a short title"), children: z.array(z.any()).describe("the panels") }),
  component: ({ props, renderNode }) => (
    <section className="flex flex-col gap-2">
      <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{props.title}</h2>
      <div className="grid gap-4 md:grid-cols-2">{renderNode(props.children)}</div>
    </section>
  ),
});

const Note = defineComponent({
  name: "Note", description: "One or two plain sentences from you, the agent, on the evidence around them. No Markdown.",
  props: z.object({ text: z.string().describe("the sentences; every number must be in the facts") }),
  component: ({ props }) => (
    <aside className="rounded-r-md border-l-2 border-info bg-accent/40 px-4 py-2.5 text-sm">
      <span className="mb-0.5 block text-[10px] uppercase tracking-wider text-muted-foreground">Agent's note, not a check result</span>
      {props.text}
    </aside>
  ),
});

const Choice = defineComponent({
  name: "Choice", description: "One next step. Pressing it sends the prompt as if the person had typed it.",
  props: z.object({
    label: z.string().describe("two to five words on the button"),
    prompt: z.string().describe("the plain request that gets sent, such as: Try another Euler order for this cell"),
    detail: z.string().optional().describe("a few words on what it would do"),
  }),
  component: ({ props }) => {
    const send = useSend();
    return (
      <Button variant="outline" className="h-auto flex-col items-start gap-0.5 whitespace-normal py-2 text-left" onClick={() => send(props.prompt)}>
        <span className="text-sm">{props.label}</span>
        {props.detail && <span className="text-xs font-normal text-muted-foreground">{props.detail}</span>}
      </Button>
    );
  },
});

const Choices = defineComponent({
  name: "Choices", description: "What the person can do next: two to four Choice buttons. Ends the page.",
  props: z.object({ options: z.array(Choice.ref).describe("the choices") }),
  component: ({ props, renderNode }) => (
    <section className="flex flex-col gap-2" aria-label="What next">
      <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">What next</h2>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{renderNode(props.options)}</div>
    </section>
  ),
});

const Verdict = defineComponent({
  name: "Verdict", description: "The run's result, read from the check reports: status, function, width, cost. Always first.",
  props: z.object({ run: handle.describe("a run handle") }),
  component: ({ props }) => {
    const { data, error } = useEvidence<RunView>(props.run);
    if (!data) return <Waiting error={error} />;
    const stats: [string, string | number][] = [["Sites", data.best?.sites ?? "none"], ["Builds", data.revisions.length], ["Model calls", data.calls.model], ["Seconds", data.seconds]];
    return (
      <Panel title="Verdict" note={`${data.run} · stopped: ${data.stop || "finished"}`} wide>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <Status value={data.status} />
          <code className="font-mono text-base">{data.function}</code>
          <dl className="ml-auto flex gap-6">
            {stats.map(([k, v]) => <div key={k}><dt className="text-[11px] text-muted-foreground">{k}</dt><dd className="font-mono text-lg font-semibold">{v}</dd></div>)}
          </dl>
        </div>
      </Panel>
    );
  },
});

const RevisionTable = defineComponent({
  name: "RevisionTable", description: "Every revision of a run with its settings and results. Use it when more than one was built.",
  props: z.object({ run: handle.describe("a run handle") }),
  component: ({ props }) => {
    const { data, error } = useEvidence<RunView>(props.run);
    if (!data) return <Waiting error={error} />;
    return (
      <Panel title="Revisions" note="The best one is marked; earlier ones stay on record" wide>
        <Table>
          <TableHeader><TableRow><TableHead>Id</TableHead><TableHead>Result</TableHead><TableHead>Sites</TableHead><TableHead>met1 nets</TableHead><TableHead>Breaks</TableHead><TableHead>Settings</TableHead></TableRow></TableHeader>
          <TableBody>
            {data.revisions.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-mono">{r.id}{r.id === data.best?.id ? " ★" : ""}</TableCell><TableCell><Status value={r.status} /></TableCell><TableCell>{r.sites}</TableCell>
                <TableCell>{r.met1_nets.join(" ") || "none"}</TableCell><TableCell>{r.breaks}</TableCell>
                <TableCell className="font-mono text-xs">{Object.entries(r.settings).map(([k, v]) => `${k}=${v}`).join(" ")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
    );
  },
});

const RevisionGhost = defineComponent({
  name: "RevisionGhost", description: "Two revisions of a run laid over each other: solid and ghost outline. Shows what moved.",
  props: z.object({ run: handle.describe("a run handle") }),
  component: ({ props }) => {
    const { data, error } = useEvidence<RunView>(props.run);
    const revs = data?.revisions ?? [];
    const a = revs[0], b = data?.best && data.best.id !== a?.id ? data.best : revs[revs.length - 1];
    const one = useEvidence<Layout>(a && handleOf(a), "layout");
    const two = useEvidence<Layout>(b && handleOf(b), "layout");
    if (!data || !one.data || !two.data) return <Waiting error={error || one.error || two.error} />;
    const W = Math.max(one.data.width_um, two.data.width_um);
    return (
      <Panel title="Revision ghosts" note={`solid ${b.id}, outline ${a.id}`} wide>
        <svg viewBox={`-0.2 -0.2 ${W + 0.4} 3.12`} role="img" aria-label="Two layouts overlaid" className="max-h-80 w-full rounded-md bg-background">
          <g transform="matrix(1 0 0 -1 0 2.72)">
            {["diff", "poly", "li1", "met1"].map((l) => (
              <g key={l} fill={LAYER_COLOURS[l]} fillOpacity={0.45}>{two.data!.layers[l].map((p, i) => <polygon key={i} points={p.map((q) => q.join(",")).join(" ")} />)}</g>
            ))}
            {["poly", "li1"].map((l) => (
              <g key={l} fill="none" stroke="#f2f5fa" strokeDasharray="0.03 0.02" strokeWidth={0.012}>{one.data!.layers[l].map((p, i) => <polygon key={i} points={p.map((q) => q.join(",")).join(" ")} />)}</g>
            ))}
          </g>
        </svg>
      </Panel>
    );
  },
});

const CheckMatrix = defineComponent({
  name: "CheckMatrix", description: "Every check of one cell with its status. Use it to show why a cell passed or failed.",
  props: z.object({ cell: handle.describe("a cell handle") }),
  component: ({ props }) => {
    const { data, error } = useEvidence<CellView>(props.cell);
    if (!data) return <Waiting error={error} />;
    return (
      <Panel title="Checks" note={data.cell}>
        <ul className="grid gap-1 text-xs">
          {data.checks.map((c) => <li key={c.check} className="grid grid-cols-[84px_1fr_auto] items-center gap-2"><Status value={c.status} /><span>{c.check}</span><span className="font-mono text-muted-foreground">{c.detail}</span></li>)}
        </ul>
      </Panel>
    );
  },
});

const LayoutView = defineComponent({
  name: "LayoutView", description: "The cell's layout from its GDS, flat in 2D, with a switch for each layer.",
  props: z.object({ cell: handle.describe("a cell handle") }),
  component: ({ props }) => {
    const { data, error } = useEvidence<Layout>(props.cell, "layout");
    const [off, setOff] = useState<Set<string>>(new Set(["nwell"]));
    const layers = useMemo(() => Object.keys(LAYER_COLOURS), []);
    if (!data) return <Waiting error={error} />;
    return (
      <Panel title="Layout" note={`${data.width_um} × ${data.height_um} µm`}>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Layers">
          {layers.map((l) => (
            <button key={l} aria-pressed={!off.has(l)} className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-mono text-[11px] ${off.has(l) ? "opacity-40" : ""}`}
              onClick={() => setOff((s) => { const n = new Set(s); if (n.has(l)) n.delete(l); else n.add(l); return n; })}>
              <i className="size-2.5 rounded-sm" style={{ background: LAYER_COLOURS[l] }} />{l}
            </button>
          ))}
        </div>
        <svg viewBox={`-0.3 -0.3 ${data.width_um + 0.6} ${data.height_um + 0.6}`} role="img" aria-label="Cell layout" className="max-h-96 w-full rounded-md bg-background">
          <g transform={`matrix(1 0 0 -1 0 ${data.height_um})`}>
            {layers.filter((l) => !off.has(l)).map((l) => (
              <g key={l} fill={LAYER_COLOURS[l]} fillOpacity={l === "licon" || l === "mcon" ? 0.95 : 0.5} stroke={LAYER_COLOURS[l]} strokeWidth={0.006}>
                {(data.layers[l] ?? []).map((p, i) => <polygon key={i} points={p.map((q) => q.join(",")).join(" ")} />)}
              </g>
            ))}
          </g>
          {data.labels.map((t, i) => <text key={i} x={t.x} y={data.height_um - t.y} textAnchor="middle" fontSize={0.13} fill="var(--foreground)" className="font-mono">{t.text}</text>)}
        </svg>
      </Panel>
    );
  },
});

const Layout3D = defineComponent({
  name: "Layout3D", description: "The cell's layers as an illustrative 3D extrusion the person can orbit and explode. A striking first view of a cell.",
  props: z.object({ cell: handle.describe("a cell handle") }),
  component: ({ props }) => <Cell3D cell={props.cell} />,
});

const TimeMachine = defineComponent({
  name: "TimeMachine", description: "The real ngspice transient with a slider: as time moves, the devices that conduct light up on the layout. Shows how the cell works.",
  props: z.object({ cell: handle.describe("a cell handle") }),
  component: ({ props }) => <TimeMachineView cell={props.cell} />,
});

const TimingSurface = defineComponent({
  name: "TimingSurface", description: "A delay or transition table as a 3D surface, next to the shipped Liberty. Only for reference cells.",
  props: z.object({ cell: handle.describe("a reference cell handle") }),
  component: ({ props }) => <TimingView cell={props.cell} />,
});

const NetworkView = defineComponent({
  name: "NetworkView", description: "How the function became transistors: stages, count, series depth, sizing and width.",
  props: z.object({ cell: handle.describe("a cell handle") }),
  component: ({ props }) => {
    const { data, error } = useEvidence<CellView>(props.cell);
    if (!data) return <Waiting error={error} />;
    const n = data.network;
    const rows: [string, string | number][] = [["Stages", n.stages], ["Transistors", n.transistors], ["Most in series", n.max_series], ["Sizing", data.sizing?.policy],
      ["Width", `${data.sites} sites`], ["Gate pitch", data.gate_pitch_um?.join(" ") || "none"], ["met1 nets", data.met1_nets.join(" ") || "none"]];
    return <Panel title="Network"><dl className="grid grid-cols-2 gap-2">{rows.map(([k, v]) => <div key={k}><dt className="text-[11px] text-muted-foreground">{k}</dt><dd className="font-mono text-sm">{v}</dd></div>)}</dl></Panel>;
  },
});

const EulerRows = defineComponent({
  name: "EulerRows", description: "The gate order and what sits along each diffusion row, with its breaks.",
  props: z.object({ cell: handle.describe("a cell handle") }),
  component: ({ props }) => {
    const { data, error } = useEvidence<CellView>(props.cell);
    if (!data) return <Waiting error={error} />;
    return (
      <Panel title="Gate order" note={`breaks: NMOS ${data.breaks?.n ?? 0}, PMOS ${data.breaks?.p ?? 0}`}>
        <div className="flex flex-wrap gap-1">{data.gate_order?.map((g, i) => <b key={i} className="rounded border px-2 py-0.5 font-mono text-xs">{g}</b>)}</div>
        {(["p", "n"] as const).map((r) => (
          <p key={r} className="flex flex-wrap items-baseline gap-2 text-xs"><span className="text-muted-foreground">{r === "p" ? "PMOS" : "NMOS"}</span>
            {data.rows?.[r]?.map((seg, i) => <code key={i} className="font-mono">{seg.join(" – ")}</code>)}
          </p>
        ))}
      </Panel>
    );
  },
});

const TruthTable = defineComponent({
  name: "TruthTable", description: "The cell's truth table, as built and checked.",
  props: z.object({ cell: handle.describe("a cell handle") }),
  component: ({ props }) => {
    const { data, error } = useEvidence<CellView>(props.cell);
    if (!data) return <Waiting error={error} />;
    return (
      <Panel title="Truth table">
        <table className="font-mono text-xs">
          <thead><tr>{data.inputs.map((x) => <th key={x} className="px-2 text-muted-foreground">{x}</th>)}<th className="px-2 text-muted-foreground">Y</th></tr></thead>
          <tbody>{data.truth.map((t) => <tr key={t.row}>{data.inputs.map((x, k) => <td key={x} className="px-2 text-center">{(t.row >> k) & 1}</td>)}<td className={`px-2 text-center ${t.y ? "font-semibold text-info" : ""}`}>{t.y}</td></tr>)}</tbody>
        </table>
      </Panel>
    );
  },
});

export const library = createLibrary({
  components: [Report, Section, Note, Choices, Choice, Verdict, RevisionTable, RevisionGhost, CheckMatrix, LayoutView, Layout3D, TimeMachine, TimingSurface, NetworkView, EulerRows, TruthTable],
  root: "Report",
});
