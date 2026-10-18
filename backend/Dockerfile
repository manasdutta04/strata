FROM python:3.12-slim
WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/models
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY data/ /app/data/
# Bake the local embedding model into the image so the container needs no network at runtime.
ARG PRELOAD_MODEL=1
RUN if [ "$PRELOAD_MODEL" = "1" ]; then python -c "from embeddings import embed; embed(['warm up'])"; fi
EXPOSE 8000
# Seed the synthetic company only when the graph is empty, so a restart keeps ingested decisions and approvals.
CMD ["sh", "-c", "python seed.py --if-empty && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
