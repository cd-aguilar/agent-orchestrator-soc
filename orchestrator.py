"""
Punto de entrada: arma el grafo (StateGraph) de LangGraph y ejecuta un caso
de prueba de triage de una alerta de seguridad.

Uso:
    python ingest_kb.py     # una sola vez, para construir el índice RAG
    python orchestrator.py  # ejecuta el pipeline multi-agente
"""

from dotenv import load_dotenv

load_dotenv()  # carga .env si existe (OLLAMA_HOST, futuras API keys, etc.)
# Debe ejecutarse ANTES de importar agents, que lee OLLAMA_HOST al cargar el módulo.

from langgraph.graph import END, StateGraph  # noqa: E402

from agents import (  # noqa: E402
    TriageState,
    enrichment_node,
    report_node,
    research_node,
    route_after_supervisor,
    supervisor_node,
)

SAMPLE_ALERT = """\
[EDR ALERT] Host: WKS-FINANCE-07
Proceso: powershell.exe -EncodedCommand JABzAD0ATgB...
Proceso padre: winword.exe
Conexión saliente detectada: 185.220.101.5:443
Tráfico adicional interno: WKS-FINANCE-07 -> DC01:445
"""


def build_graph():
    graph = StateGraph(TriageState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("enrichment", enrichment_node)
    graph.add_node("research", research_node)
    graph.add_node("report", report_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "enrichment": "enrichment",
            "research": "research",
            "report": "report",
            "end": END,
        },
    )
    # Cada worker vuelve al supervisor para que decida el siguiente paso
    graph.add_edge("enrichment", "supervisor")
    graph.add_edge("research", "supervisor")
    graph.add_edge("report", "supervisor")

    return graph.compile()


def main():
    app = build_graph()

    final_state = app.invoke(
        {
            "alert_raw": SAMPLE_ALERT,
            "enrichment": "",
            "research": "",
            "report": "",
            "next_step": "",
        }
    )

    print("\n" + "=" * 70)
    print("INFORME DE TRIAGE")
    print("=" * 70)
    print(final_state["report"])


if __name__ == "__main__":
    main()
