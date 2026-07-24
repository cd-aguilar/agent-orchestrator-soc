# SOC Agent Orchestrator

Sistema multi-agente para triage automático de alertas de seguridad, construido
con **LangGraph** (orquestación), **Ollama** (LLM local) y **ChromaDB** (RAG
sobre tu propia base de conocimiento: notas MITRE ATT&CK, runbooks, writeups
de HTB, reglas de Elastic, etc.).

Pensado como pieza de portafolio para roles de **AI Engineer / Detection
Engineer / Security Automation Engineer**, y como base reutilizable para tu
"segundo cerebro" (mismo stack: Ollama + ChromaDB + LangChain).

## Arquitectura

```
              ┌──────────────┐
     ┌───────▶│  Supervisor  │◀───────┐
     │        └──────┬───────┘        │
     │               │ decide         │
     │      siguiente paso            │
┌────┴─────┐   ┌─────┴──────┐   ┌─────┴─────┐
│Enrichment│   │  Research  │   │  Report   │
│  (tools) │   │   (RAG)    │   │  (LLM)    │
└──────────┘   └────────────┘   └───────────┘
```

Patrón **supervisor-worker**: el supervisor no hace trabajo, solo decide qué
agente actúa después según el estado acumulado. Cada worker hace una sola
cosa:

- **Enrichment** — usa *tool calling* para extraer IOCs de la alerta y
  consultarlos contra un feed de threat intel (simulado; reemplázalo por
  VirusTotal/AbuseIPDB/OTX/tu SIEM).
- **Research (RAG)** — busca en tu base de conocimiento local (ChromaDB) el
  contexto relevante (técnicas MITRE, playbooks) para esa alerta.
- **Report** — redacta el informe final de triage con severidad y acción
  recomendada.

Este patrón escala: puedes añadir más agentes (DFIR, consulta a Elastic,
generación de reglas de detección) sin tocar los existentes, solo conectando
nuevos nodos al grafo.

## Por qué este stack

| Decisión | Razón |
|---|---|
| LangGraph en vez de un loop manual | Estado tipado explícito, ramificación condicional, fácil de depurar y extender — es lo que usan en producción los equipos de AI Engineering, buena señal en portafolio |
| Ollama (modelo local) | Costo cero, datos sensibles (alertas de seguridad) nunca salen de tu máquina, reutilizable en tu segundo cerebro |
| ChromaDB | Ligero, embebido, cero infraestructura — ideal para RAG local |
| Tool calling nativo en vez de prompts con parsing manual | Más confiable, es el patrón que usarás en cualquier stack de agentes en producción (también aplica a MCP) |

## Cómo correrlo

### Opción A: local (Python + venv)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # incluye ruff y pytest
cp .env.example .env                  # completa claves si vas a usar APIs reales

ollama pull llama3.1
ollama pull nomic-embed-text

python ingest_kb.py       # construye el índice RAG desde data/*.md
python orchestrator.py    # ejecuta el triage sobre la alerta de ejemplo
```

### Opción B: Docker

```bash
docker compose up --build
# en otra terminal, la primera vez, descarga los modelos dentro del contenedor:
docker exec -it soc-orchestrator-ollama ollama pull llama3.1
docker exec -it soc-orchestrator-ollama ollama pull nomic-embed-text
docker compose restart app
```

### Tests

```bash
PYTHONPATH=. pytest tests/ -v   # no requiere Ollama corriendo
ruff check .                    # lint
```

## Seguridad: API keys y secretos

Este proyecto corre 100% local (Ollama), así que no necesita ninguna key por
defecto. Si lo extiendes con APIs reales (VirusTotal, OpenAI, un LLM cloud),
sigue esta regla: **las claves nunca van en el código ni se commitean**.

- Guárdalas en un archivo `.env` local (ya está en `.gitignore`, revisa que
  no aparezca en `git status` antes de cada commit).
- Usa `.env.example` como plantilla pública (sin valores reales) para que
  cualquiera que clone el repo sepa qué variables necesita.
- Carga las variables con `python-dotenv` (`load_dotenv()`), como ya hace
  `orchestrator.py`, y accede a ellas con `os.environ.get(...)`.
- Antes de tu primer `git push`, corre un scanner de secretos
  (`gitleaks detect` o `trufflehog filesystem .`) para asegurarte de que no
  quedó ninguna key en el historial.
- Si en el futuro conectas esto a un pipeline o a producción, sube las claves
  a GitHub Actions como *Repository Secrets* (Settings → Secrets and
  variables → Actions) en vez de un `.env` — nunca las metas directamente en
  el YAML del workflow.

## Cómo extenderlo (roadmap sugerido)

1. **Datos reales**: reemplaza `data/mitre_notes.md` por tus notas de HTB,
   reglas de detección de Elastic, o exporta páginas de tu vault de Obsidian.
2. **Herramientas reales**: conecta `tools.py` a APIs reales (VirusTotal,
   AbuseIPDB) o, mejor, a tus propios servidores MCP.
3. **Trigger real**: usa n8n para que una alerta de tu SIEM/Elastic dispare
   este pipeline automáticamente vía webhook, y publique el informe en Slack
   o Obsidian.
4. **Humano en el loop**: añade un nodo de "espera de aprobación" antes de
   cualquier acción destructiva (aislar host, bloquear IP) — patrón estándar
   en agentes de seguridad en producción.
5. **Evaluación**: registra pares (alerta, informe) y arma un set de
   regresión para medir si cambios al prompt/modelo mejoran o empeoran la
   calidad del triage.

## Valor para tu portafolio

- Demuestra orquestación multi-agente (no solo "un prompt con RAG"), que es
  lo que distingue a un AI Engineer de alguien que solo llama a una API.
- Conecta directamente con tus objetivos de Blue Team / Detection
  Engineering: es una herramienta que un SOC real usaría.
- Es 100% reproducible sin costo (modelo local), así que cualquier
  reclutador puede clonarlo y correrlo.
- Publícalo en GitHub con un GIF de la ejecución y una entrada corta en tu
  blog técnico (aigis-cloud.com) explicando el patrón supervisor-worker.
