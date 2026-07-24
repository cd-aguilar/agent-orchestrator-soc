# PROJECT.md — Contexto para IA

> Leer este archivo primero, completo, antes de explorar el repo o proponer cambios.
> Si existe `AI/GlobalContext.md` en el workspace del usuario, leerlo también.

## Objetivo
Sistema multi-agente (patrón supervisor-worker con LangGraph) para triage automático de
alertas de seguridad: enriquece IOCs, busca contexto en una base de conocimiento local
(RAG sobre notas MITRE/runbooks/HTB) y redacta un informe de triage con severidad y
acción recomendada. Pieza de portfolio para roles de AI Engineer / Detection Engineer /
Security Automation Engineer.

## Alcance
Incluye: grafo supervisor → enrichment (tool calling) → research (RAG) → report, 100%
local (Ollama + ChromaDB), con datos de ejemplo (`data/mitre_notes.md`) y threat intel
simulado (`tools.py`).
No incluye todavía: APIs reales de threat intel (VirusTotal/AbuseIPDB/OTX), trigger real
vía SIEM/n8n, humano-en-el-loop antes de acciones destructivas, evaluación con set de
regresión. Ver Roadmap.

## Arquitectura
Supervisor decide el siguiente paso según el estado acumulado; cada worker hace una sola
cosa (enrichment, research, report) y vuelve al supervisor. Diagrama completo en README.md.

## Decisiones clave
- **LangGraph sobre un loop manual**: estado tipado explícito, ramificación condicional,
  patrón usado en producción por equipos de AI Engineering.
- **Ollama (modelo local), no una API externa**: costo cero y las alertas de seguridad
  (dato sensible) nunca salen de la máquina — reutilizable en el stack del segundo cerebro.
- **ChromaDB embebido**: cero infraestructura para el RAG local.
- **Tool calling nativo, no parsing manual de prompts**: más confiable, mismo patrón que
  se usa con MCP.

## Restricciones
- El enrichment de IOCs es simulado (`_FAKE_INTEL_DB` en tools.py) — no reemplazar por
  una API real sin agregar manejo de rate limits y `.env` para la key.
- Sin humano-en-el-loop todavía: no conectar a acciones destructivas reales (aislar host,
  bloquear IP) sin agregar ese nodo de aprobación primero.

## Roadmap
- [ ] Reemplazar `data/mitre_notes.md` por notas reales (HTB, reglas Elastic, export del vault).
- [ ] Conectar `tools.py` a APIs reales (VirusTotal, AbuseIPDB) o a servidores MCP propios.
- [ ] Trigger real vía n8n (webhook desde SIEM/Elastic) + publicación del informe en Slack/Obsidian.
- [ ] Nodo de "espera de aprobación humana" antes de acciones destructivas.
- [ ] Set de regresión (alerta, informe) para medir calidad del triage ante cambios de prompt/modelo.

## Pendientes
Ver TODO.md

## Tecnologías
Python, LangGraph, LangChain (langchain-ollama, langchain-chroma), Ollama (llama3.1 +
nomic-embed-text), ChromaDB.

## Reglas del proyecto
- Nunca commitear `chroma_db/` (índice derivado, se reconstruye con `ingest_kb.py`).
- Cuando se conecten APIs reales de threat intel, la key va en `.env` (ver `.env.example`),
  nunca hardcodeada en `tools.py`.
- Todo cambio de arquitectura relevante se documenta acá, en "Decisiones clave".
- Commits: Conventional Commits (feat:, fix:, docs:, chore:).
