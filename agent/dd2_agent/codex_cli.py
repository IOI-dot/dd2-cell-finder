"""The model behind the agent: Codex CLI, wrapped so that the rest of the code sees a normal chat API.

`CodexCLI.complete` takes OpenAI-style messages and an OpenAI-style `response_format`, and returns an
OpenAI-style chat completion as a plain dict. `ChatCodexCLI` is the same thing as a LangChain chat model.

Codex is a coding agent, so it is run here as a model and nothing else: an empty scratch directory,
a read-only sandbox, no user config (so no MCP servers, plugins or rules), no session files, no
web search, no shell tool, and our prompt in place of its own. A reply that reports any tool use is
refused: a model that acted on its own is a guardrail failure, not an answer.
"""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

ALLOWED_ITEMS = {"agent_message", "reasoning"}


class CodexError(OSError):
    """The CLI failed, timed out, or did something a plain model must not do."""


class CodexCLI:
    def __init__(self, model: str = "gpt-5.6-sol", effort: str = "high", timeout_s: float = 180, binary: str = "codex"):
        self.model, self.effort, self.timeout_s, self.binary = model, effort, timeout_s, binary

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def command(self, system_file: Path, schema_file: Path | None, cwd: Path) -> list:
        argv = [self.binary, "exec", "-m", self.model, "-c", f"model_reasoning_effort={self.effort}",
                "--ignore-user-config", "--ignore-rules", "--sandbox", "read-only", "--skip-git-repo-check",
                "--ephemeral", "-c", f'model_instructions_file="{system_file}"', "-c", 'web_search="disabled"',
                "-c", 'model_reasoning_summary="concise"',
                "-c", "features.shell_tool=false", "--disable", "plugins", "--disable", "apps", "--json", "-C", str(cwd)]
        return argv + (["--output-schema", str(schema_file)] if schema_file else []) + ["-"]

    @staticmethod
    def render(messages: list) -> tuple:
        """(system text, conversation text). A one-shot CLI has no message list, so roles become labels."""
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        turns = [(m["role"], m["content"]) for m in messages if m["role"] != "system"]
        if len(turns) == 1:
            return system, turns[0][1]
        return system, "\n\n".join(f"[{r}]\n{c}" for r, c in turns)

    @staticmethod
    def parse_events(stdout: str, on_thought=None) -> tuple:
        """(reply text, usage) from `codex exec --json`, refusing any tool use."""
        text, usage = None, {}
        for line in stdout.splitlines():
            if not line.startswith("{"):
                continue
            ev = json.loads(line)
            if ev.get("type") == "item.completed":
                item = ev.get("item", {})
                if item.get("type") not in ALLOWED_ITEMS:
                    raise CodexError(f"the model used a tool: {item.get('type')}")
                if item.get("type") == "agent_message":
                    text = item.get("text")
                elif on_thought and item.get("text"):
                    on_thought(item["text"])
            elif ev.get("type") == "turn.completed":
                usage = ev.get("usage", {})
            elif ev.get("type") in ("turn.failed", "error"):
                raise CodexError(f"codex reported: {json.dumps(ev)[:300]}")
        if text is None:
            raise CodexError("codex gave no reply")
        return text, usage

    def spawn(self, argv: list, prompt: str, cancel=None) -> tuple:
        """Run the CLI: (exit code, stdout, stderr). `cancel` is a threading.Event that kills it."""
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        out = {}
        t = threading.Thread(target=lambda: out.update(zip(("o", "e"), p.communicate(prompt))), daemon=True)
        t.start()
        deadline = time.time() + self.timeout_s
        while t.is_alive():
            t.join(0.2)
            stopped = bool(cancel and cancel.is_set())
            if t.is_alive() and (stopped or time.time() > deadline):
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                t.join(5)
                raise CodexError("canceled" if stopped else f"no reply in {self.timeout_s} s")
        return p.returncode, out.get("o", ""), out.get("e", "")

    def complete(self, messages: list, response_format: dict | None = None, on_thought=None, cancel=None) -> dict:
        """One chat completion, in the shape of the OpenAI API."""
        system, prompt = self.render(messages)
        with tempfile.TemporaryDirectory(prefix="dd2_model_") as tmp:
            d = Path(tmp).resolve()
            (d / "system.md").write_text(system or "You are a careful assistant.")
            schema = None
            if response_format and response_format.get("type") == "json_schema":
                schema = d / "schema.json"
                schema.write_text(json.dumps(response_format["json_schema"]["schema"]))
            work = d / "empty"
            work.mkdir()
            t0 = time.time()
            code, stdout, stderr = self.spawn(self.command(d / "system.md", schema, work), prompt, cancel)
        if code:
            raise CodexError(f"codex exited {code}: {stderr[-300:]}")
        text, usage = self.parse_events(stdout, on_thought)
        return {"id": f"chatcmpl-{uuid.uuid4().hex}", "object": "chat.completion", "created": int(t0), "model": self.model,
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0),
                          "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                          "prompt_tokens_details": {"cached_tokens": usage.get("cached_input_tokens", 0)},
                          "completion_tokens_details": {"reasoning_tokens": usage.get("reasoning_output_tokens", 0)}},
                "system_fingerprint": f"codex-exec effort={self.effort}", "latency_s": round(time.time() - t0, 2)}


ROLES = ((SystemMessage, "system"), (HumanMessage, "user"), (AIMessage, "assistant"))


def to_openai(messages) -> list:
    out = []
    for m in messages:
        role = next((r for cls, r in ROLES if isinstance(m, cls)), None)
        if role is None:
            raise ValueError(f"unsupported message type {type(m).__name__}")
        out.append({"role": role, "content": m.content if isinstance(m.content, str) else json.dumps(m.content)})
    return out


class ChatCodexCLI(BaseChatModel):
    """LangChain's view of CodexCLI. `.bind(response_format=...)` asks for structured output."""

    model_name: str = "gpt-5.6-sol"
    effort: str = "high"
    timeout_s: float = 180

    @property
    def _llm_type(self) -> str:
        return "codex-cli"

    @property
    def _identifying_params(self) -> dict:
        return {"model_name": self.model_name, "effort": self.effort}

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        r = CodexCLI(self.model_name, kwargs.get("effort") or self.effort, self.timeout_s).complete(to_openai(messages), kwargs.get("response_format"),
                                                                            kwargs.get("on_thought"), kwargs.get("cancel"))
        u = r["usage"]
        msg = AIMessage(r["choices"][0]["message"]["content"], response_metadata={"model_name": r["model"], "id": r["id"]},
                        usage_metadata={"input_tokens": u["prompt_tokens"], "output_tokens": u["completion_tokens"],
                                        "total_tokens": u["total_tokens"]})
        return ChatResult(generations=[ChatGeneration(message=msg)], llm_output={"token_usage": u, "model_name": r["model"]})
