# EU AI Act Screener, for a Hugging Face Docker Space (CPU basic, port 7860).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DO_NOT_TRACK=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    ANONYMIZED_TELEMETRY=False \
    CHROMA_TELEMETRY=False \
    FASTEMBED_CACHE_PATH=/app/models \
    PORT=7860

# Hugging Face Spaces run the container as uid 1000.
RUN useradd --create-home --uid 1000 user \
    && mkdir -p /app/models \
    && chown user:user /app /app/models
WORKDIR /app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user . .

USER user

# Bake the embedding model into the image as the user that runs the app, so the files
# belong to it and the Space never downloads the model at start.
# The build fails when the retriever cannot use the dense index. The download leaves only
# empty log folders in the user's Hugging Face cache; they are removed.
RUN python -c "import sys, app.retrieval as rt; from fastembed import TextEmbedding; TextEmbedding(model_name=rt.EMBED_MODEL, cache_dir=rt.cache_dir()); ok = rt.get_retriever().ready(); print('retriever ready:', ok); sys.exit(0 if ok else 1)" \
    && rm -rf /home/user/.cache/huggingface

# From here on the app never calls the Hugging Face Hub.
ENV HF_HUB_OFFLINE=1

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
