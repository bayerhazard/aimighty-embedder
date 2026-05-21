import sys, os
sys.path.insert(0, "/pypackages")
import time, logging, asyncio, threading, ctypes
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Union
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
OV_PERFORMANCE_HINT = os.getenv("PERFORMANCE_HINT", "LATENCY")
OV_NUM_STREAMS = os.getenv("NUM_STREAMS", "1")
CPU_PINNING = os.getenv("CPU_PINNING", "NO")  # Default to NO for cooperative resource sharing

def _build_ov_config(device):
    cfg = {
        "PERFORMANCE_HINT": "LATENCY",
        "NUM_STREAMS": "1",
    }
    if device.upper() == "CPU":
        cfg["INFERENCE_NUM_THREADS"] = "8"
        cfg["SCHEDULING_CORE_TYPE"] = "PCORE_ONLY"
        cfg["ENABLE_CPU_PINNING"] = "YES" if CPU_PINNING.upper() == "YES" else "NO"
    return cfg

app = FastAPI()
_model = None
_tokenizer = None
_infer_lock = threading.Lock()
_model_ready = False
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

@app.get("/", response_class=HTMLResponse)
def root():
    """Browser landing page. API consumers use /v1/embeddings, /v1/models, /health."""
    status_color = "#10b981" if _model_ready else "#f59e0b"
    status_text = "Ready" if _model_ready else "Loading model..."
    device = OV_DEVICE.upper()
    mode = os.getenv("EMBEDDER_MODE", "single")
    mode_label = "Cluster (2 iGPUs)" if mode == "cluster" else "Single (1 iGPU)"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aimighty Embedder &mdash; {MODEL_NAME}</title>
