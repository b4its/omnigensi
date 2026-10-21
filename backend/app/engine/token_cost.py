import re
from typing import Tuple, Dict, Any

# Pricing per 1,000,000 tokens (USD)
# Format: (prompt_cost_per_million, completion_cost_per_million)
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    # Anthropic
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-haiku": (0.25, 1.25),
    # DeepSeek
    "deepseek-chat": (0.14, 0.28),
    "deepseek-coder": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    "deepseek-v3": (0.14, 0.28),
    "deepseek-r1": (0.55, 2.19),
    # Meta Llama
    "llama-3.3-70b": (0.35, 0.40),
    "llama-3.1-70b": (0.35, 0.40),
    "llama-3.1-8b": (0.05, 0.05),
    "llama-3.1-405b": (2.00, 2.00),
    # Google Gemini
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    # Qwen & Mistral
    "qwen-2.5-72b": (0.35, 0.40),
    "mistral-large": (2.00, 6.00),
    "mistral-small": (0.20, 0.60),
    # Local
    "ollama": (0.00, 0.00),
    "local": (0.00, 0.00),
}


def estimate_tokens_from_text(text: str) -> int:
    """
    Standard character-to-token heuristic (~4 chars/token).
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def get_model_rates(model_name: str) -> Tuple[float, float]:
    """
    Finds rates (prompt_usd_per_m, completion_usd_per_m) based on model name substring.
    """
    norm = model_name.lower().replace(":", "-").replace("/", "-")
    for key, rates in MODEL_PRICING.items():
        if key in norm:
            return rates
    # Default fallback rate: $1.00 prompt / $2.00 completion per million tokens
    return (1.00, 2.00)


def calculate_cost(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """
    Calculates exact estimated USD cost for a given prompt and completion token count.
    """
    p_rate, c_rate = get_model_rates(model_name)
    cost = (prompt_tokens * (p_rate / 1_000_000.0)) + (completion_tokens * (c_rate / 1_000_000.0))
    return round(cost, 6)


def calculate_execution_summary(
    task_prompt: str,
    execution_logs: list,
    model_name: str = "default",
) -> Dict[str, Any]:
    """
    Computes total input tokens, output tokens, overall tokens, and total cost USD.
    """
    input_tokens = estimate_tokens_from_text(task_prompt)
    output_chars = 0

    for log in execution_logs:
        # Check if content_length is present
        clen = log.get("content_length", 0)
        output_chars += clen
        # Also check decision feedback
        dec = log.get("decision", {})
        if isinstance(dec, dict):
            output_chars += len(dec.get("feedback", ""))

    output_tokens = max(50, output_chars // 4)
    total_tokens = input_tokens + output_tokens
    cost_usd = calculate_cost(model_name, input_tokens, output_tokens)

    return {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": cost_usd,
    }
