import sys, os
sys.path.insert(0, "/pypackages")
import time, logging, asyncio, threading, ctypes
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Union
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("embedder")

# Creative Cooperative Optimization: Run with nice value 10 (lower priority)
# This allows the parsing module (or other CPU-heavy ingestion processes) to take P-cores
# when needed, while the embedder gracefully yields and runs on remaining resources.
# When the parser is idle, the embedder automatically bursts to utilize the full CPU power.
try:
    os.nice(10)
    log.info("Successfully set process niceness to 10 (cooperative background priority)")
except Exception as e:
    log.warning("Could not set process niceness: %s", e)

# Create symlinks for Intel GPU compute runtimes if running with GPU enabled
if os.path.exists("/host_libs"):
    log.info("Setting up Intel GPU runtime symlinks from host libraries...")
    libs = [
        ("libOpenCL.so.1", "libOpenCL.so.1"),
        ("libOpenCL.so.1", "libOpenCL.so"),
        ("libigc.so.1", "libigc.so.1"),
        ("libigdfcl.so.1", "libigdfcl.so.1"),
        ("libigdgmm.so.12", "libigdgmm.so.12"),
        ("libopencl-clang.so.14", "libopencl-clang.so.14"),
        ("libLLVMSPIRVLib.so.14", "libLLVMSPIRVLib.so.14"),
        ("libclang-cpp.so.14", "libclang-cpp.so.14"),
        ("libLLVM-14.so.1", "libLLVM-14.so.1"),
        ("libLLVM-14.so.1", "libLLVM-14.so"),
        # Level Zero dependencies for Arrow Lake iGPU compute
        ("libze_intel_gpu.so.1", "libze_intel_gpu.so.1"),
        ("libze_intel_gpu.so.1", "libze_intel_gpu.so"),
        ("libze_loader.so.1", "libze_loader.so.1"),
        ("libze_loader.so.1", "libze_loader.so"),
        ("libze_tracing_layer.so.1", "libze_tracing_layer.so.1"),
        ("libze_validation_layer.so.1", "libze_validation_layer.so.1"),
    ]
    for src_name, dst_name in libs:
        src = os.path.join("/host_libs", src_name)
        dst = os.path.join("/usr/lib/x86_64-linux-gnu", dst_name)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                os.symlink(src, dst)
                log.info("Created symlink: %s -> %s", dst, src)
            except Exception as e:
                log.error("Failed to symlink %s: %s", dst, e)

MODEL_DIR  = os.getenv("MODEL_DIR", "/models_cache/aimighty-embedding-4b")
MODEL_NAME = os.getenv("MODEL_NAME", "aimighty-embedding-4b")
PORT       = int(os.getenv("PORT", "9997"))

OV_DEVICE = os.getenv("OV_DEVICE", "CPU")
OV_PERFORMANCE_HINT = os.getenv("PERFORMANCE_HINT", "THROUGHPUT")
OV_NUM_STREAMS = os.getenv("NUM_STREAMS", "1")
INFERENCE_THREADS = os.getenv("INFERENCE_THREADS", "8")
CPU_PINNING = os.getenv("CPU_PINNING", "YES")  # deterministic scheduling; nice(10) already yields priority
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "8192"))
EMBED_DIM = int(os.getenv("EMBED_DIM", "0"))  # 0 = full dim (2560); 32..2560 = Matryoshka (MRL) slice
DEFAULT_INSTRUCTION = os.getenv("DEFAULT_INSTRUCTION", "")  # e.g. "Given a web search query, retrieve relevant passages that answer the query"
BATCH_WINDOW = float(os.getenv("BATCH_WINDOW_MS", "5")) / 1000.0  # coalescing window for concurrent requests
INFER_TIMEOUT = float(os.getenv("INFER_TIMEOUT_SEC", "300"))

