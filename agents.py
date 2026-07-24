"""
Define el estado compartido y los nodos (agentes) del grafo de orquestación.

Patrón: Supervisor-Worker.
Un agente "supervisor" no ejecuta trabajo directamente: decide qué agente
especializado debe actuar a continuación, en base al estado acumulado.
Cada worker hace UNA cosa bien y devuelve su resultado al estado compartido.
"""

import os
from pathlib import Path
from typing import Literal, TypedDict

from langchain_chroma import Chroma
from langchain_ollama import ChatOllama, OllamaEmbeddings

from tools import enrich_ioc, get_host_criticality

PERSIST_DIR = Path(__file__).parent / "chroma_db"

# En local usa http://localhost:11434. En docker-compose, la variable
# OLLAMA_HOST se sobreescribe a http://ollama:11434 (ver docker-compose.yml).
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Modelo local vía Ollama. Cambia "llama3.1" por el modelo que tengas descargado.
llm = ChatOllama(model="llama3.1", temperature=0, base_url=OLLAMA_HOST)


# --- Estado compartido entre agentes -----------------------------------------
class TriageState(TypedDict):
    alert_raw: str          # alerta cruda de entrada (log, EDR, SIEM)
    enrichment: str         # resultado del agente de enriquecimiento
    research: str           # resultado del agente de investigación (RAG)
    report: str             # informe final
    next_step: str          # decisión de enrutamiento del supervisor


# --- Agente Supervisor ---------------------------------------------------
def supervisor_node(state: TriageState) -> dict:
    """Decide el siguiente paso del pipeline. En este ejemplo el flujo es lineal
    y determinista (enrich -> research -> report), pero aquí es donde
    introducirías lógica condicional real (p. ej. saltar research si la
    alerta ya viene enriquecida, o pedir intervención humana si la
    confianza es baja)."""
    if not state.get("enrichment"):
        return {"next_step": "enrichment"}
    if not state.get("research"):
        return {"next_step": "research"}
    if not state.get("report"):
        return {"next_step": "report"}
    return {"next_step": "end"}


def route_after_supervisor(state: TriageState) -> Literal["enrichment", "research", "report", "end"]:
    return state["next_step"]  # type: ignore[return-value]


# --- Agente de Enriquecimiento (tool calling) --------------------------------
def enrichment_node(state: TriageState) -> dict:
    llm_with_tools = llm.bind_tools([enrich_ioc, get_host_criticality])
    prompt = (
        "Eres un analista SOC de nivel 1. Extrae los indicadores relevantes "
        "(IPs, puertos, hostnames) de la siguiente alerta y usa las "
        "herramientas disponibles para enriquecerlos.\n\n"
        f"Alerta:\n{state['alert_raw']}"
    )
    response = llm_with_tools.invoke(prompt)

    results = []
    for call in response.tool_calls:
        if call["name"] == "enrich_ioc":
            results.append(enrich_ioc.invoke(call["args"]))
        elif call["name"] == "get_host_criticality":
            results.append(get_host_criticality.invoke(call["args"]))

    return {"enrichment": "\n".join(results) if results else "Sin IOCs claros para enriquecer."}


# --- Agente de Investigación (RAG sobre tu base de conocimiento) -------------
def research_node(state: TriageState) -> dict:
    embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_HOST)
    vectorstore = Chroma(persist_directory=str(PERSIST_DIR), embedding_function=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    relevant_docs = retriever.invoke(state["alert_raw"])
    context = "\n---\n".join(d.page_content for d in relevant_docs)

    prompt = (
        "Eres un analista de detección. Con base en el siguiente contexto de "
        "tu base de conocimiento (runbooks, notas MITRE ATT&CK), identifica qué "
        "técnica(s) ATT&CK corresponden a la alerta y qué acción recomienda el playbook.\n\n"
        f"Contexto:\n{context}\n\n"
        f"Alerta:\n{state['alert_raw']}"
    )
    response = llm.invoke(prompt)
    return {"research": response.content}


# --- Agente de Reporte --------------------------------------------------
def report_node(state: TriageState) -> dict:
    prompt = (
        "Redacta un informe de triage de seguridad conciso y accionable, en español, "
        "con estas secciones: Resumen, Severidad (Low/Medium/High/Critical), "
        "Indicadores enriquecidos, Técnicas MITRE ATT&CK identificadas, y "
        "Acción recomendada.\n\n"
        f"Alerta original:\n{state['alert_raw']}\n\n"
        f"Enriquecimiento:\n{state['enrichment']}\n\n"
        f"Investigación:\n{state['research']}"
    )
    response = llm.invoke(prompt)
    return {"report": response.content}
