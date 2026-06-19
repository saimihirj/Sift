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
MODEL_PROVIDER = os.environ.get("SIFT_MODEL_PROVIDER", "auto").lower()
CONTINUE_PROMPT = (
    "Continue exactly from where you stopped. Do not restart, summarize, apologize, or repeat headings already covered. "
    "Resume with the unfinished point and finish the answer cleanly."
)
VISION_MODEL_HINTS = (
    "qwen2.5vl",
    "qwen2.5-vl",
    "qwen3-vl",
    "qwen-vl",
    "gemma3",
    "llava",
    "bakllava",
    "moondream",
    "gpt-5",
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
    "local_openai": True,
    "open_source": True,
    "groq": True,
    "cerebras": False,
    "openai": True,
    "openrouter": True,
    "anthropic": True,
    "gemini": True,
    "vertex": True,
}
RECOMMENDED_DECK_MODELS = {
    "ollama": "qwen2.5vl:7b",
    "local_openai": os.environ.get("LOCAL_OPENAI_DECK_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct"),
    "open_source": os.environ.get("OPEN_SOURCE_DECK_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct"),
    "groq": "",
    "cerebras": "",
    "openai": "gpt-4.1",
    "openrouter": "meta-llama/llama-4-maverick",
    "anthropic": "claude-sonnet-4-5",
    "gemini": "gemini-2.5-flash",
    "vertex": "gemini-2.5-flash",
    "sift_brain": "sift-brain",
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


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
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
        default_speed_model=os.environ.get("OLLAMA_MODEL_SPEED", "qwen3:8b"),
        default_balanced_model=os.environ.get("OLLAMA_MODEL_BALANCED", "qwen3:30b"),
        requires_api_key=False,
    ),
    "local_openai": ProviderConfig(
        key="local_openai",
        label="Local OpenAI-compatible",
        api_style="openai",
        base_url=os.environ.get("LOCAL_OPENAI_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/"),
        env_api_key_var="LOCAL_OPENAI_API_KEY",
        default_speed_model=os.environ.get("LOCAL_OPENAI_MODEL_SPEED", "Qwen/Qwen3-8B"),
        default_balanced_model=os.environ.get("LOCAL_OPENAI_MODEL_BALANCED", "Qwen/Qwen3-30B-A3B"),
        requires_api_key=False,
    ),
    "open_source": ProviderConfig(
        key="open_source",
        label="Open-source endpoint",
        api_style="openai",
        base_url=os.environ.get("OPEN_SOURCE_BASE_URL", "").strip().rstrip("/"),
        env_api_key_var="OPEN_SOURCE_API_KEY",
        default_speed_model=os.environ.get("OPEN_SOURCE_MODEL_SPEED", "Qwen/Qwen3-8B"),
        default_balanced_model=os.environ.get("OPEN_SOURCE_MODEL_BALANCED", "Qwen/Qwen3-30B-A3B"),
        requires_api_key=os.environ.get("OPEN_SOURCE_REQUIRES_API_KEY", "true").strip().lower() not in {"0", "false", "no", "off"},
    ),
    "groq": ProviderConfig(
        key="groq",
        label="Groq",
        api_style="openai",
        base_url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        env_api_key_var="GROQ_API_KEY",
        default_speed_model=os.environ.get("GROQ_MODEL_SPEED", "meta-llama/llama-4-scout-17b-16e-instruct"),
        default_balanced_model=os.environ.get("GROQ_MODEL_BALANCED", "meta-llama/llama-4-maverick-17b-128e-instruct"),
        requires_api_key=True,
    ),
    "cerebras": ProviderConfig(
        key="cerebras",
        label="Cerebras",
        api_style="openai",
        base_url=os.environ.get("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
        env_api_key_var="CEREBRAS_API_KEY",
        default_speed_model=os.environ.get("CEREBRAS_MODEL_SPEED", "qwen-3-8b"),
        default_balanced_model=os.environ.get("CEREBRAS_MODEL_BALANCED", "qwen-3-32b"),
        requires_api_key=True,
    ),
    "openai": ProviderConfig(
        key="openai",
        label="OpenAI",
        api_style="openai",
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        env_api_key_var="OPENAI_API_KEY",
        default_speed_model=os.environ.get("OPENAI_MODEL_SPEED", "gpt-4.1-mini"),
        default_balanced_model=os.environ.get("OPENAI_MODEL_BALANCED", "gpt-4.1"),
        requires_api_key=True,
    ),
    "openrouter": ProviderConfig(
        key="openrouter",
        label="OpenRouter",
        api_style="openai",
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        env_api_key_var="OPENROUTER_API_KEY",
        default_speed_model=os.environ.get("OPENROUTER_MODEL_SPEED", "meta-llama/llama-4-scout"),
        default_balanced_model=os.environ.get("OPENROUTER_MODEL_BALANCED", "meta-llama/llama-4-maverick"),
        requires_api_key=True,
    ),
    "anthropic": ProviderConfig(
        key="anthropic",
        label="Anthropic",
        api_style="anthropic",
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
        env_api_key_var="ANTHROPIC_API_KEY",
        default_speed_model=os.environ.get("ANTHROPIC_MODEL_SPEED", "claude-haiku-4-5"),
        default_balanced_model=os.environ.get("ANTHROPIC_MODEL_BALANCED", "claude-sonnet-4-5"),
        requires_api_key=True,
    ),
    "gemini": ProviderConfig(
        key="gemini",
        label="Gemini",
        api_style="gemini",
        base_url=os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
        env_api_key_var="GEMINI_API_KEY",
        default_speed_model=os.environ.get("GEMINI_MODEL_SPEED", "gemini-2.5-flash"),
        default_balanced_model=os.environ.get("GEMINI_MODEL_BALANCED", "gemini-2.5-pro"),
        requires_api_key=True,
    ),
    "vertex": ProviderConfig(
        key="vertex",
        label="Vertex AI Gemini",
        api_style="vertex_gemini",
        base_url=os.environ.get("VERTEX_BASE_URL", ""),
        env_api_key_var=None,
        default_speed_model=os.environ.get("VERTEX_MODEL_SPEED", os.environ.get("GEMINI_MODEL_SPEED", "gemini-2.5-flash")),
        default_balanced_model=os.environ.get("VERTEX_MODEL_BALANCED", os.environ.get("GEMINI_MODEL_BALANCED", "gemini-2.5-pro")),
        requires_api_key=False,
    ),
    # Sift Brain — custom fine-tuned decision layer
    # Started separately via: python3 scripts/serve_sift_brain.py
    "sift_brain": ProviderConfig(
        key="sift_brain",
        label="Sift Brain (custom LLM)",
        api_style="openai",
        base_url=os.environ.get("SIFT_BRAIN_BASE_URL", "http://127.0.0.1:8001/v1"),
        env_api_key_var=None,
        default_speed_model=os.environ.get("SIFT_BRAIN_MODEL", "sift-brain"),
        default_balanced_model=os.environ.get("SIFT_BRAIN_MODEL", "sift-brain"),
        requires_api_key=False,
    ),
}

