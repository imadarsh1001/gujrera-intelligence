"""Cloudflare AI Gateway REST Client Integration.

Configures an OpenAI-compatible ChatOpenAI client routing through Cloudflare AI Gateway:
https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/v1
with headers:
  Authorization: Bearer {CF_API_TOKEN}
  cf-aig-gateway-id: {CF_GATEWAY_ID}

Gracefully handles Cloudflare Guardrails error codes 2016 and 2017.
Detects missing credentials and signals offline_mode=True.
Supports separate router and synthesis models with synchronous guardrail enforcement.
"""

import os
import re
from typing import Any, Dict, Optional, Tuple
from langchain_openai import ChatOpenAI


CLOUDFLARE_GUARDRAIL_CODES = {
    2016: "Cloudflare AI Guardrail blocked input prompt",
    2017: "Cloudflare AI Guardrail blocked model response",
}


def is_cloud_llm_available() -> bool:
    """Check if all required Cloudflare AI Gateway credentials are provided."""
    account_id = os.getenv("CF_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CF_API_TOKEN", "").strip()
    gateway_id = os.getenv("CF_GATEWAY_ID", "").strip()
    return bool(account_id and api_token and gateway_id)


def get_llm(
    llm_override: Optional[Any] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    disable_streaming: bool = True,
    max_tokens: Optional[int] = None,
) -> Tuple[Optional[Any], bool]:
    """Obtain the chat LLM instance or determine offline fallback mode.

    Args:
        llm_override: Injected mock/fake chat model for tests.
        model_name: Model identifier (defaults to CF_MODEL_NAME or 'gpt-4o-mini').
        temperature: Sampling temperature (default 0.0 for deterministic forensic analysis).
        disable_streaming: Enforce synchronous execution for guardrail enforcement.
        max_tokens: Optional completion token cap.

    Returns:
        (llm_instance, offline_mode_bool)
    """
    if llm_override is not None:
        return llm_override, False

    if not is_cloud_llm_available():
        return None, True

    account_id = os.getenv("CF_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CF_API_TOKEN", "").strip()
    gateway_id = os.getenv("CF_GATEWAY_ID", "").strip()
    model = model_name or os.getenv("CF_MODEL_NAME", "gpt-4o-mini")

    base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
    headers = {"cf-aig-gateway-id": gateway_id}

    kwargs: Dict[str, Any] = {
        "model": model,
        "api_key": api_token,
        "base_url": base_url,
        "default_headers": headers,
        "temperature": temperature,
        "disable_streaming": disable_streaming,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    llm = ChatOpenAI(**kwargs)
    return llm, False


def get_router_llm(
    llm_override: Optional[Any] = None,
    temperature: float = 0.0,
    max_tokens: int = 384,
) -> Tuple[Optional[Any], bool]:
    """Obtain the fast router LLM for coordinator routing."""
    model = os.getenv("CF_ROUTER_MODEL") or "@cf/ibm-granite/granite-4.0-h-micro"
    return get_llm(
        llm_override=llm_override,
        model_name=model,
        temperature=temperature,
        disable_streaming=True,
        max_tokens=max_tokens,
    )


def get_synthesis_llm(
    llm_override: Optional[Any] = None,
    temperature: float = 0.0,
    max_tokens: int = 3072,
) -> Tuple[Optional[Any], bool]:
    """Obtain the synthesis LLM for evidence-grounded answer generation."""
    model = os.getenv("CF_SYNTHESIS_MODEL") or os.getenv("CF_MODEL_NAME", "gpt-4o-mini")
    return get_llm(
        llm_override=llm_override,
        model_name=model,
        temperature=temperature,
        disable_streaming=True,
        max_tokens=max_tokens,
    )


def parse_cloudflare_guardrail_error(error: Exception) -> Optional[str]:
    """Inspect exception for Cloudflare Guardrails error codes (2016 / 2017).

    Returns description string if guardrail triggered, else None.
    """
    err_str = str(error)
    for code, desc in CLOUDFLARE_GUARDRAIL_CODES.items():
        if str(code) in err_str:
            return f"GuardrailViolation ({code}): {desc}"

    if re.search(r"\b(guardrail|content_policy_violation)\b", err_str, re.IGNORECASE):
        return f"GuardrailViolation: {err_str}"

    return None
