# web/: Atlas Cell Studio front end

The studio has one tab per option, and the agent panel on the right is shared by both:

- **Option 1 · Cells**: the live run of a cell build, described below.
- **Option 2 · Designs**: Option 2's saved Milestone 2 records (`src/Option2.tsx`): status and open items,
  measured savings, ranked candidates, the area model, every mapping with its equivalence and timing, and, for
  Option 3, what Option 1 answered for each requested cell. They come from `/api/option2`, which only reads
  `results/m2/` and `cells/<name>/response.json`.
- **Evidence**: Option 1 Milestone 2's saved records.

The agent answers Option 2 questions from those records, with the same number check as every answer, opens the
section a question is about, and builds a requested candidate with Option 1 on request ("build candidate M2-002").

A generative UI for the Option 1 agent. Its few UI primitives are in `src/ui.tsx`, and its colours in `src/app.css`.

    make agent-server   # back end on 127.0.0.1:8123
    make web            # front end on 127.0.0.1:5173

The mic (`src/useMic.ts`), or right Option on its own, records 16 kHz audio in the browser, ends when you stop talking, and posts it to
`/api/transcribe`. `agent/dd2_agent/voice.py` runs Parakeet TDT 0.6 v3 on this machine, from the path in
`config/agent.toml`, and the text lands in the box for you to edit and send. Audio is never stored. Install it with
`uv pip install -e ".[voice]"`. Without the model, the mic says so and the rest of the app is unaffected.

## How a page reaches the screen

1. The browser posts to `/agent` with `@ag-ui/client`. One thread is one session, so follow-ups see the cell.
2. `agent/dd2_agent/server.py` streams AG-UI events: `STEP_*` for the graph nodes, `STATE_SNAPSHOT` for the
   revisions, `CUSTOM` (`atlas`) for each step, tool call and chat reply.
3. The agent's last message is a page in OpenUI Lang, written by the Research Explainer or by
   `generative_ui.fixed_page`. `check_page` reads a model's page before it leaves the server.
4. `<Renderer>` draws that page from the closed library in `src/library.tsx`. `npm run prompt` writes the
   library's description to `prompts/ui_library.md`, so the model and the renderer cannot drift apart.

The panels take handles such as `cell:A-1102-01/web_cell_r0`, and fetch their numbers from `/api/evidence`.
So a model can choose and order panels, and write Notes, but it cannot put a result on the page.

A `Choice` is a button with a prompt the agent wrote. Pressing it shows the prompt in the box and sends it,
through the same guarded path as typing. It grants nothing a person could not ask for.

Closing the tab, refreshing or pressing Stop drops the connection. The server then kills the build's
process group, its labelled Docker containers and any model call.

The Evidence tab reads the saved milestone records, so it is full before anything runs here.

## The Workbench

Three columns from `lg`, and one pane with a bottom nav below that.

- **Pipeline** (`Steps.tsx`): every stage of `stages.ts` with its state and time. Pressing one opens it.
- **Run** (`RunView.tsx`): the overview lists what ran, in order, with each stage's real output. Earlier
  revisions fold. A stage's own page adds the full tables, each call's command and its raw log.
- **Agent** (`Chat.tsx`): the conversation, with model calls, tool calls and guardrail decisions between the
  messages. They stay one line each until opened. Each build sends a short update per phase, written by code
  from what the flow reported, and the run ends with a closing summary.

The overview scrolls to the step that is working, until you scroll yourself. Time estimates are the median of
past runs of the same kind (`agent/dd2_agent/timings.py`, stored in `build/stage_times.jsonl`), so there are none
until a real build has finished. A question about the project gets an answer from the notes in
`prompts/interpreter.md`, and code refuses any number that is not in those notes.

Nothing inside the page scrolls on its own, and text is never cut off. Every table and graph in `stepviews.tsx` draws data from a flow event. `src/cellgen/stepdata.py` turns tool
output into that data, and decides nothing: pass and fail still come only from the check scripts. The 3D
layer stack is a small option on the layout page.
