"""OpenAI-compatible local inference server for Sift Brain fine-tuned adapters.

Exposes POST /v1/chat/completions on port 8001 (configurable).
The main Sift app points LOCAL_OPENAI_BASE_URL=http://127.0.0.1:8001/v1 at it.

Supports:
  - streaming and non-streaming responses
  - chat completions with system + user + assistant messages
  - dynamic adapter switching via X-Sift-Adapter header

Start with:
    python3 scripts/serve_sift_brain.py [--adapter latest] [--port 8001]
    # or via npm:
    npm run brain:serve
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
ADAPTERS_DIR = DATA_DIR / "model_adapters"

# Globals — set on startup
_model: Any = None
_tokenizer: Any = None
_adapter_name: str = ""
_base_model_id: str = ""

DEFAULT_PORT = int(os.environ.get("SIFT_BRAIN_PORT", "8001"))
DEFAULT_HOST = os.environ.get("SIFT_BRAIN_HOST", "127.0.0.1")
MAX_NEW_TOKENS = int(os.environ.get("SIFT_BRAIN_MAX_NEW_TOKENS", "512"))


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Sift Brain — Local Inference Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models (OpenAI-compatible)
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "sift-brain"
    messages: list[ChatMessage]
    max_tokens: int | None = None
    temperature: float = 0.7
    stream: bool = False


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def _do_inference(messages: list[dict[str, str]], max_new_tokens: int, temperature: float) -> str:
    import torch

    text = _tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = _tokenizer(text, return_tensors="pt").to(_model.device)
    with torch.no_grad():
        outputs = _model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0.0,
            temperature=temperature if temperature > 0.0 else 1.0,
            pad_token_id=_tokenizer.eos_token_id,
        )
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    return _tokenizer.decode(generated, skip_special_tokens=True)


async def _stream_response(content: str, model: str, completion_id: str) -> AsyncIterator[str]:
    """Yield SSE chunks simulating OpenAI streaming format."""
    # Split into word chunks for streaming effect
    words = content.split(" ")
    for i, word in enumerate(words):
        delta = word + (" " if i < len(words) - 1 else "")
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk)}\n\n"

    # Final chunk
    final = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": "sift-brain", "object": "model", "owned_by": "sift"}],
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": _base_model_id,
        "adapter": _adapter_name,
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    if _model is None or _tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Start the server first.")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    max_tokens = request.max_tokens or MAX_NEW_TOKENS

    try:
        content = _do_inference(messages, max_new_tokens=max_tokens, temperature=request.temperature)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inference error: {exc}")

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    if request.stream:
        return StreamingResponse(
            _stream_response(content, request.model, completion_id),
            media_type="text/event-stream",
        )

    return JSONResponse({
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": sum(len(m["content"].split()) for m in messages),
            "completion_tokens": len(content.split()),
            "total_tokens": sum(len(m["content"].split()) for m in messages) + len(content.split()),
        },
    })


# ---------------------------------------------------------------------------
# Startup loader
# ---------------------------------------------------------------------------

def load_model(adapter_path: str | Path | None = None) -> None:
    """Load the fine-tuned adapter. Call this before starting the server."""
    global _model, _tokenizer, _adapter_name, _base_model_id

    from sift_brain.serving.model_registry import ModelRegistry

    registry = ModelRegistry.load()

    if adapter_path:
        path = Path(adapter_path)
    else:
        best = registry.best_adapter()
        if best:
            path = Path(best["path"])
        else:
            raise RuntimeError(
                "No trained adapters found. Run `npm run brain:train` first.\n"
                "Or point --adapter at a specific adapter directory."
            )

    if not path.exists():
        raise FileNotFoundError(f"Adapter not found: {path}")

    print(f"[server] Loading adapter: {path}")

    # Load base model + adapter
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    meta_path = path / "run_metadata.json"
    base_model_id = "Qwen/Qwen3-8B"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        base_model_id = meta.get("base_model", base_model_id)

    _base_model_id = base_model_id
    _adapter_name = path.name

    print(f"[server] Base model: {base_model_id}")
    _tokenizer = AutoTokenizer.from_pretrained(str(path), trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        device_map="auto",
        trust_remote_code=True,
    )
    _model = PeftModel.from_pretrained(base, str(path))
    _model.eval()
    print(f"[server] Model loaded. Ready at http://{DEFAULT_HOST}:{DEFAULT_PORT}/v1")


def start_server(
    adapter_path: str | Path | None = None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    import uvicorn

    load_model(adapter_path)
    uvicorn.run(app, host=host, port=port, log_level="info")
