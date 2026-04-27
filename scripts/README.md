# Olares Sidecar Patcher Scripts

This directory contains scripts to fix the long-request timeout issue in Olares per-app Envoy sidecars.

## The Problem

Each Olares app gets an `olares-envoy-sidecar` injected into its pod. This sidecar enforces two timeouts that break long-running embedding requests (e.g., RAGFlow processing 359 chunks):

| Timeout | Default | Where | Override |
|---------|---------|-------|----------|
| Route timeout | 15s | `route_config.routes[].route.timeout` | `apiTimeout` in OlaresManifest |
| Cluster idle timeout | 10s | `cluster.common_http_protocol_options.idle_timeout` | None (hardcoded in app-service) |

When the embedder is processing a batch and the connection sits "idle" (no bytes flowing) for >10s, the sidecar Envoy resets the connection with `upstream request timeout`.

## The Fix

Two-part fix is required:

### Part 1: apiTimeout (route timeout)

Set `apiTimeout: 3600` in `OlaresManifest.yaml` -> route timeout becomes 3600s.

This is already configured in `aimighty-embedder-chart/OlaresManifest.yaml` for new installs. For existing installs, patch the ApplicationManager `spec.config.ApiTimeout` field directly.

### Part 2: idle_timeout (cluster timeout)

The cluster `idle_timeout` is hardcoded at `framework/app-service/pkg/sandbox/sidecar/envoy.go` lines 246 and 657 in the Olares source. There is no override mechanism, so we patch the rendered ConfigMap and re-patch every 5s when the controller resets it.

## Files

| File | Purpose |
|------|---------|
| `olares-sidecar-patcher.sh` | The actual loop: patches ConfigMaps every 5s |
| `olares-sidecar-patcher.service` | Systemd unit for persistent operation |
| `install-sidecar-patcher.sh` | Installer that copies files + enables service |

## Installation

```bash
# On the Olares host as user `olares`:
cd scripts/
bash install-sidecar-patcher.sh
```

The installer:
1. Copies `olares-sidecar-patcher.sh` to `/usr/local/bin/`
2. Installs `olares-sidecar-patcher.service` to `/etc/systemd/system/`
3. Runs `systemctl daemon-reload`, `enable`, `start`

## Monitoring

```bash
sudo systemctl status olares-sidecar-patcher.service
sudo journalctl -u olares-sidecar-patcher.service -f
```

Log entries appear only when the patcher actually had to apply a fix. Idle log = healthy state.

## Configuration

Edit `olares-sidecar-patcher.sh` to add more namespaces:

```bash
NAMESPACES_AND_CONFIGMAPS=(
    "ragflow-aimighty:olares-sidecar-config-ragflow"
    "embedder-dev-aimighty:olares-sidecar-config-embedder-dev"
    "your-app-aimighty:olares-sidecar-config-your-app"
)
```

Then `sudo systemctl restart olares-sidecar-patcher.service`.

## Uninstall

```bash
sudo systemctl stop olares-sidecar-patcher.service
sudo systemctl disable olares-sidecar-patcher.service
sudo rm /etc/systemd/system/olares-sidecar-patcher.service
sudo rm /usr/local/bin/olares-sidecar-patcher.sh
sudo systemctl daemon-reload
```
