"""
LangSmith tracing, set up once for every way the pipeline runs (the API server and the scripts
alike): config.py calls configure_tracing() as soon as the settings are read, before anything
is traced.

What may leave for LangSmith is decided in the one client every trace goes through (LangChain's
model calls, LangGraph's nodes and the @traceable functions), not by each caller. With
settings.langsmith_hide_content on, the default:
- the inputs and outputs of every run are hidden: prompts, responses, node state;
- metadata keeps only the keys allowed below, none of which can carry data; any other key (a
  supplier name, say) is dropped;
- an error keeps only the exception's type and where it was raised (file, line, function): its
  message can quote data, such as an output that failed to parse, and is not sent;
- run names are fixed (trace_config).
Turn it off (LANGSMITH_HIDE_CONTENT=false) only on synthetic data: then everything is sent.
"""
import os
import re
from typing import Any

# Metadata that may be sent: the ids and names set in code, and what LangChain and LangGraph add
# (model and provider names, node names, steps)
METADATA_KEYS = {"env", "run_id", "checks", "attempt", "revision_id"}
METADATA_PREFIXES = ("ls_", "langgraph_", "checkpoint_")

# An exception's type as repr() starts it ("ValueError('...')"), or as the last line of a
# traceback names it ("openai.BadRequestError: ..."); only names shaped like an exception's
_REPR_TYPE = re.compile(r"\s*([A-Za-z_][\w.]*)\(")
_LINE_TYPE = re.compile(r"((?:[A-Za-z_]\w*\.)*[A-Z]\w*(?:Error|Exception|Exit|Interrupt|Timeout|Cancelled|Warning))(?::|$)")
_FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
_SEP = re.compile(r"[\\/]")
FRAMES_KEPT = 8

_hide = True


def safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Only the metadata keys that cannot carry data."""
    return {k: v for k, v in metadata.items() if k in METADATA_KEYS or k.startswith(METADATA_PREFIXES)}


def safe_error(error: str) -> str:
    """An error as LangSmith receives it (repr of the exception, then its traceback), reduced to the
    exception's type and the frames it passed through: file (its last two path parts, so no local
    folder names), line and function. The message, which can quote data, is left out."""
    kinds = [m.group(1) for line in error.splitlines() if (m := _LINE_TYPE.match(line))]
    first = _REPR_TYPE.match(error)
    kind = kinds[-1] if kinds else (first.group(1) if first else "Error")
    frames = ["/".join(_SEP.split(path)[-2:]) + f":{line} in {func}"
              for path, line, func in _FRAME.findall(error)][-FRAMES_KEPT:]
    return f"{kind} (message not sent)" + "".join(f"\n  at {f}" for f in frames)


def _mask(data: dict[str, Any]) -> dict[str, Any]:
    """The client's anonymizer. With inputs and outputs hidden outright, it is given each run's
    metadata, and each run's error as {"error": text}."""
    if set(data) == {"error"} and isinstance(data["error"], str):
        return {"error": safe_error(data["error"])}
    return safe_metadata(data)


def configure_tracing(settings: Any) -> None:
    """Tracing as the settings say, through one client that applies the rules above."""
    global _hide
    _hide = bool(settings.langsmith_hide_content)
    if _hide:  # also for any client made elsewhere, which reads these
        os.environ["LANGSMITH_HIDE_INPUTS"] = "true"
        os.environ["LANGSMITH_HIDE_OUTPUTS"] = "true"
    if not settings.langchain_tracing_v2:
        return
    key = re.sub(r"[^a-zA-Z0-9_-]", "", settings.langchain_api_key or "")  # stray spaces or quotes
    os.environ.update({"LANGCHAIN_TRACING_V2": "true", "LANGSMITH_TRACING": "true",
                       "LANGCHAIN_ENDPOINT": settings.langchain_endpoint, "LANGCHAIN_API_KEY": key,
                       "LANGCHAIN_PROJECT": settings.langchain_project})
    import langsmith
    hidden = {"hide_inputs": True, "hide_outputs": True, "anonymizer": _mask} if _hide else {}
    langsmith.configure(client=langsmith.Client(api_url=settings.langchain_endpoint, api_key=key, **hidden))


def trace_config(name: str, run_id: str, env: str, supplier: str = "") -> dict[str, Any]:
    """A graph run's name and metadata: a fixed name while content is hidden; on synthetic data
    the supplier is added to both, to find a run."""
    if _hide or not supplier:
        return {"run_name": name, "metadata": {"env": env, "run_id": run_id}}
    return {"run_name": f"{name}-{supplier}", "metadata": {"supplier": supplier, "env": env, "run_id": run_id}}
