"""The Option 1 agent as a LangGraph (implementation plan 8.3):

    intent_parser -> invoke_allowed_tool -> observe_structured_result -> assess_retry
    assess_retry -> finish, or fetch_context -> plan_one_bounded_action -> validate_action
    validate_action -> invoke_allowed_tool, plan_one_bounded_action (once, on a refusal), or finish
    finish -> explain_evidence -> END

The model only proposes the next build's settings from a closed list. Everything else is
deterministic: the schema, the claim checks on its reply, the budget, the tool policy, and the
verdict, which comes from the check report of the revision that scored best (overview 4.3, rule 1).
"""
import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import ValidationError

from dd2 import boolfn as bf
from dd2 import paths, provenance

from . import audit, codex_cli, generative_ui, model, option2, policy, timings, tools

AGENT = "diagnostician"
ORDERS = 6
HIDE = {"metadata": {"emit-messages": False, "emit-tool-calls": False}}      # internal JSON stays off the UI stream


class State(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    run_id: str
    expr: str
    settings: dict
    revisions: list
    pending: list
    intent: dict
    stage: str
    decision: dict
    facts: dict
    rejected: str
    stop: str
    verdict: dict
    ui: dict
    history: list                       # what the agent chose and why, for questions afterwards
    ended: str                          # why the last build run stopped, in plain words


FORBIDDEN_TEXT = re.compile(
    r"\b(delete|remove|edit|change|modify|alter|skip|disable|fake|force|bypass|waive|ignore)\b.{0,60}"
    r"\b(check|checks|checker|test|tests|broken|pdk|drc|lvs|truth table|measurement|measurements|result|results|liberty|rule|rules)\b"
    r"|\bmark\b.{0,40}\bpass|\bmake\b.{0,40}\bpass\b|\bpositive no matter\b|\baccept anyway\b", re.I)


def expression_ok(text: str) -> bool:
    """A Boolean expression of 1 to 4 inputs that parses, using only the request grammar."""
    if not text or not re.fullmatch(tools.EXPR[1:-1], text) or not re.search(r"[!&|^]", text):
        return False
    try:
        names = sorted({t for t in bf.tokenize(text) if t[0].isalpha()})
        return 1 <= len(names) <= 4 and bf.eval_expr(text, names) is not None
    except (ValueError, KeyError, IndexError):
        return False


def facts(report: dict, settings: dict, rev_id: str = "r0") -> dict:
    """What a revision's check report says, reduced to numbers the score and the model use."""
    lay = report.get("layout", {})
    checks = report.get("checks", {}).get("network", {})
    return {"id": rev_id, "settings": settings, "status": report.get("status", "fail"), "failed": report.get("failed_checks", ["build"]),
            "sites": lay.get("width_sites"), "met1_nets": lay.get("met1_nets") or [], "breaks": lay.get("diffusion_breaks"),
            "route_failures": lay.get("route_failures") or [], "transistors": checks.get("transistors"), "stages": checks.get("stages")}


def score(rev: dict) -> tuple:
    """Lower is better: passing, then width, then nets on met1, then diffusion breaks."""
    return (rev["status"] != "pass", rev["sites"] or 10 ** 6, len(rev["met1_nets"]), rev["breaks"] if rev["breaks"] is not None else 10 ** 6)


PHASES = {"network": ("Design", "Network"), "ordering": ("Design", "Euler order"), "layout": ("Design", "Layout"),
          "geometry": ("Physical checks", "Frame and pins"), "drc": ("Physical checks", "DRC"), "abutment": ("Physical checks", "Abutment"),
          "lvs": ("Physical checks", "LVS"), "rc": ("Physical checks", "RC-LVS"), "spice": ("Simulation", "SPICE"), "verilog": ("Simulation", "Verilog")}
PROJECT_FALLBACK = "I can tell you about the project, but a measured number has to come from the check records, so try the Evidence tab."
TIMES = paths.build("stage_times.jsonl")


def progress_note(e: dict) -> tuple | None:
    """(phase, one short line) when a stage of the flow has finished, from what the flow reported."""
    where = PHASES.get(e["id"])
    if not where or e["state"] == "running":
        return None
    return where[0], f"{'✓' if e['state'] == 'ok' else '✕'} {where[1]}: {e['detail']}"


def checked_reply(text: str, facts: str, fallback: str) -> str:
    """A model's answer may only quote numbers that are in what it was given: results come from records."""
    numbers = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
    return text if set(numbers.findall(text)) <= set(numbers.findall(facts)) else fallback


def nothing_to_build(expr: str) -> str | None:
    """Why an expression has no cell to build, in plain words; None when it has one."""
    names = sorted({t for t in bf.tokenize(expr) if t[0].isalpha()})
    n, tt = len(names), bf.eval_expr(expr, names)
    mask = (1 << (1 << n)) - 1
    if tt in (0, mask):
        return f"{expr} is always {1 if tt else 0}, whatever the inputs are, so there is no logic to build. It is just a connection to {'VPWR' if tt else 'VGND'}."
    for k, name in enumerate(names):
        if tt == bf.var_tt(k, n):
            return f"{expr} is the same as {name}, so it is a wire, not a cell."
    unused = [x for k, x in enumerate(names) if k not in bf.depends_on(tt, n)]
    if unused:
        return f"{expr} does not depend on {', '.join(unused)}. Remove it from the function and I can build the rest."
    return None


def why_stopped(stop: str) -> str:
    """A run's stop reason as a person would say it."""
    return {"tool calls": "it reached its limit of builds for one request", "model calls": "it reached its limit of model calls",
            "time": "it reached its time limit", "input tokens": "it reached its token limit", "output tokens": "it reached its token limit",
            "cost": "it reached its cost limit", "nothing to improve": "there was nothing left to improve",
            "model chose to stop": "the agent judged that another build would not help", "build crashed": "a tool crashed, so another setting would not help",
            "canceled": "you stopped it", "invalid model reply": "the guardrails refused the model's reply twice",
            "model unavailable": "the model could not be reached", "requested build done": "the build you asked for was done"}.get(stop, stop)


def failure_lines(rev: dict) -> list:
    """Why a build failed, as far as its records can say."""
    lines = []
    if rev.get("error"):
        lines.append(f"• The build crashed: {rev['error']}")
    if rev.get("route_failures"):
        lines.append(f"• The router could not route {' '.join(rev['route_failures'])}, so the layout is unfinished")
    checks = [x for x in rev["failed"] if x not in ("build", "route")]
    if checks:
        lines.append(f"• Failed checks: {', '.join(checks)}")
    return lines


def last_error(log: str) -> str:
    """The line of a crashed tool's log that says what went wrong."""
    lines = [x.strip() for x in log.splitlines() if x.strip()]
    return lines[-1] if lines else ""


def parse_decision(text: str, info: dict) -> tuple:
    """(decision, problem). A reply outside the schema, or one that claims what the facts do not
    show, is refused and never repaired."""
    try:
        d = model.Decision.model_validate_json(text)
    except (ValidationError, ValueError) as e:
        return None, f"not the required JSON: {str(e).splitlines()[0][:120]}"
    known = {r["id"] for r in info["history"]}
    cur, untried = info["current"], info["untried"]
    if not d.evidence_refs or not set(d.evidence_refs) <= known:
        return None, f"evidence_refs must name revisions from the facts: {sorted(known)}"
    if d.action == "TRY_DIFFERENT_EULER_ORDER" and d.order_index not in untried["orders"]:
        return None, f"order_index {d.order_index} is not in untried.orders {untried['orders']}"
    if d.action == "SWITCH_SIZING_POLICY" and d.sizing not in untried["sizing"]:
        return None, f"sizing {d.sizing!r} is not in untried.sizing {untried['sizing']}"
    if d.action == "RETRY_ROUTING_WITH_PRIORITY" and d.net not in cur["met1_nets"] + cur["route_failures"]:
        return None, f"net {d.net!r} is not among the current revision's met1 nets or route failures"
    if d.action == "STAY_ON_LI1" and (info["untried"]["li1_only_tried"] or not cur["met1_nets"]):
        return None, "STAY_ON_LI1 needs met1 nets and may be used once"
    if (bad := unsupported_numbers(f"{d.reason} {d.expected_effect}", info)):
        return None, f"these numbers are not in the facts: {bad}"
    return d.model_dump(), None


def unsupported_numbers(text: str, info: dict) -> list:
    """Numbers in the model's words that appear nowhere in the facts (ids such as r2 do not count)."""
    allowed = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(info)))
    return [n for n in re.findall(r"(?<![A-Za-z_.\d])\d+(?:\.\d+)?", text) if n not in allowed]


