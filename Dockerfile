FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg2 ca-certificates git && \
    wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
    gpg --dearmor --output /usr/share/keyrings/intel-graphics-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-archive-keyring.gpg] https://repositories.intel.com/gpu/ubuntu noble unified" > \
    /etc/apt/sources.list.d/intel-gpu-noble.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    intel-opencl-icd \
    libze-intel-gpu1 \
    libze1 && \
    rm -rf /var/lib/apt/lists/*

# OpenVINO 2026.0.0+ with Optimum Intel 2.1.0.dev0 (installed from git main branch)
RUN pip install --no-cache-dir \
    openvino>=2026.0.0 \
    "optimum-intel[openvino] @ git+https://github.com/huggingface/optimum-intel.git@main" \
    transformers==4.57.6 \
    fastapi uvicorn[standard] torch>=2.4.0 tokenizers>=0.21 sentencepiece

COPY embedder-server.py /app/server.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
RUN mkdir -p /models_cache
WORKDIR /app

ENV MALLOC_ARENA_MAX=1
ENV OV_CACHE_DIR=/tmp/ov_cache
ENV MODEL_CACHE_DIR=/models_cache

EXPOSE 9997

ENTRYPOINT ["/app/entrypoint.sh"]