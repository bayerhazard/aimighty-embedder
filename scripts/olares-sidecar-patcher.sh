#!/bin/bash
# Olares Sidecar Envoy ConfigMap Patcher
#
# Patches applied every 5 seconds (Olares app-service controller resets on reconcile):
#   1. idle_timeout: 10s -> 3600s (prevents killing long-running embedding requests)
#   2. ext_authz removal from embedder sidecar (allows RAGFlow API access without Authelia)
#   3. NetworkPolicy: allows ragflow-aimighty -> embedder-dev-aimighty ingress
#
# The idle_timeout 10s default is hardcoded in:
#   framework/app-service/pkg/sandbox/sidecar/envoy.go (lines 246, 657)
# The ext_authz filter enforces Authelia browser-auth on ALL inbound requests,
#   which blocks service-to-service API calls (RAGFlow sends Bearer token, not cookies).
# The NetworkPolicy is enforced by the Olares DevBox controller and removes
#   custom ingress rules within ~2 seconds.
#
# Install via systemd: see scripts/olares-sidecar-patcher.service

set -e

NAMESPACES_AND_CONFIGMAPS=(
    "ragflow-aimighty:olares-sidecar-config-ragflow"
    "embedder-dev-aimighty:olares-sidecar-config-embedder-dev"
)

patch_idle_timeout() {
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
}

patch_embedder_auth() {
    local NS="embedder-dev-aimighty"
    local CM="olares-sidecar-config-embedder-dev"
    CURRENT=$(kubectl get configmap "$CM" -n "$NS" -o jsonpath='{.data.envoy\.yaml}' 2>/dev/null || echo "")
    if [ -z "$CURRENT" ]; then return; fi
    if ! echo "$CURRENT" | grep -q "ext_authz"; then return; fi

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Removing ext_authz from $NS/$CM"
    kubectl get configmap "$CM" -n "$NS" -o json | python3 -c '
import json, sys, yaml

cm = json.load(sys.stdin)
config = yaml.safe_load(cm["data"]["envoy.yaml"])

for listener in config.get("static_resources", {}).get("listeners", []):
    if listener.get("name") == "listener_0":
        for fc in listener.get("filter_chains", []):
            for filt in fc.get("filters", []):
                tc = filt.get("typed_config", {})
                if "http_filters" in tc:
                    tc["http_filters"] = [
                        hf for hf in tc["http_filters"]
                        if hf.get("name") != "envoy.filters.http.ext_authz"
                    ]
                if "route_config" in tc:
                    for vh in tc["route_config"].get("virtual_hosts", []):
                        vh.pop("typed_per_filter_config", None)

config["static_resources"]["clusters"] = [
    c for c in config["static_resources"]["clusters"]
    if c.get("name") != "authelia"
]

cm["data"]["envoy.yaml"] = yaml.dump(config, default_flow_style=False, allow_unicode=True)
for k in ["resourceVersion", "uid", "creationTimestamp", "generation", "managedFields"]:
    cm["metadata"].pop(k, None)
cm["metadata"].pop("annotations", None)
print(json.dumps(cm))
' | kubectl replace -f - >/dev/null 2>&1 || echo "  patch failed, will retry"
}

patch_network_policy() {
    local NS="embedder-dev-aimighty"
    local NP="app-np"
    CURRENT=$(kubectl get networkpolicy "$NP" -n "$NS" -o json 2>/dev/null || echo "")
    if [ -z "$CURRENT" ]; then return; fi
    if echo "$CURRENT" | grep -q "ragflow-aimighty"; then return; fi

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Adding ragflow-aimighty to NetworkPolicy $NS/$NP"
    kubectl -n "$NS" patch networkpolicy "$NP" --type=json \
        -p '[{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"ragflow-aimighty"}}}}]' \
        >/dev/null 2>&1 || true
}

while true; do
    patch_idle_timeout
    patch_embedder_auth
    patch_network_policy
    sleep 5
done
