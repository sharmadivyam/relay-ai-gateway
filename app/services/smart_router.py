from app.config import get_settings


def route(prompt: str, token_count: int) -> dict:
    """Returns {model, tier, reason} — pure function, no I/O."""
    settings = get_settings()
    has_code = "```" in prompt or "def " in prompt or "function " in prompt
    complex_keywords = (
        "explain", "analyze", "step by step", "summarize in detail",
        "write", "describe", "compare", "critique", "detail", "elaborate",
        "protest", "opinion", "think about",
    )
    is_complex = (
        token_count > 150
        or has_code
        or any(k in prompt.lower() for k in complex_keywords)
    )
    if is_complex:
        return {
            "model": settings.premium_model,
            "tier": "complex",
            "reason": "length_or_code_or_keyword",
        }
    return {
        "model": settings.cheap_model,
        "tier": "simple",
        "reason": "short_plain_prompt",
    }
