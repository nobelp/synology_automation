# Synology Automation

## adguard_sync.py
Synchronisiert Clients von Omada Controller + Docker automatisch nach AdGuard Home.

- Omada ist Source of Truth (MAC als Schluessel)
- Name, IP, MAC und Tags werden automatisch synchronisiert
- Docker Container werden mit device_other + os_linux getaggt
- Cronjob: stuendlich via Synology Aufgabenplaner

### Ausfuehren
```bash
python3 /volume1/docker/adguard_sync/adguard_sync.py
```

### Log
```bash
cat /volume1/docker/adguard_sync/sync.log
```
