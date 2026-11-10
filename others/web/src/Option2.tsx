import { useEffect, useState } from "react";
import { Status } from "./panels";
import { Grid, Stats } from "./stepviews";
import { Rich } from "./text";

type Row = Record<string, string>;
type Answer = { request_id: string; name: string; option1: string; real_area_um2: number | null; reason: string };
type View = {
  readiness: { checkpoint_ready?: boolean; experimental_flow_status?: string; checks?: Record<string, boolean>; remaining?: string[]; final_only?: string[] };
  area_model: { loo_mean_absolute_percent_error?: number; training_cells?: number };
  counts: { candidates: number; eligible: number; requested: number };
  candidates: (Row & { request: Answer | null })[];
  best_of_both: Row[]; mappings: Row[]; figures: string[];
  option3: { cells: Answer[]; summary: Record<string, unknown> | null; best_of_both: Row[] };
};

export const SECTIONS: [string, string][] = [["o2-status", "Status"], ["o2-savings", "Measured savings"], ["o2-candidates", "Candidates"],
  ["o2-model", "Area model"], ["o2-mappings", "Mappings"], ["o2-cells", "Option 3: real cells"]];

const pct = (v?: string) => (v === undefined || v === "" ? "" : `${Number(v).toFixed(3)}%`);
const um2 = (v?: string | number | null) => (v === undefined || v === null || v === "" ? "" : Number(v).toFixed(4));
const FIGURE_NOTE: Record<string, string> = {
  "01_area_model_validation.png": "Held-out predictions against the HD cell areas. The dashed line is an exact prediction.",
  "02_candidate_ranking.png": "Predicted savings used for ranking: a heuristic. Overlapping cuts and remapping change the outcome.",
  "03_measured_area_reduction.png": "Measured from the baseline and extended mappings, the smaller A/B area on each side.",
};

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="flex scroll-mt-4 flex-col gap-3">
      <h2 className="text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Option1Answer({ a }: { a: Answer | null }) {
  if (!a) return <span className="text-muted-foreground">not requested</span>;
  return <span className="inline-flex items-center gap-2"><span className="font-mono">{a.request_id}</span><Status value={a.option1} /></span>;
}

