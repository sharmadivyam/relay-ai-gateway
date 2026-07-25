"""
Input Guardrails — Phase 4.

Scans every incoming message for prompt injection, jailbreak attempts,
and system-prompt extraction probes using a layered regex pattern library.

Architecture:
  PATTERN_LIBRARY  — dict[category_name -> list[compiled regex]]
  scan_input()     — checks all user/system message content against every
                     category; returns on the first match (fail-fast).

Adding new patterns: append a compiled re.Pattern to the relevant category
list, or add a new category key. No other code needs to change.

Phase 4+ upgrade path:
  Replace or supplement the regex engine with NeMo Guardrails or Llama-Guard
  by swapping the body of scan_input(). GuardrailResult interface stays the same
  so proxy.py is unaffected.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class GuardrailResult:
    action: str                 # "passed" | "blocked"
    reason: Optional[str] = None


# ── Pattern Library ────────────────────────────────────────────────────────
# Each key is a human-readable category used in the block reason.
# Patterns are matched case-insensitively against the full message content.

_F = re.IGNORECASE

PATTERN_LIBRARY: dict[str, list[re.Pattern]] = {

    # ── Instruction override ───────────────────────────────────────────────
    # Classic prompt injection: telling the model to forget its system prompt.
    "instruction_override": [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", _F),
        re.compile(r"disregard\s+((?:all|your|prior|previous)\s+){1,3}instructions?", _F),
        re.compile(r"forget\s+(all\s+)?(previous|prior|your)\s+instructions?", _F),
        re.compile(r"override\s+(your|all)?\s*(instructions?|rules?|guidelines?)", _F),
        re.compile(r"bypass\s+(your|all)?\s*(instructions?|rules?|safety|restrictions?)", _F),
        re.compile(r"your\s+(new\s+)?instructions?\s+are", _F),
    ],

    # ── Jailbreak personas ─────────────────────────────────────────────────
    # DAN, developer mode, and "act as unrestricted AI" patterns.
    "jailbreak_persona": [
        re.compile(r"\bDAN\s+mode\b", _F),
        re.compile(r"\bdo\s+anything\s+now\b", _F),
        re.compile(r"\bdeveloper\s+mode\b", _F),
        re.compile(r"\bjailbreak\b", _F),
        re.compile(r"act\s+as\s+(if\s+you\s+(have\s+no|are\s+without)|an?\s+unrestricted)", _F),
        re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(an?\s+)?(different|unrestricted|evil|unfiltered|jailbroken)", _F),
        re.compile(r"you\s+are\s+now\s+(freed?|unfiltered|unrestricted|evil|without\s+(limits?|rules?|guidelines?))", _F),
        re.compile(r"from\s+now\s+on\s+(you\s+)?(are|will\s+be|must\s+act\s+as)\s+(a\s+)?(new|different|unrestricted)", _F),
    ],

    # ── System prompt extraction ───────────────────────────────────────────
    # Attempts to read the gateway's or model's system prompt.
    "system_prompt_extraction": [
        re.compile(r"(print|repeat|show|reveal|output|display|tell\s+me|what\s+is)\s+(your\s+)?(system\s+prompt|system\s+instructions?|initial\s+instructions?|base\s+prompt)", _F),
        re.compile(r"what\s+(are\s+)?(your|the)\s+system\s+(prompt|instructions?|rules?)", _F),
        re.compile(r"(summarize|repeat|echo)\s+.{0,30}\s+above\s+(this|the)\s+(prompt|instruction|message)", _F),
        re.compile(r"(leak|expose|dump)\s+(your\s+)?(prompt|instructions?|config)", _F),
    ],

    # ── Prompt injection delimiters ────────────────────────────────────────
    # Structural tokens used to inject fake system/instruction blocks.
    "injection_delimiter": [
        re.compile(r"###\s*instruction", _F),
        re.compile(r"<\s*system\s*>", _F),
        re.compile(r"\[INST\]", _F),
        re.compile(r"<\|im_start\|>", _F),
        re.compile(r"<\|system\|>", _F),
        re.compile(r"----+\s*(system|instruction|new\s+task|override)", _F),
        re.compile(r"={3,}\s*(system|instruction|override)", _F),
    ],

    # ── Harmful content requests ───────────────────────────────────────────
    # Direct requests for content that violates acceptable use.
    "harmful_content": [
        re.compile(r"(step[\s-]by[\s-]step|detailed|exact)\s+(instructions?|guide|recipe|tutorial)\s+(to|for|on\s+how\s+to)\s+(make|build|create|synthesize)\s+(a\s+)?(bomb|weapon|malware|virus|ransomware|bioweapon|explosive)", _F),
        re.compile(r"how\s+to\s+(hack|exploit|attack)\s+(a\s+)?(bank|hospital|power\s+grid|government|election)", _F),
        re.compile(r"generate\s+(working\s+)?(malware|ransomware|exploit\s+code|keylogger|rootkit)", _F),
    ],

    # ── Credential / key exfiltration ─────────────────────────────────────
    # Attempts to get the model to output real secrets it may have seen.
    "credential_exfiltration": [
        re.compile(r"(print|output|reveal|show|give\s+me)\s+(the\s+)?(api[\s_-]?key|secret[\s_-]?key|access[\s_-]?token|password|credentials?)", _F),
        re.compile(r"what\s+(is\s+)?(the\s+)?(openai|gemini|anthropic)[\s_-]?(api[\s_-]?)?key", _F),
    ],
}


def _extract_text(messages: list[dict]) -> list[tuple[str, str]]:
    """Returns list of (role, content) pairs with non-empty content."""
    out = []
    for msg in messages:
        content = msg.get("content") or ""
        role = msg.get("role", "user")
        if content.strip():
            out.append((role, content))
    return out


async def scan_input(messages: list[dict]) -> GuardrailResult:
    """
    Scans all messages against the full pattern library.
    Returns on the first match (fail-fast — one block reason is enough).
    Clean messages return action="passed".
    """
    pairs = _extract_text(messages)

    for category, patterns in PATTERN_LIBRARY.items():
        for pattern in patterns:
            for role, content in pairs:
                if pattern.search(content):
                    return GuardrailResult(
                        action="blocked",
                        reason=f"[{category}] Pattern matched in {role} message: '{pattern.pattern}'",
                    )

    return GuardrailResult(action="passed")
