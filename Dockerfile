FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ollama corre en un contenedor aparte (ver docker-compose.yml) y se
# consulta vía red interna en http://ollama:11434
ENV OLLAMA_HOST=http://ollama:11434

CMD ["python", "orchestrator.py"]