PROVIDER_PUBLIC_META: dict[str, dict[str, Any]] = {
    "ollama": {
        "latencyHint": "Local models — zero latency on device, complete data privacy.",
        "bestFor": "Local-first, private inference, and zero-key use.",
        "speedLabel": "Qwen3 8B",
        "balancedLabel": "Qwen3 30B",
        "publicReadiness": "Local install required",
        "openWeight": True,
        "docsUrl": "https://ollama.com/library/qwen3",
    },
    "local_openai": {
        "latencyHint": "Open-source models served by vLLM, TGI, LM Studio, or llama.cpp.",
        "bestFor": "Fast local GPUs, Hugging Face models, private endpoints.",
        "speedLabel": "Qwen3 8B",
        "balancedLabel": "Qwen3 30B",
        "publicReadiness": "Local endpoint",
        "openWeight": True,
        "docsUrl": "https://docs.vllm.ai/en/latest/serving/openai_compatible_server/",
    },
    "open_source": {
        "latencyHint": "Server-side open-source model endpoint for Qwen, Llama, Gemma, Pixtral, or other OpenAI-compatible deployments.",
        "bestFor": "Public demos that need open-source models without making users run local hardware.",
        "speedLabel": "Qwen VL",
        "balancedLabel": "Qwen VL",
        "publicReadiness": "Open-source cloud lane",
        "openWeight": True,
        "docsUrl": "https://docs.vllm.ai/en/latest/serving/openai_compatible_server/",
    },
    "groq": {
        "latencyHint": "World's fastest hosted inference — sub-100 ms TTFT on Llama-4.",
        "bestFor": "Low-latency public launch with Llama-4 open-weight models.",
        "speedLabel": "Llama-4 Scout",
        "balancedLabel": "Llama-4 Maverick",
        "publicReadiness": "Recommended hosted default",
        "openWeight": True,
        "docsUrl": "https://console.groq.com/docs/models",
    },
    "cerebras": {
        "latencyHint": "Fastest hosted open-weight throughput — Qwen3 on Cerebras silicon.",
        "bestFor": "High-speed expert and evaluation turns on Qwen3.",
        "speedLabel": "Qwen3 8B",
        "balancedLabel": "Qwen3 32B",
        "publicReadiness": "Performance lane",
        "openWeight": True,
        "docsUrl": "https://inference-docs.cerebras.ai/models/overview",
    },
    "openai": {
        "latencyHint": "Frontier quality for complex synthesis, deck reasoning, and polish.",
        "bestFor": "Highest-quality public mode when cost is acceptable.",
        "speedLabel": "GPT-4.1 mini",
        "balancedLabel": "GPT-4.1",
        "publicReadiness": "Frontier quality lane",
        "openWeight": False,
        "docsUrl": "https://platform.openai.com/docs/models",
    },
    "openrouter": {
        "latencyHint": "Flexible broker for comparing open-weight and closed frontier models.",
        "bestFor": "Provider experiments without changing the app.",
        "speedLabel": "Llama-4 Scout",
        "balancedLabel": "Llama-4 Maverick",
        "publicReadiness": "Experiment lane",
        "openWeight": True,
        "docsUrl": "https://openrouter.ai/models",
    },
    "anthropic": {
        "latencyHint": "Strong long-form synthesis with hosted API latency.",
        "bestFor": "Careful narrative analysis and investor-style memo work.",
        "speedLabel": "Haiku",
        "balancedLabel": "Sonnet",
        "publicReadiness": "Quality lane",
        "openWeight": False,
        "docsUrl": "https://docs.anthropic.com/en/docs/about-claude/models",
    },
    "gemini": {
        "latencyHint": "Fast hosted multimodal fallback for broad consumer access.",
        "bestFor": "Affordable hosted analysis and deck-adjacent workflows.",
        "speedLabel": "Flash",
        "balancedLabel": "Pro",
        "publicReadiness": "Multimodal lane",
        "openWeight": False,
        "docsUrl": "https://ai.google.dev/gemini-api/docs/models",
    },
    "vertex": {
        "latencyHint": "Google Cloud hosted Gemini path using the Cloud Run service account.",
        "bestFor": "Using GCP credits and IAM instead of per-session API keys.",
        "speedLabel": "Gemini Flash",
        "balancedLabel": "Gemini Pro",
        "publicReadiness": "GCP-native lane",
        "openWeight": False,
        "docsUrl": "https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference",
    },
}

