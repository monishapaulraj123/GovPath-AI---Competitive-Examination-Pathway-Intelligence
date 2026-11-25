"""
Server-side External LLM Integration Client (OpenAI / Gemini) with structured JSON support,
provider logging, configurable timeouts, and graceful deterministic fallback.
"""

from dataclasses import dataclass
import json
import logging
import re
import time
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
import requests

from app.config import get_settings

logger = logging.getLogger("govpath.llm")

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMCallResult:
    ok: bool
    provider: str
    model: str
    raw_text: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    tokens_used: int = 0
    latency_ms: float = 0.0


def _redact_secrets(text: str, settings: Any) -> str:
    cleaned = str(text)
    for secret in (settings.OPENAI_API_KEY, settings.GEMINI_API_KEY):
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    cleaned = re.sub(r"([?&]key=)[^&\s]+", r"\1[REDACTED]", cleaned)
    return cleaned


def _resolve_active_provider(settings: Any) -> tuple[str, str, bool]:
    pref = (settings.LLM_PROVIDER or "auto").strip().lower()
    if pref in ("none", "disabled", "deterministic", "off"):
        return "grounded_deterministic", "GovPath Grounded Synthesis Engine", False

    if pref == "openai":
        if settings.OPENAI_API_KEY:
            return "openai", settings.OPENAI_MODEL, True
        return "grounded_deterministic", "GovPath Grounded Synthesis Engine", False

    if pref == "gemini":
        if settings.GEMINI_API_KEY:
            return "gemini", settings.GEMINI_MODEL, True
        return "grounded_deterministic", "GovPath Grounded Synthesis Engine", False

    # auto mode
    if settings.OPENAI_API_KEY:
        return "openai", settings.OPENAI_MODEL, True
    if settings.GEMINI_API_KEY:
        return "gemini", settings.GEMINI_MODEL, True
    return "grounded_deterministic", "GovPath Grounded Synthesis Engine", False


def get_llm_status() -> dict[str, Any]:
    settings = get_settings()
    provider, model, configured = _resolve_active_provider(settings)
    return {
        "configured": configured,
        "provider": provider,
        "model": model,
        "preferred_provider": settings.LLM_PROVIDER,
        "fallback_active": not configured,
    }


