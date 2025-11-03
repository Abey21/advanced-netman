#!/usr/bin/env python3
import os, sys, csv, json, requests

NAUTOBOT_URL   = os.environ.get("NAUTOBOT_URL", "http://127.0.0.1:8080").rstrip("/")
NAUTOBOT_TOKEN = os.environ.get("NAUTOBOT_TOKEN")
if not NAUTOBOT_TOKEN:
    print("ERROR: NAUTOBOT_TOKEN not set")
    sys.exit(1)

s = requests.Session()
s.headers.update({
    "Authorization": "Token " + NAUTOBOT_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
})
s.verify = True  # set False if using self-signed TLS

def _get(path, params=None):
    r = s.get(NAUTOBOT_URL + path, params=params or {})
    r.raise_for_status()
    return r.json()

def _post(path, payload):
    r = s.post(NAUTOBOT_URL + path, data=json.dumps(payload))
    if r.status_code not in (200, 201):
        raise requests.HTTPError(str(r.status_code) + " " + r.text)
    return r.json()

def _patch(path, payload):
    r = s.patch(NAUTOBOT_URL + path, data=json.dumps(payload))
    if r.status_code not in (200, 201):
        raise requests.HTTPError(str(r.status_code) + " " + r.text)
    return r.json()

def _list_all(path):
    results, limit, offset = [], 100, 0
    while True:
        data = _get(path, {"limit": limit, "offset": offset})
        if isinstance(data, dict) and "results" in data:
            results.extend(data.get("results", []))
            if data.get("next"):
                offset += limit
                continue
        break
    return results

def _cts_to_strings(objs):
    out = set()
    for o in (objs or []):
        if isinstance(o, str) and "." in o:
            out.add(o)
        elif isinstance(o, dict):
            app = o.get("app_label") or o.get("app")
            model = o.get("model")
            if app and model:
                out.add(app + "." + model)
    return out

def ensure_location_type(name):
    want_cts = set(["dcim.device"])
    for lt in _list_all("/api/dcim/location-types/"):
        if lt.get("name") == name:
            have = _cts_to_strings(lt.get("content_types"))
            if not want_cts.issubset(have):
                _patch("/api/dcim/location-types/" + lt["id"] + "/", {
                    "content_types": sorted(list(have.union(want_cts)))
                })
            return lt["id"]
    created = _post("/api/dcim/location-types/", {
        "name": name,
        "content_types": sorted(list(want_cts)),
    })
    return created["id"]

def ensure_location(name, location_type_id):
    for loc in _list_all("/api/dcim/locations/"):
        if loc.get("name") == name:
            return loc["id"]
    created = _post("/api/dcim/locations/", {
        "name": name,
        "location_type": location_type_id,
        "status": "active"
    })
    return created["id"]

def ensure_role(name):
    want_cts = set(["dcim.device"])
    slug = name.lower().replace(" ", "-")
    for r in _list_all("/api/extras/roles/"):
        if r.get("slug") == slug or r.get("name") == name:
            have = _cts_to_strings(r.get("content_types"))
            if not want_cts.issubset(have):
                _patch("/api/extras/roles/" + r["id"] + "/", {
                    "content_types": sorted(list(have.union(want_cts)))
                })
            return r["id"]
    created = _post("/api/extras/roles/", {
        "name": name,
        "slug": slug,
        "color": "9e9e9e",
        "content_types": sorted(list(want_cts)),
    })
    return created["id"]

def ensure_manufacturer(name):
    slug = name.lower().replace(" ", "-")
    for m in _list_all("/api/dcim/manufacturers/"):
        if m.get("slug") == slug or m.get("name") == name:
            return m["id"]
    created = _post("/api/dcim/manufacturers/", {"name": name, "slug": slug})
    return created["id"]

def ensure_device_type(model, manufacturer_id):
    for dt in _list_all("/api/dcim/device-types/"):
        man = dt.get("manufacturer")
        man_id = man if isinstance(man, str) else (man or {}).get("id")
        if dt.get("model") == model and man_id == manufacturer_id:
            return dt["id"]
    created = _post("/api/dcim/device-types/", {
        "model": model,
        "manufacturer": manufacturer_id
    })
    return created["id"]

