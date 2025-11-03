import os
import glob
import subprocess
import yaml
from flask import Flask, render_template, request, redirect, jsonify
from netmiko import ConnectHandler

# ---------- Paths ----------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DEVICES_DIR = os.path.join(REPO_ROOT, "data", "devices")
GENERATED_CONFIGS_DIR = os.path.join(REPO_ROOT, "startup_configs")
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")
SCRIPT_PATH = os.path.join(REPO_ROOT, "generate_config.py")
ZTP_SCRIPT = os.path.join(REPO_ROOT, "scripts", "ztp.py")

os.makedirs(DATA_DEVICES_DIR, exist_ok=True)
os.makedirs(GENERATED_CONFIGS_DIR, exist_ok=True)

# ---------- Grafana ----------
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://10.224.76.95:3000")
GRAFANA_DASH_UID = os.environ.get("GRAFANA_DASH_UID", "xf6o9HCHk")

app = Flask(__name__)

# ---------- Utility ----------
def list_devices():
    rows = []
    for y in sorted(glob.glob(os.path.join(DATA_DEVICES_DIR, "*.yaml"))):
        try:
            with open(y) as f:
                d = yaml.safe_load(f) or {}
            dev = d.get("device", {})
            rows.append({
                "name": dev.get("name"),
                "vendor": dev.get("vendor"),
                "mgmt_ip": dev.get("mgmt_ip"),
                "yaml_file": os.path.basename(y),
            })
        except Exception:
            pass
    return rows


def clean_empty_fields(x):
    """Return None if field is empty string."""
    return None if (x is None or str(x).strip() == "") else x


def safe_list(form, field):
    """Return list safely even if missing."""
    return request.form.getlist(field) if field in request.form else []


# ---------- Routes ----------
@app.route("/")
def index():
    devices = list_devices()
    grafana_iframe = f"{GRAFANA_URL}/d/{GRAFANA_DASH_UID}/device-status?orgId=1&refresh=5s"
    return render_template("index.html", devices=devices, grafana_iframe=grafana_iframe)


@app.route("/grafana")
def grafana():
    return redirect(f"{GRAFANA_URL}/d/{GRAFANA_DASH_UID}/device-status?orgId=1&refresh=5s")


