import sys, os
sys.path.insert(0, "/pypackages")
import time, logging, asyncio, threading, ctypes
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Union
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("embedder")

MODEL_DIR  = os.getenv("MODEL_DIR", "/models_cache/aimighty-embedding-4b")
MODEL_NAME = os.getenv("MODEL_NAME", "aimighty-embedding-4b")
PORT       = int(os.getenv("PORT", "9997"))

OV_DEVICE = os.getenv("OV_DEVICE", "CPU")
OV_PERFORMANCE_HINT = os.getenv("PERFORMANCE_HINT", "LATENCY")
OV_NUM_STREAMS = os.getenv("NUM_STREAMS", "1")
OV_INFERENCE_PRECISION = os.getenv("INFERENCE_PRECISION_HINT", "f16")
OV_GPU_LARGE_ALLOC = os.getenv("GPU_ENABLE_LARGE_ALLOCATIONS", "NO")

def _build_ov_config():
    cfg = {
        "PERFORMANCE_HINT": OV_PERFORMANCE_HINT,
        "NUM_STREAMS": OV_NUM_STREAMS,
    }
    if OV_DEVICE.upper() == "GPU":
        cfg["INFERENCE_PRECISION_HINT"] = OV_INFERENCE_PRECISION
        cfg["GPU_ENABLE_LARGE_ALLOCATIONS"] = OV_GPU_LARGE_ALLOC
    return cfg

app = FastAPI()
_model = None
_tokenizer = None
_infer_lock = threading.Lock()
_model_ready = False

def get_model():
    global _model, _tokenizer, _model_ready
    if _model:
        return _model, _tokenizer

    log.info("=" * 50)
    log.info("Loading model from: %s", MODEL_DIR)
    log.info("=" * 50)

    from optimum.intel import OVModelForFeatureExtraction
    from transformers import AutoTokenizer

    log.info("Loading tokenizer...")
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    log.info("Tokenizer loaded successfully.")

    log.info("Loading OpenVINO model on %s...", OV_DEVICE)

    ov_config = _build_ov_config()
    log.info("OpenVINO config: %s", ov_config)

    device_to_use = OV_DEVICE
    try:
        _model = OVModelForFeatureExtraction.from_pretrained(
            MODEL_DIR,
            device=device_to_use,
            compile=True,
            ov_config=ov_config,
        )
        log.info("Model loaded on %s successfully.", device_to_use)
    except RuntimeError as e:
        if "GPU" in str(e) and device_to_use.upper() == "GPU":
            log.warning("GPU not available, falling back to CPU: %s", e)
            device_to_use = "CPU"
            _model = OVModelForFeatureExtraction.from_pretrained(
                MODEL_DIR,
                device="CPU",
                compile=True,
                ov_config={"PERFORMANCE_HINT": "LATENCY", "NUM_STREAMS": "1"},
            )
            log.info("Model loaded on CPU (fallback) successfully.")
        else:
            raise

    _model_ready = True
    log.info("=" * 50)
    log.info("Model ready. Serving requests on port %d", PORT)
    log.info("=" * 50)
    return _model, _tokenizer

class EmbReq(BaseModel):
    input: Union[str, List[str]]
    model: str = MODEL_NAME

@app.get("/health")
def health():
    status = "ready" if _model_ready else "loading"
    return {"status": status}

@app.get("/v1/models")
def models():
    return {
        "object": "list",
        "data": [{
            "id": MODEL_NAME,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "aimighty"
        }]
    }

def _run_inference(texts):
    """Synchronous inference — runs in a worker thread to keep the event loop free.
    The threading.Lock serialises access so the OpenVINO engine never sees
    concurrent infer requests (prevents 'Infer Request is busy')."""
    import torch

    with _infer_lock:
        model, tok = get_model()
        log.info("Embedding %d text(s)", len(texts))

        enc = tok(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")

        with torch.no_grad():
            out = model(**enc)

        emb = out[0]
        mask = enc["attention_mask"].unsqueeze(-1).expand(emb.size()).float()
        pooled = (emb * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        norms = pooled.norm(dim=1, keepdim=True).clamp(min=1e-9)
        vecs = (pooled / norms).tolist()
        total = int(enc["input_ids"].numel())

    try:
        ctypes.CDLL("libc.so.6", mode=ctypes.RTLD_GLOBAL).malloc_trim(0)
    except (AttributeError, OSError):
        pass
    return vecs, total

@app.post("/v1/embeddings")
async def embed(req: EmbReq):
    texts = [req.input] if isinstance(req.input, str) else req.input
    vecs, total = await asyncio.to_thread(_run_inference, texts)

    return {
        "object": "list",
        "model": req.model,
        "data": [
            {"object": "embedding", "index": i, "embedding": v}
            for i, v in enumerate(vecs)
        ],
        "usage": {"prompt_tokens": total, "total_tokens": total}
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)