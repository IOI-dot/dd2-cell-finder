# web/: Atlas Cell Studio front end

A generative UI for the Option 1 agent, on the Design System Studio components and the Graphite Cyan
theme. It needs `DesignSystemStudio/` beside it on the machine, which is deliberately not in git.

    make agent-server   # back end on 127.0.0.1:8123
    make web            # front end on 127.0.0.1:5173

## How a page reaches the screen

1. The browser posts to `/agent` with `@ag-ui/client`. One thread is one session, so follow-ups see the cell.
2. `agent/dd2_agent/server.py` streams AG-UI events: `STEP_*` for the graph nodes, `STATE_SNAPSHOT` for the
   revisions, `CUSTOM` (`atlas`) for each line of the activity feed.
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
