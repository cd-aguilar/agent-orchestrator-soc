FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ollama runs in a separate container (see docker-compose.yml) and is
# reached over the internal network at http://ollama:11434
ENV OLLAMA_HOST=http://ollama:11434

CMD ["python", "orchestrator.py"]
