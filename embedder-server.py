import sys, os
sys.path.insert(0, "/pypackages")
import time, logging, asyncio, ctypes
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Union
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("embedder")

MODEL_DIR  = os.getenv("MODEL_DIR", "/models_cache/aimighty-embedding-4b")
MODEL_NAME = os.getenv("MODEL_NAME", "aimighty-embedding-4b")
PORT       = int(os.getenv("PORT", "9997"))

app = FastAPI()
_model = None
_tokenizer = None
_model_lock = asyncio.Lock()
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

    log.info("Loading OpenVINO model on CPU...")

    _model = OVModelForFeatureExtraction.from_pretrained(
        MODEL_DIR,
        device="CPU",
        compile=True,
        ov_config={
            "PERFORMANCE_HINT": "LATENCY",
            "NUM_STREAMS": "1",
        }
    )
    log.info("Model loaded on CPU successfully.")

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

@app.post("/v1/embeddings")
async def embed(req: EmbReq):
    import torch

    async with _model_lock:
        model, tok = get_model()
        texts = [req.input] if isinstance(req.input, str) else req.input
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

    ctypes.CDLL("libc.so.6").malloc_trim(0)

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
