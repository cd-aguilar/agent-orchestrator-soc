"""Unit tests for the agent tools (don't require Ollama)."""

from tools import enrich_ioc, get_host_criticality


def test_enrich_ioc_known_indicator():
    result = enrich_ioc.invoke({"indicator": "185.220.101.5"})
    assert "malicious" in result.lower()


def test_enrich_ioc_unknown_indicator():
    result = enrich_ioc.invoke({"indicator": "8.8.8.8"})
    assert "no matches" in result.lower()


def test_host_criticality_critical_host():
    result = get_host_criticality.invoke({"hostname": "DC01"})
    assert "critical" in result.lower()


def test_host_criticality_standard_host():
    result = get_host_criticality.invoke({"hostname": "WKS-FINANCE-07"})
    assert "standard" in result.lower()


def test_enrich_ioc_splits_ip_and_port():
    result = enrich_ioc.invoke({"indicator": "185.220.101.5:443"})
    assert "malicious" in result.lower()


def test_enrich_ioc_accepts_list_of_indicators():
    result = enrich_ioc.invoke({"indicator": ["185.220.101.5", "8.8.8.8"]})
    assert "malicious" in result.lower()
    assert "no matches" in result.lower()


def test_enrich_ioc_accepts_mixed_type_list():
    result = enrich_ioc.invoke({"indicator": ["185.220.101.5", 443, "WKS-FINANCE-07"]})
    assert "malicious" in result.lower()
