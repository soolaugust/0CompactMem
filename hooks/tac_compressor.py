"""
tac_compressor.py — Thinking-as-Compression (TaC) for memory chunks

Inspired by "Thinking as Compression" (Ma et al., 2026, arXiv:2605.28713):
reasoning models naturally compress long contexts by organizing task-relevant
information during their thinking process.

This module provides TaC compression for PreCompact and other contexts where
we need to fit more knowledge into a limited token budget.

Design choices:
  - Uses local Ollama model (zero API key dependency)
  - Fallback to truncation if Ollama unavailable
  - Budget-aware: output guaranteed <= target chars
"""

import os
import time

# TaC prompt template
TAC_PROMPT = """You are compressing knowledge for an AI assistant's persistent memory.
Preserve ALL decisions, constraints, and facts. Remove discussion, reasoning process, and filler.
Output ONLY the compressed text — one line per item, no explanation.

Budget: {budget} characters maximum.

Knowledge to compress:
{context}

Compressed:"""


def tac_compress(text: str, budget_chars: int = 1500,
                 model: str = "gemma3:1b") -> tuple[str, dict]:
    """
    Compress text using TaC (Thinking as Compression).

    Returns (compressed_text, metadata_dict).
    Falls back to truncation if Ollama unavailable.
    """
    if not text or len(text) <= budget_chars:
        return text, {"method": "passthrough", "ratio": 1.0}

    try:
        import ollama
        t0 = time.perf_counter()
        response = ollama.generate(
            model=model,
            prompt=TAC_PROMPT.format(budget=budget_chars, context=text),
            options={"num_predict": budget_chars // 2}
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        compressed = response["response"].strip()

        # Remove <think> blocks if present
        if "<think>" in compressed:
            import re
            compressed = re.sub(r"<think>.*?</think>", "", compressed, flags=re.DOTALL).strip()

        # Enforce budget hard limit
        if len(compressed) > budget_chars:
            compressed = compressed[:budget_chars]

        ratio = len(text) / max(len(compressed), 1)
        return compressed, {
            "method": "tac",
            "model": model,
            "original_chars": len(text),
            "compressed_chars": len(compressed),
            "ratio": round(ratio, 2),
            "elapsed_ms": round(elapsed_ms, 1),
        }

    except Exception as e:
        # Fallback: simple truncation
        truncated = text[:budget_chars]
        return truncated, {
            "method": "truncation_fallback",
            "reason": str(e),
            "original_chars": len(text),
            "compressed_chars": len(truncated),
            "ratio": round(len(text) / budget_chars, 2),
        }
