# Aimighty Embedder — GPU-Integration: Dokumentation

> **Stand:** 2. Mai 2026  
> **Version:** 0.1.9 / Image `igpu-v12`  
> **Status:** CPU-Mode produktiv, GPU-Mode inkompatibel

---

## 1. Zielsetzung

Deployment eines OpenAI-kompatiblen Embedding-API-Servers (Qwen3-Embedding-4B, INT8-quantisiert via OpenVINO) auf einem Olares-Cluster mit **Intel Arrow Lake iGPU**-Beschleunigung.

### Hardware
- **Control-Plane:** Intel Core Ultra 9 275HX (Arrow Lake-S, PCI 0x7d67) + NVIDIA RTX 5090
- **Worker:** Intel Core Ultra 9 275HX (Arrow Lake-S, PCI 0x7d67) + NVIDIA RTX 5090
- **RAM:** je 96 GB pro Node

### Software-Stack
- **Olares:** v1.12.5 (K3s v1.33.3)
- **Kernel:** 6.14.0-35-generic mit Community SR-IOV i915 Treiber (2025.12.10)
- **OpenVINO:** 2026.1.0
- **Optimum Intel:** 2.1.0.dev0 (git main)
- **Transformers:** 4.55.4

---

## 2. Chronologie der GPU-Probleme

### Phase 1: OPA-Blockade
**Problem:** `privileged: true` wird von OPA-ValidatingWebhook blockiert.  
**Ursache:** Namespace fehlt das Label `bytetrade.io/ns-type=user-space`.  
**Lösung:** `kubectl label ns embedding-dev-aimighty bytetrade.io/ns-type=user-space`  
**Note:** Olares Studio setzt dieses Label **nicht** automatisch.

### Phase 2: OpenCL fehlt
**Problem:** `libOpenCL.so.1: cannot open shared object file`  
**Ursache:** `intel-opencl-icd` und `ocl-icd-libopencl1` waren nicht im Docker-Image.  
**Lösung:** Pakete im Dockerfile hinzugefügt. `intel-level-zero-gpu` entfernt (libigc1/libigc2-Konflikt).

### Phase 3: OpenCL 25.18 Crash
**Problem:** `free(): invalid next size (fast)` bei GPU-Modell-Kompilierung.  
**Lösung:** Pin auf `intel-opencl-icd=24.52.32224.14`.

### Phase 4: OpenCL 24.52 Crash
**Problem:** `longjmp causes uninitialized stack frame` bei GPU-Inferenz.  
**Ursache:** Community SR-IOV i915-Treiber (2025.12.10) nicht kompatibel mit Intel Compute Runtime.

### Phase 5: force_probe
**Problem:** `i915.force_probe=7d67` fehlte in Kernel-Boot-Parametern.  
**Lösung:** In GRUB-Config beider Nodes hinzugefügt + Reboot.  
**Ergebnis:** GPU wird jetzt korrekt erkannt, aber Compute crasht weiterhin.

### Phase 6: Intel Compute Runtime 26.14
**Problem:** Neueste Runtime braucht `libigdgmm12 >= 22.9` — nicht im Container verfügbar.  

---

## 3. Root Cause

```
Arrow Lake GPU Compute Stack:
  Userspace:  intel-opencl-icd (24.52/25.18/26.14)
  Kernel:     i915 SR-IOV (2025.12.10, Community-DKMS)
  Firmware:   Meteor Lake GuC/HuC (Arrow Lake nicht nativ)
  Hardware:   Arrow Lake-S GPU → CRASH
```

Community SR-IOV i915 ≠ offizieller Intel-Treiber. Arrow Lake läuft auf Meteor-Lake-Firmware-Fallback. Intel Compute Runtime erwartet Standard-Treiber.

---

## 4. Status

| Feature | Status |
|---------|--------|
| CPU-Mode | ✅ 176ms/req, 5.7 req/s, stabil |
| Cluster-Mode | ✅ 2 Pods via podAntiAffinity |
| GPU-Erkennung | ✅ `['CPU', 'GPU']` seit force_probe |
| GPU-Inferenz | ❌ Crash (Treiber-Inkompatibilität) |
| Modell Pre-Conversion | ✅ INT8 im Image, kein Runtime-Memory-Spike |

---

## 5. Nächste Optionen

| Option | Aufwand | Erfolgschance |
|--------|---------|---------------|
| **NVIDIA RTX 5090 CUDA** | Mittel | Hoch |
| **Kernel-Update auf standard xe** | Hoch (Host-Änderung) | Hoch |
| **CPU-Mode behalten** | Keiner | ✅ Bereits stabil |

---

## 6. Konfiguration

### Kernel-Parameter (GRUB, beide Nodes)
```
i915.force_probe=7d67 i915.enable_guc=3 i915.max_vfs=3
```

### OPA-Label (nach jedem Deploy!)
```bash
kubectl label ns embedding-dev-aimighty bytetrade.io/ns-type=user-space --overwrite
```

### Aktuelles Chart
```
embedding-0.1.9.tgz / ghcr.io/bayerhazard/aimighty-embedder:igpu-v12
```

---

## 7. Performance

| Metrik | CPU | GPU (theoretisch) |
|--------|-----|-------------------|
| Latenz | 176ms | ~50-80ms |
| Durchsatz/Pod | 5.7 req/s | ~15 req/s |
| Cluster (2 Pods) | ~11 req/s | ~30 req/s |

---

## 8. Cheatsheet

```bash
ssh -i ~/.ssh/id_ed25519_olares olares@172.20.0.4
kubectl -n embedding-dev-aimighty get pods -o wide
kubectl -n embedding-dev-aimighty logs deployment/embedding-dev -c embedder --tail=20
kubectl label ns embedding-dev-aimighty bytetrade.io/ns-type=user-space --overwrite
kubectl -n embedding-dev-aimighty set env deployment/embedding-dev OV_DEVICE=CPU
```
