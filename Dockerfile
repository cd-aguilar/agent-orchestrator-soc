FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ollama runs in a separate container (see docker-compose.yml) and is
# reached over the internal network at http://ollama:11434
ENV OLLAMA_HOST=http://ollama:11434

EXPOSE 8000

# Runs the FastAPI webhook (POST /triage, GET /health, GET /docs) by
# default, so the container is ready to receive alerts from n8n/a SIEM.
# For the original one-shot CLI demo instead, run:
#   docker compose exec app python orchestrator.py
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
