# Base de conocimiento de ejemplo (reemplázala con tus notas reales de HTB / Elastic / runbooks)

## T1059.001 - PowerShell
Ejecución de comandos PowerShell ofuscados o con `-EncodedCommand` suele indicar
intento de evasión de logging. Común en payloads de post-explotación (Empire, Cobalt Strike).
Mitigación: habilitar Script Block Logging y Constrained Language Mode.

## T1021.002 - SMB/Windows Admin Shares
Movimiento lateral vía recursos administrativos (\\host\C$). Se observa tráfico
en puerto 445 entre hosts que normalmente no se comunican. Buscar en Elastic:
`event.category:network and destination.port:445 and source.ip:(internal_subnet)`.

## T1003 - OS Credential Dumping
Acceso a LSASS (procdump, mimikatz) genera eventos 4656/4663 en Windows con
`ObjectName:*lsass.exe*`. Alta severidad si el proceso origen no es un EDR/AV conocido.

## Playbook general de triage
1. Confirmar si el host es crítico (dominio, servidor, endpoint).
2. Enriquecer IOCs (IP, hash, dominio) contra feeds de threat intel.
3. Mapear el comportamiento a técnicas MITRE ATT&CK.
4. Clasificar severidad (Low/Medium/High/Critical) según alcance y confianza.
5. Recomendar acción (aislar host, bloquear IOC, escalar a IR).
