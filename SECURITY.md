# Seguridad

## Contexto
Este proyecto procesa alertas de seguridad y IOCs. Hoy corre 100% local (Ollama +
ChromaDB simulado), pero el roadmap prevé conectar APIs reales de threat intel y,
eventualmente, acciones sobre hosts reales (aislar, bloquear IP).

## Buenas prácticas a mantener
- Ninguna key de threat intel real hardcodeada — usar `.env` (ver `.env.example`) apenas
  se reemplace `_FAKE_INTEL_DB` por una API real.
- No conectar ningún nodo que ejecute acciones destructivas (aislamiento de host, bloqueo
  de IP, etc.) sin un nodo de aprobación humana antes — este es un requisito de diseño,
  no solo una buena práctica, para un agente que opera sobre infraestructura de seguridad real.
- Si en algún momento se ingiere contenido real de HTB en `data/`, aplicar la misma regla
  que en `_rag_project`: nunca subir ese contenido a un repo público.

## Reportar un problema
Abrir un issue privado o contactar a cdario.a@gmail.com.
