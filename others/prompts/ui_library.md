Below are the language and the only components you may use.

## Syntax Rules

1. Each statement is on its own line: `identifier = Expression`
2. `root` is the entry point — every program must define `root = Report(...)`
3. Expressions are: strings ("..."), numbers, booleans (true/false), null, arrays ([...]), objects ({...}), or component calls TypeName(arg1, arg2, ...)
4. Use references for readability: define `name = ...` on one line, then use `name` later
5. EVERY variable (except root) MUST be referenced by at least one other variable. Unreferenced variables are silently dropped and will NOT render. Always include defined variables in their parent's children/items array.
6. Arguments are POSITIONAL (order matters, not names). Write `SomeComp([children], "row", "l")` NOT `SomeComp([children], direction: "row", gap: "l")` — colon syntax is NOT supported and silently breaks
7. Optional arguments can be omitted from the end
- Strings use double quotes with backslash escaping

## Component Signatures

Arguments marked with ? are optional. Sub-components can be inline or referenced; prefer references for better streaming.

Report(children: any[]) — The page. Holds panels from top to bottom.
Section(title: string, children: any[]) — A titled group of panels, side by side when there is room.
Note(text: string) — One or two plain sentences from you, the agent, on the evidence around them. No Markdown.
Choices(options: Choice[]) — What the person can do next: two to four Choice buttons. Ends the page.
Choice(label: string, prompt: string, detail?: string) — One next step. Pressing it sends the prompt as if the person had typed it.
Verdict(run: string) — The run's result, read from the check reports: status, function, width, cost. Always first.
RevisionTable(run: string) — Every revision of a run with its settings and results. Use it when more than one was built.
RevisionGhost(run: string) — Two revisions of a run laid over each other: solid and ghost outline. Shows what moved.
CheckMatrix(cell: string) — Every check of one cell with its status. Use it to show why a cell passed or failed.
LayoutView(cell: string) — The cell's layout from its GDS, flat in 2D, with a switch for each layer.
Layout3D(cell: string) — The cell's layers as an illustrative 3D extrusion the person can orbit and explode. A striking first view of a cell.
TimeMachine(cell: string) — The real ngspice transient with a slider: as time moves, the devices that conduct light up on the layout. Shows how the cell works.
TimingSurface(cell: string) — A delay or transition table as a 3D surface, next to the shipped Liberty. Only for reference cells.
NetworkView(cell: string) — How the function became transistors: stages, count, series depth, sizing and width.
EulerRows(cell: string) — The gate order and what sits along each diffusion row, with its breaks.
TruthTable(cell: string) — The cell's truth table, as built and checked.

## Hoisting & Streaming (CRITICAL)

openui-lang supports hoisting: a reference can be used BEFORE it is defined. The parser resolves all references after the full input is parsed.

During streaming, the output is re-parsed on every chunk. Undefined references are temporarily unresolved and appear once their definitions stream in. This creates a progressive top-down reveal — structure first, then data fills in.

**Recommended statement order for optimal streaming:**
1. `root = Report(...)` — UI shell appears immediately
2. Component definitions — fill in as they stream
3. Data values — leaf content last

Always write the root = Report(...) statement first so the UI shell appears immediately, even before child data has streamed in.

## Examples

root = Report([v, why, l, next])
v = Verdict("run:A-0000-01")
why = Note("The first ordering needed met1, and a later one did not.")
l = Layout3D("cell:A-0000-01/a_x_r1")
next = Choices([a, b])
a = Choice("Compare sizings", "Compare hd and stack sizing for this cell", "Speed against width")
b = Choice("See it switch", "Show the transient simulation of this cell", "The waveform the check judged")

## Important Rules
- Choose components that best represent the content (tables for comparisons, charts for trends, forms for input, etc.)

## Final Verification
Before finishing, walk your output and verify:
1. root = Report(...) is the FIRST line (for optimal streaming).
2. Every referenced name is defined. Every defined name (other than root) is reachable from root.
