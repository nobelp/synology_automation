# Synology Automation

## adguard_sync.py
Synchronisiert Clients von Omada Controller + Docker automatisch nach AdGuard Home.

- Omada ist Source of Truth (MAC als Schluessel)
- Name, IP, MAC und Tags werden automatisch synchronisiert
- Docker Container werden mit device_other + os_linux getaggt
- Cronjob: stuendlich via Synology Aufgabenplaner

---

## Verbindungen & Zugangsdaten

### Omada Controller
- Host: `https://192.168.2.104:443`
- Benutzer: `hassio.api`
- Passwort: `T9!qM_7F{AeZ5$Lx@Kp2]hR^C)S-wJ8`
- Site: `MasterSite`

### AdGuard Home
- Host: `http://192.168.2.200:9080`
- Benutzer: `adguard_admin`
- Passwort: `z\k-6xZ&>\`~;c7a.tDw~+wW^UR3J,%ngqv8+zM9;LQw&W}g^2{`

### Docker
- Socket: `/var/run/docker.sock`

---

## Tag Mapping Omada -> AdGuard

| Omada DeviceType | AdGuard Tag |
|---|---|
| Television, Media Player, Projector | device_tv |
| Audio Player | device_audio |
| IPC, Doorbell | device_camera |
| Mobile | device_phone |
| Tablet | device_tablet |
| Laptop | device_laptop |
| Computer | device_pc |
| Server | device_nas |
| alle anderen | device_other |

| Omada OS | AdGuard Tag |
|---|---|
| iOS | os_ios |
| macOS | os_macos |
| Windows | os_windows |
| Android | os_android |
| Linux / DSM | os_linux |
| Sonos, tvOS | os_other |

| Docker | AdGuard Tags |
|---|---|
| Alle Container | device_other + os_linux |

---

## Manuell ausfuehren
```bash
python3 /volume1/docker/adguard_sync/adguard_sync.py
```

## Log anschauen
```bash
cat /volume1/docker/adguard_sync/sync.log
```

---

## Cronjob einrichten (Synology DSM)

1. DSM oeffnen
2. Systemsteuerung -> Aufgabenplaner
3. Erstellen -> Geplante Aufgabe -> Benutzerdefiniertes Script
4. Tab "Allgemein":
   - Aufgabenname: `Omada AdGuard Sync`
   - Benutzer: `root`
5. Tab "Zeitplan":
   - An folgenden Tagen ausfuehren: Taeglich
   - Startzeit: 00:00
   - Haken setzen: "Weiterhin innerhalb desselben Tages ausfuehren"
   - Wiederholen: Jede Stunde
   - Letzte Ausfuehrungszeit: 23:00
6. Tab "Aufgabeneinstellungen":
   - Befehl: `python3 /volume1/docker/adguard_sync/adguard_sync.py`
   - Optional: E-Mail Benachrichtigung aktivieren bei Fehler
7. OK klicken

---

## Voraussetzungen

```bash
pip3 install requests --break-system-packages
```

---

## Infrastruktur

| Geraet | Hostname | IP | Funktion |
|---|---|---|---|
| Synology NAS | Diskstation5 | 192.168.2.200 | NAS, Docker Host, AdGuard |
| Omada Controller | TurbiControl | 192.168.2.104 | Netzwerk Management (OC220) |