PROVIDER_MODEL_PRESETS: dict[str, list[dict[str, str]]] = {
    "ollama": [
        {"label": "Qwen3 8B", "value": "qwen3:8b", "note": "Fast default."},
        {"label": "Qwen3 30B", "value": "qwen3:30b", "note": "Deeper reasoning."},
        {"label": "Qwen2.5 VL", "value": "qwen2.5vl:7b", "note": "Vision · deck image reading."},
        {"label": "Llama 3.2", "value": "llama3.2:latest", "note": "Lightweight CPU fallback."},
    ],
    "local_openai": [
        {"label": "Qwen3 8B", "value": "Qwen/Qwen3-8B", "note": "Fast open-weight default."},
        {"label": "Qwen3 30B", "value": "Qwen/Qwen3-30B-A3B", "note": "MoE · better reasoning."},
        {"label": "Qwen2.5 VL", "value": "Qwen/Qwen2.5-VL-7B-Instruct", "note": "Vision · deck image reading."},
        {"label": "Llama 4 Scout", "value": "meta-llama/Llama-4-Scout-17B-16E", "note": "Efficient MoE open-weight."},
    ],
    "open_source": [
        {"label": "Qwen2.5 VL", "value": "Qwen/Qwen2.5-VL-7B-Instruct", "note": "Best open-source deck vision default."},
        {"label": "Qwen3 VL", "value": "Qwen/Qwen3-VL-8B-Instruct", "note": "Newer open-source vision lane when available."},
        {"label": "Llama Vision", "value": "meta-llama/Llama-3.2-11B-Vision-Instruct", "note": "Alternative open-source visual reviewer."},
        {"label": "Pixtral", "value": "mistralai/Pixtral-12B-2409", "note": "Open multimodal deck reader."},
    ],
    "vertex": [
        {"label": "Gemini 2.5 Flash", "value": "gemini-2.5-flash", "note": "Stable low-latency GCP default."},
        {"label": "Gemini 2.5 Pro", "value": "gemini-2.5-pro", "note": "Stable higher-quality GCP default."},
        {"label": "Gemini 3 Flash", "value": "gemini-3-flash-preview", "note": "Latest fast preview lane."},
        {"label": "Gemini 3.1 Pro", "value": "gemini-3.1-pro-preview", "note": "Latest reasoning preview lane."},
    ],
    "gemini": [
        {"label": "Gemini 2.5 Flash", "value": "gemini-2.5-flash", "note": "Stable low-latency API default."},
        {"label": "Gemini 2.5 Pro", "value": "gemini-2.5-pro", "note": "Stable higher-quality API default."},
        {"label": "Gemini 3 Flash", "value": "gemini-3-flash-preview", "note": "Latest fast preview lane."},
        {"label": "Gemini 3.1 Pro", "value": "gemini-3.1-pro-preview", "note": "Latest reasoning preview lane."},
    ],
    "groq": [
        {"label": "Llama-4 Scout", "value": "meta-llama/llama-4-scout-17b-16e-instruct", "note": "Fast 17B MoE."},
        {"label": "Llama-4 Maverick", "value": "meta-llama/llama-4-maverick-17b-128e-instruct", "note": "Higher quality, 128E."},
        {"label": "Qwen3 8B", "value": "qwen/qwen3-8b", "note": "Groq open-weight alternative."},
    ],
    "cerebras": [
        {"label": "Qwen3 8B", "value": "qwen-3-8b", "note": "Fast Cerebras lane."},
        {"label": "Qwen3 32B", "value": "qwen-3-32b", "note": "Higher quality Cerebras lane."},
    ],
    "openai": [
        {"label": "GPT-4.1 mini", "value": "gpt-4.1-mini", "note": "Fast and affordable."},
        {"label": "GPT-4.1", "value": "gpt-4.1", "note": "Strongest reasoning."},
        {"label": "GPT-4o", "value": "gpt-4o", "note": "Vision + multimodal."},
    ],
    "openrouter": [
        {"label": "Llama-4 Scout", "value": "meta-llama/llama-4-scout", "note": "Fast open-weight via Router."},
        {"label": "Llama-4 Maverick", "value": "meta-llama/llama-4-maverick", "note": "Sharper open-weight via Router."},
        {"label": "Qwen3 8B", "value": "qwen/qwen3-8b", "note": "Lightweight open-weight."},
    ],
    "anthropic": [
        {"label": "Haiku 4.5", "value": "claude-haiku-4-5", "note": "Fast, affordable."},
        {"label": "Sonnet 4.5", "value": "claude-sonnet-4-5", "note": "Best balance for decks."},
    ],
}


