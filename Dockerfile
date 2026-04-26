FROM python:3.11-slim

RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] optimum-intel[openvino] \
    transformers>=4.45.0 torch>=2.4.0 tokenizers>=0.21 sentencepiece

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
