# Aimighty OpenVINO Embedder - Docker

OpenAI-kompatibler Embedding-Service mit OpenVINO-Optimierung fuer Intel Core Ultra 275HX (Meteor Lake iGPU).

## Features

- OpenAI-kompatible API (`/v1/embeddings`, `/v1/models`)
- Automatischer Download und OpenVINO-Konvertierung beim ersten Start
- OpenVINO INT8 quantisiertes Qwen3-Embedding-4B Modell
- iGPU-Optimierung: THROUGHPUT-Hint, 2 Streams, FP16, Large Allocations
- Async Endpoints mit Lock gegen Race Conditions
- Automatische CPU-Fallback bei iGPU-Fehlern
- malloc_trim fuer Speicheroptimierung
- Persistentes Model-Cache via Docker Volume

## Voraussetzungen

- Docker + Docker Compose
- Intel Core Ultra 275HX (oder andere Intel GPU mit OpenCL-Support)
- Mindestens 16 GB RAM
- Internetverbindung fuer ersten Modell-Download (~8 GB)

## Schnellstart

```bash
# .env anpassen
cp .env.example .env

# Bauen und starten
docker compose up -d --build

# Logs verfolgen (zeigt Download- und Konvertierungsfortschritt)
docker compose logs -f embedder
```

### Erster Start

Beim ersten Start wird das Modell automatisch heruntergeladen und nach OpenVINO INT8 konvertiert:

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
  Device: iGPU (fallback: CPU)
============================================
```

Das konvertierte Modell wird in einem Docker Volume persistent gespeichert. Nachfolgende Starts verwenden den Cache und starten sofort.

## API Nutzung

### Embeddings erstellen

```bash
curl http://localhost:9997/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "Hallo Welt", "model": "aimighty-embedding-4b"}'
```

### Batch-Embeddings

```bash
curl http://localhost:9997/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": ["Text 1", "Text 2", "Text 3"]}'
```

### Verfuegbare Modelle

```bash
curl http://localhost:9997/v1/models
```

### Health Check

```bash
curl http://localhost:9997/health
# {"status": "ready"} oder {"status": "loading"}
```

## RAGFlow / GPUStack Integration

Provider in GPUStack konfigurieren:
- **URL:** `http://<host>:9997`
- **Model:** `aimighty-embedding-4b`
- **Typ:** Embedder

## Konfiguration (.env)

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| MODEL_NAME | aimighty-embedding-4b | Modellname fuer die API |
| HF_MODEL_ID | Qwen/Qwen3-Embedding-4b | HuggingFace Modell-ID |
| HUGGING_FACE_HUB_TOKEN | - | HF Token (fuer gated models) |
| PORT | 9997 | API Port |
| PERFORMANCE_HINT | THROUGHPUT | OpenVINO Performance-Hint |
| NUM_STREAMS | 2 | Parallele Execution-Streams |
| GPU_ENABLE_LARGE_ALLOCATIONS | YES | Unified Memory Limit entfernen |
| INFERENCE_PRECISION_HINT | f16 | FP16 fuer iGPU |
| MALLOC_ARENA_MAX | 1 | glibc Speicherfragmentierung begrenzen |

## Architektur-Hinweise

- **Meteor Lake iGPU** hat keine XMX-Einheiten -- die XMX-Optimierungen aus OpenVINO 2025.4 greifen hier nicht
- **NUM_STREAMS=2** nutzt die parallele Verarbeitung der Arc-GPU effizient
- **GPU_ENABLE_LARGE_ALLOCATIONS=YES** entfernt das 4.2 GB Limit fuer Unified Memory (wichtig bei 88 GB RAM)
- Bei iGPU-Ausfall erfolgt automatischer Fallback auf CPU mit LATENCY-Hint

## Monitoring

```bash
# Logs (zeigt Download-Fortschritt beim ersten Start)
docker compose logs -f embedder

# Ressourcen
docker stats aimighty-embedder

# Health
curl http://localhost:9997/health
```

## Troubleshooting

**"Infer Request is busy"**: Durch asyncio.Lock() behoben. Falls dennoch auftretend, Container neustarten.

**iGPU nicht verfuegbar**: Pruefe `ls -la /dev/dri` und dass die Gruppen 994 (render) und 44 (video) existieren.

**OOM**: Memory-Limit in docker-compose.yml auf 16G gesetzt. MALLOC_ARENA_MAX=1 reduziert Fragmentierung.

**Modell-Download fehlerhaft**: `docker compose down -v` loescht den Cache. Danach erneut `docker compose up -d --build`.

**Health zeigt "loading"**: Modell wird noch geladen oder konvertiert. Logs pruefen mit `docker compose logs -f embedder`.