OLLAMA_MODEL_PROFILES = {
    "speed": ModelProfileConfig(
        key="speed",
        model=PROVIDER_CONFIGS["ollama"].default_speed_model,
        timeout_seconds=_env_float("OLLAMA_TIMEOUT_SPEED", 24.0),
        options={
            "num_ctx": _env_int("OLLAMA_NUM_CTX_SPEED", 4096),
            "temperature": 0.72,
            "top_p": 0.9,
            "repeat_penalty": 1.06,
            "num_predict": _env_int("OLLAMA_MAX_TOKENS_SPEED", 180),
        },
    ),
    "balanced": ModelProfileConfig(
        key="balanced",
        model=PROVIDER_CONFIGS["ollama"].default_balanced_model,
        timeout_seconds=_env_float("OLLAMA_TIMEOUT_BALANCED", 42.0),
        options={
            "num_ctx": _env_int("OLLAMA_NUM_CTX_BALANCED", 6144),
            "temperature": 0.74,
            "top_p": 0.9,
            "repeat_penalty": 1.05,
            "num_predict": _env_int("OLLAMA_MAX_TOKENS_BALANCED", 360),
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


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _ollama_enabled() -> bool:
    return _bool_env("SIFT_ENABLE_OLLAMA", True)


def _local_openai_enabled() -> bool:
    return _bool_env("SIFT_ENABLE_LOCAL_OPENAI", not bool(_gcp_project_id()))


def _open_source_enabled() -> bool:
    return _bool_env("SIFT_ENABLE_OPEN_SOURCE_PROVIDER", bool(os.environ.get("OPEN_SOURCE_BASE_URL", "").strip()))


def _fallback_provider_for_disabled_ollama() -> str:
    if _gcp_project_id():
        return "vertex"
    for key, config in PROVIDER_CONFIGS.items():
        if key in {"ollama", "local_openai", "open_source"} or not config.env_api_key_var:
            continue
        if os.environ.get(config.env_api_key_var, "").strip():
            return key
    if _local_openai_enabled():
        return "local_openai"
    return "ollama"


def normalize_provider(provider: str | None) -> str:
    value = (provider or "ollama").strip().lower()
    if value == "ollama" and not _ollama_enabled():
        return _fallback_provider_for_disabled_ollama()
    if value == "local_openai" and not _local_openai_enabled():
        return _fallback_provider_for_disabled_ollama()
    if value == "open_source" and not _open_source_enabled():
        return _fallback_provider_for_disabled_ollama()
    return value if value in PROVIDER_CONFIGS else _fallback_provider_for_disabled_ollama()


def provider_catalog() -> list[dict[str, Any]]:
    catalog = []
    for provider in PROVIDER_CONFIGS.values():
        if provider.key == "ollama" and not _ollama_enabled():
            continue
        if provider.key == "local_openai" and not _local_openai_enabled():
            continue
        if provider.key == "open_source" and not _open_source_enabled():
            continue
        meta = PROVIDER_PUBLIC_META.get(provider.key, {})
        catalog.append(
            {
                "key": provider.key,
                "label": provider.label,
                "requiresApiKey": provider.requires_api_key,
                "serverConfigured": _provider_server_configured(provider.key),
                "defaultSpeedModel": provider.default_speed_model,
                "defaultBalancedModel": provider.default_balanced_model,
                "supportsVisionModels": PROVIDER_VISION_SUPPORT.get(provider.key, False),
                "recommendedDeckModel": RECOMMENDED_DECK_MODELS.get(provider.key, ""),
                "modelPresets": PROVIDER_MODEL_PRESETS.get(provider.key, []),
                **meta,
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


def _cap_ollama_tokens(provider: str, profile: str, max_tokens_override: int | None) -> int | None:
    if normalize_provider(provider) != "ollama" or not max_tokens_override or max_tokens_override <= 0:
        return max_tokens_override
    cap_name = "OLLAMA_MAX_TOKENS_SPEED" if normalize_profile(profile) == "speed" else "OLLAMA_MAX_TOKENS_BALANCED"
    default_cap = 180 if normalize_profile(profile) == "speed" else 360
    return min(int(max_tokens_override), _env_int(cap_name, default_cap))


def _profile_config_for_provider(
    provider: str,
    response_profile: str,
    model_override: str = "",
) -> ModelProfileConfig:
    normalized_provider = normalize_provider(provider)
    profile = normalize_profile(response_profile)
    chosen_model = model_override.strip() or default_model_for_provider(normalized_provider, profile)

    if normalized_provider == "ollama":
        timeout_seconds = _env_float("OLLAMA_TIMEOUT_SPEED", 24.0) if profile == "speed" else _env_float("OLLAMA_TIMEOUT_BALANCED", 42.0)
        options = {
            "num_ctx": _env_int("OLLAMA_NUM_CTX_SPEED", 4096) if profile == "speed" else _env_int("OLLAMA_NUM_CTX_BALANCED", 6144),
            "temperature": 0.72 if profile == "speed" else 0.74,
            "top_p": 0.9,
            "repeat_penalty": 1.06 if profile == "speed" else 1.05,
            "num_predict": _env_int("OLLAMA_MAX_TOKENS_SPEED", 180) if profile == "speed" else _env_int("OLLAMA_MAX_TOKENS_BALANCED", 360),
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


def _provider_server_configured(provider: str) -> bool:
    requested = (provider or "").strip().lower()
    config = PROVIDER_CONFIGS.get(requested) or PROVIDER_CONFIGS[normalize_provider(provider)]
    if config.key == "ollama":
        return _ollama_enabled()
    if config.key == "local_openai":
        return _local_openai_enabled()
    if config.key == "open_source":
        if not _open_source_enabled():
            return False
        return bool(config.base_url and (not config.requires_api_key or _provider_api_key(config.key)))
    if config.key == "vertex":
        return bool(_gcp_project_id())
    if not config.requires_api_key:
        return True
    return bool(_provider_api_key(config.key))


def _gcp_project_id() -> str:
    return (
        os.environ.get("SIFT_GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or ""
    ).strip()


def _vertex_location() -> str:
    return os.environ.get("VERTEX_LOCATION", os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")).strip() or "us-central1"


def _vertex_access_token() -> str:
    try:
        import google.auth  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Vertex AI provider requires google-auth, included with the Google Cloud client libraries.") from exc

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    return credentials.token or ""


def _vertex_model_url(model: str, *, multimodal: bool = False) -> str:
    project = _gcp_project_id()
    if not project:
        raise RuntimeError("Vertex AI provider requires SIFT_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT.")
    location = _vertex_location()
    base_url = PROVIDER_CONFIGS["vertex"].base_url.strip().rstrip("/")
    if not base_url:
        base_url = f"https://{location}-aiplatform.googleapis.com/v1"
    model_resource = f"projects/{project}/locations/{location}/publishers/google/models/{model}"
    method = "generateContent"
    return f"{base_url}/{model_resource}:{method}"


def active_provider() -> str:
    if MODEL_PROVIDER in PROVIDER_CONFIGS:
        chosen = normalize_provider(MODEL_PROVIDER)
        if _provider_server_configured(chosen):
            return chosen
    for provider in ("vertex", "groq", "cerebras", "openai", "openrouter", "anthropic", "gemini"):
        if _provider_server_configured(provider):
            return provider
    return "ollama" if _ollama_enabled() else _fallback_provider_for_disabled_ollama()


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


def _ollama_keep_alive() -> str:
    return os.environ.get("OLLAMA_KEEP_ALIVE", "10m").strip() or "10m"


def _ollama_runtime_options(options: dict[str, Any]) -> dict[str, Any]:
    configured = dict(options)
    num_thread = _env_int("OLLAMA_NUM_THREAD", 0)
    if num_thread > 0:
        configured["num_thread"] = num_thread
    num_gpu = _env_int("OLLAMA_NUM_GPU", -1)
    if num_gpu >= 0:
        configured["num_gpu"] = num_gpu
    return configured


def _ollama_payload(system: str, messages: list[dict[str, Any]], config: ModelProfileConfig, stream: bool) -> dict[str, Any]:
    return {
        "model": config.model,
        "stream": stream,
        "messages": _merge_messages(system, messages),
        "keep_alive": _ollama_keep_alive(),
        "options": _ollama_runtime_options(config.options),
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
        "num_ctx": _env_int("OLLAMA_NUM_CTX_MULTIMODAL", 6144),
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
        "keep_alive": _ollama_keep_alive(),
        "options": _ollama_runtime_options(options),
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
        headers["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "https://sift.local")
        headers["X-Title"] = "Sift"

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
                choices = data.get("choices") if isinstance(data.get("choices"), list) else []
                if not choices:
                    continue
                first_choice = choices[0] if isinstance(choices[0], dict) else {}
                finish_reason = _normalize_finish_reason(first_choice.get("finish_reason", finish_reason))
                delta = first_choice.get("delta", {}).get("content", "")
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
        if provider_config.requires_api_key and not chosen_api_key:
            raise RuntimeError(f"{provider_config.label} API key is not configured")
        async for event, payload in _stream_from_openai_compatible(normalized_provider, system, messages, config, chosen_api_key or "local"):
            yield event, payload
        return

    if provider_config.requires_api_key and not chosen_api_key:
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
        max_tokens_override=_cap_ollama_tokens(provider, requested, max_tokens_override),
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
            max_tokens_override=_cap_ollama_tokens(provider, "speed", max_tokens_override),
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
        "keep_alive": _ollama_keep_alive(),
        "options": _ollama_runtime_options({
            "num_ctx": _env_int("OLLAMA_NUM_CTX_BALANCED", 6144),
            "temperature": temperature,
            "top_p": top_p,
            "repeat_penalty": 1.08,
            "num_predict": max_tokens,
        }),
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
        headers["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "https://sift.local")
        headers["X-Title"] = "Sift"
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


async def _complete_vertex_gemini(
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
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _gemini_contents(messages),
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
            "maxOutputTokens": max_tokens,
        },
    }
    timeout = httpx.Timeout(timeout_seconds, connect=3.0, read=timeout_seconds)
    headers = {"Authorization": f"Bearer {_vertex_access_token()}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(_vertex_model_url(model), headers=headers, json=payload)
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
        result = await _complete_ollama(
            system,
            messages,
            chosen_model,
            min(max_tokens, _env_int("OLLAMA_MAX_TOKENS_DIRECT", 420)),
            temperature,
            top_p,
            timeout_seconds,
        )
    elif provider_config.api_style == "openai":
        result = await _complete_openai(
            normalized_provider,
            system,
            messages,
            chosen_model,
            chosen_api_key or "local",
            max_tokens,
            temperature,
            top_p,
            timeout_seconds,
        )
    elif provider_config.api_style == "anthropic":
        result = await _complete_anthropic(system, messages, chosen_model, chosen_api_key, max_tokens, temperature, timeout_seconds)
    elif provider_config.api_style == "gemini":
        result = await _complete_gemini(system, messages, chosen_model, chosen_api_key, max_tokens, temperature, top_p, timeout_seconds)
    elif provider_config.api_style == "vertex_gemini":
        result = await _complete_vertex_gemini(system, messages, chosen_model, max_tokens, temperature, top_p, timeout_seconds)
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
        headers["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "https://sift.local")
        headers["X-Title"] = "Sift"
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


async def _complete_vertex_gemini_multimodal(
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
    headers = {"Authorization": f"Bearer {_vertex_access_token()}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(_vertex_model_url(model, multimodal=True), headers=headers, json=payload)
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
        result = await _complete_ollama_multimodal(
            system,
            prompt,
            image_paths,
            chosen_model,
            min(max_tokens, _env_int("OLLAMA_MAX_TOKENS_MULTIMODAL", 480)),
            temperature,
            top_p,
            timeout_seconds,
        )
    elif provider_config.api_style == "openai":
        result = await _complete_openai_multimodal(
            normalized_provider,
            system,
            prompt,
            image_paths,
            chosen_model,
            chosen_api_key or "local",
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
    elif provider_config.api_style == "vertex_gemini":
        result = await _complete_vertex_gemini_multimodal(
            system,
            prompt,
            image_paths,
            chosen_model,
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
    profile = _profile_config_for_provider(provider, response_profile)
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
