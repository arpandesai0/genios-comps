# API image: the Python comps service. Data is mounted at runtime (DATA_DIR), never baked in.
FROM python:3.11.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# Exact versions of every runtime dependency (regenerate with:
# uv pip compile pyproject.toml --python-version 3.11 -o requirements.lock --no-header)
COPY requirements.lock ./
RUN pip install -r requirements.lock
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-deps .
# The embedding model is required and the service runs offline: download it now, at build time.
# Any download failure fails the build. At runtime MODEL_OFFLINE=1 forbids downloads, so a missing
# model stops start-up instead of falling back to anything.
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL} MODEL_CACHE_DIR=/models
RUN python -m comps.retrieval.embedding
ENV MODEL_OFFLINE=1 HF_HUB_OFFLINE=1
ENV DATA_DIR=/data
EXPOSE 8000
CMD ["uvicorn", "comps.api:app", "--host", "0.0.0.0", "--port", "8000"]
