# Aimighty OpenVINO Embedder - Docker

OpenAI-compatible Embedding Service with OpenVINO optimization for Intel Arrow Lake-S iGPU.

## Features

- OpenAI-compatible API (`/v1/embeddings`, `/v1/models`)
- Automatic download and OpenVINO conversion on first start
- OpenVINO INT8 quantized Qwen3-Embedding-4B model
- iGPU optimization: THROUGHPUT hint, 2 streams, FP16, Large Allocations
- Async endpoints with lock against race conditions
- Automatic CPU fallback on iGPU failure
- malloc_trim for memory optimization
- Persistent model cache via Docker volume

## Prerequisites

- Docker + Docker Compose
- Intel GPU with OpenCL support (Arrow Lake-S, Meteor Lake, etc.)
- Intel GPU Device Plugin (for Kubernetes deployments)
- SR-IOV disabled on host (required for Level Zero GPU enumeration)
- Minimum 16 GB RAM, 24 GB recommended
- Internet connection for initial model download (~8 GB)

## Quick Start

```bash
# Customize .env
cp .env.example .env

# Build and start
docker compose up -d --build

# Follow logs (shows download and conversion progress)
docker compose logs -f embedder
```

### First Start

On first start, the model is automatically downloaded and converted to OpenVINO INT8:

```
============================================
  Aimighty OpenVINO Embedder
============================================

[1/3] Checking model cache...
  Cache directory: /models_cache
  Model path:      /models_cache/aimighty-embedding-4b

  [!] Model not found in cache.

[2/3] Downloading and converting Qwen/Qwen3-Embedding-4B to OpenVINO INT8...
  This may take 10-30 minutes depending on network speed.
  Downloading model weights (~8 GB)...
  Converting to OpenVINO IR with INT8 quantization...

  [OK] Model conversion successful.
  Converted model saved to: /models_cache/aimighty-embedding-4b

[3/3] Starting Aimighty Embedder Server...
  Model:  /models_cache/aimighty-embedding-4b
  Port:   9997
  Device: GPU
============================================
```

The converted model is persisted in a Docker volume. Subsequent starts use the cache and start immediately.

## API Usage

### Create Embeddings

```bash
curl http://localhost:9997/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world", "model": "aimighty-embedding-4b"}'
```

### Batch Embeddings

```bash
curl http://localhost:9997/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": ["Text 1", "Text 2", "Text 3"]}'
```

### Available Models

```bash
curl http://localhost:9997/v1/models
```

### Health Check

```bash
curl http://localhost:9997/health
# {"status": "ready"} or {"status": "loading"}
```

## RAGFlow / GPUStack Integration

Configure provider in GPUStack:
- **URL:** `http://<host>:9997`
- **Model:** `aimighty-embedding-4b`
- **Type:** Embedder

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| MODEL_NAME | aimighty-embedding-4b | Model name for the API |
| HF_MODEL_ID | Qwen/Qwen3-Embedding-4B | HuggingFace model ID |
| HUGGING_FACE_HUB_TOKEN | - | HF token (for gated models) |
| PORT | 9997 | API port |
| OV_DEVICE | GPU | OpenVINO device (GPU or CPU) |
| PERFORMANCE_HINT | THROUGHPUT | OpenVINO performance hint |
| NUM_STREAMS | 2 | Parallel execution streams |
| INFERENCE_PRECISION_HINT | f16 | Inference precision (f16, f32, bf16) |
| GPU_ENABLE_LARGE_ALLOCATIONS | YES | Remove unified memory limit |
| MALLOC_ARENA_MAX | 1 | Limit glibc memory fragmentation |

## Architecture Notes

- **Arrow Lake-S iGPU** (8086:7d67) is fully supported by Intel Compute Runtime
- **NUM_STREAMS=2** utilizes parallel processing of Arc GPU efficiently
- **GPU_ENABLE_LARGE_ALLOCATIONS=YES** removes the 4.2 GB unified memory limit (important for 4B models)
- On iGPU failure, automatic fallback to CPU with LATENCY hint
- **IGC Driver Pinning**: Intel GPU drivers pinned to OpenCL 24.39.x in Dockerfile. Version 25.18.x causes a `longjmp causes uninitialized stack frame` crash when compiling 4B models on Arrow Lake iGPU.

## Docker Image

