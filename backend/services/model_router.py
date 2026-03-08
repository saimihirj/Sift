"""Model routing for local and API-key-backed runtimes."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx


OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
MODEL_PROVIDER = os.environ.get("VK_MODEL_PROVIDER", "auto").lower()


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
            "num_predict": 150,
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
            "num_predict": 220,
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
            "max_tokens": 120,
        },
    ),
    "balanced": ModelProfileConfig(
        key="balanced",
        model=PROVIDER_CONFIGS["groq"].default_balanced_model,
        timeout_seconds=22.0,
        options={
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 160,
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
            }
        )
    return catalog


def provider_requires_api_key(provider: str) -> bool:
    return PROVIDER_CONFIGS[normalize_provider(provider)].requires_api_key


def default_model_for_provider(provider: str, response_profile: str = "speed") -> str:
    config = PROVIDER_CONFIGS[normalize_provider(provider)]
    return config.default_balanced_model if normalize_profile(response_profile) == "balanced" else config.default_speed_model


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
            "num_predict": 150 if profile == "speed" else 220,
        }
        return ModelProfileConfig(key=profile, model=chosen_model, timeout_seconds=timeout_seconds, options=options)

    timeout_seconds = 18.0 if profile == "speed" else 22.0
    options = {
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 120 if profile == "speed" else 160,
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
                    yield "complete", {
                        "message": "".join(accumulated).strip(),
                        "responseProfile": config.key,
                        "model": config.model,
                        "provider": "ollama",
                        "fallbackUsed": False,
                        "timings": {
                            "firstTokenSeconds": round(first_token_seconds or total_seconds, 3),
                            "totalSeconds": round(total_seconds, 3),
                        },
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
        headers["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "https://signal.local")
        headers["X-Title"] = "Signal"

    start = time.perf_counter()
    first_token_seconds = None
    accumulated: list[str] = []
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
                delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    accumulated.append(delta)
                    if first_token_seconds is None:
                        first_token_seconds = time.perf_counter() - start
                    yield "delta", {"delta": delta}
            total_seconds = time.perf_counter() - start
            yield "complete", {
                "message": "".join(accumulated).strip(),
                "responseProfile": config.key,
                "model": config.model,
                "provider": provider,
                "fallbackUsed": False,
                "timings": {
                    "firstTokenSeconds": round(first_token_seconds or total_seconds, 3),
                    "totalSeconds": round(total_seconds, 3),
                },
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
        "timings": result["timings"],
    }


async def stream_chat_completion(
    system: str,
    messages: list[dict[str, Any]],
    response_profile: str,
    provider_override: str | None = None,
    model_override: str = "",
    api_key: str | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    requested = normalize_profile(response_profile)
    provider = normalize_provider(provider_override or active_provider())
    primary = _profile_config_for_provider(provider, requested, model_override)
    allow_fallback = not model_override.strip()

    try:
        async for event, payload in _stream_from_profile(system, messages, primary, provider, api_key):
            yield event, payload
        return
    except Exception as exc:
        if requested == "speed" or not allow_fallback:
            raise exc

    fallback = _profile_config_for_provider(provider, "speed")
    async for event, payload in _stream_from_profile(system, messages, fallback, provider, api_key):
        if event in {"meta", "complete"}:
            payload["fallbackUsed"] = True
            payload["requestedProfile"] = requested
        yield event, payload


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
    return {
        "message": data.get("message", {}).get("content", "").strip(),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
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
        headers["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "https://signal.local")
        headers["X-Title"] = "Signal"
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{provider_config.base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    total_seconds = time.perf_counter() - start
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {
        "message": (content or "").strip(),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
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
    return {
        "message": "".join(text_parts).strip(),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
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
    return {
        "message": "".join(parts).strip(),
        "timings": {
            "firstTokenSeconds": round(total_seconds, 3),
            "totalSeconds": round(total_seconds, 3),
        },
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
        "timings": result["timings"],
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
