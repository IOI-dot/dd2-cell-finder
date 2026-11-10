import { Button } from "./ui";
import { useEffect, useMemo, useState } from "react";
import { LAYER_COLOURS, Panel, Waiting } from "./panels";
import { useEvidence } from "./useEvidence";

type Wave = { slot_ns: number; states: number[]; t_ns: number[]; y_v: number[]; vdd: number };
type Bits = { inputs: string[]; rows: Record<string, number>[] };
type Summary = { transistors: { kind: string; gate: string; w: number; l: number; x: number }[]; sites: number };
type Layout = { width_um: number; height_um: number; layers: Record<string, number[][][]> };

/* The Silicon Time Machine: the slider moves along the transient the SPICE check judged. The input state
   comes from that run's stimulus, the curve from ngspice, and which devices conduct from the schematic. */
export function TimeMachineView({ cell }: { cell: string }) {
  const wave = useEvidence<Wave>(cell, "waveform");
  const bits = useEvidence<Bits>(cell, "bits");
  const sum = useEvidence<Summary>(cell);
  const lay = useEvidence<Layout>(cell, "layout");
  const [t, setT] = useState(0.5);
  const [play, setPlay] = useState(false);
  const w = wave.data;
  const end = w ? w.t_ns[w.t_ns.length - 1] : 1;

  useEffect(() => {
    if (!play) return;
    const id = setInterval(() => setT((x) => (x + end / 400 > end ? 0 : x + end / 400)), 40);
    return () => clearInterval(id);
  }, [play, end]);

  const path = useMemo(() => {
    if (!w) return "";
    return w.t_ns.map((x, i) => `${i ? "L" : "M"}${(x / end) * 1000} ${100 - (w.y_v[i] / w.vdd) * 90}`).join(" ");
  }, [w, end]);

  if (!w || !bits.data || !sum.data || !lay.data) return <Waiting error={wave.error || bits.error} />;
  const slot = Math.min(w.states.length - 1, Math.floor(t / w.slot_ns));
  const row = w.states[slot];
  const nets = bits.data.rows[row];
  const y = w.y_v[Math.max(0, w.t_ns.findIndex((x) => x >= t))] ?? 0;
  const H = lay.data.height_um;
  const on = (d: Summary["transistors"][0]) => nets[d.gate] === (d.kind === "n" ? 1 : 0);
  return (
    <Panel title="Silicon Time Machine" note={`${w.states.length} steps of the ngspice transient · every state, every toggle`} wide>
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <svg viewBox={`-0.2 -0.2 ${lay.data.width_um + 0.4} ${H + 0.4}`} role="img" aria-label="Devices that conduct in this input state" className="w-full rounded-md bg-background">
          <g transform={`matrix(1 0 0 -1 0 ${H})`}>
            {(["diff", "poly"] as const).map((l) => (
              <g key={l} fill={LAYER_COLOURS[l]} fillOpacity={0.14} stroke={LAYER_COLOURS[l]} strokeOpacity={0.25} strokeWidth={0.006}>
                {lay.data!.layers[l].map((p, i) => <polygon key={i} points={p.map((q) => q.join(",")).join(" ")} />)}
              </g>
            ))}
            {sum.data.transistors.map((d, i) => {
              const y0 = d.kind === "n" ? 0.235 : 2.485 - d.w;
              return <rect key={i} data-on={on(d)} x={d.x} y={y0} width={d.l} height={d.w} fill={on(d) ? "#34c77b" : "#f2562b"} fillOpacity={on(d) ? 0.95 : 0.16} />;
            })}
          </g>
        </svg>
        <div className="flex min-w-0 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
            {bits.data.inputs.map((x) => <span key={x} className={`rounded border px-2 py-0.5 ${nets[x] ? "border-primary text-primary" : "text-muted-foreground"}`}>{x}={nets[x]}</span>)}
            <span className="rounded border border-info px-2 py-0.5 text-info" data-testid="tm-y">Y = {y.toFixed(3)} V</span>
            <span className="ml-auto text-muted-foreground">{t.toFixed(2)} ns</span>
          </div>
          <svg viewBox="0 0 1000 110" preserveAspectRatio="none" role="img" aria-label="Output voltage over time" className="h-32 w-full rounded-md bg-background">
            <path d={path} fill="none" stroke="var(--info)" strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
            <line x1={(t / end) * 1000} x2={(t / end) * 1000} y1={0} y2={110} stroke="var(--primary)" vectorEffect="non-scaling-stroke" />
          </svg>
          <input type="range" aria-label="Time" min={0} max={end} step={end / 2000} value={t} onChange={(e) => { setPlay(false); setT(Number(e.target.value)); }} className="w-full accent-primary" />
          <div className="flex items-center gap-3">
            <Button size="sm" variant="outline" className="min-h-11 lg:min-h-8" onClick={() => setPlay((p) => !p)}>{play ? "Pause" : "Play"}</Button>
            <span className="text-xs text-muted-foreground">Green devices conduct in this state, red ones are off. A path of green from Y to a rail is what drives it.</span>
          </div>
        </div>
      </div>
    </Panel>
  );
}
