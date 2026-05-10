FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git && \
    pip install --no-cache-dir \
        openvino>=2026.0.0 \
        "optimum-intel[openvino] @ git+https://github.com/huggingface/optimum-intel.git@main" \
        transformers==4.55.4 \
        fastapi uvicorn[standard] torch>=2.4.0 tokenizers>=0.21 sentencepiece && \
    apt-get remove -y git && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*




# Pre-convert Qwen3-Embedding-4B to OpenVINO INT8 during build
# This avoids ~14GB runtime memory spike from on-demand conversion
RUN optimum-cli export openvino \
    --model Qwen/Qwen3-Embedding-4B \
    --task feature-extraction \
    --weight-format int8 \
    /models_cache/aimighty-embedding-4b && \
    rm -rf /root/.cache/huggingface

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