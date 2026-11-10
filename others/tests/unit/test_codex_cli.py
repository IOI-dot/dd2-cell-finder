"""The CLI adapter: normal chat-completion JSON out, and no tool use let through. No network here."""
import json
import pytest

pytest.importorskip("langchain_core", reason="make setup installs LangChain")
from dd2_agent import codex_cli


def done(text="{}"):
    return "\n".join(json.dumps(e) for e in [
        {"type": "thread.started"}, {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 3, "cached_input_tokens": 2}}])


def fake_run(stdout, code=0):
    return lambda *a, **k: (code, stdout, "boom")


def test_a_reply_has_the_shape_of_a_chat_completion(monkeypatch):
    monkeypatch.setattr(codex_cli.CodexCLI, "spawn", fake_run(done('{"a":1}')))
    r = codex_cli.CodexCLI().complete([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}])
    assert r["object"] == "chat.completion" and r["choices"][0]["message"] == {"role": "assistant", "content": '{"a":1}'}
    assert r["usage"]["prompt_tokens"] == 10 and r["usage"]["completion_tokens"] == 3 and r["usage"]["total_tokens"] == 13


def test_tool_use_is_refused():
    out = json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}})
    with pytest.raises(codex_cli.CodexError, match="used a tool"):
        codex_cli.CodexCLI.parse_events(out + "\n" + done())


def test_a_failed_turn_and_an_empty_reply_are_errors():
    with pytest.raises(codex_cli.CodexError, match="reported"):
        codex_cli.CodexCLI.parse_events(json.dumps({"type": "turn.failed", "error": {}}))
    with pytest.raises(codex_cli.CodexError, match="no reply"):
        codex_cli.CodexCLI.parse_events("not json\n")


def test_the_command_turns_everything_off():
    argv = codex_cli.CodexCLI().command("/s", None, "/w")
    text = " ".join(map(str, argv))
    for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--sandbox read-only", "features.shell_tool=false",
                 'web_search="disabled"', "--disable plugins", "--disable apps", "--json"):
        assert flag in text
    assert "danger" not in text and "bypass" not in text


def test_a_timeout_kills_the_process():
    cli = codex_cli.CodexCLI(timeout_s=0.3)
    with pytest.raises(codex_cli.CodexError, match="no reply in"):
        cli.spawn(["sleep", "30"], "")


def test_cancel_kills_the_process_at_once():
    import threading
    import time
    ev = threading.Event()
    threading.Timer(0.2, ev.set).start()
    t0 = time.time()
    with pytest.raises(codex_cli.CodexError, match="canceled"):
        codex_cli.CodexCLI().spawn(["sleep", "30"], "", ev)
    assert time.time() - t0 < 3


def test_reasoning_summaries_reach_the_callback():
    seen = []
    out = json.dumps({"type": "item.completed", "item": {"type": "reasoning", "text": "thinking"}}) + "\n" + done()
    codex_cli.CodexCLI.parse_events(out, seen.append)
    assert seen == ["thinking"]


def test_langchain_sees_a_normal_chat_model(monkeypatch):
    from langchain_core.messages import HumanMessage, SystemMessage
    monkeypatch.setattr(codex_cli.CodexCLI, "spawn", fake_run(done("hello")))
    r = codex_cli.ChatCodexCLI().invoke([SystemMessage("s"), HumanMessage("u")])
    assert r.content == "hello" and r.usage_metadata["input_tokens"] == 10
