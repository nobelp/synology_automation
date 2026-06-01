# Synology Automation

## adguard_sync.py
Synchronisiert Clients von Omada Controller + Docker automatisch nach AdGuard Home.

- Omada ist Source of Truth (MAC als Schluessel)
- Name, IP, MAC und Tags werden automatisch synchronisiert
- Docker Container werden mit device_other + os_linux getaggt
- Cronjob: stuendlich via Synology Aufgabenplaner

## Konfiguration
Alle Verbindungen & Zugangsdaten werden in der `.env` Datei konfiguriert.
Kopiere `.env.template` nach `.env` und trage deine Werte ein:

```bash
cp .env.template .env
vi .env
```

## Verbindungen & Zugangsdaten
> Siehe `.env.template` — alle Werte dort eintragen und Datei als `.env` speichern.

### Omada Controller
- Host: `<OMADA_HOST>:<OMADA_PORT>`
- Benutzer: `<OMADA_USER>`
- Passwort: `<OMADA_PASS>`
- Site: `<OMADA_SITE>`

### AdGuard Home
- Host: `<ADGUARD_HOST>:<ADGUARD_PORT>`
- Benutzer: `<ADGUARD_USER>`
- Passwort: `<ADGUARD_PASS>`

### Docker
- Socket: `/var/run/docker.sock`