<link rel="icon" type="image/png" href="https://github.com/bayerhazard/aimighty-embedder/raw/main/icon.png">
<style>
  *,*::before,*::after{{box-sizing:border-box}}
  html,body{{margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:linear-gradient(135deg,#0f172a 0%,#1e293b 50%,#0f172a 100%);color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem 1rem}}
  .card{{width:100%;max-width:780px;background:rgba(15,23,42,.72);border:1px solid rgba(148,163,184,.15);border-radius:20px;padding:2.5rem;backdrop-filter:blur(20px);box-shadow:0 25px 50px -12px rgba(0,0,0,.5)}}
  .header{{display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem}}
  .icon{{width:64px;height:64px;border-radius:14px;background:#fff;padding:6px;flex-shrink:0}}
  h1{{margin:0;font-size:1.75rem;font-weight:700;letter-spacing:-.02em}}
  .subtitle{{margin:.25rem 0 0;color:#94a3b8;font-size:.95rem}}
  .badge{{display:inline-flex;align-items:center;gap:.5rem;margin-top:.75rem;padding:.35rem .75rem;background:rgba(16,185,129,.12);border:1px solid {status_color}55;border-radius:999px;font-size:.8rem;font-weight:600;color:{status_color}}}
  .dot{{width:8px;height:8px;border-radius:50%;background:{status_color};box-shadow:0 0 12px {status_color}}}
  h2{{margin:2rem 0 .75rem;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:#64748b}}
  .endpoints{{display:grid;gap:.5rem}}
  .endpoint{{display:flex;align-items:center;gap:.75rem;padding:.75rem 1rem;background:rgba(30,41,59,.5);border:1px solid rgba(148,163,184,.1);border-radius:10px;font-family:"SF Mono",Monaco,Consolas,monospace;font-size:.85rem}}
  .method{{flex-shrink:0;font-weight:700;font-size:.7rem;padding:.2rem .5rem;border-radius:5px;letter-spacing:.05em}}
  .method.GET{{background:rgba(59,130,246,.2);color:#60a5fa}}
  .method.POST{{background:rgba(168,85,247,.2);color:#c084fc}}
  .path{{color:#e2e8f0;flex:1}}
  .desc{{color:#64748b;font-size:.8rem;font-family:-apple-system,sans-serif}}
  pre{{margin:0;padding:1.25rem;background:#020617;border:1px solid rgba(148,163,184,.1);border-radius:10px;font-family:"SF Mono",Monaco,Consolas,monospace;font-size:.8rem;color:#cbd5e1;overflow-x:auto;line-height:1.6}}
  .kw{{color:#f472b6}}.str{{color:#86efac}}.num{{color:#fbbf24}}
  .meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.75rem;margin-top:1rem}}
  .meta-item{{padding:.85rem 1rem;background:rgba(30,41,59,.4);border:1px solid rgba(148,163,184,.1);border-radius:10px}}
  .meta-label{{font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;color:#64748b;font-weight:700}}
  .meta-value{{margin-top:.3rem;color:#e2e8f0;font-size:.95rem;font-weight:600;font-family:"SF Mono",Monaco,Consolas,monospace}}
  footer{{margin-top:2rem;padding-top:1.25rem;border-top:1px solid rgba(148,163,184,.1);color:#64748b;font-size:.8rem;text-align:center}}
  a{{color:#60a5fa;text-decoration:none;transition:color .15s}}
  a:hover{{color:#93c5fd}}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <img class="icon" src="https://github.com/bayerhazard/aimighty-embedder" alt="Aimighty Embedder">
    <div>
      <h1>Aimighty Embedder (Optimized)</h1>
      <p class="subtitle">OpenAI-compatible embedding API &middot; OpenVINO on Intel CPU/iGPU</p>
      <span class="badge"><span class="dot"></span>{status_text}</span>
    </div>
  </div>
  <div class="meta">
    <div class="meta-item"><div class="meta-label">Model</div><div class="meta-value">{MODEL_NAME}</div></div>
    <div class="meta-item"><div class="meta-label">Device</div><div class="meta-value">{device}</div></div>
    <div class="meta-item"><div class="meta-label">Mode</div><div class="meta-value">{mode_label}</div></div>
    <div class="meta-item"><div class="meta-label">Max tokens</div><div class="meta-value">8192</div></div>
  </div>
  <h2>API Endpoints</h2>
  <div class="endpoints">
    <div class="endpoint"><span class="method POST">POST</span><span class="path">/v1/embeddings</span><span class="desc">Generate embeddings (OpenAI-compatible)</span></div>
    <div class="endpoint"><span class="method GET">GET</span><span class="path">/v1/models</span><span class="desc">List available models</span></div>
    <div class="endpoint"><span class="method GET">GET</span><span class="path">/health</span><span class="desc">Liveness probe</span></div>
  </div>
  <h2>Quick start</h2>
  <pre><span class="kw">curl</span> -X POST <span class="str">"$ENDPOINT/v1/embeddings"</span> \\
  -H <span class="str">"Content-Type: application/json"</span> \\
  -d <span class="str">'{{"input": "Hello world", "model": "{MODEL_NAME}"}}'</span></pre>
  <footer>
    Built for <a href="https://github.com/bayerhazard/aimighty-embedder" target="_blank" rel="noopener">Olares</a> &middot;
    <a href="https://huggingface.co/Qwen/Qwen3-Embedding-4B" target="_blank" rel="noopener">Qwen3-Embedding-4B</a> &middot;
    <a href="https://docs.openvino.ai/" target="_blank" rel="noopener">OpenVINO 2026</a>
  </footer>
</div>
</body>
</html>"""
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
    """Synchronous inference — runs in a worker thread to keep the event loop free."""
    import torch

    with _infer_lock:
        model, tok = get_model()
        log.info("Embedding %d text(s)", len(texts))

        enc = tok(texts, padding=True, truncation=True, max_length=8192, return_tensors="pt")

        with torch.no_grad():
            out = model(**enc)

        # Qwen3-Embedding requires LAST TOKEN pooling
        last_hidden = out[0]
        attention_mask = enc["attention_mask"]
        pooled = last_hidden[:, -1]
        pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        vecs = pooled.tolist()
        total = int(enc["input_ids"].numel())

    try:
        _libc.malloc_trim(0)
    except (AttributeError, OSError):
        pass
    return vecs, total

@app.post("/v1/embeddings")
async def embed(req: EmbReq):
    texts = [req.input] if isinstance(req.input, str) else req.input

    try:
        vecs, total = await asyncio.wait_for(
            asyncio.to_thread(_run_inference, texts),
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        log.error("Inference timeout after 300s for %d text(s)", len(texts))
        return JSONResponse(
            status_code=504,
            content={"error": "inference timeout", "detail": "Request exceeded 300s limit"},
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

@app.on_event("startup")
def startup_event():
    log.info("FastAPI startup: warming up model...")
    try:
        model, tok = get_model()
        import torch
        enc = tok(["warmup"], padding=True, truncation=True, return_tensors="pt")
        with _infer_lock:
            with torch.no_grad():
                model(**enc)
        log.info("Warmup inference complete. Model ready.")
    except Exception as e:
        log.exception("Model warmup failed: %s", e)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, workers=2)