def ensure_platform(name, manufacturer_id=None):
    slug = name.lower().replace(" ", "-")
    for p in _list_all("/api/dcim/platforms/"):
        if p.get("slug") == slug or p.get("name") == name:
            return p["id"]
    payload = {"name": name, "slug": slug}
    if manufacturer_id:
        payload["manufacturer"] = manufacturer_id
    created = _post("/api/dcim/platforms/", payload)
    return created["id"]

def ensure_device(name, device_type_id, role_id, location_id, platform_id=None):
    for d in _list_all("/api/dcim/devices/"):
        if d.get("name") == name:
            return d["id"]
    payload = {
        "name": name,
        "device_type": device_type_id,
        "role": role_id,
        "location": location_id,
        "status": "active",
    }
    if platform_id:
        payload["platform"] = platform_id
    created = _post("/api/dcim/devices/", payload)
    return created["id"]

def ensure_interface(device_id, name, iftype="virtual"):
    for iface in _list_all("/api/dcim/interfaces/"):
        dev = iface.get("device")
        dev_id = dev if isinstance(dev, str) else (dev or {}).get("id")
        if iface.get("name") == name and dev_id == device_id:
            return iface["id"]
    created = _post("/api/dcim/interfaces/", {
        "device": device_id,
        "name": name,
        "type": iftype
    })
    return created["id"]

def ensure_ip(address, interface_id=None):
    for ip in _list_all("/api/ipam/ip-addresses/"):
        if ip.get("address") == address:
            if interface_id and not ip.get("assigned_object_id"):
                _patch("/api/ipam/ip-addresses/" + ip["id"] + "/", {
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": interface_id,
                    "status": "active"
                })
            return ip["id"]
    payload = {"address": address, "status": "active"}
    if interface_id:
        payload["assigned_object_type"] = "dcim.interface"
        payload["assigned_object_id"] = interface_id
    created = _post("/api/ipam/ip-addresses/", payload)
    return created["id"]

def set_primary_ip4(device_id, ip_id):
    _patch("/api/dcim/devices/" + device_id + "/", {"primary_ip4": ip_id})

def main():
    if len(sys.argv) != 2:
        print("Usage: " + sys.argv[0] + " ./seed/devices.csv")
        sys.exit(2)

    with open(sys.argv[1], newline="") as f:
        rows = list(csv.DictReader(f))

    for i, row in enumerate(rows, 1):
        try:
            lt_name  = (row.get("location_type") or "Lab").strip()
            loc_name = (row.get("location") or "containerlab").strip()
            role_name= (row.get("device_role") or "router").strip()
            mfr_name = (row.get("manufacturer") or "Arista").strip()
            model    = (row.get("device_type") or "vEOS").strip()
            plat     = (row.get("platform") or "arista_eos").strip()
            name     = (row.get("device_name") or "").strip()
            ip       = (row.get("mgmt_ip") or "").strip()
            mask     = (row.get("mgmt_mask") or "24").strip()
            iface    = (row.get("mgmt_iface") or "Management0").strip()

            if not (lt_name and loc_name and role_name and name and ip):
                print("[" + str(i) + "] SKIP (missing required fields) -> " + str(row))
                continue

            print("[" + str(i) + "] " + name + ": creating/ensuring objects...")

            lt_id   = ensure_location_type(lt_name)
            loc_id  = ensure_location(loc_name, lt_id)
            role_id = ensure_role(role_name)
            mfr_id  = ensure_manufacturer(mfr_name)
            dt_id   = ensure_device_type(model, mfr_id)
            plat_id = ensure_platform(plat, mfr_id)

            dev_id  = ensure_device(name, dt_id, role_id, loc_id, plat_id)
            if_id   = ensure_interface(dev_id, iface, "virtual")
            ip_id   = ensure_ip(ip + "/" + mask, if_id)
            set_primary_ip4(dev_id, ip_id)

            print("    OK -> " + name + " " + iface + " " + ip + "/" + mask)

        except requests.HTTPError as he:
            print("[" + str(i) + "] HTTP ERROR: " + str(he))
        except Exception as e:
            print("[" + str(i) + "] ERROR: " + str(e))

    print("Done.")

if __name__ == "__main__":
    main()
