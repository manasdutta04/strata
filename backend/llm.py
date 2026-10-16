"""LLM access. Default provider shells out to the local Claude Code CLI (no API key)."""
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


def complete(prompt: str, system: str = "", cache: bool = True) -> str:
    """Return raw text. Responses are cached on disk by prompt hash for reproducible runs."""
    key = hashlib.sha256(f"{settings.llm_model}|{system}|{prompt}".encode()).hexdigest()
    path = CACHE_DIR / f"{key}.txt"
    if cache and path.exists():
        return path.read_text(encoding="utf-8")
    text = _call_cli(prompt, system)
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