def _build_ov_config(device):
    cfg = {
        "PERFORMANCE_HINT": OV_PERFORMANCE_HINT,
        "NUM_STREAMS": OV_NUM_STREAMS,
    }
    if device.upper() == "CPU":
        cfg["INFERENCE_NUM_THREADS"] = INFERENCE_THREADS
        cfg["SCHEDULING_CORE_TYPE"] = "PCORE_ONLY"
        cfg["ENABLE_CPU_PINNING"] = "YES" if CPU_PINNING.upper() == "YES" else "NO"
    return cfg

_model = None
_tokenizer = None
_infer_lock = threading.Lock()
_model_ready = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("FastAPI startup: warming up model...")
    try:
        _run_inference(["warmup"])
        log.info("Warmup inference complete. Model ready.")
    except Exception as e:
        log.exception("Model warmup failed: %s", e)
    yield

app = FastAPI(lifespan=lifespan)
try:
    _libc = ctypes.CDLL("libc.so.6", mode=ctypes.RTLD_GLOBAL)
except (AttributeError, OSError):
    _libc = None

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
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, padding_side="left")
    log.info("Tokenizer loaded successfully.")

    log.info("Loading OpenVINO model on %s...", OV_DEVICE)

    device_to_use = OV_DEVICE
    ov_config = _build_ov_config(device_to_use)
    log.info("OpenVINO config: %s", ov_config)

    try:
        _model = OVModelForFeatureExtraction.from_pretrained(
            MODEL_DIR,
            device=device_to_use,
            compile=False,
            ov_config=ov_config,
        )
        # Force compilation inside try block to catch any GPU/OpenCL driver load issues
        _model.compile()
        log.info("Model loaded and compiled on %s successfully.", device_to_use)
    except Exception as e:
        if "GPU" in device_to_use.upper():
            log.warning("GPU compile failed, falling back to CPU: %s", e)
            device_to_use = "CPU"
            ov_config_fallback = _build_ov_config("CPU")
            _model = OVModelForFeatureExtraction.from_pretrained(
                MODEL_DIR,
                device="CPU",
                compile=False,
                ov_config=ov_config_fallback,
            )
            _model.compile()
            log.info("Model loaded and compiled on CPU (fallback) successfully.")
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
    instruction: Optional[str] = None  # optional query-side task instruction (Qwen3 instruct format)

