"""Provider probing shared by registration, editing and testing.

Two different questions matter to an operator, and they are not the same:

* **Reachability** - can we list models at ``/models``? (cheap, no tokens)
* **Usability** - does a chat completion with a specific model actually
  return content? (costs a few tokens, but proves key + model + routing)

This module answers both without ever substituting fake data, unlike the
legacy ``GET /providers/{id}/models`` behaviour.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("omnigensi.providers")

REQUEST_TIMEOUT = 12.0
CHAT_TIMEOUT = 60.0

# Candidate model-listing endpoints per provider shape.
def _model_endpoints(base_url: str) -> List[str]:
    base = base_url.rstrip("/")
    if base.endswith("/v1") or base.endswith("/api/v1"):
        return [f"{base}/models"]
    return [f"{base}/v1/models", f"{base}/models", f"{base}/api/tags"]


def build_chat_url(base_url: str, provider_type: str = "custom") -> str:
    """Absolute URL of the OpenAI-compatible chat completions endpoint."""
    base = base_url.rstrip("/")
    if base.endswith("/v1") or base.endswith("/api/v1"):
        return f"{base}/chat/completions"
    if provider_type.lower() == "ollama" and base.endswith("/api"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


@dataclass
class ModelDiscovery:
    """Result of asking a provider for its model list."""

    ok: bool
    models: List[Dict[str, Any]] = field(default_factory=list)
    checked_url: Optional[str] = None
    status_code: Optional[int] = None
    latency_ms: int = 0
    error: Optional[str] = None


def _normalise_model(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Maps OpenAI-style and Ollama-style entries onto one shape."""
    model_id = raw.get("id") or raw.get("model") or raw.get("name")
    if not model_id:
        return None

    pricing = raw.get("pricing") if isinstance(raw.get("pricing"), dict) else {}
    context_length = raw.get("context_length")
    if context_length is None and isinstance(raw.get("top_provider"), dict):
        context_length = raw["top_provider"].get("context_length")

    return {
        "model_id": str(model_id),
        "display_name": raw.get("name") or str(model_id),
        "context_length": context_length if isinstance(context_length, int) else None,
        "description": raw.get("description")
        or (
            f"Format: {raw.get('details', {}).get('format', 'ollama')}"
            if isinstance(raw.get("details"), dict)
            else None
        ),
        "pricing": pricing,
    }


async def discover_models(
    base_url: str,
    api_key: Optional[str],
    default_headers: Optional[Dict[str, Any]] = None,
) -> ModelDiscovery:
    """Fetch the model list from a provider, reporting failures truthfully."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    if default_headers:
        headers.update({str(k): str(v) for k, v in default_headers.items()})

    started = time.perf_counter()
    last_error = "No candidate endpoint responded"
    last_status: Optional[int] = None
    last_url: Optional[str] = None

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, verify=False) as client:
        for url in _model_endpoints(base_url):
            try:
                resp = await client.get(url, headers=headers)
                last_url, last_status = url, resp.status_code

                if resp.status_code in (401, 403):
                    return ModelDiscovery(
                        ok=False,
                        status_code=resp.status_code,
                        checked_url=url,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        error="Authentication failed - check the API key",
                    )

                if resp.status_code != 200:
                    last_error = f"Provider responded with HTTP {resp.status_code}"
                    continue

                payload = resp.json()
                entries: List[Dict[str, Any]] = []
                if isinstance(payload, dict):
                    for key in ("data", "models"):
                        block = payload.get(key)
                        if isinstance(block, list):
                            entries = [_normalise_model(m) for m in block if isinstance(m, dict)]
                            entries = [e for e in entries if e]
                            break

                return ModelDiscovery(
                    ok=True,
                    models=entries,
                    checked_url=url,
                    status_code=resp.status_code,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            except httpx.TimeoutException:
                last_error = "Connection timed out"
            except Exception as exc:  # noqa: BLE001 - surfaced to the operator
                last_error = str(exc)

    return ModelDiscovery(
        ok=False,
        status_code=last_status,
        checked_url=last_url,
        latency_ms=int((time.perf_counter() - started) * 1000),
        error=last_error,
    )


@dataclass
class ChatProbe:
    """Result of a real chat completion against one model."""

    ok: bool
    model_id: str
    response_text: Optional[str] = None
    latency_ms: int = 0
    status_code: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    error: Optional[str] = None
    checked_url: Optional[str] = None


def _extract_text(payload: Any) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """Pulls assistant text and token usage out of an OpenAI/Ollama reply."""
    if not isinstance(payload, dict):
        return None, None, None

    text = None
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] or {}
        message = first.get("message") or {}
        if isinstance(message, dict):
            text = message.get("content")
        if not text:
            text = first.get("text")

    # Ollama native shape
    if not text and isinstance(payload.get("message"), dict):
        text = payload["message"].get("content")
    if not text and isinstance(payload.get("response"), str):
        text = payload["response"]

    usage = payload.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens") or payload.get("prompt_eval_count")
    completion_tokens = usage.get("completion_tokens") or payload.get("eval_count")
    return text, prompt_tokens, completion_tokens


async def probe_chat(
    base_url: str,
    api_key: Optional[str],
    model_id: str,
    prompt: str,
    provider_type: str = "custom",
    default_headers: Optional[Dict[str, Any]] = None,
    max_tokens: int = 64,
) -> ChatProbe:
    """Send a minimal chat completion and return the assistant reply.

    This is the only check that proves the combination of key + model +
    routing works end to end.
    """
    url = build_chat_url(base_url, provider_type)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if default_headers:
        headers.update({str(k): str(v) for k, v in default_headers.items()})

    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": False,
    }

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=CHAT_TIMEOUT, verify=False) as client:
            resp = await client.post(url, headers=headers, json=body)
            latency = int((time.perf_counter() - started) * 1000)

            if resp.status_code in (401, 403):
                return ChatProbe(
                    ok=False,
                    model_id=model_id,
                    status_code=resp.status_code,
                    latency_ms=latency,
                    checked_url=url,
                    error="Authentication failed - check the API key",
                )

            if resp.status_code >= 400:
                detail = ""
                try:
                    err = resp.json()
                    detail = str(
                        (err.get("error") or {}).get("message")
                        if isinstance(err.get("error"), dict)
                        else err.get("error") or err.get("detail") or ""
                    )
                except Exception:  # noqa: BLE001 - body may not be JSON
                    detail = resp.text[:200]
                return ChatProbe(
                    ok=False,
                    model_id=model_id,
                    status_code=resp.status_code,
                    latency_ms=latency,
                    checked_url=url,
                    error=f"HTTP {resp.status_code}: {detail}".strip(),
                )

            text, prompt_tokens, completion_tokens = _extract_text(resp.json())
            if not text:
                return ChatProbe(
                    ok=False,
                    model_id=model_id,
                    status_code=resp.status_code,
                    latency_ms=latency,
                    checked_url=url,
                    error="Provider returned an empty completion",
                )

            return ChatProbe(
                ok=True,
                model_id=model_id,
                response_text=text.strip(),
                latency_ms=latency,
                status_code=resp.status_code,
                checked_url=url,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
    except httpx.TimeoutException:
        return ChatProbe(
            ok=False,
            model_id=model_id,
            latency_ms=int((time.perf_counter() - started) * 1000),
            checked_url=url,
            error="Chat completion timed out",
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator
        return ChatProbe(
            ok=False,
            model_id=model_id,
            latency_ms=int((time.perf_counter() - started) * 1000),
            checked_url=url,
            error=str(exc),
        )
