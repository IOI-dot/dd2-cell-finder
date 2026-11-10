import { Button } from "./ui";
import { Card } from "./ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui";
import { useEffect, useState } from "react";
import { Cell3D } from "./Layout3D";
import { Panel, Status } from "./panels";
import { TimingView } from "./TimingSurface";

type Row = Record<string, string>;
type Overview = { table4: Row[]; test_cells: Row[]; agent: Row[]; timing: Row[];
  table5: { requirements?: Record<string, unknown>; builds?: Record<string, { median_abs_pct: number; max_abs_pct: number; entries: number }>;
    cells?: Record<string, { median_abs_pct: number; stock_median_abs_pct: number }> } };

function Data({ rows, columns, caption }: { rows: Row[]; columns: [string, string][]; caption: string }) {
  const download = () => {
    const text = [columns.map((c) => c[1]).join(","), ...rows.map((r) => columns.map((c) => r[c[0]] ?? "").join(","))].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
    a.download = `${caption}.csv`;
    a.click();
  };
  return (
    <Panel title={caption} wide>
      <div className="flex justify-end"><Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={download}>Download CSV</Button></div>
      <Table>
        <TableHeader><TableRow>{columns.map((c) => <TableHead key={c[0]}>{c[1]}</TableHead>)}</TableRow></TableHeader>
        <TableBody>{rows.map((r, i) => <TableRow key={i}>{columns.map((c) => <TableCell key={c[0]} className="text-xs">{c[0] === "status" ? <Status value={r[c[0]]} /> : r[c[0]]}</TableCell>)}</TableRow>)}</TableBody>
      </Table>
    </Panel>
  );
}

/* The milestone records as saved by `make o1-m2`. Nothing here is computed or typed. */
export function Evidence() {
  const [o, setO] = useState<Overview>();
  const [ref, setRef] = useState("a21oi_1");
  const [failed, setFailed] = useState("");
  useEffect(() => {
    fetch("/api/overview").then((r) => (r.ok ? r.json() : Promise.reject(new Error(`it answered ${r.status}`)))).then(setO).catch((e) => setFailed(e.message));
  }, []);
  if (failed) return <p className="text-sm text-destructive">The records could not be loaded from the back end: {failed}. Check that make agent-server is running.</p>;
  if (!o) return <p className="text-sm text-muted-foreground">Loading the records…</p>;
  const t5 = o.table5;
  const cells: Row[] = Object.entries(t5.cells ?? {}).map(([c, v]) => ({ cell: c, fixed: String(v.median_abs_pct), stock: String(v.stock_median_abs_pct) }));
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold">Option 1, Milestone 2: saved records</h1>
        <p className="text-sm text-muted-foreground">Saved results of <code className="font-mono">make o1-m2</code>, read from <code className="font-mono">results/option1/m2/</code>. They exist before anything runs here, and nothing you do in the Workbench changes them.</p>
      </header>
      <section className="grid gap-4 md:grid-cols-2">
        {Object.entries(t5.builds ?? {}).map(([k, v]) => (
          <Card key={k} className="gap-1 px-4 py-4">
            <span className="text-xs text-muted-foreground">{k} ngspice, median error against the shipped Liberty</span>
            <b className="font-mono text-3xl font-semibold text-info">{v.median_abs_pct}%</b>
            <span className="text-xs text-muted-foreground">{v.entries} table entries, max {v.max_abs_pct}%</span>
          </Card>
        ))}
      </section>
      <Panel title="Table 5 requirements" wide>
        <ul className="grid gap-1 text-xs md:grid-cols-2">
          {Object.entries(t5.requirements ?? {}).map(([k, v]) => <li key={k} className="flex items-center gap-2"><Status value={v === true || v === "pass" ? "pass" : "fail"} />{k.replaceAll("_", " ")}</li>)}
        </ul>
      </Panel>
      <div className="flex flex-wrap items-center gap-1">
        <span className="mr-2 text-xs text-muted-foreground">Reference cell</span>
        {["inv_1", "nand2_1", "nor2_1", "nand3_1", "a21oi_1", "o21ai_1"].map((c) => <Button key={c} size="sm" variant={c === ref ? "default" : "outline"} className="h-6 px-2 font-mono text-xs" onClick={() => setRef(c)}>{c}</Button>)}
      </div>
      <TimingView key={`t${ref}`} cell={`cell:dd2_ref__${ref}`} />
      <Cell3D key={`c${ref}`} cell={`cell:dd2_ref__${ref}`} />
      <Data caption="Median error per cell (%)" rows={cells} columns={[["cell", "Cell"], ["fixed", "Fixed"], ["stock", "Stock"]]} />
      <Data caption="Table 4 reference cells" rows={o.table4} columns={[["cell", "Cell"], ["status", "Result"], ["frame", "Frame"], ["transistors_lvs", "LVS vs HD"], ["rc_lvs", "RC-LVS"], ["pins", "Pins"], ["wiring", "Wiring"], ["abutment_errors", "Abutment"], ["sites_ours", "Sites"], ["sites_installed", "HD sites"]]} />
      {!!o.timing.length && <Data caption="Table 4 timing" rows={o.timing} columns={[["cell", "Cell"], ["median_vs_installed_pct", "Median vs installed (%)"], ["median_vs_shipped_pct", "Median vs shipped (%)"]]} />}
      <Data caption="Table 6 test cells" rows={o.test_cells} columns={[["cell", "Cell"], ["expression", "Function"], ["status", "Result"], ["stages", "Stages"], ["transistors", "T"], ["sites", "Sites"], ["met1_nets", "met1 nets"], ["drc", "DRC"], ["lvs", "LVS"], ["rc_lvs", "RC-LVS"], ["spice", "SPICE"]]} />
      {!!o.agent.length && <Data caption="Agent and fixed choices" rows={o.agent} columns={[["function", "Function"], ["mode", "Mode"], ["status", "Result"], ["sites", "Sites"], ["met1_nets", "met1 nets"], ["breaks", "Breaks"], ["builds", "Builds"], ["model_calls", "Model calls"], ["seconds", "Seconds"]]} />}
    </div>
  );
}
