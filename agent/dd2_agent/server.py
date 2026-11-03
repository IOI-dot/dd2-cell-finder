"""The web back end: `make agent-server`.

  POST /agent                 the agent over AG-UI (ag-ui-langgraph streams its events)
  GET  /api/evidence/{handle} read-only evidence for the panels, by the handles of generative_ui.py
  GET  /api/overview          the milestone tables
  GET  /api/estimates         how long each stage took in past runs
  POST /api/transcribe        a short WAV recording to text, on this machine
  POST /v1/chat/completions   the model as a normal chat API (agent/dd2_agent/codex_cli.py)

A handle is checked against one pattern and then resolved inside `runs/`, `cells/` or `ai/runs/`, so
no request can name a path. Everything here reads, and only the agent's tools write, under their policy.
Binds to localhost: authentication and rate limits belong to the platform backend of Backend.md.
"""
import asyncio
import csv
import json
import os
import re
from pathlib import Path

from ag_ui.core.types import RunAgentInput
from ag_ui.encoder import EventEncoder
from ag_ui_langgraph import LangGraphAgent
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dd2 import paths

from . import audit, codex_cli, generative_ui, graph, model, timings, voice

ROOT = paths.ROOT
M2 = paths.results("option1", "m2")
LAYERS = ("nwell", "diff", "poly", "li1", "met1", "licon", "mcon")
CONTACTS = {"licon": (66, 44), "mcon": (67, 44)}
LOG_NAME = re.compile(r"[a-z0-9_]{1,40}\.(log|out)")
LOG_LINES = 400


def resolve(handle: str) -> tuple:
    """(kind, path of its JSON) for a valid handle. Raises 404 for anything else."""
    if not generative_ui.HANDLE.match(handle):
        raise HTTPException(404, "unknown handle")
    kind, rest = handle.split(":", 1)
    if kind == "run":
        p = audit.LOG_DIR / f"{rest}.checks.json"
    elif "/" in rest:
        run, cell = rest.split("/", 1)
        p = ROOT / "runs" / run / "cells" / cell / "report.json"
    else:
        p = ROOT / "cells" / rest / "report.json"
    if not p.is_file() or not p.resolve().is_relative_to(ROOT.resolve()):
        raise HTTPException(404, "no such evidence")
    return kind, p


def cell_view(report: dict) -> dict:
    """What the panels show of a report: the check statuses, never a free-form log."""
    ck = report.get("checks", {})
    rows = [{"check": k, "status": v.get("status", "?"), "detail": "tap rules only" if k == "drc_standalone" and v.get("errors") else
             next((str(v[x]) for x in ("errors", "result") if x in v and not isinstance(v[x], list)), "")}
            for k, v in ck.items() if isinstance(v, dict)]
    lay = report.get("layout", {})
    inputs = report.get("inputs", [])
    tt = int(report.get("truth_table", "0x0"), 16)
    return {"cell": report.get("cell"), "status": report.get("status"), "failed": report.get("failed_checks", []), "checks": rows,
            "inputs": inputs, "truth": [{"row": i, "y": (tt >> i) & 1} for i in range(1 << len(inputs))],
            "sites": lay.get("width_sites"), "width_um": lay.get("width_um"), "gate_order": lay.get("gate_order"),
            "gate_pitch_um": lay.get("gate_pitch_um"), "breaks": lay.get("row_breaks"), "met1_nets": lay.get("met1_nets") or [],
            "transistors": lay.get("transistors"), "rows": ck.get("ordering", {}).get("rows"),
            "network": {k: ck.get("network", {}).get(k) for k in ("transistors", "stages", "stage_outputs", "max_series")},
            "sizing": report.get("sizing"), "layout_options": report.get("layout_options")}


def log_view(report_path: Path, name: str) -> dict:
    """The end of one tool's raw log, by its file name. The name is checked, so it cannot leave the cell."""
    if not LOG_NAME.fullmatch(name):
        raise HTTPException(404, "unknown log")
    cell = report_path.parent
    for folder in (cell / "logs", cell.parent.parent / "work" / cell.name):
        if (folder / name).is_file():
            lines = (folder / name).read_text(errors="replace").splitlines()
            return {"name": name, "lines": len(lines), "text": "\n".join(lines[-LOG_LINES:])}
    raise HTTPException(404, "no such log")


