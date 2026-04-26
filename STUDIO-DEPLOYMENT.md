# Aimighty Embedder - Studio Deployment Guide

## Voraussetzungen

1. Olares 1.12.2 oder neuer
2. Docker Image `aimighty-embedder:latest` muss auf dem Olares-Host verfuegbar sein
3. Intel GPU Device Plugin muss installiert sein (gpu.intel.com/i915)

## Schritt 1: Docker Image auf den Olares-Host bringen

Da der Mac kein Docker hat, muss das Image auf dem Olares-Host gebaut werden. Kopiere die Dateien vom Mac auf den Olares-Host:

```bash
# Auf dem Mac:
scp -r "/Users/marc/Documents/Olares/RAG/Embedder und Reranker/Embedder" marc@<olares-ip>:~/aimighty-embedder/

# Auf dem Olares-Host:
cd ~/aimighty-embedder
docker build -t aimighty-embedder:latest .
```

## Schritt 2: Studio oeffnen

1. Olares Web-UI oeffnen
2. **Studio** aus dem App-Menue starten
3. **Create a new application** klicken

## Schritt 3: App erstellen

1. **App name**: `aimighty-embedder` eingeben
2. **Confirm** klicken
3. **Port your own container to Olares** auswaehlen

## Schritt 4: Image, Port und Instance Spec konfigurieren

| Feld | Wert |
|------|------|
| **Image** | `aimighty-embedder:latest` |
| **Port** | `9997` (nur Container-Port, Studio managed Host-Port automatisch) |
| **Instance Specifications - CPU** | `2` core |
| **Instance Specifications - Memory** | `4` Gi |

**GPU aktivieren:**
- Unter Instance Specifications die **GPU**-Option aktivieren
- GPU Vendor: **Intel** auswaehlen

## Schritt 5: Environment Variables hinzufuegen

Klicke **Add** und trage folgende Key-Value-Paare ein:

| Key | Value |
|-----|-------|
| `MODEL_NAME` | `aimighty-embedding-4b` |
| `HF_MODEL_ID` | `Qwen/Qwen3-Embedding-4B` |
| `PORT` | `9997` |
| `PERFORMANCE_HINT` | `THROUGHPUT` |
| `NUM_STREAMS` | `2` |
| `GPU_ENABLE_LARGE_ALLOCATIONS` | `YES` |
| `INFERENCE_PRECISION_HINT` | `f16` |
| `MALLOC_ARENA_MAX` | `1` |
| `OV_CACHE_DIR` | `/tmp/ov_cache` |
| `MODEL_CACHE_DIR` | `/models_cache` |
| `HUGGING_FACE_HUB_TOKEN` | *(leer, oder dein HF Token)* |

## Schritt 6: Storage Volume hinzufuegen

Das Modell-Cache-Volume muss persistent sein:

1. **Add** neben **Storage Volume** klicken
2. **Host path**: `/app/cache` auswaehlen, dann `/aimighty-embedder-models` eingeben
3. **Mount path**: `/models_cache` eingeben
4. **Submit** klicken

> Hinweis: `/app/cache` wird von Olares verwaltet. Der tatsaechliche Pfad auf dem Host ist `/Cache/<device-name>/studio/aimighty-embedder/aimighty-embedder-models`.

## Schritt 7: App erstellen und deployen

1. **Create** klicken
2. Studio generiert die Package-Files und deployed die App automatisch
3. Status in der unteren Leiste beobachten

## Schritt 8: Deployment ueberpruefen

Beim ersten Start wird das Modell heruntergeladen und konvertiert (~10-30 Min):

```bash
# Logs verfolgen:
docker compose logs -f aimighty-embedder
# oder im Studio: App -> Deployment Details -> Logs
```

Du solltest diese Ausgabe sehen:

```
============================================
  Aimighty OpenVINO Embedder
============================================

[1/3] Checking model cache...
  [!] Model not found in cache.

[2/3] Downloading and converting Qwen/Qwen3-Embedding-4B to OpenVINO INT8...
  This may take 10-30 minutes depending on network speed.

  [OK] Model conversion successful.

[3/3] Starting Aimighty Embedder Server...
```

## Schritt 9: API testen

Nach erfolgreichem Start:

```bash
# Health Check:
curl http://<olares-ip>:<auto-port>/health
# {"status": "ready"}

# Embedding testen:
curl http://<olares-ip>:<auto-port>/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "Hallo Welt", "model": "aimighty-embedding-4b"}'
```

> Den auto-port findest Du im Studio unter der App -> Entrance.

## Troubleshooting

| Problem | Loesung |
|---------|---------|
| **Pod startet nicht** | Pruefe Logs im Studio -> Deployment Details |
| **GPU nicht verfuegbar** | Intel GPU Device Plugin muss installiert sein |
| **OOMKilled** | Memory Limit im Studio auf 16 Gi erhoehen |
| **Health zeigt "loading"** | Modell wird noch heruntergeladen/konvertiert - warten |
| **"Infer Request is busy"** | Container im Studio neustarten |

## Alternative: Chart Deployment (fuer Produktion)

Fuer produktive Nutzung mit vollem Olares-Feature-Set (GPU-Passthrough, Security Context, Provider API):

```bash
# Chart-Verzeichnis auf Olares-Host kopieren
scp -r aimighty-embedder-chart/ marc@<olares-ip>:~/

# Auf Olares-Host:
cd ~/aimighty-embedder-chart
# Chart via Olares CLI oder Market hochladen
```

Das Chart (`aimighty-embedder-chart/`) enthaelt:
- `Chart.yaml` - Chart Metadaten
- `OlaresManifest.yaml` - Olares App Konfiguration mit GPU, Envs, Provider
- `values.yaml` - Default Werte mit GPU Resource Limits
- `templates/deployment.yaml` - Kubernetes Deployment mit /dev/dri Mount
- `templates/service.yaml` - ClusterIP Service
- `templates/provider.yaml` - Provider API fuer andere Apps
