#!/bin/bash
# Olares Sidecar Envoy ConfigMap Patcher
#
# Patches idle_timeout from 10s to 3600s every 5 seconds.
# The Olares app-service controller resets the cluster idle_timeout to 10s
# on every reconcile (hardcoded in app-service/pkg/sandbox/sidecar/envoy.go).
# This kills long-running embedding requests. No per-app override exists.
#
# Install via systemd: see scripts/olares-sidecar-patcher.service

set -e

NAMESPACES_AND_CONFIGMAPS=(
    "ragflow-aimighty:olares-sidecar-config-ragflow"
    "embedder-dev-aimighty:olares-sidecar-config-embedder-dev"
)

while true; do
    for ENTRY in "${NAMESPACES_AND_CONFIGMAPS[@]}"; do
        NS="${ENTRY%%:*}"
        CM="${ENTRY##*:}"

        CURRENT=$(kubectl get configmap "$CM" -n "$NS" -o jsonpath='{.data.envoy\.yaml}' 2>/dev/null || echo "")
        if [ -z "$CURRENT" ]; then continue; fi
        if echo "$CURRENT" | grep -q "idle_timeout: 3600s"; then continue; fi

        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Patching $NS/$CM (idle_timeout 10s -> 3600s)"
        kubectl get configmap "$CM" -n "$NS" -o json | python3 -c '
import json, sys
cm = json.load(sys.stdin)
for key in ["envoy.yaml", "envoy2.yaml"]:
    if key in cm["data"]:
        cm["data"][key] = cm["data"][key].replace("idle_timeout: 10s", "idle_timeout: 3600s")
for k in ["resourceVersion", "uid", "creationTimestamp", "generation", "managedFields"]:
    cm["metadata"].pop(k, None)
cm["metadata"].pop("annotations", None)
print(json.dumps(cm))
' | kubectl replace -f - >/dev/null 2>&1 || echo "  patch failed, will retry"
    done
    sleep 5
done
