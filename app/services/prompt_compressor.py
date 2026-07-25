_compressor = None  # lazy singleton — importing llmlingua pulls torch/transformers,
                    # so we defer until a prompt actually hits the threshold.


def get_compressor():
    global _compressor
    if _compressor is None:
        from llmlingua import PromptCompressor  # deferred import keeps server startup fast
        _compressor = PromptCompressor(
            model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
        )
    return _compressor


def maybe_compress(prompt: str, token_count: int, threshold: int) -> dict:
    """
    Returns a dict with keys: prompt, compressed, original_tokens, final_tokens.

    If token_count is below threshold the prompt is returned unchanged.
    If at or above threshold the prompt is compressed to ~50% of its tokens.
    """
    if token_count < threshold:
        return {
            "prompt": prompt,
            "compressed": False,
            "original_tokens": token_count,
            "final_tokens": token_count,
        }
    result = get_compressor().compress_prompt(prompt, rate=0.5)
    return {
        "prompt": result["compressed_prompt"],
        "compressed": True,
        "original_tokens": token_count,
        "final_tokens": result["compressed_tokens"],
    }
