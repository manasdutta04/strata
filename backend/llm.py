"""LLM access. Default provider shells out to the local Claude Code CLI (no API key).

LLM_PROVIDER=anthropic calls the Anthropic Messages API instead (LLM_API_KEY or ANTHROPIC_API_KEY), which is
what a hosted deployment uses since it has no logged-in CLI."""
import hashlib
import json
import subprocess
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from config import settings

T = TypeVar("T", bound=BaseModel)
CACHE_DIR = Path(".llm_cache")


def _call_cli(prompt: str, system: str) -> str:
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--tools", ""]
    if system:
        cmd += ["--system-prompt", system]
    if settings.llm_model:
        cmd += ["--model", settings.llm_model]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {proc.stderr[:500]}")
    return json.loads(proc.stdout)["result"]


DEFAULT_API_MODEL = "claude-opus-5-5"


def _call_api(prompt: str, system: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.llm_api_key or None)  # None: SDK reads ANTHROPIC_API_KEY
    kwargs = {"system": system} if system else {}
    resp = client.beta.messages.create(
        model=settings.llm_model or DEFAULT_API_MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},  # short extraction and diff drafting
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # a policy decline is retried server-side on a fallback model
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Anthropic API declined the request")
    return "".join(b.text for b in resp.content if b.type == "text")


def complete(prompt: str, system: str = "", cache: bool = True) -> str:
    """Return raw text. Responses are cached on disk by prompt hash for reproducible runs."""
    key = hashlib.sha256(f"{settings.llm_model}|{system}|{prompt}".encode()).hexdigest()
    path = CACHE_DIR / f"{key}.txt"
    if cache and path.exists():
        return path.read_text(encoding="utf-8")
    text = _call_api(prompt, system) if settings.llm_provider == "anthropic" else _call_cli(prompt, system)
    if cache:
        CACHE_DIR.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text


def structured(prompt: str, schema: type[T], system: str = "") -> T:
    """Ask for JSON matching `schema`; validate with Pydantic, retry once on bad output."""
    spec = json.dumps(schema.model_json_schema())
    full = f"{prompt}\n\nRespond with ONLY a JSON object matching this JSON schema:\n{spec}"
    last: Exception | None = None
    for attempt in range(2):
        raw = complete(full if attempt == 0 else full + "\nPrevious reply was invalid JSON.", system, cache=attempt == 0)
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return schema.model_validate_json(raw)
        except Exception as e:  # noqa: BLE001
            last = e
    raise ValueError(f"LLM output failed validation: {last}")
