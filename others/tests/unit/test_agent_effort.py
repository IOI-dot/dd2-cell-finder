"""Thinking effort follows the kind of work: low to read a request, high to choose a layout setting."""
import pytest

pytest.importorskip("langgraph", reason="make setup installs the agent extra")
from dd2_agent import codex_cli, model

CFG = {"provider": "codex-cli", "name": "gpt-5.6-sol", "reasoning_effort": "high",
       "effort": {"interpreter": "low", "diagnostician": "high", "explainer": "medium"}}


@pytest.mark.parametrize("role, want", [("interpreter", "low"), ("diagnostician", "high"), ("explainer", "medium"), ("someone", "high")])
def test_each_role_gets_its_own_effort(role, want):
    assert model.effort(CFG, role) == want


def test_a_refused_reply_is_retried_one_level_higher_and_never_above_high():
    assert model.effort(CFG, "interpreter", escalate=1) == "medium"
    assert model.effort(CFG, "interpreter", escalate=5) == "high"
    assert model.effort(CFG, "diagnostician", escalate=1) == "high"


def test_without_a_table_every_role_uses_the_one_setting():
    assert model.effort({"reasoning_effort": "medium"}, "interpreter") == "medium"


def test_an_unknown_level_is_refused():
    with pytest.raises(ValueError):
        model.effort({"reasoning_effort": "high", "effort": {"interpreter": "max"}}, "interpreter")


def test_the_effort_of_one_call_reaches_the_command(monkeypatch):
    seen = {}

    class Fake(codex_cli.CodexCLI):
        def complete(self, *a, **k):
            seen["argv"] = self.command("s", None, ".")
            return {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "model": "m", "id": "i"}

    monkeypatch.setattr(codex_cli, "CodexCLI", Fake)
    codex_cli.ChatCodexCLI(effort="high").bind(effort="low").invoke("hi")
    assert "model_reasoning_effort=low" in seen["argv"]


def test_the_label_says_effort_is_by_role():
    assert model.label(CFG) == "codex-cli:gpt-5.6-sol effort by role: interpreter low, diagnostician high, explainer medium"


def _run(tmp_path, replies):
    from langchain_core.messages import HumanMessage

    from dd2_agent import graph
    cfg = model.load_config()
    cfg["model"]["provider"] = "scripted"
    r = graph.Run("t", cfg, "A-0101-09", tmp_path)
    asked = []

    def ask(system, user, fmt, ref, role="diagnostician", escalate=0):
        asked.append((role, escalate))
        r.used = (0, 0)
        return replies[len(asked) - 1], None

    r.ask = ask
    out = r.intent_parser({"messages": [HumanMessage("what is this project?")], "revisions": []})
    return out, asked


INTENT = '{"kind": "ABOUT_PROJECT", "expression": "", "sizing": "hd", "order_index": 0, "revision": "", "reason": "%s", "options": [], "focus": "", "candidate": ""}'


def test_an_unreadable_reply_is_asked_again_one_level_higher(tmp_path):
    out, asked = _run(tmp_path, ["not json", INTENT % "We build cells."])
    assert asked == [("interpreter", 0), ("interpreter", 1)] and out["intent"]["kind"] == "ABOUT_PROJECT"


def test_an_answer_with_a_number_it_was_not_given_is_asked_again(tmp_path):
    out, asked = _run(tmp_path, [INTENT % "It saves 4242 um2.", INTENT % "We build cells."])
    assert asked == [("interpreter", 0), ("interpreter", 1)] and out["intent"]["reason"] == "We build cells."


def test_a_good_reply_costs_one_low_effort_call(tmp_path):
    out, asked = _run(tmp_path, [INTENT % "We build cells."])
    assert asked == [("interpreter", 0)]
