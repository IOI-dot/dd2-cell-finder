"""The agent's guardrails, without a model or a build."""
import json

import pytest

pytest.importorskip("langgraph", reason="make setup installs the agent extra")
from dd2_agent import generative_ui, graph, model

INFO = {"function": "A^B", "current": {"id": "r0", "status": "pass", "failed": [], "sites": 8, "met1_nets": ["Y"], "breaks": 1, "route_failures": []},
        "best": "r0", "history": [{"id": "r0", "settings": {"sizing": "hd", "order_index": 0}, "status": "pass", "sites": 8, "met1_nets": ["Y"], "breaks": 1}],
        "untried": {"orders": [1, 2], "sizing": ["stack"], "li1_only_tried": False}, "budget": {"builds_left": 3, "model_calls_left": 5}}


def ok(**kw):
    return json.dumps({"action": "STOP_AND_REPORT", "order_index": 0, "sizing": "", "net": "", "reason": "r",
                       "evidence_refs": ["r0"], "expected_effect": "e"} | kw)


def test_a_valid_reply_passes():
    d, p = graph.parse_decision(ok(), INFO)
    assert p is None and d["action"] == "STOP_AND_REPORT"


@pytest.mark.parametrize("action", model.FORBIDDEN)
def test_every_forbidden_action_is_refused(action):
    d, p = graph.parse_decision(ok(action=action), INFO)
    assert d is None and p


@pytest.mark.parametrize("text", ["not json", "[]", '{"action": "STOP_AND_REPORT"}', ok(extra="x")])
def test_malformed_replies_are_refused(text):
    assert graph.parse_decision(text, INFO)[0] is None


@pytest.mark.parametrize("change, why", [
    ({"action": "TRY_DIFFERENT_EULER_ORDER", "order_index": 0}, "untried"),
    ({"action": "TRY_DIFFERENT_EULER_ORDER", "order_index": 9}, "untried"),
    ({"action": "SWITCH_SIZING_POLICY", "sizing": "hd"}, "sizing"),
    ({"action": "SWITCH_SIZING_POLICY", "sizing": "x4"}, "JSON"),
    ({"action": "RETRY_ROUTING_WITH_PRIORITY", "net": "N"}, "net"),
    ({"evidence_refs": []}, "evidence"),
    ({"evidence_refs": ["r7"]}, "evidence"),
    ({"reason": "this saves 37.5 percent"}, "numbers"),
    ({"expected_effect": "down to 7 sites"}, "numbers"),
])
def test_claims_the_facts_do_not_support_are_refused(change, why):
    d, p = graph.parse_decision(ok(**change), INFO)
    assert d is None and why in p


def test_numbers_from_the_facts_and_revision_ids_are_fine():
    assert graph.parse_decision(ok(reason="r0 has 8 sites and 1 break"), INFO)[1] is None


def test_a_repeated_setting_is_refused():
    st = {"settings": {"sizing": "hd", "order_index": 0}, "revisions": [{"settings": {"sizing": "hd", "order_index": 0}}]}
    d = {"action": "TRY_DIFFERENT_EULER_ORDER", "order_index": 0}
    assert graph.Run.apply(d, st) is None
    assert graph.Run.apply(d | {"order_index": 1}, st) == {"sizing": "hd", "order_index": 1}


def test_score_prefers_passing_then_narrow_then_li1():
    a = {"status": "pass", "sites": 8, "met1_nets": [], "breaks": 1}
    b = {"status": "pass", "sites": 8, "met1_nets": ["Y"], "breaks": 0}
    c = {"status": "fail", "sites": 3, "met1_nets": [], "breaks": 0}
    assert min([b, c, a], key=graph.score) is a


def test_scripted_runs_say_they_are_not_a_model():
    assert "no model" in model.label({"provider": "scripted", "name": ""})


def fake_tool(tmp_path, calls, report):
    def fake(name, args, run_id, log, agent="fixed", timeout=0, on_trace=None, cancel=None):
        calls.append(args)
        out = tmp_path / f"cells/{args['name']}/report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report))
        log.tool(agent, name, args, out, exit_code=0)
        return 0, out
    return fake