def layout_view(report_path: Path) -> dict:
    """The cell's polygons by layer, in um, for the layout panel."""
    import klayout.db as kdb

    from cellgen import compare
    gds = report_path.parent / "cell.gds"
    name = report_path.parent.name
    if not gds.is_file():
        raise HTTPException(404, "no layout")
    g = compare.Gds(gds, name)
    dbu = g.ly.dbu
    out = {}
    for layer in LAYERS:
        if layer in CONTACTS:
            li = g.ly.find_layer(*CONTACTS[layer])
            region = kdb.Region(g.cell.begin_shapes_rec(li)) if li is not None else kdb.Region()
        else:
            region = g.region(layer)
        out[layer] = [[[round(p.x * dbu, 3), round(p.y * dbu, 3)] for p in q.each_point_hull()] for q in region.each()]
    labels = [{"text": t, "x": x, "y": y} for t, x, y in g.labels() + g.labels("met1.label")]
    return {"cell": name, "width_um": g.width(), "height_um": 2.72, "layers": out, "labels": labels}


def bits_of(report_path: Path, report: dict) -> dict:
    """Value of every gate net in each input row, from the cell's own schematic, by switch-level
    relaxation: what the lens lights up is computed from the netlist, not from the function."""
    devices = re.findall(r"^X\d+ (\S+) (\S+) (\S+) \S+ sky130_fd_pr__(n|p)fet", (report_path.parent / "schematic.spice").read_text(), re.M)
    inputs = report["inputs"]
    rows = []
    for row in range(1 << len(inputs)):
        val = {x: (row >> k) & 1 for k, x in enumerate(inputs)} | {"VGND": 0, "VPWR": 1}
        for _ in range(len(devices) + 2):
            changed = False
            parent = {}

            def find(x):
                parent.setdefault(x, x)
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for d, g, s_, kind in devices:
                if g in val and val[g] == (1 if kind == "n" else 0):
                    parent[find(d)] = find(s_)
            groups = {}
            for n in list(parent):
                groups.setdefault(find(n), []).append(n)
            for nets in groups.values():
                rail = next((val[n] for n in ("VGND", "VPWR") if n in nets), None)
                if rail is not None:
                    for n in nets:
                        if val.get(n) != rail:
                            val[n] = rail
                            changed = True
            if not changed:
                break
        rows.append({k: v for k, v in val.items() if k not in ("VGND", "VPWR")})
    return {"inputs": inputs, "rows": rows}