- **Registry**: `ghcr.io/bayerhazard/aimighty-embedder`
- **Tag**: `igpu-v4`
- **GPU Drivers**: Intel OpenCL 24.39.31294.21 (pinned)

## Monitoring

```bash
# Logs (shows download progress on first start)
docker compose logs -f embedder

# Resources
docker stats aimighty-embedder

# Health
curl http://localhost:9997/health
```

## Troubleshooting

**"Infer Request is busy"**: Fixed by asyncio.Lock(). If still occurring, restart container.

**iGPU not available**: Check `ls -la /dev/dri` and ensure groups 994 (render) and 44 (video) exist.

**OOM**: Memory limit in docker-compose.yml set to 24G. MALLOC_ARENA_MAX=1 reduces fragmentation.

**Model download failed**: `docker compose down -v` clears cache. Then `docker compose up -d --build` again.

**Health shows "loading"**: Model is still loading or converting. Check logs with `docker compose logs -f embedder`.

**GPU crash on model load**: Ensure Intel GPU drivers are 24.39.x (not 25.18.x). The Dockerfile pins the correct version.

**SR-IOV enabled on host**: Level Zero cannot enumerate Virtual Functions. Disable SR-IOV: `echo 0 > /sys/bus/pci/devices/0000:00:02.0/sriov_numvfs`

## Olares Deployment: Sidecar Timeout Fix

When deploying on Olares, the per-app Envoy sidecar (`olares-envoy-sidecar`) has two hardcoded timeouts that kill long-running embedding requests (e.g. RAGFlow processing 359 chunks):

| Timeout | Default | Required | Override |
|---------|---------|----------|----------|
| Route timeout (`route.timeout`) | 15s | 3600s | `apiTimeout` in OlaresManifest / ApplicationManager |
| Cluster idle timeout (`common_http_protocol_options.idle_timeout`) | 10s | 3600s | None — patched at runtime by systemd service |

### Fix 1: Route timeout via apiTimeout

Set `apiTimeout: 3600` in `OlaresManifest.yaml` (already done in this chart). For an already-installed app:

```bash
# Patch the ApplicationManager spec.config.ApiTimeout
python3 << 'EOF'
import json, subprocess
am_name = "embedder-dev-aimighty-embedder-dev"
ns = "embedder-dev-aimighty"
result = subprocess.run(["kubectl", "get", "applicationmanager", am_name, "-n", ns, "-o", "json"],
                        capture_output=True, text=True, check=True)
am = json.loads(result.stdout)
cfg = json.loads(am["spec"]["config"])
cfg["ApiTimeout"] = 3600
patch = json.dumps([{"op": "replace", "path": "/spec/config", "value": json.dumps(cfg)}])
subprocess.run(["kubectl", "patch", "applicationmanager", am_name, "-n", ns, "--type=json", "-p", patch], check=True)
EOF
```

### Fix 2: idle_timeout via systemd patcher

The cluster `idle_timeout` is hardcoded to 10s in `app-service` source code with no override. Install the periodic patcher as a systemd service:

```bash
# On the Olares host:
cd scripts/
bash install-sidecar-patcher.sh
```

This installs `olares-sidecar-patcher.service` which:
- Runs as user `olares` with that user's KUBECONFIG
- Watches the ConfigMaps `olares-sidecar-config-{ragflow,embedder-dev}` every 5s
- Patches `idle_timeout: 10s -> 3600s` whenever the `app-service` controller resets it
- Survives reboots (`WantedBy=multi-user.target`)

Monitor with:
```bash
sudo systemctl status olares-sidecar-patcher.service
sudo journalctl -u olares-sidecar-patcher.service -f
```

### Verification

After both fixes, restart the embedder + ragflow pods. From inside the ragflow pod:

```bash
python3 -c "
import urllib.request, json, ssl, time
chunks = ['chunk ' + str(i) for i in range(359)]
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
for i in range(0, len(chunks), 16):
    batch = chunks[i:i+16]
    data = json.dumps({'input': batch, 'model': 'aimighty-embedding-4b'}).encode()
    req = urllib.request.Request('https://<embedder-app-url>/v1/embeddings', data=data,
                                  headers={'Content-Type': 'application/json'})
    start = time.time()
    resp = urllib.request.urlopen(req, timeout=300, context=ctx)
    print(f'batch {i//16+1}: {time.time()-start:.1f}s')
"
```

Expected: 23 batches complete in ~75s, no `upstream request timeout` errors.