@app.get("/", response_class=HTMLResponse)
def root():
    """Browser landing page. API consumers use /v1/embeddings, /v1/models, /health."""
    status_color = "ready" if _model_ready else "offline"
    status_text = "Bereit" if _model_ready else "Modell wird geladen…"
    device = OV_DEVICE.upper()
    mode = os.getenv("EMBEDDER_MODE", "Single_Node")
    is_cluster = "cluster" in mode.lower()
    mode_label = "Cluster (2 Worker)" if is_cluster else "Single Node (1 Worker)"
    try:
        with open("/app/dashboard.html", encoding="utf-8") as fh:
            html = fh.read()
    except FileNotFoundError:
        html = "<!DOCTYPE html><html><body><h1>Embedder</h1></body></html>"
    replacements = {
        "__STATUS_CLASS__": status_color,
        "__STATUS_TEXT__": status_text,
        "__MODEL__": MODEL_NAME,
        "__DEVICE__": device,
        "__MODE__": mode_label,
        "__MAXTOKENS__": str(MAX_LENGTH),
    }
    for key, val in replacements.items():
        html = html.replace(key, val)
    return HTMLResponse(content=html)


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
    Returns (vectors, per-item token counts)."""
    import torch

    with _infer_lock:
        model, tok = get_model()
        log.info("Embedding %d text(s)", len(texts))

        enc = tok(texts, padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt")

        with torch.no_grad():
            out = model(**enc)

        # Qwen3-Embedding requires LAST TOKEN pooling (padding_side="left" -> real last token)
        last_hidden = out[0]
        pooled = last_hidden[:, -1]
        # Optional Matryoshka (MRL) truncation: model supports any dim 32..2560
        if EMBED_DIM and 0 < EMBED_DIM < pooled.shape[1]:
            pooled = pooled[:, :EMBED_DIM]
        pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        vecs = pooled.tolist()
        # per-item token counts from attention mask (excludes padding)
        counts = [int(c) for c in enc["attention_mask"].sum(dim=1).tolist()]

    try:
        _libc.malloc_trim(0)
    except (AttributeError, OSError):
        pass
    return vecs, counts

class _BatchAggregator:
    """Coalesce concurrent /v1/embeddings requests into a single inference call.

    Requests arriving within BATCH_WINDOW are grouped into one batched forward
    pass, which is far more efficient on CPU (memory-bound) than per-request calls.
    """

    def __init__(self, window: float):
        self._window = window
        self._lock = asyncio.Lock()
        self._pending: list = []  # [(texts: list[str], future)]
        self._task: Optional[asyncio.Task] = None

    async def submit(self, texts: List[str]):
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        async with self._lock:
            self._pending.append((texts, fut))
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._drain())
        return await asyncio.wait_for(fut, timeout=INFER_TIMEOUT)

    async def _drain(self):
        try:
            while True:
                await asyncio.sleep(self._window)
                async with self._lock:
                    batch = self._pending
                    self._pending = []
                    if not batch:
                        self._task = None
                        return
                await self._run_batch(batch)
        except asyncio.CancelledError:
            async with self._lock:
                pending = self._pending
                self._pending = []
            for _, fut in pending:
                if not fut.done():
                    fut.cancel()

    async def _run_batch(self, batch):
        flat: List[str] = []
        spans = []
        for texts, _ in batch:
            start = len(flat)
            flat.extend(texts)
            spans.append((start, len(flat)))
        try:
            vecs, counts = await asyncio.to_thread(_run_inference, flat)
        except Exception as e:
            log.exception("Batch inference failed for %d request(s)", len(batch))
            for _, fut in batch:
                if not fut.done():
                    fut.set_exception(e)
            return
        for (start, end), (_, fut) in zip(spans, batch):
            if fut.done():
                continue
            fut.set_result((vecs[start:end], sum(counts[start:end])))

aggregator = _BatchAggregator(BATCH_WINDOW)

def _apply_instruction(texts, instruction):
    """Qwen3 query-side instruct prefix (docs should be sent without instruction)."""
    if not instruction:
        return texts
    prefix = f"Instruct: {instruction}\nQuery:"
    return [prefix + t for t in texts]

@app.post("/v1/embeddings")
async def embed(req: EmbReq):
    texts = [req.input] if isinstance(req.input, str) else req.input
    instruction = req.instruction if req.instruction is not None else DEFAULT_INSTRUCTION
    texts = _apply_instruction(texts, instruction)

    try:
        vecs, total = await aggregator.submit(texts)
    except asyncio.TimeoutError:
        log.error("Inference timeout after %gs for %d text(s)", INFER_TIMEOUT, len(texts))
        return JSONResponse(
            status_code=504,
            content={"error": "inference timeout", "detail": f"Request exceeded {INFER_TIMEOUT:g}s limit"},
        )
    except Exception as e:
        log.exception("Inference failed for %d text(s)", len(texts))
        return JSONResponse(
            status_code=500,
            content={"error": "inference failed", "detail": str(e)},
        )

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
    # One worker per pod: multi-node parallelism is handled at the replica level
    # (EMBEDDER_MODE=cluster -> 2 pods, one per node). Raise UVICORN_WORKERS only
    # if you want additional in-process workers.
    num_workers = int(os.getenv("UVICORN_WORKERS", "1"))
    mode = os.getenv("EMBEDDER_MODE", "Single_Node")
    log.info("Starting uvicorn with %d worker(s) in %s mode", num_workers, mode)
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, workers=num_workers)
