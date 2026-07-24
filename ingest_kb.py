"""
Construye el índice vectorial (RAG) local a partir de data/*.md usando embeddings
de Ollama y ChromaDB. Corre esto UNA vez (o cada vez que actualices tu base de
conocimiento) antes de lanzar el orquestador.

Requisitos previos:
    ollama pull nomic-embed-text
    ollama pull llama3.1        # o el modelo que prefieras para los agentes

Uso:
    python ingest_kb.py
"""

import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import MarkdownTextSplitter

DATA_DIR = Path(__file__).parent / "data"
PERSIST_DIR = Path(__file__).parent / "chroma_db"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def main():
    docs_text = []
    for md_file in DATA_DIR.glob("*.md"):
        docs_text.append(md_file.read_text(encoding="utf-8"))

    if not docs_text:
        raise SystemExit(f"No se encontraron archivos .md en {DATA_DIR}")

    splitter = MarkdownTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.create_documents(docs_text)

    embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_HOST)

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(PERSIST_DIR),
    )
    print(f"Índice creado con {len(chunks)} fragmentos en {PERSIST_DIR}")


if __name__ == "__main__":
    main()
