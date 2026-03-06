"""Model routing for local Ollama and hosted Groq runtimes."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import AsyncIterator

import httpx


OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_PROVIDER = os.environ.get("VK_MODEL_PROVIDER", "auto").lower()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


@dataclass(frozen=True)
class ModelProfileConfig:
    key: str
    model: str
    timeout_seconds: float
    options: dict


OLLAMA_MODEL_PROFILES = {
    "speed": ModelProfileConfig(
        key="speed",
        model=os.environ.get("OLLAMA_MODEL_SPEED", "llama3.2:latest"),
        timeout_seconds=12.0,
        options={
            "num_ctx": 8192,
            "temperature": 0.7,
            "top_p": 0.9,
            "repeat_penalty": 1.12,
            "num_predict": 120,
        },
    ),
    "balanced": ModelProfileConfig(
        key="balanced",
        model=os.environ.get("OLLAMA_MODEL_BALANCED", "qwen3:4b"),
        timeout_seconds=18.0,
        options={
            "num_ctx": 8192,
            "temperature": 0.7,
            "top_p": 0.9,
            "repeat_penalty": 1.12,
            "num_predict": 140,
        },
    ),
}

GROQ_MODEL_PROFILES = {
    "speed": ModelProfileConfig(
        key="speed",
        model=os.environ.get("GROQ_MODEL_SPEED", "llama-3.1-8b-instant"),
        timeout_seconds=18.0,
        options={
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 120,
        },
    ),
    "balanced": ModelProfileConfig(
        key="balanced",
        model=os.environ.get("GROQ_MODEL_BALANCED", "llama-3.3-70b-versatile"),
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


def active_provider() -> str:
    if MODEL_PROVIDER == "groq":
        return "groq"
    if MODEL_PROVIDER == "ollama":
        return "ollama"
    if GROQ_API_KEY:
        return "groq"
    return "ollama"


def _ollama_payload(system: str, messages: list[dict], config: ModelProfileConfig, stream: bool) -> dict:
    return {
        "model": config.model,
        "stream": stream,
        "messages": [{"role": "system", "content": system}, *messages],
        "options": config.options,
    }


def _groq_payload(system: str, messages: list[dict], config: ModelProfileConfig, stream: bool) -> dict:
    payload = {
        "model": config.model,
        "messages": [{"role": "system", "content": system}, *messages],
        "temperature": config.options.get("temperature", 0.7),
        "top_p": config.options.get("top_p", 0.9),
        "max_tokens": config.options.get("max_tokens", 160),
        "stream": stream,
    }
    return payload


async def _stream_from_ollama(
    system: str,
    messages: list[dict],
    config: ModelProfileConfig,
) -> AsyncIterator[tuple[str, dict]]:
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


async def _stream_from_groq(
    system: str,
    messages: list[dict],
    config: ModelProfileConfig,
) -> AsyncIterator[tuple[str, dict]]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    payload = _groq_payload(system, messages, config, stream=True)
    start = time.perf_counter()
    first_token_seconds = None
    accumulated: list[str] = []
    timeout = httpx.Timeout(config.timeout_seconds, connect=3.0, read=config.timeout_seconds)
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{GROQ_BASE_URL}/chat/completions", headers=headers, json=payload) as response:
            response.raise_for_status()
            yield "meta", {
                "responseProfile": config.key,
                "model": config.model,
                "provider": "groq",
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
                "provider": "groq",
                "fallbackUsed": False,
                "timings": {
                    "firstTokenSeconds": round(first_token_seconds or total_seconds, 3),
                    "totalSeconds": round(total_seconds, 3),
                },
            }


async def _stream_from_profile(
    system: str,
    messages: list[dict],
    config: ModelProfileConfig,
    provider: str,
) -> AsyncIterator[tuple[str, dict]]:
    if provider == "groq":
        async for event, payload in _stream_from_groq(system, messages, config):
            yield event, payload
        return
    async for event, payload in _stream_from_ollama(system, messages, config):
        yield event, payload


async def stream_chat_completion(
    system: str,
    messages: list[dict],
    response_profile: str,
) -> AsyncIterator[tuple[str, dict]]:
    requested = normalize_profile(response_profile)
    provider = active_provider()
    profiles = GROQ_MODEL_PROFILES if provider == "groq" else OLLAMA_MODEL_PROFILES
    primary = profiles[requested]

    try:
        async for event, payload in _stream_from_profile(system, messages, primary, provider):
            yield event, payload
        return
    except Exception as exc:
        if requested == "speed":
            raise exc

    fallback = profiles["speed"]
    async for event, payload in _stream_from_profile(system, messages, fallback, provider):
        if event in {"meta", "complete"}:
            payload["fallbackUsed"] = True
            payload["requestedProfile"] = requested
        yield event, payload


async def generate_text(
    system: str,
    messages: list[dict],
    response_profile: str,
    max_tokens: int = 600,
) -> dict:
    provider = active_provider()
    profiles = GROQ_MODEL_PROFILES if provider == "groq" else OLLAMA_MODEL_PROFILES
    profile = profiles[normalize_profile(response_profile)]
    tuned_options = dict(profile.options)
    token_key = "max_tokens" if provider == "groq" else "num_predict"
    tuned_options[token_key] = max_tokens
    tuned = ModelProfileConfig(
        key=profile.key,
        model=profile.model,
        timeout_seconds=max(profile.timeout_seconds + 45.0, 90.0),
        options=tuned_options,
    )

    message = ""
    timings = {"totalSeconds": 0.0}
    async for event, payload in _stream_from_profile(system, messages, tuned, provider):
        if event == "complete":
            message = payload["message"]
            timings = payload["timings"]
            return {
                "message": message,
                "responseProfile": tuned.key,
                "model": tuned.model,
                "provider": provider,
                "timings": timings,
            }
    return {
        "message": message,
        "responseProfile": tuned.key,
        "model": tuned.model,
        "provider": provider,
        "timings": timings,
    }
