"""The formula between the agent and the front end (implementation plan 9.6).

The page a model writes is OpenUI Lang: statements such as `v = Verdict("run:A-1102-01")`, whose
component names come from a closed library in web/src/library.tsx. A component takes a handle, a
string that names evidence, and fetches its numbers from the read-only API, so a model can choose
and order panels but cannot type a result onto the page. Its own words are limited to Note(...) and
Choice(...). A Choice is a button with a prompt: pressing it sends that prompt back through the same
guarded path as anything a person types, so it grants nothing. Every number in a Note must be in the
facts.

check_page runs before a page leaves the server. A page that fails it is replaced by fixed_page,
which is what a run without a model shows too.
"""
import json
import re

from dd2 import paths

# name -> the handle kind it takes ("" for none): keep in step with web/src/library.tsx
COMPONENTS = {"Report": "", "Section": "", "Note": "", "Choices": "", "Choice": "", "Verdict": "run", "RevisionTable": "run", "RevisionGhost": "run",
              "CheckMatrix": "cell", "LayoutView": "cell", "Layout3D": "cell", "TimeMachine": "cell", "TimingSurface": "cell",
              "NetworkView": "cell", "EulerRows": "cell", "TruthTable": "cell"}
HANDLED = "|".join(k for k, v in COMPONENTS.items() if v)
HANDLE = re.compile(r"^(run|cell):[A-Za-z0-9_-]{1,60}(/[A-Za-z0-9_-]{1,60})?$")
PROMPT_FILE = paths.ROOT / "prompts" / "ui_library.md"


def library_prompt() -> str:
    """Written from the component library by `npm run prompt` in web/."""
    return PROMPT_FILE.read_text()


def cell_handle(rev: dict) -> str:
    """cell:<run>/<name> for a revision built by an agent run."""
    parts = (rev.get("report") or "runs/x/cells/x/report.json").split("/")
    return f"cell:{parts[1]}/{parts[3]}"


NO_BUILD = ("FORBIDDEN", "UNCLEAR", "ABOUT_PROJECT")
CHAT_ONLY = NO_BUILD + ("EXPLAIN_CHECK", "DISPLAY_PREVIEW", "ABOUT_OPTION2")      # answered in the chat, with no report page


def page_facts(run_id: str, v: dict) -> dict:
    """All a page may refer to."""
    revs = v.get("revisions") or []
    return {"run": f"run:{run_id}", "function": v.get("function", ""), "status": v.get("status"), "stop": v.get("stop"),
            "intent": (v.get("intent") or {}).get("kind", "BUILD_CELL"), "reason": (v.get("intent") or {}).get("reason", ""),
            "options": (v.get("intent") or {}).get("options", []),
            "best_cell": cell_handle(v["best"]) if v.get("best") else None, "best": (v.get("best") or {}).get("id"),
            "revisions": [{k: r[k] for k in ("id", "status", "sites", "met1_nets", "breaks", "failed")} | {"cell": cell_handle(r), "sizing": r["settings"].get("sizing")} for r in revs]}


def fixed_page(d: dict) -> str:
    """The page with no model: the verdict, the evidence, and what can be asked next."""
    run, cell = d["run"], d["best_cell"]
    if d["intent"] in NO_BUILD or not cell:
        note = (d.get("reason") or "No cell came out of this request.").replace('"', "'")
        options = d.get("options") or []
        if not options:
            return f'root = Report([n])\nn = Note("{note}")\n'
        names = [f"o{i}" for i in range(len(options))]
        lines = [f"root = Report([n, c])", f'n = Note("{note}")', f"c = Choices([{', '.join(names)}])"]
        for name, o in zip(names, options):
            lines.append(f'{name} = Choice("{o["label"].replace(chr(34), chr(39))}", "{o["expression"]}", "{o["expression"]}")')
        return "\n".join(lines) + "\n"
    best = next((r for r in d["revisions"] if r["cell"] == cell), {})
    options = ['g3 = Choice("Show it in 3D", "Show this cell in 3D", "An illustrative extrusion of its layers")',
               'g4 = Choice("Replay its transient", "Show the transient simulation of this cell", "The waveform the SPICE check judged")']
    if d["status"] != "pass":
        options.insert(0, f'g1 = Choice("Why did it fail?", "Explain why {(best.get("failed") or ["this check"])[0]} failed", "Read the failed check")')
    if best.get("met1_nets") or best.get("breaks"):
        options.insert(0, 'g2 = Choice("Try another gate order", "Try another Euler order for this cell", "May remove met1 nets or breaks")')
    if len({r["sizing"] for r in d["revisions"]}) < 2:
        options.append('g5 = Choice("Compare hd and stack", "Compare hd and stack sizing for this cell", "Speed against width")')
    names = [o.split(" ")[0] for o in options]
    two = len(d["revisions"]) > 1
    blocks = ["v", "revisions" if two else "", "ghost" if two else "", "s1", "s2", "next"]
    return "\n".join([f"root = Report([{', '.join(b for b in blocks if b)}])", f'v = Verdict("{run}")'] +
                     ([f'revisions = RevisionTable("{run}")', f'ghost = RevisionGhost("{run}")'] if two else []) +
                     [f's1 = Section("Best revision", [layout, checks])', f'layout = Layout3D("{cell}")', f'checks = CheckMatrix("{cell}")',
                      f's2 = Section("How it works", [machine, net, rows])', f'machine = TimeMachine("{cell}")', f'net = NetworkView("{cell}")',
                      f'rows = EulerRows("{cell}")', f"next = Choices([{', '.join(names)}])"] + options) + "\n"


def check_page(text: str, data: dict) -> list:
    """Problems with a model's page. An empty list lets it through."""
    src = (text or "").strip()
    errs = []
    if not src or len(src) > 8000:
        return ["the page is empty or too long"]
    if re.search(r"https?:|<\s*/?\s*\w+[^>]*>|javascript:|@\w+\(|\$\w+", src, re.I):
        errs.append("the page has a link, a tag, a function call or a variable")
    if not re.search(r"^root\s*=\s*Report\(", src, re.M):
        errs.append("the page must start from root = Report(...)")
    for name in set(re.findall(r"\b([A-Z][A-Za-z0-9]*)\(", re.sub(r'"(?:[^"\\]|\\.)*"', '""', src))):
        if name not in COMPONENTS:
            errs.append(f"unknown component {name}")
    handles = {data["run"]} | {r["cell"] for r in data["revisions"]}
    for name, handle in re.findall(rf'\b({HANDLED})\("([^"]*)"\)', src):
        if not HANDLE.match(handle) or handle not in handles:
            errs.append(f"{name} has an unknown handle {handle}")
        elif not handle.startswith(COMPONENTS[name] + ":"):
            errs.append(f"{name} takes a {COMPONENTS[name]} handle")
    allowed = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(data)))
    for words in re.findall(r'\bNote\("((?:[^"\\]|\\.)*)"\)', src) + re.findall(r'\bSection\("((?:[^"\\]|\\.)*)"', src):
        bad = [n for n in re.findall(r"(?<![A-Za-z_.\d])\d+(?:\.\d+)?", words) if n not in allowed]
        if bad:
            errs.append(f"numbers not in the facts: {bad}")
    return errs
