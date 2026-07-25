"""
Output Guardrails — Phase 4.

Scans LLM responses for PII and sensitive data, redacting matches in-place
before the content is returned to the client or stored in the semantic cache.

Architecture:
  REDACTION_RULES  — ordered list of (label, compiled regex, replacement)
  scan_output()    — applies every rule sequentially; returns the (possibly
                     modified) content and an action of "passed" or "redacted".

Rules are applied in order. All rules always run (no fail-fast) so that
a response containing multiple PII types is fully redacted in one pass.

Adding new rules: append a RedactionRule to REDACTION_RULES.
No other code needs to change.

Phase 4+ upgrade path:
  Add an ML-based PII detector (e.g. spaCy NER, Microsoft Presidio) by calling
  it after the regex pass. The OutputGuardrailResult interface is unchanged.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OutputGuardrailResult:
    content: str
    action: str                         # "passed" | "redacted"
    reason: Optional[str] = None        # human-readable list of what was redacted
    redacted_types: list[str] = field(default_factory=list)


@dataclass
class RedactionRule:
    label: str          # used in reason string and telemetry
    pattern: re.Pattern
    replacement: str    # what the matched text is replaced with


_F = re.IGNORECASE

REDACTION_RULES: list[RedactionRule] = [

    # ── Social Security Numbers ────────────────────────────────────────────
    # Matches: 123-45-6789  |  123 45 6789  |  123456789
    # Word boundaries are relaxed to (?<!\d)/(?!\d) so markdown bold markers
    # like **123-45-6789** don't prevent the match.
    RedactionRule(
        label="SSN",
        pattern=re.compile(r"(?<!\d)\d{3}([-\s]?)\d{2}\1\d{4}(?!\d)"),
        replacement="[SSN REDACTED]",
    ),

    # ── Credit / Debit Card Numbers ────────────────────────────────────────
    # Matches 13-16 digit card numbers with optional spaces or dashes.
    RedactionRule(
        label="CREDIT_CARD",
        pattern=re.compile(r"(?<!\d)(?:\d{4}[\s-]?){3}\d{1,4}(?!\d)"),
        replacement="[CARD REDACTED]",
    ),

    # ── Email Addresses ────────────────────────────────────────────────────
    RedactionRule(
        label="EMAIL",
        pattern=re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        replacement="[EMAIL REDACTED]",
    ),

    # ── Phone Numbers (US and international) ──────────────────────────────
    # Matches: +1-800-555-0199 | (800) 555-0199 | 800.555.0199 | 8005550199
    RedactionRule(
        label="PHONE",
        pattern=re.compile(
            r"\b(\+?1[\s\-.]?)?"
            r"(\(?\d{3}\)?[\s\-.]?)"
            r"\d{3}[\s\-.]?\d{4}\b"
        ),
        replacement="[PHONE REDACTED]",
    ),

    # ── API Keys and Bearer Tokens ─────────────────────────────────────────
    # OpenAI-style: sk-...  |  Anthropic: sk-ant-...  |  Generic Bearer tokens
    RedactionRule(
        label="API_KEY",
        pattern=re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}\b"),
        replacement="[API KEY REDACTED]",
    ),
    RedactionRule(
        label="BEARER_TOKEN",
        pattern=re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b", _F),
        replacement="[BEARER TOKEN REDACTED]",
    ),

    # ── IPv4 Addresses ─────────────────────────────────────────────────────
    # Avoids false-positive on version strings like 1.2.3.4 by requiring
    # each octet to be a valid 0-255 range.
    RedactionRule(
        label="IP_ADDRESS",
        pattern=re.compile(
            r"\b"
            r"(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\."
            r"(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\."
            r"(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\."
            r"(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)"
            r"\b"
        ),
        replacement="[IP REDACTED]",
    ),

    # ── Passwords in plaintext ─────────────────────────────────────────────
    # Catches common "password: xxxxx" or "passwd=xxxxx" patterns.
    RedactionRule(
        label="PASSWORD",
        pattern=re.compile(r"\b(password|passwd|pwd)\s*[:=]\s*\S+", _F),
        replacement="[PASSWORD REDACTED]",
    ),
]


async def scan_output(content: str) -> OutputGuardrailResult:
    """
    Applies every redaction rule to the LLM output in order.
    Returns the redacted content and a summary of what was found.
    All rules always run — multiple PII types are fully redacted in one pass.
    """
    # Normalise Unicode hyphens/dashes → ASCII hyphen so regex patterns that
    # match SSNs and card numbers don't miss digits separated by typographic
    # variants (e.g. NON-BREAKING HYPHEN U+2011 produced by some LLMs).
    redacted_content = content.translate(str.maketrans(
        "\u2010\u2011\u2012\u2013\u2014\u2015\u2212",
        "-------",
    ))
    triggered: list[str] = []

    for rule in REDACTION_RULES:
        new_content, count = rule.pattern.subn(rule.replacement, redacted_content)
        if count > 0:
            redacted_content = new_content
            triggered.append(f"{rule.label}(x{count})")

    if triggered:
        return OutputGuardrailResult(
            content=redacted_content,
            action="redacted",
            reason=f"Redacted: {', '.join(triggered)}",
            redacted_types=[t.split("(")[0] for t in triggered],
        )

    return OutputGuardrailResult(content=content, action="passed")