# ===========================================================
# Add Device (GUI Submission → YAML + CFG + ZTP Trigger)
# ===========================================================
@app.route("/add-device", methods=["GET", "POST"])
def add_device():
    if request.method == "GET":
        return render_template(
            "add_device.html",
            vendors=["arista_eos", "cisco_ios", "juniper_junos"]
        )

    router_type = request.form.get("routerType", "").strip()
    if not router_type:
        return jsonify({"status": "error", "message": "Select Access or Core"}), 400

    device = {
        "name": request.form.get("deviceName", "").strip(),
        "vendor": request.form.get("vendor", "").strip(),
        "mgmt_ip": request.form.get("wanIp", "").strip(),
        "site": clean_empty_fields(request.form.get("site"))
    }

    # -----------------------------
    # Access Router Section
    # -----------------------------
    if router_type == "Access":
        vlans = safe_list(request.form, "vlanId[]")
        interfaces = safe_list(request.form, "interfaceName[]")
        device.update({
            "vlans": [
                {
                    "id": v,
                    "name": clean_empty_fields(request.form.getlist("vlanName[]")[i]),
                    "ipv4_subnet": clean_empty_fields(request.form.getlist("ipv4Subnet[]")[i]),
                    "ipv6_subnet": clean_empty_fields(request.form.getlist("ipv6Subnet[]")[i]),
                    "ospfv3": {"area": clean_empty_fields(request.form.getlist("ospfv3Area[]")[i])},
                    "dhcp_enabled": request.form.getlist("dhcpEnabled[]")[i] == "true",
                    "ipv4_virtual_router_address": clean_empty_fields(request.form.getlist("ipv4VRouter[]")[i]),
                    "ipv6_virtual_router_address": clean_empty_fields(request.form.getlist("ipv6VRouter[]")[i]),
                } for i, v in enumerate(vlans) if v
            ],
            "interfaces": [
                {
                    "name": iface,
                    "ipv4": clean_empty_fields(request.form.getlist("ipv4[]")[i]),
                    "ipv6": clean_empty_fields(request.form.getlist("ipv6[]")[i]),
                    "mtu": clean_empty_fields(request.form.getlist("mtu[]")[i]),
                    "switchport_mode": clean_empty_fields(request.form.getlist("switchportMode[]")[i]),
                } for i, iface in enumerate(interfaces) if iface
            ],
            "routes": {
                "static": [
                    {"prefix": clean_empty_fields(request.form.getlist("staticPrefix[]")[i]),
                     "next_hop": clean_empty_fields(request.form.getlist("staticNextHop[]")[i])}
                    for i in range(len(safe_list(request.form, "staticPrefix[]")))
                    if clean_empty_fields(request.form.getlist("staticPrefix[]")[i])
                ],
                "ipv6_static": [
                    {"prefix": clean_empty_fields(request.form.getlist("ipv6StaticPrefix[]")[i]),
                     "next_hop": clean_empty_fields(request.form.getlist("ipv6StaticNextHop[]")[i])}
                    for i in range(len(safe_list(request.form, "ipv6StaticPrefix[]")))
                    if clean_empty_fields(request.form.getlist("ipv6StaticPrefix[]")[i])
                ]
            },
            "routing_protocols": {
                "ospf": {
                    "id": clean_empty_fields(request.form.get("ospfId")) or "1",
                    "networks": [
                        {"prefix": clean_empty_fields(request.form.getlist("ospfNetwork[]")[i]),
                         "area": clean_empty_fields(request.form.getlist("ospfArea[]")[i]) or "0"}
                        for i in range(len(safe_list(request.form, "ospfNetwork[]")))
                        if clean_empty_fields(request.form.getlist("ospfNetwork[]")[i])
                    ]
                },
                "rip": {
                    "networks": [
                        {"prefix": clean_empty_fields(request.form.getlist("ripNetwork[]")[i])}
                        for i in range(len(safe_list(request.form, "ripNetwork[]")))
                        if clean_empty_fields(request.form.getlist("ripNetwork[]")[i])
                    ]
                }
            }
        })
        yaml_path = os.path.join(DATA_DEVICES_DIR, f"{device['name']}_access.yaml")

    # -----------------------------
    # Core Router Section
    # -----------------------------
    elif router_type == "Core":
        vlan_ids = safe_list(request.form, "vlanIdCore[]")
        iface_names = safe_list(request.form, "interfaceNameCore[]")
        device.update({
            "vlans": [
                {
                    "id": vlan_ids[i],
                    "name": clean_empty_fields(request.form.getlist("vlanNameCore[]")[i]),
                    "ipv4_subnet": clean_empty_fields(request.form.getlist("ipv4SubnetCore[]")[i]),
                    "ipv6_subnet": clean_empty_fields(request.form.getlist("ipv6SubnetCore[]")[i]),
                    "ospfv3": {"area": clean_empty_fields(request.form.getlist("ospfv3AreaCore[]")[i])}
                } for i in range(len(vlan_ids)) if vlan_ids[i]
            ],
            "interfaces": [
                {
                    "name": iface_names[i],
                    "ipv4": clean_empty_fields(request.form.getlist("ipv4Core[]")[i]),
                    "ipv6": clean_empty_fields(request.form.getlist("ipv6Core[]")[i]),
                    "switchport_mode": clean_empty_fields(request.form.getlist("switchportModeCore[]")[i]),
                    "ospfv3_area": clean_empty_fields(request.form.getlist("ospfv3AreaInterfaceCore[]")[i])
                } for i in range(len(iface_names)) if iface_names[i]
            ],
            "routes": {
                "static": [
                    {"prefix": clean_empty_fields(request.form.getlist("staticPrefixCore[]")[i]),
                     "next_hop": clean_empty_fields(request.form.getlist("staticNextHopCore[]")[i])}
                    for i in range(len(safe_list(request.form, "staticPrefixCore[]")))
                    if clean_empty_fields(request.form.getlist("staticPrefixCore[]")[i])
                ],
                "ipv6_static": [
                    {"prefix": clean_empty_fields(request.form.getlist("ipv6StaticPrefixCore[]")[i]),
                     "next_hop": clean_empty_fields(request.form.getlist("ipv6StaticNextHopCore[]")[i])}
                    for i in range(len(safe_list(request.form, "ipv6StaticPrefixCore[]")))
                    if clean_empty_fields(request.form.getlist("ipv6StaticPrefixCore[]")[i])
                ]
            },
            "routing_protocols": {
                "ospf": {
                    "id": clean_empty_fields(request.form.get("ospfId")) or "1",
                    "networks": [
                        {"prefix": clean_empty_fields(request.form.getlist("ospfNetworkCore[]")[i]),
                         "area": clean_empty_fields(request.form.getlist("ospfAreaCore[]")[i]) or "0"}
                        for i in range(len(safe_list(request.form, "ospfNetworkCore[]")))
                        if clean_empty_fields(request.form.getlist("ospfNetworkCore[]")[i])
                    ]
                },
                "ospfv3": {"address_family": "ipv6", "redistribute_bgp": True},
                "bgp": {
                    "as": clean_empty_fields(request.form.get("bgpAsCore")),
                    "neighbors": [
                        {"ip": clean_empty_fields(request.form.getlist("neighborIpCore[]")[i]),
                         "remote_as": clean_empty_fields(request.form.getlist("remoteAsCore[]")[i])}
                        for i in range(len(safe_list(request.form, "neighborIpCore[]")))
                        if clean_empty_fields(request.form.getlist("neighborIpCore[]")[i])
                    ],
                    "networks": [
                        clean_empty_fields(request.form.getlist("bgpNetworkPrefixCore[]")[i])
                        for i in range(len(safe_list(request.form, "bgpNetworkPrefixCore[]")))
                        if clean_empty_fields(request.form.getlist("bgpNetworkPrefixCore[]")[i])
                    ]
                }
            }
        })
        yaml_path = os.path.join(DATA_DEVICES_DIR, f"{device['name']}_core.yaml")

    # -----------------------------
    # Save YAML + Generate Config
    # -----------------------------
    with open(yaml_path, "w") as f:
        yaml.safe_dump({"device": device}, f, sort_keys=False)

    try:
        subprocess.run(["python3", SCRIPT_PATH, "--config", yaml_path],
                       cwd=REPO_ROOT, check=True)
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": f"Generator failed: {e}"}), 500

    # Optional: run Git commit if repo exists
    if os.path.isdir(os.path.join(REPO_ROOT, ".git")):
        subprocess.run(["git", "add", "."], cwd=REPO_ROOT)
        subprocess.run(["git", "commit", "-m", f"add: {device['name']} {router_type} yaml+cfg"], cwd=REPO_ROOT)
        subprocess.run(["git", "push"], cwd=REPO_ROOT)

    # -------------------------------------------------
    # Trigger ZTP Auto-Push
    # -------------------------------------------------
    try:
        subprocess.Popen(["python3", ZTP_SCRIPT, "--device", device["name"]],
                         cwd=os.path.join(REPO_ROOT, "scripts"))
    except Exception as e:
        print(f"[WARN] ZTP trigger failed: {e}")

    return jsonify({"status": "ok", "yaml": os.path.basename(yaml_path)})


# ===========================================================
# Push Config (manual)
# ===========================================================
@app.route("/push-config", methods=["GET", "POST"])
def push_config():
    if request.method == "GET":
        cfgs = [os.path.basename(f) for f in glob.glob(os.path.join(GENERATED_CONFIGS_DIR, "*.cfg"))]
        return render_template("push_config.html", config_files=cfgs)

    host = request.form["mgmt_ip"].strip()
    user = request.form["username"].strip()
    pw = request.form["password"].strip()
    cfg_file = request.form["config_file"].strip()
    full_path = os.path.join(GENERATED_CONFIGS_DIR, cfg_file)

    if not os.path.exists(full_path):
        return jsonify({"status": "error", "message": "Config file not found."}), 400

    try:
        conn = ConnectHandler(
            device_type="arista_eos",
            host=host,
            username=user,
            password=pw,
        )
        with open(full_path) as f:
            cfg = f.read().splitlines()
        conn.enable()
        output = conn.send_config_set(cfg)
        conn.save_config()
        conn.disconnect()
        return jsonify({"status": "ok", "message": f"Configuration pushed successfully to {host}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ===========================================================
# Main
# ===========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