def _strip_json_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _call_provider_raw(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
    temperature: float = 0.2,
    max_tokens: int = 900,
    timeout: Optional[int] = None,
) -> LLMCallResult:
    settings = get_settings()
    provider, model, configured = _resolve_active_provider(settings)
    eff_timeout = timeout or settings.LLM_TIMEOUT_SECONDS

    if not configured:
        return LLMCallResult(
            ok=False,
            provider="grounded_deterministic",
            model="GovPath Grounded Synthesis Engine",
            error="LLM provider not configured or disabled",
        )

    started = time.perf_counter()
    if provider == "openai":
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=eff_timeout,
            )
            latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
            if not resp.ok:
                err_msg = _redact_secrets(f"OpenAI HTTP {resp.status_code}: {resp.text[:220]}", settings)
                logger.warning("LLM call failed provider=openai model=%s err=%s", model, err_msg)
                return LLMCallResult(
                    ok=False,
                    provider="openai",
                    model=model,
                    error=err_msg,
                    latency_ms=latency_ms,
                )
            body = resp.json()
            content = body["choices"][0]["message"]["content"].strip()
            usage = body.get("usage", {})
            tokens = int(usage.get("total_tokens") or (_estimate_tokens(system_prompt + user_prompt + content)))
            logger.info("LLM call ok provider=openai model=%s tokens=%s latency_ms=%s", model, tokens, latency_ms)
            return LLMCallResult(
                ok=True,
                provider="openai",
                model=model,
                raw_text=content,
                tokens_used=tokens,
                latency_ms=latency_ms,
            )
        except requests.Timeout:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
            err = f"OpenAI request timed out after {eff_timeout}s"
            logger.warning("LLM timeout provider=openai model=%s", model)
            return LLMCallResult(ok=False, provider="openai", model=model, error=err, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
            err = _redact_secrets(f"OpenAI request error: {exc}", settings)
            logger.warning("LLM error provider=openai model=%s err=%s", model, err)
            return LLMCallResult(ok=False, provider="openai", model=model, error=err, latency_ms=latency_ms)

    if provider == "gemini":
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={settings.GEMINI_API_KEY}"
        )
        gen_cfg: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if json_mode:
            gen_cfg["responseMimeType"] = "application/json"

        try:
            resp = requests.post(
                url,
                json={
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": gen_cfg,
                },
                timeout=eff_timeout,
            )
            latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
            if not resp.ok:
                err_msg = _redact_secrets(f"Gemini HTTP {resp.status_code}: {resp.text[:220]}", settings)
                logger.warning("LLM call failed provider=gemini model=%s err=%s", model, err_msg)
                return LLMCallResult(
                    ok=False,
                    provider="gemini",
                    model=model,
                    error=err_msg,
                    latency_ms=latency_ms,
                )
            body = resp.json()
            content = body["candidates"][0]["content"]["parts"][0]["text"].strip()
            tokens = _estimate_tokens(system_prompt + user_prompt + content)
            logger.info("LLM call ok provider=gemini model=%s tokens=%s latency_ms=%s", model, tokens, latency_ms)
            return LLMCallResult(
                ok=True,
                provider="gemini",
                model=model,
                raw_text=content,
                tokens_used=tokens,
                latency_ms=latency_ms,
            )
        except requests.Timeout:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
            err = f"Gemini request timed out after {eff_timeout}s"
            logger.warning("LLM timeout provider=gemini model=%s", model)
            return LLMCallResult(ok=False, provider="gemini", model=model, error=err, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
            err = _redact_secrets(f"Gemini request error: {exc}", settings)
            logger.warning("LLM error provider=gemini model=%s err=%s", model, err)
            return LLMCallResult(ok=False, provider="gemini", model=model, error=err, latency_ms=latency_ms)

    return LLMCallResult(
        ok=False,
        provider="grounded_deterministic",
        model="GovPath Grounded Synthesis Engine",
        error="No active LLM provider resolved",
    )


def generate_structured_json(
    system_prompt: str,
    user_prompt: str,
    schema_model: Optional[Type[T]] = None,
    temperature: float = 0.1,
    max_tokens: int = 1000,
    timeout: Optional[int] = None,
) -> LLMCallResult:
    """
    Call the configured server-side LLM in JSON mode, parse the response,
    and validate against a Pydantic model when provided.
    """
    res = _call_provider_raw(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=True,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    if not res.ok or not res.raw_text:
        return res

    cleaned = _strip_json_fences(res.raw_text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Malformed JSON from provider=%s model=%s: %s", res.provider, res.model, exc)
        return LLMCallResult(
            ok=False,
            provider=res.provider,
            model=res.model,
            raw_text=res.raw_text,
            error=f"Malformed JSON output: {exc}",
            tokens_used=res.tokens_used,
            latency_ms=res.latency_ms,
        )

    if schema_model is not None:
        try:
            validated = schema_model.model_validate(parsed)
            res.data = validated
        except ValidationError as exc:
            logger.warning("Schema validation failed from provider=%s model=%s: %s", res.provider, res.model, exc)
            return LLMCallResult(
                ok=False,
                provider=res.provider,
                model=res.model,
                raw_text=res.raw_text,
                error=f"Structured schema validation failed: {exc.error_count()} validation error(s)",
                tokens_used=res.tokens_used,
                latency_ms=res.latency_ms,
            )
    else:
        res.data = parsed

    return res


def generate_llm_response_detailed(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.25,
    max_tokens: int = 900,
    timeout: Optional[int] = None,
) -> LLMCallResult:
    return _call_provider_raw(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=False,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def generate_llm_response(system_prompt: str, user_prompt: str) -> Optional[str]:
    res = generate_llm_response_detailed(system_prompt=system_prompt, user_prompt=user_prompt)
    return res.raw_text if res.ok else None
