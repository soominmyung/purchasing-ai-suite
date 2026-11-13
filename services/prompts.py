"""
Agent prompts, loaded from prompts/.

Run records store a SHA-256 of each prompt as loaded here, which matches the file in the Git
history that produced the run, and PROMPT_VERSION, a short hash of the whole set, identifies the
set in the run statistics. Files are read exactly as written, including leading and trailing
whitespace.
"""
import hashlib
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# The text of each prompt, as loaded at start-up (what the agents use).
_loaded: dict[str, str] = {}


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt '{name}' not found ({path}).")
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    _loaded[name] = text
    return text


def prompt_hashes() -> dict[str, str]:
    """SHA-256 of each prompt, as loaded, for the run record."""
    return {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in sorted(_loaded.items())}


def prompt_texts() -> dict[str, str]:
    """The exact text of each prompt, as loaded."""
    return dict(sorted(_loaded.items()))


ANALYSIS_AGENT_SYSTEM = load_prompt("analysis")
# Sent back with the failures when the analysis fails a blocking check ({failures}).
ANALYSIS_REVISION_REQUEST = load_prompt("analysis_revision_request")
# The reports are assembled in code; one agent writes the purchase request's narrative.
APPROVAL_AGENT_SYSTEM = load_prompt("approval_request")
EMAIL_DRAFT_AGENT_SYSTEM = load_prompt("email_draft")
# Email check and rewrite: {email} and {feedback} are filled in by services/agents.py.
EMAIL_VALIDATOR_SYSTEM = load_prompt("email_validator_system")
EMAIL_VALIDATOR_TEMPLATE = load_prompt("email_validator")
EMAIL_REVISION_SYSTEM_SUFFIX = load_prompt("email_revision_system_suffix")
EMAIL_REVISION_REQUEST_TEMPLATE = load_prompt("email_revision_request")

# The prompt set in use, recorded with every run: 12 hex digits of a SHA-256 over every prompt's hash.
PROMPT_VERSION = hashlib.sha256(
    "".join(f"{name}:{h}\n" for name, h in prompt_hashes().items()).encode("utf-8")).hexdigest()[:12]
