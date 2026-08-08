# Knowledge base — MITRE ATT&CK triage notes

Original notes written for this project, organized by tactic. Each entry
is deliberately short: what the technique looks like in logs, one
Elastic/Lucene search hint where useful, and the mitigation/response a
tier-1 analyst would reach for. Not a copy of any vendor or course
material — write your own real detections and runbook notes here as you
build them; this file exists so the RAG step (`research_node` in
`agents.py`) has something concrete to retrieve against.

## Initial Access

### T1566.001 - Spearphishing Attachment
A user opens an email attachment (Office doc, ISO, LNK) that spawns a
child process from `winword.exe`/`excel.exe`/`outlook.exe` — legitimate
Office apps rarely spawn `cmd.exe` or `powershell.exe` as a direct child.
Search: `process.parent.name:(winword.exe OR excel.exe OR outlook.exe)
and process.name:(cmd.exe OR powershell.exe OR wscript.exe)`.
Mitigation: attachment sandboxing, disable macros by default, Office
"Protected View".

### T1190 - Exploit Public-Facing Application
A web server process (IIS, Apache, nginx worker) spawns an unexpected
shell or writes a file into a web-writable directory shortly after
receiving an anomalous request (long query string, encoded payload).
Correlate the web access log's anomalous request with the app server
process's child-process/file-write events in the same short window.
Mitigation: WAF rule for the exploited pattern, patch, isolate host.

## Execution

### T1059.001 - PowerShell
Execution of obfuscated PowerShell commands, or use of `-EncodedCommand`,
usually indicates an attempt to evade logging. Common in post-exploitation
payloads (Empire, Cobalt Strike). Mitigation: enable Script Block Logging
and Constrained Language Mode.

### T1059.003 - Windows Command Shell
`cmd.exe` chained through `cmd /c` invoked by a non-interactive parent
(a service, a scheduled task, an Office app) rather than a user's shell —
scripted/automated execution is more suspicious than an analyst typing
commands at a console. Search: `process.name:cmd.exe and
process.parent.name:(services.exe OR svchost.exe OR winword.exe)`.

## Persistence

### T1053.005 - Scheduled Task
A new scheduled task is created that runs a script or binary from a
user-writable path (`%TEMP%`, `%APPDATA%`) instead of `Program Files` or
`System32` — a common way to survive reboot without touching the
registry. Windows Event ID 4698 logs task creation with the full command
line. Mitigation: restrict `schtasks` creation to admins, alert on tasks
pointing at non-standard paths.

### T1547.001 - Registry Run Keys / Startup Folder
A new value under `HKCU\...\Run`, `HKLM\...\Run`, or a new file dropped
in the Startup folder, pointing at a binary outside `Program Files`.
Cheap and common — often the first persistence mechanism a commodity
malware family tries. Mitigation: baseline known-good Run key entries per
host image, alert on drift.

## Privilege Escalation / Defense Evasion

### T1055 - Process Injection
A process (often `explorer.exe`, `svchost.exe`, or a legitimate signed
binary) allocates remote memory and creates a remote thread in another
process — `CreateRemoteThread`/`WriteProcessMemory` call pairs, or an
EDR alert naming the technique directly. High confidence if the target
process wasn't already communicating with the source process.
Mitigation: EDR behavioral blocking; isolate and re-image if confirmed.

### T1070.001 - Indicator Removal: Clear Windows Event Logs
Windows Event ID 1102 (Security log cleared) or 104 (System log
cleared), especially outside a scheduled maintenance window or not
performed by an admin account. Near-certain sign of an attacker covering
tracks after achieving their objective — treat as High severity on its
own. Mitigation: forward logs to a separate collector in near-real-time
so local clearing doesn't destroy the only copy.

### T1027 - Obfuscated Files or Information
Base64-encoded, packed, or otherwise obfuscated payloads — encoded
PowerShell (`-EncodedCommand`), a binary with abnormally high entropy for
its apparent file type, or a script with excessive string concatenation
used to evade static signature detection. Pair with T1059.001 when the
obfuscated content is a PowerShell command.

## Credential Access

### T1003 - OS Credential Dumping
Access to LSASS (procdump, mimikatz) generates Windows events 4656/4663
with `ObjectName:*lsass.exe*`. High severity if the source process isn't
a known EDR/AV.

### T1110.001 - Brute Force: Password Guessing
A high volume of failed authentication attempts (Windows Event ID 4625,
or repeated SSH `Failed password`) against one account or host in a
short window, especially from a source that has never authenticated
successfully before. Search: `event.action:(logon-failed OR
ssh_auth_failed) and destination.ip:<host>` aggregated by source IP over
a 5-minute window. Mitigation: account lockout policy, source IP block,
MFA.

## Discovery

### T1087.002 - Domain Account Discovery
Enumeration commands (`net user /domain`, `net group "Domain Admins"
/domain`, `Get-ADUser -Filter *`) run from a host that isn't a domain
controller or an admin workstation. Low severity in isolation, but a
strong corroborating signal when paired with credential access or
lateral movement activity in the same timeframe.

## Lateral Movement

### T1021.002 - SMB/Windows Admin Shares
Lateral movement via administrative shares (\\host\C$). Observed as
network traffic on port 445 between hosts that don't normally
communicate. Search in Elastic:
`event.category:network and destination.port:445 and source.ip:(internal_subnet)`.

### T1021.001 - Remote Desktop Protocol
An interactive RDP logon (Windows Event ID 4624, logon type 10) to a
server from a workstation that doesn't normally initiate RDP sessions to
it, or a logon outside the account's normal working hours. Especially
notable on a critical host (domain controller, database server).

## Command and Control

### T1071.001 - Application Layer Protocol: Web Protocols
Outbound HTTPS connections at a regular, machine-like interval (beaconing)
to a destination with no corresponding user-initiated browser activity —
no referrer, no prior DNS-then-multi-request pattern a real page load
would show. Cross-reference the destination IP/domain against threat
intel (`enrich_ioc`); a positive match plus a beaconing pattern is a
strong C2 indicator even without payload inspection.

## Exfiltration

### T1041 - Exfiltration Over C2 Channel
A sustained spike in outbound bytes-transferred on a connection already
flagged for C2-like beaconing (T1071.001) — data leaving over the same
channel used for command and control, rather than a separate exfil
channel. Look for an outbound volume anomaly relative to that host's
30-day baseline.

## Impact

### T1486 - Data Encrypted for Impact (Ransomware)
A burst of file rename/modify events across many files in a short window
(mass `.docx` -> `.docx.locked`-style renames), often preceded by
credential dumping (T1003) and lateral movement (T1021.x) earlier in the
same incident — ransomware is usually the last stage of an intrusion,
not the first sign of one. Always Critical severity; the recommended
action is immediate host isolation, not "monitor."

## General triage playbook
1. Confirm whether the host is critical (domain controller, server, endpoint).
2. Enrich IOCs (IP, hash, domain) against threat intel feeds.
3. Map the behavior to MITRE ATT&CK techniques.
4. Classify severity (Low/Medium/High/Critical) based on scope and confidence.
5. Recommend an action (isolate host, block IOC, escalate to IR).