def scripted():
    cfg = model.load_config()
    cfg["model"]["provider"] = "scripted"
    return cfg


def test_the_cost_limit_stops_a_run(tmp_path):
    cfg = scripted()
    cfg["model"]["usd_per_mtok_in"] = 10.0
    cfg["limits"]["max_usd"] = 0.001
    r = graph.Run("t", cfg, "A-0101-03", tmp_path)
    assert r.over() is None
    r.calls["in"] = 1000
    assert r.over() == "cost"


def test_a_clean_cell_costs_no_model_call(tmp_path, monkeypatch):
    calls = []
    good = {"status": "pass", "failed_checks": [], "layout": {"width_sites": 3, "diffusion_breaks": 0}}
    monkeypatch.setattr(graph.tools, "call", fake_tool(tmp_path, calls, good))
    s = graph.run("!(A&B)", "t", scripted(), run_id="A-0101-02", log_dir=tmp_path)
    assert s["status"] == "pass" and s["calls"]["model"] == 0 and s["stop"] == "nothing to improve" and len(calls) == 1


def test_a_fail_verdict_cannot_become_a_pass(tmp_path, monkeypatch):
    calls = []
    bad = {"status": "fail", "failed_checks": ["drc"], "layout": {"width_sites": 3, "diffusion_breaks": 0}}
    monkeypatch.setattr(graph.tools, "call", fake_tool(tmp_path, calls, bad))
    s = graph.run("!(A&B)", "t", scripted(), run_id="A-0101-01", log_dir=tmp_path)
    assert s["status"] == "fail" and len(calls) >= 2 and s["log_problems"] == []


def test_a_cancelled_run_stops_building_and_still_ends_with_a_verdict(tmp_path, monkeypatch):
    calls = []
    runs = {}
    bad = {"status": "fail", "failed_checks": ["drc"], "layout": {"width_sites": 3, "diffusion_breaks": 0}}
    inner = fake_tool(tmp_path, calls, bad)

    def stopping(*a, **k):
        runs["r"].stopped.set()
        return inner(*a, **k)

    monkeypatch.setattr(graph.tools, "call", stopping)
    monkeypatch.setattr(graph.tools, "stop_containers", lambda r: None)
    cfg = scripted()
    r = runs["r"] = graph.Run("t", cfg, "A-0101-06", tmp_path)
    st = graph.build_graph(lambda s, c, n: r).invoke({"expr": "!A", "settings": {"sizing": "hd", "order_index": 0}, "revisions": []},
                                                     {"configurable": {"thread_id": "x"}, "recursion_limit": 40})
    assert len(calls) == 1 and st["verdict"]["stop"] == "canceled" and st["verdict"]["log_problems"] == []


def test_cancelling_closes_the_log_once(tmp_path, monkeypatch):
    monkeypatch.setattr(graph.tools, "stop_containers", lambda r: None)
    r = graph.Run("t", scripted(), "A-0101-07", tmp_path)
    r.log.policy("x", "y", {}, "started")
    r.busy = True
    r.cancel()
    r.cancel()
    r.log.policy("x", "y", {}, "the killed tool's line")
    r.busy = False
    import time
    time.sleep(0.3)
    lines = [json.loads(x) for x in (tmp_path / "A-0101-07.jsonl").read_text().splitlines()]
    assert [x["kind"] for x in lines] == ["policy", "policy", "result"] and lines[-1]["status"] == "fail"


def test_the_result_is_the_last_line_of_the_log(tmp_path, monkeypatch):
    calls = []
    good = {"status": "pass", "failed_checks": [], "layout": {"width_sites": 3, "diffusion_breaks": 0}}
    monkeypatch.setattr(graph.tools, "call", fake_tool(tmp_path, calls, good))
    graph.run("!A", "t", scripted(), run_id="A-0101-05", log_dir=tmp_path)
    last = json.loads((tmp_path / "A-0101-05.jsonl").read_text().splitlines()[-1])
    assert last["kind"] == "result" and last["status"] == "pass"


