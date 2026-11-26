"""
Server-side Gemini LLM Integration Client with structured JSON support,
provider logging, configurable timeouts, secret redaction, and graceful deterministic fallback.
OpenAI is disabled in the active runtime; all active LLM workflows use Gemini.
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
    pref = (settings.LLM_PROVIDER or "gemini").strip().lower()
    if pref in ("none", "disabled", "deterministic", "off"):
        return "grounded_deterministic", "GovPath Grounded Synthesis Engine", False

    if pref == "openai":
        logger.warning("LLM_PROVIDER=openai requested, but OpenAI runtime calls are disabled; active runtime requires Gemini.")
        return "grounded_deterministic", "GovPath Grounded Synthesis Engine", False

    if pref in ("gemini", "auto"):
        if settings.GEMINI_API_KEY:
            model = (settings.GEMINI_MODEL or "gemini-2.5-flash").strip()
            return "gemini", model, True
        return "grounded_deterministic", "GovPath Grounded Synthesis Engine", False

    logger.warning("Unsupported LLM_PROVIDER='%s'; falling back to deterministic mode.", pref)
    return "grounded_deterministic", "GovPath Grounded Synthesis Engine", False


def get_llm_status() -> dict[str, Any]:
    settings = get_settings()
    provider, model, configured = _resolve_active_provider(settings)
    pref = (settings.LLM_PROVIDER or "gemini").strip().lower()
    reason = None
    if not configured:
        if pref == "openai":
            reason = "OpenAI is disabled in active runtime; configure LLM_PROVIDER=gemini with GEMINI_API_KEY."
        elif pref in ("none", "disabled", "deterministic", "off"):
            reason = "LLM provider explicitly disabled."
        else:
            reason = "GEMINI_API_KEY is not configured."

    return {
        "configured": configured,
        "provider": provider,
        "model": model,
        "preferred_provider": settings.LLM_PROVIDER,
        "fallback_active": not configured,
        "unavailable_reason": reason,
        "openai_active": False,
    }


def _strip_json_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _extract_gemini_text(body: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    candidates = body.get("candidates") or []
    if not candidates:
        block_reason = body.get("promptFeedback", {}).get("blockReason")
        if block_reason:
            return None, f"Gemini prompt blocked: {block_reason}"
        return None, "Gemini returned no candidates"

    first = candidates[0]
    parts = first.get("content", {}).get("parts") or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    combined = "\n".join(texts).strip()
    if not combined:
        finish_reason = first.get("finishReason", "UNKNOWN")
        return None, f"Gemini returned empty text (finishReason={finish_reason})"
    return combined, None


def _call_provider_raw(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
    temperature: float = 0.2,
    max_tokens: int = 1200,
    timeout: Optional[int] = None,
) -> LLMCallResult:
    settings = get_settings()
    provider, model, configured = _resolve_active_provider(settings)
    eff_timeout = timeout or settings.LLM_TIMEOUT_SECONDS

    if not configured or provider != "gemini":
        pref = (settings.LLM_PROVIDER or "gemini").strip().lower()
        err = (
            "OpenAI runtime is disabled; switch LLM_PROVIDER=gemini with GEMINI_API_KEY."
            if pref == "openai"
            else "Gemini API key not configured or LLM disabled"
        )
        return LLMCallResult(
            ok=False,
            provider="grounded_deterministic",
            model="GovPath Grounded Synthesis Engine",
            error=err,
        )

    started = time.perf_counter()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    # Gemini 2.5 models consume thinking tokens inside maxOutputTokens; bound thinkingBudget and raise output cap.
    eff_max_tokens = max(max_tokens, 4096)
    gen_cfg: dict[str, Any] = {
        "temperature": temperature,
        "maxOutputTokens": eff_max_tokens,
    }
    if "2.5" in model:
        gen_cfg["thinkingConfig"] = {"thinkingBudget": 512 if json_mode else 1024}
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"

    payload: dict[str, Any] = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": gen_cfg,
    }

    try:
        resp = requests.post(
            url,
            headers={
                "x-goog-api-key": settings.GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=eff_timeout,
        )
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        if not resp.ok:
            err_msg = _redact_secrets(f"Gemini HTTP {resp.status_code}: {resp.text[:240]}", settings)
            logger.warning("LLM call failed provider=gemini model=%s err=%s", model, err_msg)
            return LLMCallResult(
                ok=False,
                provider="gemini",
                model=model,
                error=err_msg,
                latency_ms=latency_ms,
            )

        body = resp.json()
        content, extract_err = _extract_gemini_text(body)
        usage_meta = body.get("usageMetadata") or {}
        tokens = int(
            usage_meta.get("totalTokenCount")
            or _estimate_tokens(system_prompt + user_prompt + (content or ""))
        )
        if extract_err or not content:
            logger.warning("LLM empty/blocked provider=gemini model=%s err=%s", model, extract_err)
            return LLMCallResult(
                ok=False,
                provider="gemini",
                model=model,
                error=extract_err or "Gemini returned empty response",
                tokens_used=tokens,
                latency_ms=latency_ms,
            )

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


def generate_structured_json(
    system_prompt: str,
    user_prompt: str,
    schema_model: Optional[Type[T]] = None,
    temperature: float = 0.1,
    max_tokens: int = 1600,
    timeout: Optional[int] = None,
) -> LLMCallResult:
    """
    Call Gemini in JSON mode, parse the response, and validate against a Pydantic model when provided.
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
    max_tokens: int = 1600,
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
