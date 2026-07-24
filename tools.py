"""
Herramientas que los agentes pueden invocar.
En producción, reemplaza enrich_ioc por llamadas reales a VirusTotal, AbuseIPDB,
OTX AlienVault, o tu propio SIEM/Elastic vía API.
"""

from langchain_core.tools import tool

# Simulación de una base de reputación de IOCs. Sustitúyela por una API real.
_FAKE_INTEL_DB = {
    "192.168.56.101": "IP interna. Sin reputación en feeds públicos (rango RFC1918).",
    "445": "Puerto SMB. Frecuentemente abusado en movimiento lateral (T1021.002).",
    "185.220.101.5": "IP asociada a nodo de salida Tor. Reputación: maliciosa (score 8/10).",
}


@tool
def enrich_ioc(indicator: str) -> str:
    """Consulta la reputación de un indicador de compromiso (IP, hash, dominio, puerto).
    Devuelve contexto de threat intelligence sobre ese indicador."""
    return _FAKE_INTEL_DB.get(
        indicator,
        f"Sin coincidencias en feeds para '{indicator}'. Se recomienda revisión manual.",
    )


@tool
def get_host_criticality(hostname: str) -> str:
    """Devuelve el nivel de criticidad de un host según el inventario de activos."""
    critical_hosts = {"DC01", "SQL-PROD-01", "FILESERVER-HR"}
    if hostname.upper() in critical_hosts:
        return f"{hostname} es un activo CRÍTICO (servidor de dominio/producción)."
    return f"{hostname} es un endpoint estándar (criticidad baja/media)."
