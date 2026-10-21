import pytest
from app.engine.token_cost import (
    estimate_tokens_from_text,
    get_model_rates,
    calculate_cost,
    calculate_execution_summary,
)


def test_estimate_tokens():
    text = "Hello world! This is a test sentence for token heuristic."
    tokens = estimate_tokens_from_text(text)
    assert tokens > 0
    assert tokens == len(text) // 4


def test_model_rates_lookup():
    p, c = get_model_rates("gpt-4o")
    assert p == 2.50
    assert c == 10.00

    p_claude, c_claude = get_model_rates("anthropic/claude-3-5-sonnet")
    assert p_claude == 3.00
    assert c_claude == 15.00

    p_deepseek, c_deepseek = get_model_rates("deepseek-chat")
    assert p_deepseek == 0.14
    assert c_deepseek == 0.28


def test_calculate_cost():
    cost = calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    # 1000 * (2.50 / 1M) + 500 * (10.00 / 1M) = 0.0025 + 0.0050 = 0.0075
    assert round(cost, 4) == 0.0075


def test_calculate_execution_summary():
    logs = [
        {"node_id": "node-1", "content_length": 1200},
        {"node_id": "node-2", "content_length": 800, "decision": {"feedback": "Good work."}},
    ]
    summary = calculate_execution_summary(
        task_prompt="Create an AI microservice architecture",
        execution_logs=logs,
        model_name="gpt-4o",
    )
    assert summary["prompt_tokens"] > 0
    assert summary["completion_tokens"] > 0
    assert summary["total_tokens"] == summary["prompt_tokens"] + summary["completion_tokens"]
    assert summary["estimated_cost_usd"] > 0