class Run:
    def __init__(self, name: str, cfg: dict, run_id: str | None = None, log_dir=audit.LOG_DIR):
        self.name, self.cfg = name, cfg
        self.run_id = run_id or audit.new_run_id(log_dir)
        self.log = audit.RunLog(self.run_id, log_dir)
        self.llm = model.chat_model(cfg["model"])
        self.model_label = model.label(cfg["model"])
        self.limits = cfg["limits"]
        self.system, self.prompt = model.prompt_ref(AGENT)
        self.calls = {"model": 0, "tool": 0, "in": 0, "out": 0}
        self.used = (0, 0)                      # tokens of the latest model call, for its log line
        self.t0 = time.time()
        self.digest = policy.protected_digest()
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.closed = False                     # the log has its result line
        self.notes, self.closing = {}, []       # the chat's updates, and its closing message
        self.spans, self.group = timings.Spans(), "single"
        self.busy = False                       # a tool is running
        self.steps = 0

    def cancel(self) -> None:
        """The person left, or pressed Stop: running processes die at once and no new work starts.
        The stream is gone, so the graph may never reach finish: the log still gets its last line."""
        self.stopped.set()
        tools.stop_containers(self.run_id)
        threading.Thread(target=self._close_cancelled, daemon=True).start()

    def _close_cancelled(self) -> None:
        deadline = time.time() + 15
        while self.busy and time.time() < deadline:      # the killed tool logs its line first: the result stays last
            time.sleep(0.05)
        with self.lock:
            if self.closed:
                return
            self.closed = True
            chk = self.log.path.with_suffix(".checks.json")
            provenance.write_json(chk, {"run": self.run_id, "status": "fail", "stop": "canceled", "calls": self.calls,
                                        "seconds": round(time.time() - self.t0, 1), "model": self.model_label})
            self.log.result("fail", chk)

    def say(self, step: str, title: str, state: str = "ok", detail: str = "", kind: str = "step", stage: str = "", data=None, revision: str = "") -> None:
        """One live event: a pipeline step, or a reply in the chat (kind "reply"). A CUSTOM event over
        AG-UI; a no-op outside a graph."""
        self.spans.seen(stage, revision, step, time.time())
        if stage == "network" and (data or {}).get("stages"):
            self.group = "multi" if data["stages"] > 1 else "single"
        try:
            dispatch_custom_event("atlas", {"id": f"{self.run_id}:{step}", "kind": kind, "title": title, "state": state, "detail": detail,
                                            "stage": stage, "revision": revision, "data": data, "run": self.run_id, "t": round(time.time() - self.t0, 1)})
        except (RuntimeError, ValueError):
            pass

    def note(self, e: dict, revision: str) -> None:
        """One bullet for each finished stage, gathered into one chat message per phase of a build."""
        line = progress_note(e)
        if line:
            phase, text = line
            lines = self.notes.setdefault((revision, phase), [])
            lines.append(text)
            self.say(f"note-{revision}-{phase}", "\n".join([f"Build {revision}, {phase.lower()}:", *lines]), kind="reply")

    def spent(self) -> float:
        m = self.cfg["model"]
        return (self.calls["in"] * m.get("usd_per_mtok_in", 0) + self.calls["out"] * m.get("usd_per_mtok_out", 0)) / 1e6

    def over(self) -> str | None:
        lim = self.limits
        for hit, why in ((self.calls["model"] >= lim["max_model_calls"], "model calls"),
                         (self.calls["tool"] >= lim["max_tool_calls"], "tool calls"),
                         (time.time() - self.t0 >= lim["max_seconds"], "time"),
                         (self.calls["in"] >= lim["max_tokens_in"], "input tokens"),
                         (self.calls["out"] >= lim["max_tokens_out"], "output tokens"),
                         (self.spent() > lim["max_usd"], "cost")):
            if hit:
                return why
        return None

    def ask(self, system: str, user: str, fmt: dict, prompt_ref: str, role: str = AGENT) -> tuple:
        """One model call, counted, shown and retried. Returns (text, None), or (None, the failure)."""
        self.calls["model"] += 1
        self.steps += 1
        step, title = f"model{self.steps}", f"{role.title()} is thinking ({self.model_label.split(':')[-1]})"
        self.say(step, title, "running", f"{len(user)} characters of facts, prompt {prompt_ref.split('/')[-1]}", "model", role)
        kw = {"response_format": fmt} if fmt else {}
        llm = self.llm.bind(**kw, on_thought=lambda text: self.say(f"{step}t{time.time()}", text.replace("*", "").strip()[:300], "ok", "", "thought", role), cancel=self.stopped)
        msgs = [SystemMessage(system), HumanMessage(user)]
        last, t0 = None, time.time()
        for attempt in range(self.cfg["model"].get("retries", 2) + 1):
            try:
                r = llm.invoke(msgs, config=HIDE)
                u = r.usage_metadata or {}
                self.used = (u.get("input_tokens", 0), u.get("output_tokens", 0))
                self.calls["in"] += self.used[0]
                self.calls["out"] += self.used[1]
                self.say(step, f"{role.title()} replied", "ok", f"{time.time() - t0:.1f} s, {self.used[0]} tokens in, {self.used[1]} out", "model", role,
                         {"prompt": prompt_ref, "reply": str(r.content)[:6000], "tokens_in": self.used[0], "tokens_out": self.used[1]})
                return r.content, None
            except codex_cli.CodexError as e:
                last = str(e)
                if "used a tool" in last or last == "canceled":      # never retried
                    break
                self.say(step, title, "running", f"retrying: {last[:120]}", "model", role)
                time.sleep(2 ** attempt)
            except (KeyError, IndexError, ValueError) as e:
                last = f"bad reply: {e}"
                break
        self.say(step, f"{role.title()} failed", "bad", last, "model", role)
        self.log.model(role, self.model_label, prompt_ref, 0, 0, f"model call failed: {last}")
        return None, last

    def context(self, st: State) -> dict:
        revs = st["revisions"]
        tried = {r["settings"].get("order_index") for r in revs}
        cur = {k: revs[-1][k] for k in ("id", "status", "failed", "sites", "met1_nets", "breaks", "route_failures")}
        lim = self.limits
        return {"function": st["expr"], "current": cur, "best": min(revs, key=score)["id"],
                "history": [{k: r[k] for k in ("id", "settings", "status", "sites", "met1_nets", "breaks")} for r in revs],
                "untried": {"orders": [i for i in range(ORDERS) if i not in tried],
                            "sizing": sorted({"hd", "stack"} - {r["settings"]["sizing"] for r in revs}),
                            "li1_only_tried": any(r["settings"].get("no_met1") for r in revs)},
                "budget": {"builds_left": lim["max_tool_calls"] - self.calls["tool"],
                           "model_calls_left": lim["max_model_calls"] - self.calls["model"]}}

    # ---- nodes ---------------------------------------------------------------------------------

    def intent_parser(self, st: State) -> dict:
        """Structured input skips the model (plan 8.2). So does what a rule can settle: a bare
        expression, and anything that asks to change a check. A sentence goes to the Request
        Interpreter, and what it returns must still parse, like any request."""
        settings = st.get("settings") or {"sizing": "hd", "order_index": 0}
        base = {"stage": "intent", "run_id": self.run_id, "stop": "", "decision": {}, "rejected": "", "pending": [], "verdict": {}}
        if st.get("expr") and not st.get("messages"):
            return base | {"settings": settings, "revisions": st.get("revisions", []), "intent": {"kind": "BUILD_CELL"}}
        said = str(next((m.content for m in reversed(st.get("messages", [])) if isinstance(m, HumanMessage)), "")).strip()[:600]
        self.say("read", "Reading your request", "ok", said[:160], "step", "request")
        if FORBIDDEN_TEXT.search(said):
            self.say("guard", "Guardrail refused this request, with no model call", "bad", "It asks to change a check, a result or a fixed input", "guard", "request")
            self.say("reply", "I can't do that. Checks, truth tables, the PDK and measurements can't be changed from here.", kind="reply")
            self.log.policy("interpreter", "intent", {"text": said[:120]}, "refused: asks to change a check, a result or a fixed input")
            return base | {"intent": {"kind": "FORBIDDEN", "reason": "Checks, truth tables, the PDK and measurements cannot be changed from here."}, "stop": "refused"}
        if expression_ok(said):
            self.say("parse", "That is a Boolean expression, so no model is needed", "ok", said, "step", "request")
            if (why := nothing_to_build(said)):
                self.say("empty", "Nothing to build, so no tool or model is used", "ok", why, "guard", "request")
                self.say("reply", why, kind="reply")
                return base | {"intent": {"kind": "UNCLEAR", "reason": why}, "stop": "nothing to build"}
            self.say("reply", f"On it: building {said} with hd sizing.", kind="reply")
            return base | {"intent": {"kind": "BUILD_CELL"}, "expr": said, "revisions": [], "history": [], "settings": {"sizing": "hd", "order_index": 0}}
        system, ref = model.prompt_ref("interpreter")
        revs = st.get("revisions", [])
        known = {"current_function": st.get("expr", ""), "last_stop": st.get("ended", ""), "decisions": st.get("history", []),
                 "revisions": [{k: r.get(k) for k in ("id", "status", "sites", "settings", "failed", "met1_nets", "breaks", "route_failures", "error")} for r in revs],
                 "option2": option2.facts(),
                 "untried": [i for i in range(ORDERS) if i not in {r["settings"].get("order_index") for r in revs}]}
        user = f"<context>\n{json.dumps(known)}\n</context>\n<request>\n{said}\n</request>"
        text, err = self.ask(system, user, model.json_format(model.Intent), ref, "interpreter")
        if err:
            return base | {"intent": {"kind": "UNCLEAR", "reason": "The model is not available, so only expressions work right now."}, "stop": "model unavailable"}
        try:
            it = model.Intent.model_validate_json(text)
        except (ValidationError, ValueError):
            self.log.model("interpreter", self.model_label, ref, *self.used, "refused reply: not the required JSON")
            return base | {"intent": {"kind": "UNCLEAR", "reason": "The request could not be read."}, "stop": "request not understood"}
        self.log.model("interpreter", self.model_label, ref, *self.used,
                       f"{it.kind}: {it.expression} {it.reason[:120]}" + (f" [focus {it.focus}]" if it.focus else "") + (f" [candidate {it.candidate}]" if it.candidate else ""))
        self.say("intent", f"Understood as {it.kind.replace('_', ' ').lower()}", "ok", f"{it.expression} {it.reason}".strip()[:200], "guard", "request")
        if it.kind in generative_ui.CHAT_ONLY:
            it.reason = checked_reply(it.reason, system + user, PROJECT_FALLBACK)
        if it.kind == "BUILD_CELL" and expression_ok(it.expression) and (why := nothing_to_build(it.expression)):
            self.say("reply", why, kind="reply")
            return base | {"intent": {"kind": "UNCLEAR", "reason": why}, "stop": "nothing to build"}
        routed = self.route(it, st)
        kind = routed["intent"]["kind"]
        words = {"BUILD_CELL": f"On it: building {routed.get('expr')}.", "TRY_CANDIDATE": "Trying that now, as a new revision.",
                 "COMPARE_CANDIDATES": "Building both sizings to compare them.", "RESTORE_REVISION": "Going back to that revision.",
                 "BUILD_CANDIDATE": routed["intent"].get("reason")}
        self.say("reply", words.get(kind) or routed["intent"].get("reason") or "Bringing that up.", kind="reply", data={"options": routed["intent"].get("options", [])})
        if it.focus and (revs or it.focus.startswith("o2-")) and kind in generative_ui.CHAT_ONLY:
            self.say("focus", f"Opened the {it.focus} step", "ok", "", "focus", "", {"stage": it.focus})
        return base | routed

    def route(self, it, st: State) -> dict:
        have = bool(st.get("revisions"))
        intent = it.model_dump()
        if it.kind == "BUILD_CELL" and expression_ok(it.expression):
            return {"intent": intent, "expr": it.expression, "revisions": [], "history": [], "settings": {"sizing": it.sizing, "order_index": 0}}
        if it.kind == "TRY_CANDIDATE" and have:
            return {"intent": intent, "settings": {"sizing": it.sizing, "order_index": it.order_index}}
        if it.kind == "COMPARE_CANDIDATES" and (have or expression_ok(it.expression)):
            expr = it.expression if expression_ok(it.expression) else st["expr"]
            return {"intent": intent, "expr": expr, "settings": {"sizing": "hd", "order_index": 0}, "pending": [{"sizing": "stack", "order_index": 0}]}
        if it.kind in ("EXPLAIN_CHECK", "DISPLAY_PREVIEW", "RESTORE_REVISION") and have:
            return {"intent": intent, "stop": it.kind.lower()}
        if it.kind == "BUILD_CANDIDATE":
            req = option2.request_for(it.candidate)
            if req is None:
                return {"intent": {"kind": "UNCLEAR", "reason": f"Option 2 has no requested candidate {it.candidate or 'by that name'}.", "options": []},
                        "stop": "request not understood"}
            return {"intent": intent | {"reason": f"Building Option 2's {req['request_id']}, {req['name']}, with Option 1."},
                    "expr": req["expression"], "revisions": [], "history": [], "settings": {"sizing": "hd", "order_index": 0}}
        if it.kind == "FORBIDDEN":
            return {"intent": intent, "stop": "refused"}
        if it.kind in ("ABOUT_PROJECT", "ABOUT_OPTION2"):
            return {"intent": intent, "stop": "about project"}
        readings = [o.model_dump() for o in it.options if expression_ok(o.expression)][:4]    # a button must be buildable
        return {"intent": {"kind": "UNCLEAR", "reason": it.reason or "Nothing has been built yet, so there is nothing to act on.", "options": readings},
                "stop": "needs your choice" if readings else "request not understood"}

    def invoke_allowed_tool(self, st: State) -> dict:
        revisions = st.get("revisions", [])
        k = len(revisions)
        args = {"expr": st["expr"], "name": f"{self.name}_r{k}"} | st["settings"]
        self.calls["tool"] += 1
        left = max(60, self.limits["max_seconds"] - (time.time() - self.t0))    # a build cannot outlast the run
        self.steps += 1
        tag = f"b{self.steps}"
        self.say(tag, f"Tool call: build_cell, revision r{k}", "running", json.dumps(args), "tool", "", {"revision": f"r{k}", "args": args}, f"r{k}")
        t0 = time.time()
        self.busy = True
        try:
            code, out = tools.call("build_cell", args, self.run_id, self.log, AGENT, timeout=left, cancel=self.stopped,
                                   on_trace=lambda e: self.note(e, f"r{k}") or self.say(f"{tag}{e['id']}", e["title"], e["state"], e["detail"], "check", e.get("stage", ""), e.get("data"), f"r{k}"))
        finally:
            self.busy = False
        report = json.loads(Path(out).read_text()) if out and Path(out).exists() else {}
        rev = facts(report, st["settings"], f"r{k}") | {"report": paths.rel(Path(out)) if out else None, "exit_code": code}
        if rev["failed"] == ["build"] and code not in (0, 130):
            log = Path(str(out) + ".log") if out else None
            rev["error"] = last_error(log.read_text(errors="replace")) if log and log.is_file() else ""
            self.say(f"crash{k}", f"Build r{k} could not run" + (f": {rev['error']}" if rev["error"] else ""), kind="reply")
        self.say(tag, f"build_cell finished: r{k} {rev['status']}", "ok" if rev["status"] == "pass" else "bad",
                 f"{time.time() - t0:.1f} s, {rev['sites']} sites, {len(rev['met1_nets'])} met1 nets, {rev['breaks']} breaks"
                 + (f", failed: {' '.join(rev['failed'])}" if rev["failed"] else ""), "tool", "", None, f"r{k}")
        if self.stopped.is_set():
            return {"revisions": revisions + [rev], "stage": "verify", "stop": "canceled"}
        return {"revisions": revisions + [rev], "stage": "verify"}

    def assess_retry(self, st: State) -> dict:
        if self.stopped.is_set():
            return {"stop": "canceled"}
        if st.get("stop"):
            return {}
        if st["revisions"][-1].get("error") is not None:      # the tool itself crashed: another setting will not help
            self.log.policy(AGENT, "decide", {}, "stop: the build crashed")
            return {"stop": "build crashed"}
        kind = (st.get("intent") or {}).get("kind")
        if kind == "COMPARE_CANDIDATES" and st.get("pending"):
            return {"settings": st["pending"][0], "pending": st["pending"][1:], "stage": "build"}
        if kind in ("TRY_CANDIDATE", "COMPARE_CANDIDATES"):    # the person chose this build: it stands as asked
            return {"stop": "requested build done"}
        best = min(st["revisions"], key=score)
        if best["status"] == "pass" and not best["met1_nets"] and not best["breaks"]:
            # no check failed and nothing the model's actions can improve: a model call would only cost
            self.log.policy(AGENT, "decide", {}, "stop: passes with no met1 net and no diffusion break")
            self.say("clean", "Nothing to improve, so no model call is spent", "ok", f"{best['id']} passes with no met1 net and no break", "guard", "verdict")
            return {"stop": "nothing to improve"}
        if (why := self.over()):
            self.log.policy(AGENT, "budget", {}, f"stop: limit reached on {why}")
            return {"stop": why}
        return {}

    def fetch_context(self, st: State) -> dict:
        return {"facts": self.context(st), "stage": "plan", "rejected": ""}

    def plan_one_bounded_action(self, st: State) -> dict:
        info = dict(st["facts"])
        if st.get("rejected"):
            info["rejected"] = st["rejected"]
        user = f"<facts>\n{json.dumps(info, indent=1)}\n</facts>"
        text, err = self.ask(self.system, user, model.json_format(model.Decision), self.prompt)
        if err:
            return {"stop": "model unavailable"}
        d, problem = parse_decision(text, st["facts"])
        settings = None if problem else self.apply(d, st)
        if d and settings is None and d["action"] != "STOP_AND_REPORT":
            d, problem = None, "these settings were already built"
        self.steps += 1
        self.say(f"g{self.steps}", "Guardrails refused the reply" if problem else f"Guardrails accepted: {d['action'].replace('_', ' ').lower()}",
                 "bad" if problem else "ok", problem or d["reason"], "guard", AGENT,
                 {"problem": problem} if problem else {k: d.get(k) for k in ("action", "order_index", "sizing", "net", "reason", "evidence_refs", "expected_effect")})
        if d:
            self.say(f"r{self.steps}", ("Stopping here: " if d["action"] == "STOP_AND_REPORT" else "Trying another build: ") + d["reason"], kind="reply")
        self.log.model(AGENT, self.model_label, self.prompt, *self.used,
                       f"refused reply: {problem}" if problem else f"{d['action']}: {d['reason']}")
        said = [{"action": d["action"], "reason": d["reason"]}] if d else []
        return {"decision": d or {}, "rejected": problem or "", "settings": settings or st["settings"], "history": st.get("history", []) + said}

    def validate_action(self, st: State) -> dict:
        d = st.get("decision") or {}
        if self.stopped.is_set():
            return {"stop": "canceled"}
        if st.get("stop"):
            return {}
        if st.get("rejected"):
            if st.get("stage") == "replan":                 # a second refusal ends the run
                return {"stop": "invalid model reply"}
            return {"stage": "replan"}
        if d.get("action") == "STOP_AND_REPORT":
            return {"stop": "model chose to stop"}
        if (why := self.over()):
            self.log.policy(AGENT, "budget", {}, f"stop: limit reached on {why}")
            return {"stop": why}
        return {"stage": "build"}

    @staticmethod
    def apply(d: dict, st: State) -> dict | None:
        """The settings a decision asks for; None when it names nothing new."""
        s = dict(st["settings"])
        s.pop("priority", None)
        s.pop("no_met1", None)
        if d["action"] == "TRY_DIFFERENT_EULER_ORDER":
            s["order_index"] = d["order_index"]
        elif d["action"] == "RETRY_ROUTING_WITH_PRIORITY":
            s["priority"] = d["net"]
        elif d["action"] == "STAY_ON_LI1":
            s["no_met1"] = True
        elif d["action"] == "SWITCH_SIZING_POLICY":
            s["sizing"] = d["sizing"]
        else:
            return None
        return None if any(r["settings"] == s for r in st["revisions"]) else s

    def finish(self, st: State) -> dict:
        """The verdict: the best revision's check report, read here and written to a check file."""
        revs = st.get("revisions", [])
        if policy.protected_digest() != self.digest:
            self.log.policy(AGENT, "digest", {}, "violation: protected files changed during the run")
            revs = []
        best = min(revs, key=score) if revs else None
        if (st.get("intent") or {}).get("kind") == "RESTORE_REVISION":
            best = next((r for r in revs if r["id"] == st["intent"].get("revision")), best)
        summary = {"run": self.run_id, "function": st.get("expr", ""), "model": self.model_label, "prompt": self.prompt, "intent": st.get("intent"),
                   "model_settings": self.cfg["model"], "limits": self.limits, "calls": self.calls, "usd": self.spent(),
                   "seconds": round(time.time() - self.t0, 1), "stop": st.get("stop"), "revisions": revs, "best": best,
                   "status": "pass" if best and best["status"] == "pass" else "fail"}
        provenance.write_json(self.log.path.with_suffix(".checks.json"), summary)
        if (st.get("intent") or {}).get("kind") in generative_ui.CHAT_ONLY:
            pass                                                # the reply has already said it
        elif revs:
            self.say("verdict", f"Verdict from the check report: {summary['status']}", "ok" if summary["status"] == "pass" else "bad",
                     f"best revision {best['id']}, stopped: {st.get('stop') or 'finished'}", "verdict", "verdict", {"status": summary["status"]})
            if summary["status"] == "pass":
                self.closing = [f"Finished {summary['function']}:", f"• Best build: {best['id']}, of {len(revs)} built",
                                f"• Every check passed, from the check report", f"• {best['sites']} sites, {len(best['met1_nets'])} met1 nets, {best['breaks']} diffusion breaks"]
            else:
                self.closing = [f"Finished {summary['function']}, and it did not pass:", *failure_lines(best), f"• {len(revs)} built"]
            self.closing.append(f"• Stopped because {why_stopped(st.get('stop') or '')}")
            self.say("said", "\n".join(self.closing), kind="reply")
        else:
            self.say("verdict", "Nothing was built", "ok", st.get("stop") or "", "step")
        kind = (st.get("intent") or {}).get("kind")
        return {"verdict": summary, "stage": "explain"} | ({} if kind in generative_ui.CHAT_ONLY else {"ended": why_stopped(st.get("stop") or "")})

    def explain_evidence(self, st: State) -> dict:
        """The Research Explainer writes the report page in OpenUI Lang. It arranges panels; the
        panels fetch their numbers from the evidence API. If its page fails the checks, a fixed page
        takes its place, because a run must never depend on the model to show its result."""
        v = st["verdict"]
        if (v.get("intent") or {}).get("kind") in generative_ui.CHAT_ONLY and self.model_label.startswith("codex-cli"):
            with self.lock:
                if not self.closed:
                    self.closed = True
                    self.log.result(v["status"], self.log.path.with_suffix(".checks.json"))
            return {"stage": "done", "verdict": v | {"calls": self.calls, "log_problems": audit.verify(self.log.path)}}
        data = generative_ui.page_facts(self.run_id, v)
        page = generative_ui.fixed_page(data)
        source = "fixed page"
        kind = data["intent"]
        if self.model_label.startswith("codex-cli") and v["best"] and kind not in generative_ui.NO_BUILD and not self.stopped.is_set():
            system, ref = model.prompt_ref("explainer")
            text, err = self.ask(system + "\n\n" + generative_ui.library_prompt(), f"<facts>\n{json.dumps(data, indent=1)}\n</facts>", None, ref, "explainer")
            if not err:
                problems = generative_ui.check_page(text, data)
                self.say("page", "Guardrails refused the page, so the fixed page is shown" if problems else "Guardrails accepted the report page",
                         "bad" if problems else "ok", "; ".join(problems[:3]), "guard", "explainer")
                self.log.model("explainer", self.model_label, ref, *self.used, f"refused page: {problems[:3]}" if problems else "wrote the report page")
                if not problems:
                    page, source = text.strip(), "explainer"
        if self.closing:
            self.say("said", "\n".join([*self.closing, "• The report page is ready in the Report tab"]), kind="reply")
        seconds = self.spans.seconds()
        if "layout" in seconds and not self.stopped.is_set():         # a real build, carried through to the end
            timings.record(TIMES, self.group, seconds)
        with self.lock:
            if not self.closed:
                self.closed = True
                self.log.result(v["status"], self.log.path.with_suffix(".checks.json"))      # Appendix B: the last line
        v = v | {"calls": self.calls, "log_problems": audit.verify(self.log.path)}
        return {"messages": [AIMessage(page)], "ui": {"source": source, "run_id": self.run_id}, "stage": "done", "verdict": v}


