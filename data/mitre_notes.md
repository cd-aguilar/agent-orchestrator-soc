# Sample knowledge base (replace with your real HTB / Elastic / runbook notes)

## T1059.001 - PowerShell
Execution of obfuscated PowerShell commands, or use of `-EncodedCommand`,
usually indicates an attempt to evade logging. Common in post-exploitation
payloads (Empire, Cobalt Strike). Mitigation: enable Script Block Logging
and Constrained Language Mode.

## T1021.002 - SMB/Windows Admin Shares
Lateral movement via administrative shares (\\host\C$). Observed as
network traffic on port 445 between hosts that don't normally
communicate. Search in Elastic:
`event.category:network and destination.port:445 and source.ip:(internal_subnet)`.

## T1003 - OS Credential Dumping
Access to LSASS (procdump, mimikatz) generates Windows events 4656/4663
with `ObjectName:*lsass.exe*`. High severity if the source process isn't
a known EDR/AV.

## General triage playbook
1. Confirm whether the host is critical (domain controller, server, endpoint).
2. Enrich IOCs (IP, hash, domain) against threat intel feeds.
3. Map the behavior to MITRE ATT&CK techniques.
4. Classify severity (Low/Medium/High/Critical) based on scope and confidence.
5. Recommend an action (isolate host, block IOC, escalate to IR).
