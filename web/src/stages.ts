/* The pipeline as it really runs. Nothing here is a result: results only arrive as events from the check scripts. */
export type Stage = { id: string; name: string; tool: string; group: string; about: string };

export const STAGES: Stage[] = [
  { id: "request", name: "Request", tool: "parser", group: "Request", about: "Reads the request and fixes the truth table. Everything later is checked against it." },
  { id: "model", name: "Agent decisions", tool: "LangGraph", group: "Request", about: "Each model call, its reply, and what the guardrails did with it. The model picks generator settings from a closed list and never decides a result." },
  { id: "network", name: "CMOS network", tool: "cellgen.network", group: "Design", about: "Builds the pull-up and pull-down networks, then checks every input row at switch level." },
  { id: "euler", name: "Euler ordering", tool: "cellgen.euler", group: "Design", about: "Candidate gate orders. One order serves both diffusion rows, and neighbours that share a net share diffusion." },
  { id: "layout", name: "Place and route", tool: "cellgen.layout", group: "Design", about: "Tries each combination of gate order, pad pattern, gap and contact seeds, narrowest first. The first that routes wins." },
  { id: "frame", name: "Frame and pins", tool: "KLayout", group: "Physical checks", about: "Measures the cell against the HD frame in plan_hd.json, with its pins, wiring layers and implants." },
  { id: "drc", name: "Design rules", tool: "Magic", group: "Physical checks", about: "Full DRC on the cell alone and in a tap row. A cell alone may only fail the tap rules." },
  { id: "abutment", name: "Abutment", tool: "Magic", group: "Physical checks", about: "DRC with real HD cells at the sides, mirrored, next to itself and flipped onto a shared rail." },
  { id: "extract", name: "Extraction", tool: "Magic", group: "Physical checks", about: "Reads the transistors and nets back from the drawn geometry, ignoring what was intended." },
  { id: "lvs", name: "LVS", tool: "Netgen", group: "Physical checks", about: "Compares the extracted circuit with the schematic, device by device, with W and L." },
  { id: "rc", name: "RC and RC-LVS", tool: "Magic, Netgen", group: "Physical checks", about: "Extracts wire resistance and capacitance, and checks the circuit still matches with them in." },
  { id: "spice", name: "SPICE simulation", tool: "ngspice", group: "Simulation", about: "DC on every input row, then a transient that toggles each input from every state, on the RC netlist." },
  { id: "verilog", name: "Verilog model", tool: "Icarus", group: "Simulation", about: "Runs the Verilog model on every input row and compares it with the truth table." },
  { id: "verdict", name: "Verdict", tool: "check report", group: "Result", about: "Read from the check report. The model cannot change it." },
  { id: "report", name: "Report page", tool: "explainer", group: "Result", about: "The model arranges panels. Each panel fetches its numbers from the recorded results." },
];

export const stageOf = (id: string) => ({ interpreter: "model", diagnostician: "model", explainer: "report", rc_lvs: "rc" }[id] ?? id);
export const stage = (id: string) => STAGES.find((s) => s.id === stageOf(id));

/* Median seconds per stage in past runs (server: agent/dd2_agent/timings.py). None until a run has been recorded. */
export type Estimates = Record<string, Record<string, { seconds: number; runs: number }>>;
