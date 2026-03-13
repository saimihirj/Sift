"""Model routing for local and API-key-backed runtimes."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import httpx


OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
MODEL_PROVIDER = os.environ.get("VK_MODEL_PROVIDER", "auto").lower()
CONTINUE_PROMPT = (
    "Continue exactly from where you stopped. Do not restart, summarize, apologize, or repeat headings already covered. "
    "Resume with the unfinished point and finish the answer cleanly."
)
VISION_MODEL_HINTS = (
    "qwen2.5vl",
    "qwen2.5-vl",
    "qwen-vl",
    "gemma3",
    "llava",
    "bakllava",
    "moondream",
    "gpt-4o",
    "gpt-4.1",
    "o4-mini",
    "claude-3",
    "claude-3.5",
    "claude-3.7",
    "gemini",
    "pixtral",
    "vision",
)
PROVIDER_VISION_SUPPORT = {
    "ollama": True,
    "groq": True,
    "cerebras": False,
    "openai": True,
    "openrouter": True,
    "anthropic": True,
    "gemini": True,
}
RECOMMENDED_DECK_MODELS = {
    "ollama": "qwen2.5vl:7b",
    "groq": "",
    "cerebras": "",
    "openai": "gpt-4o",
    "openrouter": "anthropic/claude-3.5-sonnet",
    "anthropic": "claude-3-7-sonnet-latest",
    "gemini": "gemini-1.5-pro",
}


def _usage_record(
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int | None = None,
    *,
    estimated: bool,
) -> dict[str, Any]:
    prompt = max(int(prompt_tokens or 0), 0)
    completion = max(int(completion_tokens or 0), 0)
    total = max(int(total_tokens if total_tokens is not None else prompt + completion), 0)
    return {
        "promptTokens": prompt,
        "completionTokens": completion,
        "totalTokens": total,
        "estimated": bool(estimated),
    }


def empty_runtime_usage() -> dict[str, Any]:
    zero = _usage_record(estimated=False)
    return {"last": dict(zero), "session": dict(zero)}


def accumulate_runtime_usage(existing: dict[str, Any] | None, turn_usage: dict[str, Any] | None) -> dict[str, Any]:
    current = existing if isinstance(existing, dict) else empty_runtime_usage()
    current_last = current.get("last") if isinstance(current.get("last"), dict) else _usage_record(estimated=False)
    current_session = current.get("session") if isinstance(current.get("session"), dict) else _usage_record(estimated=False)
    next_last = normalize_usage(turn_usage)
    next_session = _usage_record(
        int(current_session.get("promptTokens", 0) or 0) + int(next_last.get("promptTokens", 0) or 0),
        int(current_session.get("completionTokens", 0) or 0) + int(next_last.get("completionTokens", 0) or 0),
        int(current_session.get("totalTokens", 0) or 0) + int(next_last.get("totalTokens", 0) or 0),
        estimated=bool(current_session.get("estimated", False) or next_last.get("estimated", False)),
    )
    return {
        "last": next_last or current_last,
        "session": next_session,
    }


def normalize_usage(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _usage_record(estimated=False)
    return _usage_record(
        prompt_tokens=int(value.get("promptTokens", 0) or 0),
        completion_tokens=int(value.get("completionTokens", 0) or 0),
        total_tokens=int(value.get("totalTokens", 0) or 0),
        estimated=bool(value.get("estimated", False)),
    )


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item.get("text", "")))
                elif item.get("text"):
                    parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict) and content.get("text"):
        return str(content.get("text", ""))
    return str(content or "")


def _estimate_token_count(text: str) -> int:
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    return max(1, (len(cleaned) + 3) // 4)


def _estimated_usage_from_messages(system: str, messages: list[dict[str, Any]], completion_text: str) -> dict[str, Any]:
    prompt_text = "\n".join(
        bit
        for bit in [system, *[_content_text(message.get("content", "")) for message in messages]]
        if bit
    )
    return _usage_record(
        _estimate_token_count(prompt_text),
        _estimate_token_count(completion_text),
        estimated=True,
    )


def _estimated_usage_from_prompt(system: str, prompt: str, completion_text: str) -> dict[str, Any]:
    prompt_text = "\n".join(bit for bit in [system, prompt] if bit)
    return _usage_record(
        _estimate_token_count(prompt_text),
        _estimate_token_count(completion_text),
        estimated=True,
    )


def _usage_from_ollama(data: dict[str, Any], *, system: str, messages: list[dict[str, Any]], completion_text: str) -> dict[str, Any]:
    prompt_tokens = int(data.get("prompt_eval_count", 0) or 0)
    completion_tokens = int(data.get("eval_count", 0) or 0)
    if prompt_tokens or completion_tokens:
        return _usage_record(prompt_tokens, completion_tokens, estimated=False)
    return _estimated_usage_from_messages(system, messages, completion_text)


def _usage_from_openai_response(data: dict[str, Any], *, system: str, messages: list[dict[str, Any]], completion_text: str) -> dict[str, Any]:
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0)
    if prompt_tokens or completion_tokens or total_tokens:
        return _usage_record(prompt_tokens, completion_tokens, total_tokens, estimated=False)
    return _estimated_usage_from_messages(system, messages, completion_text)


def _usage_from_anthropic_response(data: dict[str, Any], *, system: str, messages: list[dict[str, Any]], completion_text: str) -> dict[str, Any]:
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    prompt_tokens = int(usage.get("input_tokens", 0) or 0)
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    if prompt_tokens or completion_tokens:
        return _usage_record(prompt_tokens, completion_tokens, estimated=False)
    return _estimated_usage_from_messages(system, messages, completion_text)


def _usage_from_gemini_response(data: dict[str, Any], *, system: str, messages: list[dict[str, Any]], completion_text: str) -> dict[str, Any]:
    usage = data.get("usageMetadata") if isinstance(data.get("usageMetadata"), dict) else {}
    prompt_tokens = int(usage.get("promptTokenCount", 0) or 0)
    completion_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
    total_tokens = int(usage.get("totalTokenCount", 0) or 0)
    if prompt_tokens or completion_tokens or total_tokens:
        return _usage_record(prompt_tokens, completion_tokens, total_tokens, estimated=False)
    return _estimated_usage_from_messages(system, messages, completion_text)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ModelProfileConfig:
    key: str
    model: str
    timeout_seconds: float
    options: dict[str, Any]


@dataclass(frozen=True)
class ProviderConfig:
    key: str
    label: str
    api_style: str
    base_url: str
    env_api_key_var: str | None
    default_speed_model: str
    default_balanced_model: str
    requires_api_key: bool


PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "ollama": ProviderConfig(
        key="ollama",
        label="Ollama",
        api_style="ollama",
        base_url=OLLAMA_BASE_URL,
        env_api_key_var=None,
        default_speed_model=os.environ.get("OLLAMA_MODEL_SPEED", "llama3.2:latest"),
        default_balanced_model=os.environ.get("OLLAMA_MODEL_BALANCED", "qwen3:8b"),
        requires_api_key=False,
    ),
    "groq": ProviderConfig(
        key="groq",
        label="Groq",
        api_style="openai",
        base_url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        env_api_key_var="GROQ_API_KEY",
        default_speed_model=os.environ.get("GROQ_MODEL_SPEED", "llama-3.1-8b-instant"),
        default_balanced_model=os.environ.get("GROQ_MODEL_BALANCED", "llama-3.3-70b-versatile"),
        requires_api_key=True,
    ),
    "cerebras": ProviderConfig(
        key="cerebras",
        label="Cerebras",
        api_style="openai",
        base_url=os.environ.get("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
        env_api_key_var="CEREBRAS_API_KEY",
        default_speed_model=os.environ.get("CEREBRAS_MODEL_SPEED", "llama3.1-8b"),
        default_balanced_model=os.environ.get("CEREBRAS_MODEL_BALANCED", "gpt-oss-120b"),
        requires_api_key=True,
    ),
    "openai": ProviderConfig(
        key="openai",
        label="OpenAI",
        api_style="openai",
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        env_api_key_var="OPENAI_API_KEY",
        default_speed_model=os.environ.get("OPENAI_MODEL_SPEED", "gpt-4o-mini"),
        default_balanced_model=os.environ.get("OPENAI_MODEL_BALANCED", "gpt-4.1"),
        requires_api_key=True,
    ),
    "openrouter": ProviderConfig(
        key="openrouter",
        label="OpenRouter",
        api_style="openai",
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        env_api_key_var="OPENROUTER_API_KEY",
        default_speed_model=os.environ.get("OPENROUTER_MODEL_SPEED", "openai/gpt-4o-mini"),
        default_balanced_model=os.environ.get("OPENROUTER_MODEL_BALANCED", "anthropic/claude-3.5-sonnet"),
        requires_api_key=True,
    ),
    "anthropic": ProviderConfig(
        key="anthropic",
        label="Anthropic",
        api_style="anthropic",
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
        env_api_key_var="ANTHROPIC_API_KEY",
        default_speed_model=os.environ.get("ANTHROPIC_MODEL_SPEED", "claude-3-5-haiku-latest"),
        default_balanced_model=os.environ.get("ANTHROPIC_MODEL_BALANCED", "claude-3-7-sonnet-latest"),
        requires_api_key=True,
    ),
    "gemini": ProviderConfig(
        key="gemini",
        label="Gemini",
        api_style="gemini",
        base_url=os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
        env_api_key_var="GEMINI_API_KEY",
        default_speed_model=os.environ.get("GEMINI_MODEL_SPEED", "gemini-2.0-flash"),
        default_balanced_model=os.environ.get("GEMINI_MODEL_BALANCED", "gemini-1.5-pro"),
        requires_api_key=True,
    ),
}


OLLAMA_MODEL_PROFILES = {
    "speed": ModelProfileConfig(
        key="speed",
        model=PROVIDER_CONFIGS["ollama"].default_speed_model,
        timeout_seconds=_env_float("OLLAMA_TIMEOUT_SPEED", 30.0),
        options={
            "num_ctx": 8192,
            "temperature": 0.72,
            "top_p": 0.9,
            "repeat_penalty": 1.06,
            "num_predict": 220,
        },
    ),
    "balanced": ModelProfileConfig(
        key="balanced",
        model=PROVIDER_CONFIGS["ollama"].default_balanced_model,
        timeout_seconds=_env_float("OLLAMA_TIMEOUT_BALANCED", 50.0),
        options={
            "num_ctx": 8192,
            "temperature": 0.74,
            "top_p": 0.9,
            "repeat_penalty": 1.05,
            "num_predict": 420,
        },
    ),
}

GROQ_MODEL_PROFILES = {
    "speed": ModelProfileConfig(
        key="speed",
        model=PROVIDER_CONFIGS["groq"].default_speed_model,
        timeout_seconds=18.0,
        options={
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 320,
        },
    ),
    "balanced": ModelProfileConfig(
        key="balanced",
        model=PROVIDER_CONFIGS["groq"].default_balanced_model,
        timeout_seconds=22.0,
        options={
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 720,
        },
    ),
}


def normalize_profile(profile: str | None) -> str:
    value = (profile or "speed").lower()
    return value if value in ("speed", "balanced") else "speed"


def normalize_provider(provider: str | None) -> str:
    value = (provider or "ollama").strip().lower()
    return value if value in PROVIDER_CONFIGS else "ollama"


def provider_catalog() -> list[dict[str, Any]]:
    catalog = []
    for provider in PROVIDER_CONFIGS.values():
        catalog.append(
            {
                "key": provider.key,
                "label": provider.label,
                "requiresApiKey": provider.requires_api_key,
                "defaultSpeedModel": provider.default_speed_model,
                "defaultBalancedModel": provider.default_balanced_model,
                "supportsVisionModels": PROVIDER_VISION_SUPPORT.get(provider.key, False),
                "recommendedDeckModel": RECOMMENDED_DECK_MODELS.get(provider.key, ""),
            }
        )
    return catalog


def provider_requires_api_key(provider: str) -> bool:
    return PROVIDER_CONFIGS[normalize_provider(provider)].requires_api_key


def default_model_for_provider(provider: str, response_profile: str = "speed") -> str:
    config = PROVIDER_CONFIGS[normalize_provider(provider)]
    return config.default_balanced_model if normalize_profile(response_profile) == "balanced" else config.default_speed_model


def recommended_deck_model_for_provider(provider: str) -> str:
    return RECOMMENDED_DECK_MODELS.get(normalize_provider(provider), "")


def model_supports_vision(provider: str, model: str) -> bool:
    normalized_provider = normalize_provider(provider)
    if not PROVIDER_VISION_SUPPORT.get(normalized_provider, False):
        return False
    lowered = (model or "").strip().lower()
    if not lowered:
        lowered = default_model_for_provider(normalized_provider, "balanced").lower()
    return any(hint in lowered for hint in VISION_MODEL_HINTS)


def _with_config_overrides(
    config: ModelProfileConfig,
    *,
    max_tokens_override: int | None = None,
    timeout_seconds_override: float | None = None,
) -> ModelProfileConfig:
    options = dict(config.options)
    if max_tokens_override and max_tokens_override > 0:
        if "num_predict" in options:
            options["num_predict"] = int(max_tokens_override)
        else:
            options["max_tokens"] = int(max_tokens_override)
    timeout_seconds = float(timeout_seconds_override) if timeout_seconds_override and timeout_seconds_override > 0 else config.timeout_seconds
    return ModelProfileConfig(
        key=config.key,
        model=config.model,
        timeout_seconds=timeout_seconds,
        options=options,
    )


def _profile_config_for_provider(
    provider: str,
    response_profile: str,
    model_override: str = "",
) -> ModelProfileConfig:
    normalized_provider = normalize_provider(provider)
    profile = normalize_profile(response_profile)
    chosen_model = model_override.strip() or default_model_for_provider(normalized_provider, profile)

    if normalized_provider == "ollama":
        timeout_seconds = _env_float("OLLAMA_TIMEOUT_SPEED", 30.0) if profile == "speed" else _env_float("OLLAMA_TIMEOUT_BALANCED", 50.0)
        options = {
            "num_ctx": 8192,
            "temperature": 0.72 if profile == "speed" else 0.74,
            "top_p": 0.9,
            "repeat_penalty": 1.06 if profile == "speed" else 1.05,
            "num_predict": 220 if profile == "speed" else 420,
        }
        return ModelProfileConfig(key=profile, model=chosen_model, timeout_seconds=timeout_seconds, options=options)

    timeout_seconds = 28.0 if profile == "speed" else 42.0
    options = {
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 320 if profile == "speed" else 720,
    }
    return ModelProfileConfig(key=profile, model=chosen_model, timeout_seconds=timeout_seconds, options=options)


def _provider_api_key(provider: str, api_key: str | None = None) -> str:
    config = PROVIDER_CONFIGS[normalize_provider(provider)]
    if api_key:
        return api_key.strip()
    if not config.env_api_key_var:
        return ""
    return os.environ.get(config.env_api_key_var, "").strip()


def active_provider() -> str:
    if MODEL_PROVIDER == "groq":
        return "groq"
    if MODEL_PROVIDER == "ollama":
        return "ollama"
    if _provider_api_key("groq"):
        return "groq"
    return "ollama"


def _merge_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"role": "system", "content": system}, *messages]


def _read_image_data_uri(image_path: str) -> str:
    path = Path(image_path)
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _read_image_bytes(image_path: str) -> tuple[str, str]:
    path = Path(image_path)
    suffix = path.suffix.lower()
    media_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return media_type, encoded


def _ollama_payload(system: str, messages: list[dict[str, Any]], config: ModelProfileConfig, stream: bool) -> dict[str, Any]:
    return {
        "model": config.model,
        "stream": stream,
        "messages": _merge_messages(system, messages),
        "options": config.options,
    }


def _openai_payload(
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    temperature: float,
    top_p: float,
    stream: bool,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": _merge_messages(system, messages),
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": stream,
    }


def _openai_multimodal_payload(
    model: str,
    system: str,
    prompt: str,
    image_paths: list[str],
    max_tokens: int,
    temperature: float,
    top_p: float,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image_path in image_paths:
        content.append({"type": "image_url", "image_url": {"url": _read_image_data_uri(image_path)}})
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": False,
    }


def _anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cooked: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        if role == "system":
            continue
        if role not in {"user", "assistant"}:
            role = "user"
        cooked.append({"role": role, "content": message.get("content", "")})
    return cooked


def _anthropic_multimodal_messages(prompt: str, image_paths: list[str]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image_path in image_paths:
        media_type, data = _read_image_bytes(image_path)
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            }
        )
    return [{"role": "user", "content": content}]


def _gemini_contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        if role == "system":
            continue
        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": message.get("content", "")}],
            }
        )
    return contents


def _gemini_multimodal_contents(prompt: str, image_paths: list[str]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"text": prompt}]
    for image_path in image_paths:
        mime, data = _read_image_bytes(image_path)
        parts.append({"inline_data": {"mime_type": mime, "data": data}})
    return [{"role": "user", "parts": parts}]


def _ollama_multimodal_payload(
    model: str,
    system: str,
    prompt: str,
    image_paths: list[str],
    *,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    images = [_read_image_bytes(path)[1] for path in image_paths]
    options = {
        "num_ctx": 8192,
        "temperature": temperature,
        "top_p": top_p,
        "repeat_penalty": 1.05,
        "num_predict": max_tokens,
    }
    if timeout_seconds:
        options["timeout"] = timeout_seconds
    return {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt, "images": images},
        ],
        "options": options,
    }


def _normalize_finish_reason(value: Any) -> str:
    reason = str(value or "").strip().lower()
    if reason in {"length", "max_tokens", "max_output_tokens"}:
        return "length"
    if reason in {"stop", "end_turn", "end_turn_stop", "eos", "done"}:
        return "stop"
    if reason in {"tool_use", "tool_calls"}:
        return "tool"
    return reason


def _needs_continuation(finish_reason: str, message: str) -> bool:
    if _normalize_finish_reason(finish_reason) == "length":
        return True
    tail = (message or "").rstrip()
    if len(tail) < 80:
        return False
    return not tail.endswith((".", "!", "?", "\"", "”", ")", "]"))


def _merge_continuation_text(base: str, addition: str) -> tuple[str, str]:
    left = (base or "").rstrip()
    right = (addition or "").lstrip()
    if not left:
        return right, right
    if not right:
        return left, ""
    max_overlap = min(len(left), len(right), 140)
    overlap = 0
    for size in range(max_overlap, 15, -1):
        if left[-size:] == right[:size]:
            overlap = size
            break
    merged_addition = right[overlap:].lstrip()
    if not merged_addition or left.endswith((" ", "\n")):
        separator = ""
    elif left[-1:].isalnum() and merged_addition[:1].islower():
        separator = " "
    else:
        separator = "\n"
    merged = f"{left}{separator}{merged_addition}".strip()
    delta = f"{separator}{merged_addition}" if merged_addition else ""
    return merged, delta


async def _stream_from_ollama(
    system: str,
    messages: list[dict[str, Any]],
    config: ModelProfileConfig,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    payload = _ollama_payload(system, messages, config, stream=True)
    start = time.perf_counter()
    first_token_seconds = None
    accumulated: list[str] = []

    timeout = httpx.Timeout(config.timeout_seconds, connect=3.0, read=config.timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload) as response:
            response.raise_for_status()
            yield "meta", {
                "responseProfile": config.key,
                "model": config.model,
                "provider": "ollama",
                "fallbackUsed": False,
            }
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    accumulated.append(chunk)
                    if first_token_seconds is None:
                        first_token_seconds = time.perf_counter() - start
                    yield "delta", {"delta": chunk}
                if data.get("done"):
                    total_seconds = time.perf_counter() - start
                    message_text = "".join(accumulated).strip()
                    yield "complete", {
                        "message": message_text,
                        "responseProfile": config.key,
                        "model": config.model,
                        "provider": "ollama",
                        "fallbackUsed": False,
                        "finishReason": _normalize_finish_reason(data.get("done_reason") or data.get("doneReason") or "stop"),
                        "timings": {
                            "firstTokenSeconds": round(first_token_seconds or total_seconds, 3),
                            "totalSeconds": round(total_seconds, 3),
                        },
                        "usage": _usage_from_ollama(data, system=system, messages=messages, completion_text=message_text),
                    }
                    return


async def _stream_from_openai_compatible(
    provider: str,
    system: str,
    messages: list[dict[str, Any]],
    config: ModelProfileConfig,
    api_key: str,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    provider_config = PROVIDER_CONFIGS[normalize_provider(provider)]
    payload = _openai_payload(
        model=config.model,
        system=system,
        messages=messages,
        max_tokens=int(config.options.get("max_tokens", 160)),
        temperature=float(config.options.get("temperature", 0.7)),
        top_p=float(config.options.get("top_p", 0.9)),
        stream=True,
    )
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "https://signalx.local")
        headers["X-Title"] = "SignalX"

    start = time.perf_counter()
    first_token_seconds = None
    accumulated: list[str] = []
    finish_reason = ""
    usage_payload: dict[str, Any] | None = None
    timeout = httpx.Timeout(config.timeout_seconds, connect=3.0, read=config.timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{provider_config.base_url}/chat/completions", headers=headers, json=payload) as response:
            response.raise_for_status()
            yield "meta", {
                "responseProfile": config.key,
                "model": config.model,
                "provider": provider,
                "fallbackUsed": False,
            }
            async for raw_line in response.aiter_lines():
                line = raw_line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data_blob = line[5:].strip()
                if data_blob == "[DONE]":
                    break
                data = json.loads(data_blob)
                if isinstance(data.get("usage"), dict):
                    usage_payload = _usage_from_openai_response(
                        data,
                        system=system,
                        messages=messages,
                        completion_text="".join(accumulated).strip(),
                    )
                finish_reason = _normalize_finish_reason(data.get("choices", [{}])[0].get("finish_reason", finish_reason))
                delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    accumulated.append(delta)
                    if first_token_seconds is None:
                        first_token_seconds = time.perf_counter() - start
                    yield "delta", {"delta": delta}
            total_seconds = time.perf_counter() - start
            message_text = "".join(accumulated).strip()
            yield "complete", {
                "message": message_text,
                "responseProfile": config.key,
                "model": config.model,
                "provider": provider,
                "fallbackUsed": False,
                "finishReason": finish_reason or "stop",
                "timings": {
                    "firstTokenSeconds": round(first_token_seconds or total_seconds, 3),
                    "totalSeconds": round(total_seconds, 3),
                },
                "usage": usage_payload or _estimated_usage_from_messages(system, messages, message_text),
            }


async def _stream_from_profile(
    system: str,
    messages: list[dict[str, Any]],
    config: ModelProfileConfig,
    provider: str,
    api_key: str | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    normalized_provider = normalize_provider(provider)
    provider_config = PROVIDER_CONFIGS[normalized_provider]
    chosen_api_key = _provider_api_key(normalized_provider, api_key)

    if provider_config.api_style == "ollama":
        async for event, payload in _stream_from_ollama(system, messages, config):
            yield event, payload
        return

    if provider_config.api_style == "openai":
        if not chosen_api_key:
            raise RuntimeError(f"{provider_config.label} API key is not configured")
        async for event, payload in _stream_from_openai_compatible(normalized_provider, system, messages, config, chosen_api_key):
            yield event, payload
        return

    if not chosen_api_key:
        raise RuntimeError(f"{provider_config.label} API key is not configured")

    result = await generate_provider_text(
        provider=normalized_provider,
        model=config.model,
        system=system,
        messages=messages,
        api_key=chosen_api_key,
        max_tokens=int(config.options.get("max_tokens", 160)),
        temperature=float(config.options.get("temperature", 0.7)),
        top_p=float(config.options.get("top_p", 0.9)),
        timeout_seconds=config.timeout_seconds,
    )
    yield "meta", {
        "responseProfile": config.key,
        "model": result["model"],
        "provider": normalized_provider,
        "fallbackUsed": False,
    }
    if result["message"]:
        yield "delta", {"delta": result["message"]}
    yield "complete", {
        "message": result["message"],
        "responseProfile": config.key,
        "model": result["model"],
        "provider": normalized_provider,
        "fallbackUsed": False,
        "finishReason": result.get("finishReason", "stop"),
        "timings": result["timings"],
        "usage": result.get("usage", _usage_record(estimated=False)),
    }


async def stream_chat_completion(
    system: str,
    messages: list[dict[str, Any]],
    response_profile: str,
    provider_override: str | None = None,
    model_override: str = "",
    api_key: str | None = None,
    max_tokens_override: int | None = None,
    timeout_seconds_override: float | None = None,
    allow_continuation: bool = True,
    continuation_limit: int = 1,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    requested = normalize_profile(response_profile)
    provider = normalize_provider(provider_override or active_provider())
    primary = _with_config_overrides(
        _profile_config_for_provider(provider, requested, model_override),
        max_tokens_override=max_tokens_override,
        timeout_seconds_override=timeout_seconds_override,
    )
    allow_fallback = not model_override.strip()

    try:
        config_used = primary
        fallback_used = False
        meta_payload: dict[str, Any] | None = None
        completion_payload: dict[str, Any] | None = None
        async for event, payload in _stream_from_profile(system, messages, config_used, provider, api_key):
            if event == "meta":
                meta_payload = payload
                yield event, payload
                continue
            if event == "complete":
                completion_payload = payload
                continue
            yield event, payload
    except Exception as exc:
        if requested == "speed" or not allow_fallback:
            raise exc
        fallback_used = True
        config_used = _with_config_overrides(
            _profile_config_for_provider(provider, "speed"),
            max_tokens_override=max_tokens_override,
            timeout_seconds_override=timeout_seconds_override,
        )
        meta_payload = None
        completion_payload = None
        async for event, payload in _stream_from_profile(system, messages, config_used, provider, api_key):
            if event == "meta":
                payload["fallbackUsed"] = True
                payload["requestedProfile"] = requested
                meta_payload = payload
                yield event, payload
                continue
            if event == "complete":
                completion_payload = payload
                continue
            yield event, payload

    if completion_payload is None:
        raise RuntimeError("Model did not produce a completion")

    final_message = completion_payload.get("message", "").strip()
    final_finish_reason = completion_payload.get("finishReason", "stop")
    continuation_count = 0
    aggregate_usage = normalize_usage(completion_payload.get("usage"))
    if allow_continuation:
        while continuation_count < max(int(continuation_limit), 0) and _needs_continuation(final_finish_reason, final_message):
            continuation_count += 1
            continuation = await generate_provider_text(
                provider=provider,
                model=config_used.model,
                system=system,
                messages=[*messages, {"role": "assistant", "content": final_message}, {"role": "user", "content": CONTINUE_PROMPT}],
                api_key=api_key,
                max_tokens=int(config_used.options.get("num_predict", config_used.options.get("max_tokens", 720))),
                temperature=float(config_used.options.get("temperature", 0.7)),
                top_p=float(config_used.options.get("top_p", 0.9)),
                timeout_seconds=float(config_used.timeout_seconds),
            )
            continuation_message = continuation.get("message", "").strip()
            merged_message, delta = _merge_continuation_text(final_message, continuation_message)
            final_message = merged_message
            final_finish_reason = continuation.get("finishReason", final_finish_reason)
            aggregate_usage = _usage_record(
                aggregate_usage.get("promptTokens", 0) + int(continuation.get("usage", {}).get("promptTokens", 0) or 0),
                aggregate_usage.get("completionTokens", 0) + int(continuation.get("usage", {}).get("completionTokens", 0) or 0),
                aggregate_usage.get("totalTokens", 0) + int(continuation.get("usage", {}).get("totalTokens", 0) or 0),
                estimated=bool(aggregate_usage.get("estimated", False) or continuation.get("usage", {}).get("estimated", False)),
            )
            if delta:
                yield "delta", {"delta": delta, "continuation": True}
            if not continuation_message.strip():
                break
            if _normalize_finish_reason(final_finish_reason) != "length":
                break

    completion_payload["message"] = final_message
    completion_payload["finishReason"] = final_finish_reason or "stop"
    completion_payload["continuedAfterLengthLimit"] = continuation_count > 0
    completion_payload["continuationCount"] = continuation_count
    completion_payload["usage"] = aggregate_usage
    if fallback_used:
        completion_payload["fallbackUsed"] = True
        completion_payload["requestedProfile"] = requested
    yield "complete", completion_payload


async def _complete_ollama(
    system: str,
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    start = time.perf_counter()
    payload = {
        "model": model,
        "stream": False,
        "messages": _merge_messages(system, messages),
        "options": {
            "num_ctx": 8192,
            "temperature": temperature,
            "top_p": top_p,
            "repeat_penalty": 1.08,
            "num_predict": max_tokens,
        },
    }
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
    total_seconds = time.perf_counter() - start
    message_text = data.get("message", {}).get("content", "").strip()
    return {
        "message": message_text,
        "finishReason": _normalize_finish_reason(data.get("done_reason") or data.get("doneReason") or "stop"),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
        "usage": _usage_from_ollama(data, system=system, messages=messages, completion_text=message_text),
    }


async def _complete_openai(
    provider: str,
    system: str,
    messages: list[dict[str, Any]],
    model: str,
    api_key: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    provider_config = PROVIDER_CONFIGS[normalize_provider(provider)]
    payload = _openai_payload(model, system, messages, max_tokens, temperature, top_p, False)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "https://signalx.local")
        headers["X-Title"] = "SignalX"
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{provider_config.base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    total_seconds = time.perf_counter() - start
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    message_text = (content or "").strip()
    return {
        "message": message_text,
        "finishReason": _normalize_finish_reason(data.get("choices", [{}])[0].get("finish_reason", "stop")),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
        "usage": _usage_from_openai_response(data, system=system, messages=messages, completion_text=message_text),
    }


async def _complete_anthropic(
    system: str,
    messages: list[dict[str, Any]],
    model: str,
    api_key: str,
    max_tokens: int,
    temperature: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    start = time.perf_counter()
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": _anthropic_messages(messages),
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": os.environ.get("ANTHROPIC_VERSION", "2023-06-01"),
        "content-type": "application/json",
    }
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{PROVIDER_CONFIGS['anthropic'].base_url}/messages", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    total_seconds = time.perf_counter() - start
    text_parts = []
    for item in data.get("content", []):
        if item.get("type") == "text":
            text_parts.append(item.get("text", ""))
    message_text = "".join(text_parts).strip()
    return {
        "message": message_text,
        "finishReason": _normalize_finish_reason(data.get("stop_reason", "stop")),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
        "usage": _usage_from_anthropic_response(data, system=system, messages=messages, completion_text=message_text),
    }


async def _complete_gemini(
    system: str,
    messages: list[dict[str, Any]],
    model: str,
    api_key: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    start = time.perf_counter()
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _gemini_contents(messages),
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
            "maxOutputTokens": max_tokens,
        },
    }
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{PROVIDER_CONFIGS['gemini'].base_url}/models/{model}:generateContent",
            params={"key": api_key},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    total_seconds = time.perf_counter() - start
    parts = []
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if part.get("text"):
                parts.append(part["text"])
    finish_reason = _normalize_finish_reason((data.get("candidates", [{}]) or [{}])[0].get("finishReason", "stop"))
    message_text = "".join(parts).strip()
    return {
        "message": message_text,
        "finishReason": finish_reason,
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
        "usage": _usage_from_gemini_response(data, system=system, messages=messages, completion_text=message_text),
    }


async def generate_provider_text(
    *,
    provider: str,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    api_key: str | None = None,
    max_tokens: int = 600,
    temperature: float = 0.3,
    top_p: float = 0.9,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    normalized_provider = normalize_provider(provider)
    provider_config = PROVIDER_CONFIGS[normalized_provider]
    chosen_model = model.strip() if model else default_model_for_provider(normalized_provider)
    chosen_api_key = _provider_api_key(normalized_provider, api_key)

    if provider_config.requires_api_key and not chosen_api_key:
        raise RuntimeError(f"{provider_config.label} API key is required")

    if provider_config.api_style == "ollama":
        result = await _complete_ollama(system, messages, chosen_model, max_tokens, temperature, top_p, timeout_seconds)
    elif provider_config.api_style == "openai":
        result = await _complete_openai(
            normalized_provider,
            system,
            messages,
            chosen_model,
            chosen_api_key,
            max_tokens,
            temperature,
            top_p,
            timeout_seconds,
        )
    elif provider_config.api_style == "anthropic":
        result = await _complete_anthropic(system, messages, chosen_model, chosen_api_key, max_tokens, temperature, timeout_seconds)
    elif provider_config.api_style == "gemini":
        result = await _complete_gemini(system, messages, chosen_model, chosen_api_key, max_tokens, temperature, top_p, timeout_seconds)
    else:
        raise RuntimeError(f"Unsupported provider: {normalized_provider}")

    return {
        "message": result["message"],
        "model": chosen_model,
        "provider": normalized_provider,
        "finishReason": result.get("finishReason", "stop"),
        "timings": result["timings"],
        "usage": normalize_usage(result.get("usage")),
    }


async def _complete_ollama_multimodal(
    system: str,
    prompt: str,
    image_paths: list[str],
    model: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    start = time.perf_counter()
    payload = _ollama_multimodal_payload(
        model,
        system,
        prompt,
        image_paths,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        timeout_seconds=timeout_seconds,
    )
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
    total_seconds = time.perf_counter() - start
    message_text = data.get("message", {}).get("content", "").strip()
    return {
        "message": message_text,
        "finishReason": _normalize_finish_reason(data.get("done_reason") or data.get("doneReason") or "stop"),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
        "usage": _usage_from_ollama(data, system=system, messages=[{"role": "user", "content": prompt}], completion_text=message_text),
    }


async def _complete_openai_multimodal(
    provider: str,
    system: str,
    prompt: str,
    image_paths: list[str],
    model: str,
    api_key: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    provider_config = PROVIDER_CONFIGS[normalize_provider(provider)]
    payload = _openai_multimodal_payload(model, system, prompt, image_paths, max_tokens, temperature, top_p)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "https://signalx.local")
        headers["X-Title"] = "SignalX"
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{provider_config.base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    total_seconds = time.perf_counter() - start
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    message_text = (content or "").strip()
    return {
        "message": message_text,
        "finishReason": _normalize_finish_reason(data.get("choices", [{}])[0].get("finish_reason", "stop")),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
        "usage": _usage_from_openai_response(data, system=system, messages=[{"role": "user", "content": prompt}], completion_text=message_text),
    }


async def _complete_anthropic_multimodal(
    system: str,
    prompt: str,
    image_paths: list[str],
    model: str,
    api_key: str,
    max_tokens: int,
    temperature: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    start = time.perf_counter()
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": _anthropic_multimodal_messages(prompt, image_paths),
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": os.environ.get("ANTHROPIC_VERSION", "2023-06-01"),
        "content-type": "application/json",
    }
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{PROVIDER_CONFIGS['anthropic'].base_url}/messages", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    total_seconds = time.perf_counter() - start
    text_parts = []
    for item in data.get("content", []):
        if item.get("type") == "text":
            text_parts.append(item.get("text", ""))
    message_text = "".join(text_parts).strip()
    return {
        "message": message_text,
        "finishReason": _normalize_finish_reason(data.get("stop_reason", "stop")),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
        "usage": _usage_from_anthropic_response(data, system=system, messages=[{"role": "user", "content": prompt}], completion_text=message_text),
    }


async def _complete_gemini_multimodal(
    system: str,
    prompt: str,
    image_paths: list[str],
    model: str,
    api_key: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    start = time.perf_counter()
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _gemini_multimodal_contents(prompt, image_paths),
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
            "maxOutputTokens": max_tokens,
        },
    }
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{PROVIDER_CONFIGS['gemini'].base_url}/models/{model}:generateContent",
            params={"key": api_key},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    total_seconds = time.perf_counter() - start
    parts = []
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if part.get("text"):
                parts.append(part["text"])
    finish_reason = _normalize_finish_reason((data.get("candidates", [{}]) or [{}])[0].get("finishReason", "stop"))
    message_text = "".join(parts).strip()
    return {
        "message": message_text,
        "finishReason": finish_reason,
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
        "usage": _usage_from_gemini_response(data, system=system, messages=[{"role": "user", "content": prompt}], completion_text=message_text),
    }


async def generate_provider_multimodal_text(
    *,
    provider: str,
    model: str,
    system: str,
    prompt: str,
    image_paths: list[str],
    api_key: str | None = None,
    max_tokens: int = 1600,
    temperature: float = 0.2,
    top_p: float = 0.9,
    timeout_seconds: float = 90.0,
) -> dict[str, Any]:
    normalized_provider = normalize_provider(provider)
    provider_config = PROVIDER_CONFIGS[normalized_provider]
    chosen_model = model.strip() if model else default_model_for_provider(normalized_provider, "balanced")
    chosen_api_key = _provider_api_key(normalized_provider, api_key)

    if not model_supports_vision(normalized_provider, chosen_model):
        raise RuntimeError(f"{provider_config.label} model does not appear to support multimodal review")
    if provider_config.requires_api_key and not chosen_api_key:
        raise RuntimeError(f"{provider_config.label} API key is required")
    if not image_paths:
        raise RuntimeError("At least one image is required for multimodal review")

    if provider_config.api_style == "ollama":
        result = await _complete_ollama_multimodal(system, prompt, image_paths, chosen_model, max_tokens, temperature, top_p, timeout_seconds)
    elif provider_config.api_style == "openai":
        result = await _complete_openai_multimodal(
            normalized_provider,
            system,
            prompt,
            image_paths,
            chosen_model,
            chosen_api_key,
            max_tokens,
            temperature,
            top_p,
            timeout_seconds,
        )
    elif provider_config.api_style == "anthropic":
        result = await _complete_anthropic_multimodal(
            system,
            prompt,
            image_paths,
            chosen_model,
            chosen_api_key,
            max_tokens,
            temperature,
            timeout_seconds,
        )
    elif provider_config.api_style == "gemini":
        result = await _complete_gemini_multimodal(
            system,
            prompt,
            image_paths,
            chosen_model,
            chosen_api_key,
            max_tokens,
            temperature,
            top_p,
            timeout_seconds,
        )
    else:
        raise RuntimeError(f"Unsupported multimodal provider: {normalized_provider}")

    return {
        "message": result["message"],
        "model": chosen_model,
        "provider": normalized_provider,
        "finishReason": result.get("finishReason", "stop"),
        "timings": result["timings"],
        "usage": normalize_usage(result.get("usage")),
    }


async def generate_text(
    system: str,
    messages: list[dict[str, Any]],
    response_profile: str,
    max_tokens: int = 600,
) -> dict[str, Any]:
    provider = active_provider()
    profiles = GROQ_MODEL_PROFILES if provider == "groq" else OLLAMA_MODEL_PROFILES
    profile = profiles[normalize_profile(response_profile)]
    return {
        **await generate_provider_text(
            provider=provider,
            model=profile.model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=float(profile.options.get("temperature", 0.7)),
            top_p=float(profile.options.get("top_p", 0.9)),
            timeout_seconds=max(profile.timeout_seconds + 45.0, 90.0),
        ),
        "responseProfile": profile.key,
    }
