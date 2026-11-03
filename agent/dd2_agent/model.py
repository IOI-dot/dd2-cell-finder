"""The agent's model layer: which chat model, the typed decision it must return, and the prompts.

Every reply is untrusted: graph.py validates it before anything runs. `scripted` is not a model. It
is a fixed rule set for tests and for machines with no CLI, and its log lines say so, so a scripted
run can never pass for an AI decision.
"""
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, ConfigDict

from dd2 import paths

from . import codex_cli

CONFIG = paths.ROOT / "config" / "agent.toml"
ACTIONS = ("TRY_DIFFERENT_EULER_ORDER", "RETRY_ROUTING_WITH_PRIORITY", "STAY_ON_LI1", "SWITCH_SIZING_POLICY", "STOP_AND_REPORT")
FORBIDDEN = ("PATCH_CHECKER", "PATCH_PDK", "CHANGE_TRUTH_TABLE", "EDIT_BROKEN_TEST", "EXECUTE_SHELL",
             "ALTER_REPORTED_MEASUREMENT", "MARK_PASS")


class Decision(BaseModel):
    """overview 8.4's typed action. Unknown fields and unknown actions fail validation."""
    model_config = ConfigDict(extra="forbid")
    action: Literal["TRY_DIFFERENT_EULER_ORDER", "RETRY_ROUTING_WITH_PRIORITY", "STAY_ON_LI1", "SWITCH_SIZING_POLICY", "STOP_AND_REPORT"]
    order_index: int
    sizing: Literal["hd", "stack", ""]
    net: str
    reason: str
    evidence_refs: list[str]
    expected_effect: str


class Reading(BaseModel):
    """One possible meaning of an unclear request, offered back to the person as a button."""
    model_config = ConfigDict(extra="forbid")
    label: str
    expression: str


class Intent(BaseModel):
    """What the Request Interpreter may extract from a sentence (implementation plan, Appendix A)."""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["BUILD_CELL", "TRY_CANDIDATE", "COMPARE_CANDIDATES", "EXPLAIN_CHECK", "DISPLAY_PREVIEW", "RESTORE_REVISION", "ABOUT_PROJECT", "FORBIDDEN", "UNCLEAR"]
    expression: str
    sizing: Literal["hd", "stack"]
    order_index: int
    revision: str
    reason: str
    options: list[Reading]
    focus: Literal["", "network", "euler", "layout", "frame", "drc", "abutment", "extract", "lvs", "rc", "spice", "verilog", "model"]


def json_format(schema: type[BaseModel]) -> dict:
    return {"type": "json_schema", "json_schema": {"name": schema.__name__, "strict": True, "schema": schema.model_json_schema()}}


def load_config(path: Path = CONFIG) -> dict:
    return tomllib.loads(Path(path).read_text())


def prompt_ref(name: str = "diagnostician") -> tuple:
    """The system prompt (guardrails, then the role) and its log reference: path@hash of the text."""
    text = (paths.ROOT / "prompts" / "guardrails.md").read_text() + "\n\n" + (paths.ROOT / "prompts" / f"{name}.md").read_text()
    return text, f"prompts/{name}.md@{hashlib.sha256(text.encode()).hexdigest()[:8]}"


class ChatScripted(BaseChatModel):
    """The rule set: next untried ordering while anything can improve, else stop."""

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        s = json.loads(str(messages[-1].content).split("<facts>")[-1].split("</facts>")[0])
        cur, rev = s["current"], s["current"]["id"]
        pick = {"action": "STOP_AND_REPORT", "order_index": 0, "sizing": "", "net": "", "reason": "rule: nothing left to try",
                "evidence_refs": [rev], "expected_effect": "stop"}
        if s["untried"]["orders"] and (cur["status"] != "pass" or cur["met1_nets"] or cur["breaks"]):
            pick |= {"action": "TRY_DIFFERENT_EULER_ORDER", "order_index": s["untried"]["orders"][0],
                     "reason": "rule: next ordering", "expected_effect": "fewer met1 nets or breaks"}
        msg = AIMessage(json.dumps(pick), usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        return ChatResult(generations=[ChatGeneration(message=msg)])


def chat_model(cfg: dict) -> BaseChatModel:
    if cfg["provider"] == "codex-cli":
        return codex_cli.ChatCodexCLI(model_name=cfg["name"], effort=cfg.get("reasoning_effort", "high"), timeout_s=cfg.get("timeout_s", 180))
    if cfg["provider"] == "scripted":
        return ChatScripted()
    raise ValueError(f"unknown provider {cfg['provider']!r}")


def label(cfg: dict) -> str:
    if cfg["provider"] == "scripted":
        return "scripted (rule set, no model)"
    return f"{cfg['provider']}:{cfg['name']} effort={cfg.get('reasoning_effort', 'high')}"


def available(cfg: dict) -> bool:
    if cfg["provider"] == "codex-cli":
        return codex_cli.CodexCLI().available()
    return cfg["provider"] == "scripted"
