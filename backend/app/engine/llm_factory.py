from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from app.models.provider import LLMProvider
from app.core.security import decrypt_api_key


def create_llm_client(
    provider: LLMProvider,
    model_name: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    streaming: bool = True,
    extra_headers: Optional[Dict[str, str]] = None,
) -> ChatOpenAI:
    """
    Creates a unified OpenAI-compatible ChatOpenAI client pointing to the provider's base_url.
    Supports OpenRouter, LiteLLM, Anthropic/Gemini proxies, OpenAI, and Local Ollama/vLLM.
    """
    raw_key = decrypt_api_key(provider.api_key_encrypted)
    api_key = raw_key if raw_key else "EMPTY_KEY"

    # Normalize base_url
    base_url = provider.base_url.rstrip("/")
    if not (base_url.endswith("/v1") or base_url.endswith("/api/v1") or "ollama" in provider.provider_type):
        base_url = f"{base_url}/v1"

    headers: Dict[str, str] = {}
    if provider.default_headers and isinstance(provider.default_headers, dict):
        headers.update({str(k): str(v) for k, v in provider.default_headers.items()})

    if provider.provider_type.lower() == "openrouter":
        headers.setdefault("HTTP-Referer", "https://github.com/omnigensi")
        headers.setdefault("X-Title", "Omnigensi AIaaS")

    if extra_headers:
        headers.update(extra_headers)

    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        base_url=base_url,
        streaming=streaming,
        default_headers=headers if headers else None,
        timeout=120.0,
    )
