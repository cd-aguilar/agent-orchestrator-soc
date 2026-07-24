"""
Tools the agents can invoke.
In production, replace enrich_ioc with real calls to VirusTotal, AbuseIPDB,
OTX AlienVault, or your own SIEM/Elastic via API.
"""

from langchain_core.tools import tool

# Mocked IOC reputation database. Swap in a real API in production.
_FAKE_INTEL_DB = {
    "192.168.56.101": "Internal IP. No reputation in public feeds (RFC1918 range).",
    "445": "SMB port. Frequently abused in lateral movement (T1021.002).",
    "185.220.101.5": "IP associated with a Tor exit node. Reputation: malicious (score 8/10).",
}


@tool
def enrich_ioc(indicator: str) -> str:
    """Looks up the reputation of an indicator of compromise (IP, hash, domain, port).
    Returns threat intelligence context for that indicator."""
    return _FAKE_INTEL_DB.get(
        indicator,
        f"No matches in feeds for '{indicator}'. Manual review recommended.",
    )


@tool
def get_host_criticality(hostname: str) -> str:
    """Returns the criticality level of a host based on the asset inventory."""
    critical_hosts = {"DC01", "SQL-PROD-01", "FILESERVER-HR"}
    if hostname.upper() in critical_hosts:
        return f"{hostname} is a CRITICAL asset (domain/production server)."
    return f"{hostname} is a standard endpoint (low/medium criticality)."
