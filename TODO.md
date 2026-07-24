# TODO

## Pendiente
- [ ] Reemplazar `data/mitre_notes.md` por base de conocimiento real
- [ ] Conectar `enrich_ioc` a una API real (VirusTotal/AbuseIPDB/OTX) o a MCP propio
- [ ] Trigger vía n8n (webhook SIEM/Elastic) + publicación del informe (Slack/Obsidian)
- [ ] Nodo de aprobación humana antes de acciones destructivas
- [ ] Set de regresión (alerta, informe) para evaluar cambios de prompt/modelo
- [ ] Inicializar git + subir a GitHub como pieza de portfolio (con GIF de la ejecución)

## En progreso
- [ ]

## Finalizado
- [x] Grafo supervisor-worker con LangGraph (enrichment, research, report)
- [x] RAG local sobre `data/*.md` con Ollama + ChromaDB
- [x] Threat intel simulado + criticidad de hosts (tools.py)
