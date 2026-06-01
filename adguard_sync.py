#!/usr/bin/env python3
"""
Omada + Docker -> AdGuard Home Client Sync
Source of Truth: Omada (MAC als Schluessel)
Inkl. DHCP-Reservierungen (auch Offline-Geraete)
"""

import requests
import logging
import sys
import socket
import json as _json
import urllib3
import os


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================================
# KONFIGURATION (aus .env)
# =========================================

# env laden ohne dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

OMADA_HOST   = os.environ["OMADA_HOST"]
OMADA_PORT   = int(os.environ.get("OMADA_PORT", "443"))
OMADA_USER   = os.environ["OMADA_USER"]
OMADA_PASS   = os.environ["OMADA_PASS"]
OMADA_SITE   = os.environ.get("OMADA_SITE", "MasterSite")

ADGUARD_HOST = os.environ["ADGUARD_HOST"]
ADGUARD_PORT = int(os.environ.get("ADGUARD_PORT", "9080"))
ADGUARD_USER = os.environ["ADGUARD_USER"]
ADGUARD_PASS = os.environ["ADGUARD_PASS"]

LOG_FILE     = os.environ.get("LOG_FILE", "/volume1/docker/adguard_sync/sync.log")

# =========================================
# TAG MAPPING
# =========================================

DEVICE_TYPE_MAP = {
    "Media Player":     "device_tv",
    "Television":       "device_tv",
    "Projector":        "device_tv",
    "Audio Player":     "device_audio",
    "IPC":              "device_camera",
    "Doorbell":         "device_camera",
    "Mobile":           "device_phone",
    "Tablet":           "device_tablet",
    "Laptop":           "device_laptop",
    "Computer":         "device_pc",
    "Server":           "device_nas",
    "Photo Display":    "device_other",
    "Omada Controller": "device_other",
    "Controller":       "device_other",
    "Smart Plug":       "device_other",
    "Smart Appliance":  "device_other",
    "Smart Washer":     "device_other",
    "Smart Home":       "device_other",
    "HVAC":             "device_other",
    "Light":            "device_other",
    "Weather Station":  "device_other",
    "Network Monitor":  "device_other",
    "Pet Monitor":      "device_other",
    "Unknown":          "device_other",
}

OS_MAP = {
    "ios":      "os_ios",
    "macos":    "os_macos",
    "windows":  "os_windows",
    "android":  "os_android",
    "linux":    "os_linux",
    "dsm":      "os_linux",
    "sonos":    "os_other",
    "tvos":     "os_other",
}

def get_tags(device_type, os_name):
    tags = []
    if device_type:
        tag = DEVICE_TYPE_MAP.get(device_type)
        if tag:
            tags.append(tag)
    if os_name:
        os_key = os_name.lower().split()[0]
        tag = OS_MAP.get(os_key)
        if tag:
            tags.append(tag)
    return tags

# =========================================
# LOGGING
# =========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# =========================================
# HELPER
# =========================================

def format_mac(mac):
    return mac.replace("-", ":").lower()

# =========================================
# OMADA API
# =========================================

