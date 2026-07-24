"""
Builds the local vector index (RAG) from data/*.md using Ollama embeddings
and ChromaDB. Run this ONCE (or whenever you update your knowledge base)
before launching the orchestrator.

Prerequisites:
    ollama pull nomic-embed-text
    ollama pull llama3.1        # or whichever model you prefer for the agents

Usage:
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
        raise SystemExit(f"No .md files found in {DATA_DIR}")

    splitter = MarkdownTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.create_documents(docs_text)

    embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_HOST)

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(PERSIST_DIR),
    )
    print(f"Index built with {len(chunks)} chunks at {PERSIST_DIR}")


if __name__ == "__main__":
    main()