def waveform_view(report_path: Path, report: dict) -> dict:
    """The transient that the SPICE check judged, thinned for drawing, and the input state of each slot."""
    from cellgen import simulate
    run = report_path.parts[-4] if report_path.parts[-4].startswith("A-") else None
    name = report_path.parent.name
    work = ROOT / "runs" / run / "work" / name if run else ROOT / "build" / "cells" / name
    tran = work / "tran.txt"
    if not tran.is_file():
        raise HTTPException(404, "no transient on this machine")
    rows = [line.split() for line in tran.read_text().splitlines()[1:] if line.strip()]
    step = max(1, len(rows) // 1500)
    n = len(report["inputs"])
    return {"slot_ns": simulate.SLOT_NS, "states": simulate.sequence(n), "t_ns": [round(float(r[0]) * 1e9, 3) for r in rows[::step]],
            "y_v": [round(float(r[1]), 3) for r in rows[::step]], "vdd": simulate.VDD}


def timing_view(report_path: Path) -> dict:
    """Delay and transition tables of a reference cell, ours next to the shipped ones. Only the six
    validated cells have tables at this milestone."""
    from cellgen import characterize as ch
    name = report_path.parent.name.removeprefix("dd2_ref__")
    lib = M2 / "libs" / f"{name}_fixed.lib"
    if not lib.is_file():
        raise HTTPException(404, "no timing tables for this cell yet")
    text = lib.read_text()
    body = text[text.index("cell ("):]
    ours = []
    for m in re.finditer(r'related_pin : "(\w+)";.*?(?=timing \(\) \{|\Z)', body, re.S):
        for t in ch.TABLES.values():
            g = re.search(rf"\b{t}\s*\(", m.group(0))
            if g:
                b = ch._block(m.group(0), g.start())
                i1, i2 = ch._numbers(re.search(r'index_1\("([^"]+)"', b).group(1)), ch._numbers(re.search(r'index_2\("([^"]+)"', b).group(1))
                vals = ch._numbers(",".join(re.findall(r'"([^"]+)"', b[b.index("values"):])))
                ours.append({"pin": m.group(1), "table": t, "index_1": i1, "index_2": i2, "values": [vals[k * len(i2):(k + 1) * len(i2)] for k in range(len(i1))]})
    shipped = {(t["pin"], t["table"]): t["values"] for t in ch.read_cell(name)["tables"]}
    return {"cell": name, "tables": [t | {"shipped": shipped.get((t["pin"], t["table"]))} for t in ours]}


def _rows(name: str) -> list:
    p = M2 / name
    return list(csv.DictReader(open(p))) if p.is_file() else []


class ChatRequest(BaseModel):
    messages: list[dict]
    response_format: dict | None = None
    model: str | None = None


def create_app(cfg: dict | None = None) -> FastAPI:
    cfg = cfg or model.load_config()
    app = FastAPI(title="Atlas Cell Studio", version="0.2")
    app.add_middleware(CORSMiddleware, allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", allow_methods=["GET", "POST"], allow_headers=["*"])
    runs = {}

    def run_for(st, config, node):
        thread = config["configurable"]["thread_id"]
        if node == "intent_parser" or thread not in runs:
            runs[thread] = graph.Run("web_cell", cfg)
        return runs[thread]

    agent = LangGraphAgent(name="cell_agent", graph=graph.build_graph(run_for))

    @app.post("/agent")
    async def run_agent(body: RunAgentInput, request: Request):
        """ag-ui-langgraph's endpoint, plus one duty: when the client goes (a closed tab, a refresh, the
        Stop button), the run stops, and with it the build, its containers and any model call."""
        encoder = EventEncoder(accept=request.headers.get("accept"))
        one = agent.clone()

        def stop():
            if (r := runs.get(body.thread_id)):
                r.cancel()

        async def watch():
            while not await request.is_disconnected():
                await asyncio.sleep(0.5)
            stop()

        async def events():
            watcher = asyncio.create_task(watch())
            done = False
            try:
                async for event in one.run(body):
                    yield encoder.encode(event)
                done = True
            finally:
                watcher.cancel()
                if not done:
                    stop()

        return StreamingResponse(events(), media_type=encoder.get_content_type())

    @app.get("/api/evidence/{handle:path}")
    def evidence(handle: str, view: str = "summary", name: str = ""):
        kind, p = resolve(handle)
        data = json.loads(p.read_text())
        if kind == "run":
            return data
        if view == "layout":
            return layout_view(p)
        if view == "bits":
            return bits_of(p, data)
        if view == "waveform":
            return waveform_view(p, data)
        if view == "timing":
            return timing_view(p)
        if view == "log":
            return log_view(p, name)
        return cell_view(data)

    @app.get("/api/overview")
    def overview():
        t5 = json.loads((M2 / "table5.json").read_text()) if (M2 / "table5.json").is_file() else {}
        return {"model": model.label(cfg["model"]), "table4": _rows("table4.csv"), "timing": _rows("table4_timing.csv"), "test_cells": _rows("test_cells.csv"),
                "versus_hd": _rows("test_vs_hd.csv"), "sizing": _rows("sizing_nor3.csv"), "agent": _rows("agent_vs_fixed.csv"),
                "table5": {k: t5.get(k) for k in ("requirements", "builds", "broken_full_ramp", "design_level", "simulators")}
                | {"cells": {c: {"median_abs_pct": v["fixed"]["median_abs_pct"], "stock_median_abs_pct": v.get("stock", {}).get("median_abs_pct")}
                             for c, v in t5.get("cells", {}).items()}}}

    @app.get("/api/estimates")
    def estimates():
        return timings.estimates(graph.TIMES)

    @app.post("/api/transcribe")
    async def transcribe(request: Request):
        body = await request.body()
        if len(body) > voice.MAX_BYTES:
            raise HTTPException(413, "that recording is too long")
        try:
            return {"text": await asyncio.to_thread(voice.transcribe, body)}
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except voice.Unavailable as e:
            raise HTTPException(503, str(e)) from e

    @app.post("/v1/chat/completions")
    def completions(body: ChatRequest):
        c = cfg["model"]
        try:
            return codex_cli.CodexCLI(c["name"], c.get("reasoning_effort", "high"), c.get("timeout_s", 180)).complete(body.messages, body.response_format)
        except codex_cli.CodexError as e:
            raise HTTPException(502, str(e)) from e

    return app


def main():
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=int(os.environ.get("PORT", 8123)))


if __name__ == "__main__":
    main()
