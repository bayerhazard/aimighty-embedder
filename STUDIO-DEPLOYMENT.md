# Aimighty Embedder - Studio Deployment Guide

## Prerequisites

1. Olares 1.12.2 or newer
2. Docker image `ghcr.io/bayerhazard/almighty-embedder:igpu-v4` available on Olares host
3. Intel GPU Device Plugin installed (gpu.intel.com/i915)
4. SR-IOV disabled on host (`sriov_numvfs=0` on the iGPU PCI device)

## Step 1: Get Docker Image to Olares Host

The image must be built or imported on the Olares host:

```bash
# Option A: Build from source on Olares host
cd ~/aimighty-embedder
docker build -t ghcr.io/bayerhazard/almighty-embedder:igpu-v4 .

# Option B: Import into containerd (for K3s)
docker save ghcr.io/bayerhazard/almighty-embedder:igpu-v4 | \
  ctr -n k8s.io images import -
```

## Step 2: Open Studio

1. Open Olares Web UI
2. Launch **Studio** from the app menu
3. Click **Create a new application**

## Step 3: Create App

1. **App name**: `embedder-dev`
2. Click **Confirm**
3. Select **Port your own container to Olares**

## Step 4: Configure Image, Port, and Instance Spec

| Field | Value |
|-------|-------|
| **Image** | `ghcr.io/bayerhazard/almighty-embedder:igpu-v4` |
| **Port** | `9997` (container port only, Studio manages host port) |
| **Instance Specifications - CPU** | `2` core |
| **Instance Specifications - Memory** | `16` Gi |

**Enable GPU:**
- Under Instance Specifications, enable the **GPU** option
- GPU Vendor: **Intel**

## Step 5: Add Environment Variables

Click **Add** and enter these key-value pairs:

| Key | Value |
|-----|-------|
| `PUID` | `1000` |
| `PGID` | `1000` |
| `TZ` | `Etc/UTC` |
| `MODEL_NAME` | `aimighty-embedding-4b` |
| `HF_MODEL_ID` | `Qwen/Qwen3-Embedding-4B` |
| `PORT` | `9997` |
| `MODEL_CACHE_DIR` | `/models_cache` |
| `OV_CACHE_DIR` | `/tmp/ov_cache` |
| `OV_DEVICE` | `GPU` |
| `PERFORMANCE_HINT` | `THROUGHPUT` |
| `NUM_STREAMS` | `2` |
| `INFERENCE_PRECISION_HINT` | `f16` |
| `GPU_ENABLE_LARGE_ALLOCATIONS` | `YES` |
| `MALLOC_ARENA_MAX` | `1` |
| `HUGGING_FACE_HUB_TOKEN` | *(empty, or your HF token)* |

## Step 6: Add Storage Volume

The model cache volume must be persistent:

1. Click **Add** next to **Storage Volume**
2. **Host path**: Select `/app/cache`, then enter `/aimighty-embedder-models`
3. **Mount path**: Enter `/models_cache`
4. Click **Submit**

> Note: `/app/cache` is managed by Olares. The actual host path is `/Cache/<device-name>/studio/embedder-dev/embedder/aimighty-embedder-models`.

## Step 7: Create and Deploy

1. Click **Create**
2. Studio generates package files and deploys automatically
3. Monitor status in the bottom bar

## Step 8: Verify Deployment

On first start, the model is downloaded and converted (~10-30 min):

```bash
# Follow logs:
kubectl logs -n embedder-dev-aimighty -l app=embedder-dev -c embedder -f
```

You should see:

```
============================================
  Aimighty OpenVINO Embedder
============================================

[1/3] Checking model cache...
  [OK] OpenVINO model found in cache.
  Skipping download and conversion.

[3/3] Starting Aimighty Embedder Server...
  Device: GPU
```

## Step 9: Test API

After successful start:

```bash
# Health check:
curl http://<olares-ip>:<auto-port>/health
# {"status": "ready"}

# Test embedding:
curl http://<olares-ip>:<auto-port>/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world", "model": "aimighty-embedding-4b"}'
```

> Find the auto-port in Studio under the app -> Entrance.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Pod won't start** | Check logs in Studio -> Deployment Details |
| **GPU not available** | Intel GPU Device Plugin must be installed |
| **OOMKilled** | Increase memory limit in Studio to 24 Gi |
| **Health shows "loading"** | Model is still downloading/converting - wait |
| **"Infer Request is busy"** | Restart container in Studio |
| **GPU crash on model load** | Ensure IGC drivers are 24.39.x (not 25.18.x) |
| **SR-IOV enabled** | Disable: `echo 0 > /sys/bus/pci/devices/0000:00:02.0/sriov_numvfs` |
| **`upstream request timeout` from RAGFlow** | Two-part fix needed: set `apiTimeout: 3600` + install sidecar patcher (see below) |

## Sidecar Timeout Fix (CRITICAL for RAGFlow integration)

The Olares per-app Envoy sidecar has two timeouts that kill long embedding requests:

1. **Route timeout** (default 15s) - controls per-request HTTP timeout
2. **Cluster `idle_timeout`** (default 10s, **hardcoded** in `app-service`) - kills idle pooled connections during long inference

### Step 1: Set apiTimeout in OlaresManifest.yaml

Already configured in `aimighty-embedder-chart/OlaresManifest.yaml`:
```yaml
spec:
  apiTimeout: 3600
```

For an existing deployment, patch the ApplicationManager:
```bash
kubectl get applicationmanager <app-name> -n <namespace> -o json | \
  python3 -c "
import json, sys
am = json.load(sys.stdin)
cfg = json.loads(am['spec']['config'])
cfg['ApiTimeout'] = 3600
am['spec']['config'] = json.dumps(cfg)
print(json.dumps(am))
" | kubectl replace -f -
```

### Step 2: Install the sidecar patcher (systemd)

```bash
cd scripts/
bash install-sidecar-patcher.sh
```

This patches `idle_timeout: 10s -> 3600s` in `olares-sidecar-config-*` ConfigMaps every 5 seconds, since the `app-service` controller hardcodes 10s with no override available.

### Step 3: Restart pods

```bash
kubectl rollout restart deployment/<embedder-deployment> -n <embedder-namespace>
kubectl rollout restart deployment/ragflow -n <ragflow-namespace>
```

### Verify

Test from inside the ragflow pod with a 359-chunk batch:
```bash
# Should complete in ~75s without "upstream request timeout"
```

## Alternative: Chart Deployment (Production)

For production use with full Olares feature set (GPU passthrough, security context, provider API):

```bash
# Copy chart directory to Olares host
scp -r aimighty-embedder-chart/ user@<olares-ip>:~/

# On Olares host:
cd ~/aimighty-embedder-chart
# Upload chart via Olares CLI or Market
```

The chart (`aimighty-embedder-chart/`) contains:
- `Chart.yaml` - Chart metadata
- `OlaresManifest.yaml` - Olares app configuration with GPU, envs, provider
- `values.yaml` - Default values with GPU resource limits
- `templates/deployment.yaml` - Kubernetes deployment with /dev/dri mount
- `templates/service.yaml` - ClusterIP service
- `templates/provider.yaml` - Provider API for other apps