/** Option 2's saved records. Nothing here is recomputed: every value is read from results/m2 and the cells' responses. */
export function Option2View() {
  const [v, setV] = useState<View>();
  const [failed, setFailed] = useState("");
  useEffect(() => {
    fetch("/api/option2").then((r) => (r.ok ? r.json() : Promise.reject(new Error(`it answered ${r.status}`)))).then(setV).catch((e) => setFailed(e.message));
  }, []);
  if (failed) return <p className="p-6 text-sm text-destructive">Option 2's records could not be loaded from the back end: {failed}. Check that make agent-server is running.</p>;
  if (!v) return <p className="p-6 text-sm text-muted-foreground">Loading Option 2's records</p>;
  const r = v.readiness;
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-8 overflow-auto p-4 lg:p-6">
      <Section id="o2-status" title="Status">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-muted-foreground">Experimental flow</span><Status value={r.experimental_flow_status ?? "unknown"} />
          <span className="text-muted-foreground">Checkpoint ready</span><Status value={r.checkpoint_ready ? "pass" : "fail"} />
        </div>
        {r.checks && <Grid head={["Check", "Result"]} rows={Object.entries(r.checks).map(([k, ok]) => [k.replaceAll("_", " "), <Status value={ok ? "pass" : "fail"} />])} />}
        {!!r.remaining?.length && (
          <div className="rounded-md border border-warning/40 px-3 py-2 text-sm">
            <p className="font-medium">Open</p>
            <ul className="list-disc pl-5">{r.remaining.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
        )}
        <p className="text-xs text-muted-foreground">Areas below use estimated cells; their timing and capacitance are placeholders. Measured savings can be zero or negative and are shown as they are.</p>
      </Section>

      <Section id="o2-savings" title="Measured savings, best of scripts A and B">
        <Grid head={["Design", "Baseline (µm²)", "Extended (µm²)", "Saving (µm²)", "Reduction"]}
          rows={v.best_of_both.map((b) => [b.design, um2(b.baseline_best_um2), um2(b.extended_best_um2), um2(b.saving_um2),
            <span className={Number(b.reduction_pct) < 0 ? "text-destructive" : Number(b.reduction_pct) > 0 ? "text-success" : ""}>{pct(b.reduction_pct)}</span>])} />
        {v.figures.includes("03_measured_area_reduction.png") && <Figure name="03_measured_area_reduction.png" />}
      </Section>

      <Section id="o2-candidates" title="Candidates">
        <Stats items={[["Classes found", v.counts.candidates], ["Eligible", v.counts.eligible], ["Requested from Option 1", v.counts.requested]]} />
        <Grid head={["Rank", "Function", "Class", "Transistors", "Stages", "Est. area (µm²)", "Mapped uses", "Predicted saving (µm²)", "Option 1"]}
          rows={v.candidates.map((c) => [c.rank, <Rich text={c.expression} />, c.redundancy_class, c.transistors, c.stages, um2(c.estimated_area_um2),
            c.mapped_occurrences, um2(c.estimated_best_of_both_saving_um2), <Option1Answer a={c.request} />])} />
        <p className="text-xs text-muted-foreground">The first {v.candidates.length} of {v.counts.eligible} eligible candidates. Predicted saving ranks them; the measured remapping above decides.</p>
        {v.figures.includes("02_candidate_ranking.png") && <Figure name="02_candidate_ranking.png" />}
      </Section>

      <Section id="o2-model" title="Area model">
        <Stats items={[["HD cells fitted", v.area_model.training_cells ?? ""], ["Held-out mean error", v.area_model.loo_mean_absolute_percent_error === undefined ? "" : `${v.area_model.loo_mean_absolute_percent_error.toFixed(2)}%`]]} />
        {v.figures.includes("01_area_model_validation.png") && <Figure name="01_area_model_validation.png" />}
      </Section>

      <Section id="o2-mappings" title="Mappings, with equivalence and timing">
        <Grid head={["Design", "Script", "Baseline (µm²)", "Extended (µm²)", "New cells used", "CEC baseline", "CEC extended", "Delay baseline (ns)", "Delay extended (ns)", "Note"]}
          rows={v.mappings.map((m) => [m.design, m.script, um2(m.baseline_um2), um2(m.extended_um2), m.new_cell_instances,
            <Status value={m.baseline_equivalence} />, <Status value={m.extended_equivalence} />, m.baseline_delay_ns, m.extended_delay_ns, m.effect_note])} />
      </Section>

      <Section id="o2-cells" title="Option 3: the requested cells, built by Option 1">
        <p className="text-sm text-muted-foreground">Each request goes to Option 1 in the Appendix A format. Only a cell that passes every check, with its Liberty file, can replace the estimated one.</p>
        <Grid head={["Request", "Cell", "Option 1", "Estimated area (µm²)", "Real area (µm²)", "Option 1's reason"]}
          rows={v.option3.cells.map((a) => {
            const est = v.candidates.find((c) => c.request?.request_id === a.request_id)?.estimated_area_um2;
            return [a.request_id, a.name, <Status value={a.option1} />, um2(est), um2(a.real_area_um2), <span className="whitespace-normal">{a.reason}</span>];
          })} />
        {v.option3.best_of_both.length > 0 ? (
          <>
            <h3 className="text-sm font-medium">Measured savings with the real cells</h3>
            <p className="text-xs text-muted-foreground">Mapped on this machine's tools, so these numbers are not comparable with the M2 rows above; run <code className="font-mono">make o3-map</code> on the M2 toolchain for that. A mapping that used none of the new cells changed only because the library grew: its saving is not the new cells' doing. Each mapping's note is in <code className="font-mono">results/option3/table5_estimated.csv</code>.</p>
            <Grid head={["Design", "Baseline (µm²)", "With real cells (µm²)", "Saving (µm²)", "Reduction"]}
              rows={v.option3.best_of_both.map((b) => [b.design, um2(b.baseline_best_um2), um2(b.extended_best_um2), um2(b.saving_um2), pct(b.reduction_pct)])} />
          </>
        ) : <p className="text-sm text-muted-foreground">The designs have not been remapped with real cells yet.</p>}
      </Section>
    </div>
  );
}

function Figure({ name }: { name: string }) {
  return (
    <figure className="flex flex-col gap-1">
      <img src={`/api/option2/figure/${name}`} alt={FIGURE_NOTE[name] ?? name} className="w-full max-w-3xl rounded-md border bg-white" />
      {FIGURE_NOTE[name] && <figcaption className="text-xs text-muted-foreground">{FIGURE_NOTE[name]}</figcaption>}
    </figure>
  );
}

export function Option2Nav({ active, onPick }: { active: string; onPick: (id: string) => void }) {
  return (
    <nav aria-label="Option 2" className="flex flex-col gap-0.5">
      <h3 className="px-2 pb-0.5 text-xs font-medium text-muted-foreground">Option 2, Milestone 2</h3>
      {SECTIONS.map(([id, name]) => (
        <button key={id} aria-current={active === id} onClick={() => onPick(id)}
          className={`flex min-h-8 w-full items-center rounded-md px-2 text-left text-sm ${active === id ? "bg-sidebar-accent font-medium text-foreground" : "text-foreground hover:bg-sidebar-accent/50"}`}>{name}</button>
      ))}
    </nav>
  );
}
