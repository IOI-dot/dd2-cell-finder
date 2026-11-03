import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui";
import { useState, type ReactNode } from "react";
import { Cell3D } from "./Layout3D";
import { LAYER_COLOURS, Status } from "./panels";
import { pretty } from "./text";
import type { Step } from "./useAgent";
import { useEvidence } from "./useEvidence";

/* Each stage's real output as tables and graphs. Every value arrives in an event from the flow, so these
   views draw results and never work one out. */

/** Tables show every row: nothing here scrolls on its own, only the page does. */
export function Grid({ head, rows, onRow, picked }: { head: ReactNode[]; rows: ReactNode[][]; onRow?: (i: number) => void; picked?: number }) {
  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader className="bg-card"><TableRow>{head.map((h, i) => <TableHead key={i} className="h-8 whitespace-nowrap px-2.5 text-xs">{h}</TableHead>)}</TableRow></TableHeader>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={i} data-state={picked === i ? "selected" : undefined} onClick={onRow && (() => onRow(i))} className={onRow ? "cursor-pointer" : ""}>
              {r.map((c, j) => <TableCell key={j} className="whitespace-nowrap px-2.5 py-1 font-mono text-xs">{typeof c === "string" ? pretty(c) : c}</TableCell>)}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function Stats({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="flex flex-wrap gap-x-6 gap-y-1">
      {items.map(([k, v]) => <div key={k}><dt className="text-xs text-muted-foreground">{k}</dt><dd className="font-mono text-sm">{typeof v === "string" ? pretty(v) : v}</dd></div>)}
    </dl>
  );
}

const Yes = ({ on }: { on: boolean }) => <span className={on ? "text-foreground" : "text-muted-foreground/60"}>{on ? "on" : "off"}</span>;
const Good = ({ ok }: { ok: boolean }) => <span className={ok ? "text-success" : "text-destructive"}>{ok ? "✓" : "✕"}</span>;
const bits = (row: number, n: number) => Array.from({ length: n }, (_, k) => (row >> k) & 1);

function NetworkStage({ d, full }: { d: any; full: boolean }) {
  if (!d.switch) return <p className="font-mono text-xs text-muted-foreground">Truth table loaded, finding the network</p>;
  return (
    <div className="flex flex-col gap-3">
      <Stats items={[["Transistors", d.transistors.length], ["Stages", d.stages], ["Most in series", d.max_series], ["Switch-level errors", d.errors.length]]} />
      <h4 className="text-xs font-medium text-muted-foreground">Switch-level check, every input row</h4>
      <Grid head={[...d.inputs, "Pull-up", "Pull-down", "Y", "Expected", ""]}
        rows={d.switch.map((r: any) => [...bits(r.row, d.inputs.length), <Yes on={r.up} />, <Yes on={r.down} />, r.y, r.expected, <Good ok={r.y === r.expected && r.up !== r.down} />])} />
      {full && (
        <>
          <h4 className="text-xs font-medium text-muted-foreground">Transistors</h4>
          <Grid head={["Type", "Gate", "Drain", "Source", "W (µm)", "Stage"]}
            rows={d.transistors.map((t: any) => [t.kind === "n" ? "NMOS" : "PMOS", t.gate, t.drain, t.source, t.w, t.stage])} />
        </>
      )}
    </div>
  );
}

/** Both diffusion rows under one gate order. Each net's name sits in the diffusion between two gates, so
    names cannot touch: strips that share a net run together, and a break leaves a gap with a name either side. */
function EulerDiagram({ order }: { order: any }) {
  const W = 124, L = 64, reach = W / 2 - 8, inset = W * 0.27, rows: [string, string, number][] = [["p", "PMOS", 24], ["n", "NMOS", 104]];
  const gate = (i: number) => L + W / 2 + i * W;
  const width = L + order.gates.length * W + 8;
  const name = (x: number, y: number, net: string, key: string) => <text key={key} x={x} y={y + 21} textAnchor="middle" fontSize={12} className="font-mono" fill="var(--foreground)">{pretty(net)}</text>;
  return (
    <svg viewBox={`0 0 ${width} 184`} style={{ maxWidth: width }} role="img" aria-label={`Diffusion rows for gate order ${order.gates.join(" ")}`} className="w-full">
      {order.gates.map((g: string, i: number) => (
        <g key={i}>
          <rect x={gate(i) - 3} y={12} width={6} height={148} fill={LAYER_COLOURS.poly} fillOpacity={0.8} />
          <text x={gate(i)} y={178} textAnchor="middle" fontSize={12} className="font-mono" fill="var(--foreground)">{pretty(g)}</text>
        </g>
      ))}
      {rows.map(([key, label, y]) => (
        <g key={key}>
          <text x={0} y={y + 21} fontSize={12} fill="var(--muted-foreground)">{label}</text>
          {order[key].map((s: any, i: number) => {
            if (!s) return null;
            const before = order[key][i - 1], after = order[key][i + 1];
            const joinLeft = before?.right === s.left, joinRight = after?.left === s.right;
            const x0 = gate(i) - (joinLeft ? W / 2 : reach), x1 = gate(i) + (joinRight ? W / 2 : reach);
            return (
              <g key={i}>
                <rect x={x0} y={y} width={x1 - x0} height={32} fill={key === "p" ? "var(--info)" : "var(--success)"} fillOpacity={0.28} />
                {!joinLeft && name(gate(i) - inset, y, s.left, "l")}
                {name(joinRight ? gate(i) + W / 2 : gate(i) + inset, y, s.right, "r")}
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

function EulerStage({ d, chosen, full }: { d: any; chosen: string | undefined; full: boolean }) {
  const orders: any[] = d.orders ?? [];
  const used = orders.findIndex((o) => o.gates.join(" ") === chosen);
  const [pick, setPick] = useState<number | null>(null);
  const shown = pick ?? Math.max(used, 0);
  if (!orders.length) return null;
  return (
    <div className="flex flex-col gap-3">
      <EulerDiagram order={orders[shown]} />
      <Grid onRow={setPick} picked={shown} head={["Candidate", "Gate order", "Diffusion breaks", ""]}
        rows={orders.map((o, i) => [i, o.gates.join(" "), o.breaks, i === used ? "used" : ""])} />
    </div>
  );
}

const SHAPES = ["nwell", "diff", "poly", "licon", "li1", "mcon", "met1"];

function Geometry({ d }: { d: any }) {
  return (
    <svg viewBox={`-0.15 -0.15 ${d.width_um + 0.3} ${d.height_um + 0.3}`} role="img" aria-label="Cell geometry" className="h-64 max-w-full rounded-md border bg-background">
      <g transform={`matrix(1 0 0 -1 0 ${d.height_um})`}>
        {SHAPES.map((l) => (
          <g key={l} fill={LAYER_COLOURS[l]} fillOpacity={l === "licon" || l === "mcon" ? 0.95 : 0.45}>
            {(d.rects[l] ?? []).map((b: number[], i: number) => <rect key={i} x={b[0]} y={b[1]} width={b[2] - b[0]} height={b[3] - b[1]} />)}
          </g>
        ))}
      </g>
      {(d.labels ?? []).filter((t: any[]) => !/^V/.test(t[1])).map((t: any[], i: number) => (
        <text key={i} x={t[2]} y={d.height_um - t[3]} textAnchor="middle" fontSize={0.14} className="font-mono" fill="var(--foreground)">{t[1]}</text>
      ))}
    </svg>
  );
}

function LayoutStage({ d, cell, full }: { d: any; cell?: string; full: boolean }) {
  const [view, setView] = useState("2D");
  const attempts: any[] = d.attempts ?? [];
  const last = attempts.slice(full ? -200 : -6).reverse();
  return (
    <div className="flex flex-col gap-3">
      <Stats items={[["Combinations tried", d.tried ?? attempts.length], ["Width", d.width_um ? `${d.width_um} µm` : "…"], ["Gate order", d.gate_order?.join(" ") ?? attempts.at(-1)?.order ?? "…"], ["met1 nets", d.met1_nets ? d.met1_nets.join(" ") || "none" : "…"]]} />
      {attempts.length > 0 && (
        <div role="img" aria-label={`${attempts.filter((a) => a.failed.length).length} attempts left nets unrouted`} className="flex flex-wrap gap-0.5">
          {attempts.slice(-200).map((a) => <i key={a.n} title={`#${a.n}: ${a.sites} sites, ${a.order}${a.failed.length ? `, unrouted ${a.failed.join(" ")}` : ", routed"}`} className={`size-2 rounded-[1px] ${a.failed.length ? "bg-destructive/60" : "bg-success"}`} />)}
        </div>
      )}
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex flex-col gap-2">
          {full && cell && (
            <div role="group" aria-label="View" className="flex gap-1">
              {["2D", "3D layers"].map((v) => <button key={v} aria-pressed={view === v} onClick={() => setView(v)} className={`min-h-11 rounded-md border px-2 text-xs lg:min-h-7 ${view === v ? "border-primary" : "text-muted-foreground"}`}>{v}</button>)}
            </div>
          )}
          {view === "2D" ? d.rects && <Geometry d={d} /> : <div className="w-[min(36rem,100%)]"><Cell3D cell={cell!} /></div>}
          {view === "2D" && d.rects && <div className="flex flex-wrap gap-x-2.5 gap-y-0.5">{SHAPES.map((l) => <span key={l} className="flex items-center gap-1 font-mono text-xs text-muted-foreground"><i className="size-2 rounded-sm" style={{ background: LAYER_COLOURS[l] }} />{l}</span>)}</div>}
        </div>
        <div className="flex min-w-0 flex-1 basis-[38rem] flex-col gap-1">
          {!full && attempts.length > 6 && <p className="text-xs text-muted-foreground">Latest 6 of {d.tried ?? attempts.length}. Open the step to see the rest.</p>}
          <Grid head={["#", "Sites", "Gate order", "Pads", "Style", "Gap", "Seeds", "Layer", "Unrouted"]}
            rows={last.map((a) => [a.n, a.sites, a.order, a.pads, a.style, Array.isArray(a.gap) ? a.gap.join(", ") : a.gap, a.seeds, a.met1 ? "li1+met1" : "li1", a.failed.length ? <span className="text-destructive">{pretty(a.failed.join(" "))}</span> : <span className="text-success">routed</span>])} />
        </div>
      </div>
    </div>
  );
}

function FrameStage({ d, full }: { d: any; full: boolean }) {
  if (!d.frame) return null;
  const off = d.frame.filter((r: any) => !r.match);
  const span = (v: any) => (Array.isArray(v) ? v.join(" to ") : String(v));
  return (
    <div className="flex flex-col gap-3">
      <Stats items={[["Frame rows matched", `${d.frame.length - off.length} of ${d.frame.length}`], ["Pin errors", d.pins.length], ["met1 outside rails", `${d.wiring.met1_outside_rails_um2} µm²`], ["li1 present", d.wiring.li1_present ? "yes" : "no"], ["Implant errors", d.layers.length]]} />
      <Grid head={["Layer", "Measured (µm)", "plan_hd (µm)", ""]} rows={d.frame.map((r: any) => [r.layer, span(r.measured), span(r.plan_hd), <Good ok={r.match} />])} />
      {[...d.pins, ...d.layers].map((e: string, i: number) => <p key={i} className="font-mono text-xs text-destructive">{pretty(e)}</p>)}
    </div>
  );
}

const WHERE: Record<string, string> = { "drc_standalone.log": "standalone", "drc_side.log": "side", "drc_mirror.log": "mirror", "drc_self.log": "self", "drc_flip.log": "flip" };

function DrcStage({ items, d }: { items: Step[]; d: any }) {
  const runs = items.filter((x) => x.data?.log);
  const result = (log: string) => (log === "drc_standalone.log" ? d.standalone : d.fixtures?.[WHERE[log]] ?? (WHERE[log] === "side" ? d.side : undefined));
  return (
    <div className="flex flex-col gap-3">
      <Grid head={["Run", "State", "Errors", "Rules"]} rows={runs.map((r) => {
        const x = result(r.data.log);
        return [r.title.replace("Magic DRC: ", ""), r.state === "running" ? "running" : r.state === "ok" ? "finished" : "failed", x?.errors ?? "…", x?.rules?.join(" ") || "none"];
      })} />
      {d.note && <p className="text-xs text-muted-foreground">Note from the check: {d.note}</p>}
    </div>
  );
}

function ExtractStage({ d, full }: { d: any; full: boolean }) {
  if (!d.devices) return <p className="font-mono text-xs text-muted-foreground">Extracting</p>;
  return (
    <Grid head={["Device", "Type", "Gate", "Drain", "Source", "W (µm)", "L (µm)"]}
      rows={d.devices.map((t: any) => [t.name, t.type === "n" ? "NMOS" : "PMOS", t.gate, t.drain, t.source, t.w, t.l])} />
  );
}

function LvsStage({ d, full }: { d: any; full: boolean }) {
  if (!d.result) return <p className="font-mono text-xs text-muted-foreground">Comparing</p>;
  const sig = (t: any) => `${t.type === "n" ? "NMOS" : "PMOS"} ${t.gate} W=${t.w} L=${t.l}`;
  const tally = (l: any[]) => l.reduce((m, t) => m.set(sig(t), (m.get(sig(t)) ?? 0) + 1), new Map<string, number>());
  const a = tally(d.layout), b = tally(d.schematic);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2"><span className="text-xs text-muted-foreground">Netgen</span><Status value={d.result} /></div>
      {d.counts?.layout && <Grid head={["", "Layout", "Schematic"]} rows={[["Devices", d.counts.layout.devices, d.counts.schematic.devices], ["Nets", d.counts.layout.nets, d.counts.schematic.nets]]} />}
      {full && <Grid head={["Device class", "Layout", "Schematic"]} rows={[...new Set([...a.keys(), ...b.keys()])].sort().map((k) => [k, a.get(k) ?? 0, b.get(k) ?? 0])} />}
    </div>
  );
}

function RcStage({ d, full }: { d: any; full: boolean }) {
  if (!d.nets) return <p className="font-mono text-xs text-muted-foreground">Extracting parasitics</p>;
  const top = Math.max(...d.nets.map((n: any) => n.ff), 1e-9);
  const nets = [...d.nets].sort((a: any, b: any) => b.ff - a.ff);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-6"><Stats items={[["Resistors", d.resistors], ["Capacitors", d.capacitors]]} /><div className="flex items-center gap-2"><span className="text-xs text-muted-foreground">RC-LVS</span><Status value={d.result} /></div></div>
      <Grid head={["Net", "R sum (Ω)", "C sum (fF)", ""]}
        rows={nets.map((n: any) => [n.net, n.ohms, (n.ff).toFixed(3), <i className="block h-1.5 w-32 rounded-sm bg-muted"><i className="block h-full rounded-sm bg-info" style={{ width: `${(n.ff / top) * 100}%` }} /></i>])} />
    </div>
  );
}

function Wave({ d }: { d: any }) {
  const end = d.states.length * d.slot_ns, w = 720, lane = 26, names: string[] = d.inputs;
  const x = (t: number) => (t / end) * w;
  const top = names.length * lane + 8, h = top + 72;
  const logic = (k: number) => {
    const y = (on: number) => k * lane + (on ? 4 : 20);
    return d.states.map((s: number, i: number) => {
      const v = (s >> k) & 1;
      return `${i ? "L" : "M"}${x(i * d.slot_ns)} ${y(v)} L${x((i + 1) * d.slot_ns)} ${y(v)}`;
    }).join(" ");
  };
  const wave = d.wave.filter((p: number[]) => p[0] <= end).map((p: number[], i: number) => `${i ? "L" : "M"}${x(p[0])} ${top + 62 - (p[1] / 1.8) * 58}`).join(" ");
  return (
    <svg viewBox={`-26 0 ${w + 34} ${h}`} role="img" aria-label="Transient: inputs and output against time" className="w-full">
      {names.map((n, k) => (
        <g key={n}><text x={-22} y={k * lane + 16} fontSize={11} className="font-mono" fill="var(--muted-foreground)">{n}</text>
          <path d={logic(k)} fill="none" stroke="var(--muted-foreground)" strokeWidth={1} /></g>
      ))}
      <text x={-22} y={top + 36} fontSize={11} className="font-mono" fill="var(--foreground)">Y</text>
      <path d={wave} fill="none" stroke="var(--info)" strokeWidth={1.4} />
    </svg>
  );
}

function SpiceStage({ items, d, full }: { items: Step[]; d: any; full: boolean }) {
  if (!d.dc) return <p className="font-mono text-xs text-muted-foreground">{items.filter((x) => x.state === "running").map((x) => x.title).join(", ") || "Simulating"}</p>;
  const rows = Object.entries(d.dc as Record<string, number>).map(([r, v]) => [...bits(+r, d.inputs.length), (d.tt >> +r) & 1, Number(v).toFixed(3)]);
  return (
    <div className="flex flex-col gap-3">
      <Stats items={[["DC rows", rows.length], ["Transient toggles", d.states.length], ["Slot", `${d.slot_ns} ns`], ["Errors", d.errors.length]]} />
      <h4 className="text-xs font-medium text-muted-foreground">Transient on the RC netlist</h4>
      <Wave d={d} />
      <h4 className="text-xs font-medium text-muted-foreground">DC, every input row</h4>
      <Grid head={[...d.inputs, "Expected Y", "V(Y)"]} rows={rows} />
      {d.errors.map((e: string, i: number) => <p key={i} className="font-mono text-xs text-destructive">{pretty(e)}</p>)}
    </div>
  );
}

function VerilogStage({ d, full }: { d: any; full: boolean }) {
  if (!d.rows) return null;
  return (
    <Grid head={[...d.inputs, "Truth table", "Model", ""]}
      rows={Object.entries(d.rows as Record<string, string>).map(([r, v]) => [...bits(+r, d.inputs.length), (d.tt >> +r) & 1, v, <Good ok={String((d.tt >> +r) & 1) === v} />])} />
  );
}

function reply(text: string) {
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch { return text; }
}

function ModelStage({ items, full }: { items: Step[]; full: boolean }) {
  return (
    <div className="flex flex-col gap-2">
      {items.map((x) => (
        <div key={x.id} className="flex flex-col gap-1">
          <p className={`text-sm ${x.state === "bad" ? "text-destructive" : ""}`}>{pretty(x.title)}</p>
          {x.detail && <p className="font-mono text-xs text-muted-foreground">{pretty(x.detail)}</p>}
          {x.data?.action && <Stats items={[["Action", x.data.action], ["Order", x.data.order_index], ["Evidence", x.data.evidence_refs?.join(" ")]]} />}
          {full && x.data?.reply && <pre className="overflow-x-auto rounded-md border bg-background p-2.5 font-mono text-xs">{reply(x.data.reply)}</pre>}
        </div>
      ))}
    </div>
  );
}

function Plain({ items }: { items: Step[] }) {
  return <ul className="flex flex-col gap-1">{items.map((x) => <li key={x.id} className="text-sm">{pretty(x.title)}{x.detail && <span className="block font-mono text-xs text-muted-foreground">{pretty(x.detail)}</span>}</li>)}</ul>;
}

/** A stage's output, compact in the run overview and in full on its own page. */
export function StepBody({ id, items, chosen, cell, full }: { id: string; items: Step[]; chosen?: string; cell?: string; full: boolean }) {
  const d = Object.assign({}, ...items.map((x) => x.data ?? {}));
  switch (id) {
    case "network": return <NetworkStage d={d} full={full} />;
    case "euler": return <EulerStage d={d} chosen={chosen} full={full} />;
    case "layout": return <LayoutStage d={d} cell={cell} full={full} />;
    case "frame": return <FrameStage d={d} full={full} />;
    case "drc": case "abutment": return <DrcStage items={items} d={d} />;
    case "extract": return <ExtractStage d={d} full={full} />;
    case "lvs": return <LvsStage d={d} full={full} />;
    case "rc": return <RcStage d={d} full={full} />;
    case "spice": return <SpiceStage items={items} d={d} full={full} />;
    case "verilog": return <VerilogStage d={d} full={full} />;
    case "model": return <ModelStage items={items} full={full} />;
    default: return <Plain items={items} />;
  }
}

export function LogView({ cell, name }: { cell: string; name: string }) {
  const { data, error } = useEvidence<{ lines: number; text: string }>(cell, `log&name=${name}`);
  if (error) return <p className="text-xs text-muted-foreground">This log is not saved for this cell.</p>;
  if (!data) return <p className="text-xs text-muted-foreground">Loading</p>;
  return <pre className="overflow-x-auto rounded-md border bg-background p-2.5 font-mono text-xs leading-relaxed">{data.text}</pre>;
}
