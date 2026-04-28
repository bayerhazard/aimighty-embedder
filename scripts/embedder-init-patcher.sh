#!/bin/bash
# Embedder Envoy Config Patcher
# Patches route timeouts: 15s → 120s for large document embedding
set -e

NAMESPACE="embedding-dev-aimighty"
CONFIGMAP="olares-sidecar-config-embedding-dev"
RETRY_INTERVAL=2

echo "[INIT] Starting Envoy timeout patcher..."

# Wait for sidecar to create the ConfigMap
sleep 15

MAX_RETRIES=90
retry=0
while [ $retry -lt $MAX_RETRIES ]; do
    # Check if ConfigMap exists
    if kubectl get configmap "$CONFIGMAP" -n "$NAMESPACE" &>/dev/null; then
        echo "[INIT] ConfigMap found, patching timeouts..."
        
        # Patch all timeout: 15s to timeout: 120s in envoy.yaml
        kubectl get configmap "$CONFIGMAP" -n "$NAMESPACE" -o json | python3 -c '
import json, sys
cm = json.load(sys.stdin)
if "envoy.yaml" in cm["data"]:
    original = cm["data"]["envoy.yaml"]
    patched = original.replace("timeout: 15s", "timeout: 120s")
    if patched != original:
        cm["data"]["envoy.yaml"] = patched
        # Remove managed fields that cause conflicts
        for k in ["resourceVersion", "uid", "creationTimestamp", "generation", "managedFields"]:
            cm["metadata"].pop(k, None)
        cm["metadata"].pop("annotations", None)
        print(json.dumps(cm))
    else:
        print("NO_CHANGE")
        sys.exit(0)
' | kubectl replace -f - &>/dev/null && echo "[INIT] ✓ Patched timeout 15s → 120s" || echo "[INIT] Patch failed, retrying..."
        
        break
    fi
    
    retry=$((retry + 1))
    echo "[INIT] Waiting for ConfigMap... ($retry/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

if [ $retry -eq $MAX_RETRIES ]; then
    echo "[INIT] WARNING: ConfigMap not found after $MAX_RETRIES attempts, continuing anyway..."
fi

echo "[INIT] Done. Passing control to main process..."

# Exit successfully - let the next process continue
exec "$@"