def omada_login():
    base = "%s:%d" % (OMADA_HOST, OMADA_PORT)
    session = requests.Session()
    session.verify = False

    r = session.get("%s/api/info" % base, timeout=10)
    r.raise_for_status()
    controller_id = r.json()["result"]["omadacId"]
    log.info("Omada Controller ID: %s" % controller_id)

    r = session.post(
        "%s/%s/api/v2/login" % (base, controller_id),
        json={"username": OMADA_USER, "password": OMADA_PASS},
        timeout=10
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errorCode") != 0:
        raise Exception("Omada Login fehlgeschlagen: %s" % data.get("msg"))
    token = data["result"]["token"]
    log.info("Omada Login OK")
    headers = {"Csrf-Token": token}

    r = session.get(
        "%s/%s/api/v2/sites?currentPage=1&currentPageSize=100" % (base, controller_id),
        headers=headers, timeout=10
    )
    r.raise_for_status()
    sites = r.json()["result"]["data"]
    site_id = None
    for site in sites:
        if site["name"] == OMADA_SITE:
            site_id = site["id"]
            break
    if not site_id:
        raise Exception("Site '%s' nicht gefunden!" % OMADA_SITE)
    log.info("Site ID: %s" % site_id)

    return session, base, controller_id, site_id, headers

def omada_get_active_clients(session, base, controller_id, site_id, headers):
    macs = []
    page = 1
    while True:
        r = session.get(
            "%s/%s/api/v2/sites/%s/clients?currentPage=%d&currentPageSize=200&filters.active=false" % (base, controller_id, site_id, page),
            headers=headers, timeout=10
        )
        r.raise_for_status()
        result = r.json()["result"]
        batch = result.get("data", [])
        macs.extend([c["mac"] for c in batch])
        if len(macs) >= result.get("totalRows", 0):
            break
        page += 1
    log.info("Omada aktive Clients: %d MACs" % len(macs))

    clients = []
    for mac in macs:
        r = session.get(
            "%s/%s/api/v2/sites/%s/clients/%s" % (base, controller_id, site_id, mac),
            headers=headers, timeout=10
        )
        if r.json().get("errorCode") == 0:
            clients.append(r.json()["result"])
    log.info("Omada aktive Client-Details: %d" % len(clients))
    return clients

def omada_get_dhcp_reservations(session, base, controller_id, site_id, headers):
    """Liest DHCP-Reservierungen - auch Offline-Geraete wie Dell Screen etc."""
    try:
        r = session.get(
            "%s/%s/api/v2/sites/%s/setting/lan/dhcpReservation?currentPage=1&currentPageSize=200" % (base, controller_id, site_id),
            headers=headers, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        reservations = data.get("result", {}).get("data", [])
        log.info("Omada DHCP-Reservierungen: %d gefunden" % len(reservations))
        return reservations
    except Exception as e:
        log.warning("DHCP-Reservierungen konnten nicht geladen werden: %s" % e)
        return []

def omada_get_clients():
    session, base, controller_id, site_id, headers = omada_login()

    active = omada_get_active_clients(session, base, controller_id, site_id, headers)
    reservations = omada_get_dhcp_reservations(session, base, controller_id, site_id, headers)

    session.post("%s/%s/api/v2/logout" % (base, controller_id), headers=headers, timeout=10)

    # Aktive Clients als Basis
    combined = {}
    for c in active:
        mac = format_mac(c.get("mac", ""))
        name = c.get("name", "")
        ip = c.get("ip", "")
        device_type = c.get("deviceType", "")
        os_name = c.get("osName", "")
        is_mac_name = len(name) == 17 and (name.count("-") == 5 or name.count(":") == 5)
        if mac and ip and name and not is_mac_name:
            combined[mac] = {
                "name": name,
                "ip": ip,
                "mac": c.get("mac", ""),
                "tags": get_tags(device_type, os_name)
            }

    # DHCP-Reservierungen ergaenzen (nur wenn nicht bereits aktiv vorhanden)
    dhcp_added = 0
    for r in reservations:
        mac = format_mac(r.get("mac", ""))
        name = r.get("hostName") or r.get("name") or r.get("clientName") or ""
        ip = r.get("ip", "")
        is_mac_name = len(name) == 17 and (name.count("-") == 5 or name.count(":") == 5)
        if mac and ip and name and not is_mac_name and mac not in combined:
            combined[mac] = {
                "name": name,
                "ip": ip,
                "mac": r.get("mac", ""),
                "tags": ["device_other"]
            }
            dhcp_added += 1

    log.info("DHCP-Reservierungen neu hinzugefuegt: %d" % dhcp_added)
    log.info("Gesamt verwertbare Clients: %d" % len(combined))
    return combined

# =========================================
# DOCKER API
# =========================================

def docker_get_containers():
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect("/var/run/docker.sock")
        sock.send(b"GET /containers/json HTTP/1.0\r\nHost: localhost\r\n\r\n")
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        sock.close()
        body = response.split(b"\r\n\r\n", 1)[1]
        return _json.loads(body)
    except Exception as e:
        log.warning("Docker API Fehler: %s" % e)
        return []

# =========================================
# ADGUARD API
# =========================================

def adguard_get_clients():
    r = requests.get(
        "%s:%d/control/clients" % (ADGUARD_HOST, ADGUARD_PORT),
        auth=(ADGUARD_USER, ADGUARD_PASS),
        timeout=10
    )
    r.raise_for_status()
    existing = r.json().get("clients") or []
    log.info("AdGuard: %d bestehende Clients" % len(existing))
    return existing

def adguard_add_client(name, ip, mac=None, tags=None):
    ids = [ip]
    if mac:
        ids.append(format_mac(mac))
    payload = {
        "name": name,
        "ids": ids,
        "tags": tags or [],
        "use_global_settings": True,
        "use_global_blocked_services": True,
        "filtering_enabled": True,
        "parental_enabled": False,
        "safebrowsing_enabled": False,
        "safesearch_enabled": False,
        "upstreams": []
    }
    r = requests.post(
        "%s:%d/control/clients/add" % (ADGUARD_HOST, ADGUARD_PORT),
        auth=(ADGUARD_USER, ADGUARD_PASS),
        json=payload, timeout=10
    )
    if r.status_code == 200:
        mac_str = " / %s" % format_mac(mac) if mac else ""
        tag_str = " [%s]" % ",".join(tags) if tags else ""
        log.info("  + Hinzugefuegt: %s (%s%s)%s" % (name, ip, mac_str, tag_str))
    else:
        log.warning("  ! Fehler bei %s (%s): %s" % (name, ip, r.text))

def adguard_update_client(old_name, name, ip, mac=None, tags=None):
    ids = [ip]
    if mac:
        ids.append(format_mac(mac))
    payload = {
        "name": old_name,
        "data": {
            "name": name,
            "ids": ids,
            "tags": tags or [],
            "use_global_settings": True,
            "use_global_blocked_services": True,
            "filtering_enabled": True,
            "parental_enabled": False,
            "safebrowsing_enabled": False,
            "safesearch_enabled": False,
            "upstreams": []
        }
    }
    r = requests.post(
        "%s:%d/control/clients/update" % (ADGUARD_HOST, ADGUARD_PORT),
        auth=(ADGUARD_USER, ADGUARD_PASS),
        json=payload, timeout=10
    )
    if r.status_code == 200:
        mac_str = " / %s" % format_mac(mac) if mac else ""
        tag_str = " [%s]" % ",".join(tags) if tags else ""
        log.info("  ~ Aktualisiert: %s -> %s (%s%s)%s" % (old_name, name, ip, mac_str, tag_str))
    else:
        log.warning("  ! Fehler Update %s: %s" % (name, r.text))

# =========================================
# OMADA SYNC
# =========================================

def sync_omada():
    log.info("=" * 50)
    log.info("Starte Omada -> AdGuard Sync (inkl. DHCP-Reservierungen)")
    log.info("=" * 50)

    omada_by_mac = omada_get_clients()

    existing = adguard_get_clients()
    ag_by_mac  = {}
    ag_by_name = {}
    for c in existing:
        ag_by_name[c["name"]] = c
        for id_ in c.get("ids", []):
            if ":" in id_ and len(id_) == 17:
                ag_by_mac[id_] = c

    added = updated = skipped = 0

    for mac, info in omada_by_mac.items():
        name    = info["name"]
        ip      = info["ip"]
        raw_mac = info["mac"]
        tags    = info["tags"]

        if mac in ag_by_mac:
            existing_client = ag_by_mac[mac]
            old_name = existing_client["name"]
            existing_ids = existing_client.get("ids", [])
            existing_ip = next((id_ for id_ in existing_ids if ":" not in id_ or len(id_) != 17), None)
            existing_tags = existing_client.get("tags", [])
            if old_name != name or existing_ip != ip or existing_tags != tags:
                adguard_update_client(old_name, name, ip, raw_mac, tags)
                updated += 1
            else:
                skipped += 1
        elif name in ag_by_name:
            adguard_update_client(name, name, ip, raw_mac, tags)
            updated += 1
        else:
            adguard_add_client(name, ip, raw_mac, tags)
            added += 1

    log.info("=" * 50)
    log.info("Omada Sync: %d neu, %d aktualisiert, %d unveraendert" % (added, updated, skipped))
    log.info("=" * 50)

# =========================================
# DOCKER SYNC
# =========================================

def sync_docker():
    log.info("=" * 50)
    log.info("Starte Docker -> AdGuard Sync")
    log.info("=" * 50)

    containers = docker_get_containers()
    if not containers:
        log.warning("Keine Docker Container gefunden")
        return

    docker_map = {}
    for c in containers:
        name = c["Names"][0].lstrip("/")
        networks = c["NetworkSettings"]["Networks"]
        seen_name = False
        for net_name, net in networks.items():
            ip = net.get("IPAddress", "")
            if ip:
                if not seen_name:
                    docker_map[ip] = name
                    seen_name = True
                else:
                    docker_map[ip] = "%s (%s)" % (name, net_name)

    log.info("Docker: %d Container-IPs gefunden" % len(docker_map))

    existing = adguard_get_clients()
    existing_ips = {}
    for c in existing:
        for id_ in c.get("ids", []):
            existing_ips[id_] = c["name"]

    docker_tags = ["device_other", "os_linux"]

    added = updated = skipped = 0
    for ip, name in docker_map.items():
        if ip in existing_ips:
            if existing_ips[ip] != name:
                adguard_update_client(existing_ips[ip], name, ip, None, docker_tags)
                updated += 1
            else:
                skipped += 1
        else:
            adguard_add_client(name, ip, None, docker_tags)
            added += 1

    log.info("=" * 50)
    log.info("Docker Sync: %d neu, %d aktualisiert, %d unveraendert" % (added, updated, skipped))
    log.info("=" * 50)

# =========================================
# MAIN
# =========================================

if __name__ == "__main__":
    try:
        sync_omada()
        sync_docker()
    except Exception as e:
        log.error("FEHLER: %s" % e, exc_info=True)
        sys.exit(1)