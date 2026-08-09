"""
Tools the agents can invoke.
enrich_ioc queries VirusTotal, AbuseIPDB, and OTX AlienVault when API
keys are configured (VIRUSTOTAL_API_KEY / ABUSEIPDB_API_KEY /
OTX_API_KEY in .env), falling back to the mocked reputation table
(_FAKE_INTEL_DB) when no key is set or when the real APIs return
nothing useful.
"""

import ipaddress
import os
import re
import time

import requests
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY")
ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY")
OTX_API_KEY = os.getenv("OTX_API_KEY")

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2

_HASH_RE = re.compile(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$")

# Mocked IOC reputation database. Used when no real API key is configured,
# or as a last resort when the real APIs have no data for the indicator.
_FAKE_INTEL_DB = {
    "192.168.56.101": "Internal IP. No reputation in public feeds (RFC1918 range).",
    "445": "SMB port. Frequently abused in lateral movement (T1021.002).",
    "185.220.101.5": "IP associated with a Tor exit node. Reputation: malicious (score 8/10).",
}


def _is_ip(indicator: str) -> bool:
    try:
        ipaddress.ip_address(indicator)
        return True
    except ValueError:
        return False


def _is_hash(indicator: str) -> bool:
    return bool(_HASH_RE.match(indicator))


def _request_with_backoff(method: str, url: str, **kwargs) -> requests.Response | None:
    """Issues an HTTP request, retrying on rate-limit (429) and 5xx with exponential backoff."""
    response = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.request(method, url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
        except requests.RequestException:
            if attempt == MAX_RETRIES:
                return None
            time.sleep(BACKOFF_BASE_SECONDS**attempt)
            continue

        if response.status_code == 429 or response.status_code >= 500:
            if attempt == MAX_RETRIES:
                return response
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else BACKOFF_BASE_SECONDS**attempt
            time.sleep(delay)
            continue

        return response
    return response


def _query_virustotal(indicator: str) -> str | None:
    if not VIRUSTOTAL_API_KEY:
        return None

    if _is_ip(indicator):
        endpoint = f"https://www.virustotal.com/api/v3/ip_addresses/{indicator}"
    elif _is_hash(indicator):
        endpoint = f"https://www.virustotal.com/api/v3/files/{indicator}"
    else:
        endpoint = f"https://www.virustotal.com/api/v3/domains/{indicator}"

    response = _request_with_backoff(
        "GET", endpoint, headers={"x-apikey": VIRUSTOTAL_API_KEY}
    )
    if response is None or response.status_code != 200:
        return None

    stats = response.json()["data"]["attributes"]["last_analysis_stats"]
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    total = sum(stats.values())
    return f"VirusTotal: {malicious} malicious / {suspicious} suspicious out of {total} engines."


def _query_abuseipdb(indicator: str) -> str | None:
    if not ABUSEIPDB_API_KEY or not _is_ip(indicator):
        return None

    response = _request_with_backoff(
        "GET",
        "https://api.abuseipdb.com/api/v2/check",
        headers={"Key": ABUSEIPDB_API_KEY, "Accept": "application/json"},
        params={"ipAddress": indicator, "maxAgeInDays": 90},
    )
    if response is None or response.status_code != 200:
        return None

    data = response.json()["data"]
    return (
        f"AbuseIPDB: {data['abuseConfidenceScore']}% abuse confidence "
        f"({data['totalReports']} reports)."
    )


def _query_otx(indicator: str) -> str | None:
    if not OTX_API_KEY:
        return None

    if _is_ip(indicator):
        section = "IPv4"
    elif _is_hash(indicator):
        section = "file"
    else:
        section = "domain"

    response = _request_with_backoff(
        "GET",
        f"https://otx.alienvault.com/api/v1/indicators/{section}/{indicator}/general",
        headers={"X-OTX-API-KEY": OTX_API_KEY},
    )
    if response is None or response.status_code != 200:
        return None

    pulse_count = response.json().get("pulse_info", {}).get("count", 0)
    return f"OTX AlienVault: seen in {pulse_count} threat intel pulse(s)."


def _split_host_port(indicator: str) -> tuple[str, str] | None:
    """Splits 'host:port' or 'ip:port' into its two parts. Models sometimes
    pass IP:port as a single indicator instead of two separate tool calls;
    _FAKE_INTEL_DB and the real APIs key IPs and ports separately, so an
    unsplit 'ip:port' string silently misses a match on either."""
    host, sep, port = indicator.rpartition(":")
    if sep and host and port.isdigit():
        return host, port
    return None


def _enrich_one(indicator: str) -> str:
    split = _split_host_port(indicator)
    if split:
        host, port = split
        return f"{_enrich_one(host)} | {_enrich_one(port)}"

    if VIRUSTOTAL_API_KEY or ABUSEIPDB_API_KEY or OTX_API_KEY:
        results = [
            r
            for r in (
                _query_virustotal(indicator),
                _query_abuseipdb(indicator),
                _query_otx(indicator),
            )
            if r
        ]
        if results:
            return " | ".join(results)

    return _FAKE_INTEL_DB.get(
        indicator,
        f"No matches in feeds for '{indicator}'. Manual review recommended.",
    )


@tool
def enrich_ioc(indicator: str | list[str | int]) -> str:
    """Looks up the reputation of an indicator of compromise (IP, hash, domain, port).
    Returns threat intelligence context for that indicator. Accepts either a
    single indicator or a list of indicators (some models batch several IOCs
    into one call instead of calling the tool once per IOC, sometimes mixing
    a numeric port in with string IPs/hostnames in the same list)."""
    if isinstance(indicator, str):
        return _enrich_one(indicator)
    return "\n".join(f"{ioc}: {_enrich_one(str(ioc))}" for ioc in indicator)


@tool
def get_host_criticality(hostname: str) -> str:
    """Returns the criticality level of a host based on the asset inventory."""
    critical_hosts = {"DC01", "SQL-PROD-01", "FILESERVER-HR"}
    if hostname.upper() in critical_hosts:
        return f"{hostname} is a CRITICAL asset (domain/production server)."
    return f"{hostname} is a standard endpoint (low/medium criticality)."
