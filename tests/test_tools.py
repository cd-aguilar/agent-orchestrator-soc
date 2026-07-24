"""Tests unitarios para las herramientas de los agentes (no requieren Ollama)."""

from tools import enrich_ioc, get_host_criticality


def test_enrich_ioc_known_indicator():
    result = enrich_ioc.invoke({"indicator": "185.220.101.5"})
    assert "maliciosa" in result.lower()


def test_enrich_ioc_unknown_indicator():
    result = enrich_ioc.invoke({"indicator": "8.8.8.8"})
    assert "sin coincidencias" in result.lower()


def test_host_criticality_critical_host():
    result = get_host_criticality.invoke({"hostname": "DC01"})
    assert "crítico" in result.lower()


def test_host_criticality_standard_host():
    result = get_host_criticality.invoke({"hostname": "WKS-FINANCE-07"})
    assert "estándar" in result.lower()