def test_a_broken_model_still_ends_with_a_verdict(tmp_path, monkeypatch):
    calls = []
    okish = {"status": "pass", "failed_checks": [], "layout": {"width_sites": 3, "diffusion_breaks": 1}}
    monkeypatch.setattr(graph.tools, "call", fake_tool(tmp_path, calls, okish))
    cfg = scripted()

    class Broken(model.ChatScripted):
        def _generate(self, *a, **k):
            raise KeyError("message")

    monkeypatch.setattr(graph.model, "chat_model", lambda c: Broken())
    s = graph.run("!A", "t", cfg, run_id="A-0101-04", log_dir=tmp_path)
    assert s["stop"] == "model unavailable" and s["status"] == "pass" and s["log_problems"] == []


@pytest.mark.parametrize("text, ok", [("!(A & B)", True), ("A ^ B ^ C", True), ("A&B&C&D&E", False), ("hello there", False),
                                      ("!(A &", False), ("A", False), ("", False)])
def test_only_a_real_expression_skips_the_model(text, ok):
    assert graph.expression_ok(text) is ok


@pytest.mark.parametrize("text", ["delete the broken DRC case", "Please change the truth table", "mark it as pass", "make this pass",
                                  "skip the LVS check", "make area reduction positive no matter what", "accept anyway", "edit the PDK rules"])
def test_a_rule_refuses_forbidden_requests_before_any_model(text):
    assert graph.FORBIDDEN_TEXT.search(text)


@pytest.mark.parametrize("text", ["why did LVS fail?", "try another Euler order", "show the DRC result", "compare hd and stack sizing"])
def test_ordinary_requests_are_not_forbidden(text):
    assert not graph.FORBIDDEN_TEXT.search(text)


FACTS = {"run": "run:A-1-1", "function": "A^B", "status": "pass", "stop": None, "best_cell": "cell:A-1-1/a_r0", "intent": "BUILD_CELL", "reason": "",
         "revisions": [{"id": "r0", "status": "pass", "sites": 8, "met1_nets": [], "breaks": 1, "failed": [], "sizing": "hd", "cell": "cell:A-1-1/a_r0"}]}


def test_the_fixed_page_passes_its_own_checks():
    assert generative_ui.check_page(generative_ui.fixed_page(FACTS), FACTS) == []


def test_a_failed_cell_is_offered_no_way_to_accept_it():
    page = generative_ui.fixed_page(FACTS | {"status": "fail", "revisions": [FACTS["revisions"][0] | {"status": "fail", "failed": ["drc"]}]})
    assert "Explain why drc failed" in page and not any(w in page.lower() for w in ("accept", "waive", "override"))


def test_an_unclear_request_comes_back_as_its_readings():
    d = FACTS | {"intent": "UNCLEAR", "best_cell": None, "reason": "Two readings fit.",
                 "options": [{"label": "(A and B) or C", "expression": "(A & B) | C"}, {"label": "A and (B or C)", "expression": "A & (B | C)"}]}
    page = generative_ui.fixed_page(d)
    assert page.count("Choice(") == 2 and '"(A & B) | C"' in page and '"A & (B | C)"' in page and "Choices([o0, o1])" in page
    assert generative_ui.check_page(page, d) == []


def test_a_refused_request_gets_a_page_with_no_evidence():
    page = generative_ui.fixed_page(FACTS | {"intent": "FORBIDDEN", "best_cell": None, "reason": "No."})
    assert 'Note("No.")' in page and "Verdict" not in page and "Choice" not in page


@pytest.mark.parametrize("page, why", [
    ('root = Report([x])\nx = Exec("rm")', "unknown component"),
    ('root = Report([x])\nx = Verdict("run:OTHER")', "unknown handle"),
    ('root = Report([x])\nx = CheckMatrix("run:A-1-1")', "takes a cell"),
    ('root = Report([x])\nx = Note("it is 41 percent better")', "numbers"),
    ('root = Report([x])\nx = Note("<script>alert(1)</script>")', "tag"),
    ('root = Report([x])\nx = Note("see https://evil.example")', "link"),
    ('x = Verdict("run:A-1-1")', "root"),
    ("", "empty"),
])
def test_a_bad_page_is_refused(page, why):
    assert any(why in e for e in generative_ui.check_page(page, FACTS))
