# Instrucciones para Claude Code

Antes de cualquier tarea:
1. Leer PROJECT.md completo.
2. Leer TODO.md.
3. Si existe `../AI/GlobalContext.md`, leerlo. No lo dupliques acá.

## Cómo correr esto
No hay Makefile. Todo se ejecuta con:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.1
ollama pull nomic-embed-text
python ingest_kb.py       # construye el índice RAG (una vez, o al actualizar data/)
python orchestrator.py    # ejecuta el triage
```

## Reglas de este proyecto
- Nunca commitear `chroma_db/` ni un futuro `.env` con keys reales.
- Si se conecta una API de threat intel real, agregar manejo de errores/rate-limit y
  documentar la decisión en PROJECT.md.
- No agregar un nodo que ejecute acciones destructivas (aislar host, bloquear IP) sin
  el nodo de aprobación humana primero — ver Roadmap en PROJECT.md.
- Al terminar una tarea: actualizar TODO.md y CHANGELOG.md.

## Convenciones
- Commits: Conventional Commits (feat:, fix:, docs:, chore:).
- Idioma de código/comentarios: español (así está el repo). Documentación: español.