def build_graph(run_for, checkpointer=None):
    """run_for(state, config, node) gives the Run a node works on: one for the CLI; for the server, a
    new one for each message of a thread, so that each has its own log and budget."""
    g = StateGraph(State)
    for name in ("intent_parser", "invoke_allowed_tool", "assess_retry", "fetch_context", "plan_one_bounded_action",
                 "validate_action", "finish", "explain_evidence"):
        g.add_node(name, (lambda n: lambda st, config: getattr(run_for(st, config, n), n)(st))(name))
    g.add_edge(START, "intent_parser")
    g.add_conditional_edges("intent_parser", lambda st: "finish" if st.get("stop") else "invoke_allowed_tool")
    g.add_edge("invoke_allowed_tool", "assess_retry")
    g.add_conditional_edges("assess_retry", lambda st: "finish" if st.get("stop") else
                            "invoke_allowed_tool" if st.get("stage") == "build" else "fetch_context")
    g.add_edge("fetch_context", "plan_one_bounded_action")
    g.add_edge("plan_one_bounded_action", "validate_action")
    g.add_conditional_edges("validate_action", lambda st: "finish" if st.get("stop") else
                            "plan_one_bounded_action" if st.get("stage") == "replan" else "invoke_allowed_tool")
    g.add_edge("finish", "explain_evidence")
    g.add_edge("explain_evidence", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


def run(expr: str, name: str, cfg: dict | None = None, settings: dict | None = None, run_id=None, log_dir=audit.LOG_DIR) -> dict:
    cfg = cfg or model.load_config()
    r = Run(name, cfg, run_id, log_dir)
    g = build_graph(lambda st, config, node: r)
    st = g.invoke({"expr": expr, "settings": settings or {"sizing": "hd", "order_index": 0}, "revisions": []},
                  {"recursion_limit": 8 * cfg["limits"]["max_tool_calls"] + 12, "configurable": {"thread_id": r.run_id}})
    return st["verdict"]


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="dd2_agent.graph", description="One headless agent run on one function.")
    ap.add_argument("--func", required=True)
    ap.add_argument("--name", default="agent_cell")
    ap.add_argument("--scripted", action="store_true", help="the rule set instead of a model; the log says so")
    a = ap.parse_args(argv)
    cfg = model.load_config()
    if a.scripted:
        cfg["model"]["provider"] = "scripted"
    if not model.available(cfg["model"]):
        print(f"model {model.label(cfg['model'])} is not available: install Codex CLI and sign in, or pass --scripted", file=sys.stderr)
        return 2
    s = run(a.func, a.name, cfg)
    print(json.dumps({k: s[k] for k in ("run", "status", "stop", "seconds", "calls", "model")} | {"best": s["best"]}))
    return 0 if s["status"] == "pass" and not s["log_problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
