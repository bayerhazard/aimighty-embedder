#!/bin/bash
set -e

echo "============================================"
echo "  Aimighty OpenVINO Embedder"
echo "============================================"
echo ""

echo "[0/4] Patching Envoy timeouts..."
/app/init-patcher.sh || true

# Patch envoy config files mounted from emptyDir (Olares sidecar reads these)
ENVOY_DIR="/etc/envoy-config"
if [ -d "$ENVOY_DIR" ]; then
    for f in "$ENVOY_DIR"/envoy.yaml "$ENVOY_DIR"/envoy2.yaml; do
        if [ -f "$f" ]; then
            if grep -q "timeout: 15s" "$f" 2>/dev/null; then
                sed -i 's/timeout: 15s/timeout: 120s/g' "$f"
                echo "  [OK] Patched $f: 15s → 120s"
            fi
        fi
    done
fi

CACHE_DIR="${MODEL_CACHE_DIR:-/models_cache}"
MODEL_SUBDIR="${MODEL_NAME:-aimighty-embedding-4b}"
MODEL_PATH="${CACHE_DIR}/${MODEL_SUBDIR}"
HF_MODEL_ID="${HF_MODEL_ID:-Qwen/Qwen3-Embedding-4B}"
OV_DEVICE="${OV_DEVICE:-CPU}"
export OV_DEVICE
export GPU_ENABLE_LARGE_ALLOCATIONS="${GPU_ENABLE_LARGE_ALLOCATIONS:-NO}"

echo "[1/4] Checking model cache..."
echo "  Cache directory: ${CACHE_DIR}"
echo "  Model path:      ${MODEL_PATH}"
echo ""

if [ -f "${MODEL_PATH}/openvino_model.xml" ]; then
    echo "  [OK] OpenVINO model found in cache."
    echo "  Skipping download and conversion."
else
    echo "  [!] Model not found in cache."
    echo ""
    echo "[2/4] Downloading and converting ${HF_MODEL_ID} to OpenVINO INT8..."
    echo "  This may take 10-30 minutes depending on network speed."
    echo "  Downloading model weights (~8 GB)..."
    echo "  Converting to OpenVINO IR with INT8 quantization..."
    echo ""

    mkdir -p "${MODEL_PATH}"

    optimum-cli export openvino \
        --model "${HF_MODEL_ID}" \
        --task feature-extraction \
        --weight-format int8 \
        "${MODEL_PATH}"

    echo ""
    if [ -f "${MODEL_PATH}/openvino_model.xml" ]; then
        echo "  [OK] Model conversion successful."
        echo "  Converted model saved to: ${MODEL_PATH}"
    else
        echo "  [ERROR] Model conversion failed. openvino_model.xml not found."
        exit 1
    fi
fi

echo ""
echo "[3/4] Starting Aimighty Embedder Server..."
echo "  Model:  ${MODEL_PATH}"
echo "  Port:   ${PORT:-9997}"
echo "  Device: ${OV_DEVICE}"
echo "============================================"
echo ""

export MODEL_DIR="${MODEL_PATH}"

exec python3 /app/server.py
