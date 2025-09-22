import os, glob, subprocess, yaml
from flask import Flask, render_template, request, redirect, jsonify

# ---------- Paths (repo-relative) ----------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DEVICES_DIR = os.path.join(REPO_ROOT, "data", "devices")
GENERATED_CONFIGS_DIR = os.path.join(REPO_ROOT, "generated-configs")
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")
SCRIPT_PATH = os.path.join(REPO_ROOT, "generate_config.py")
os.makedirs(DATA_DEVICES_DIR, exist_ok=True)
os.makedirs(GENERATED_CONFIGS_DIR, exist_ok=True)

# ---------- Grafana (configurable) ----------
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://10.224.77.95:3000")
GRAFANA_DASH_UID = os.environ.get("GRAFANA_DASH_UID", "xf6o9HCHk")  # replace with your UID

app = Flask(__name__)

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

@app.route("/")
def index():
    devices = list_devices()
    grafana_iframe = f"{GRAFANA_URL}/d/{GRAFANA_DASH_UID}/device-status?orgId=1&refresh=5s"
    return render_template("index.html", devices=devices, grafana_iframe=grafana_iframe)

@app.route("/grafana")
def grafana():
    return redirect(f"{GRAFANA_URL}/d/{GRAFANA_DASH_UID}/device-status?orgId=1&refresh=5s")

def clean_empty_fields(x):
    return None if (x is None or str(x).strip() == "") else x

@app.route('/add-device', methods=['GET', 'POST'])
def add_device():
    if request.method == 'GET':
        return render_template('add_device.html',
                               vendors=['arista_eos', 'cisco_ios', 'juniper_junos'])
    # POST
    router_type = request.form.get('routerType', '').strip()   # Access or Core
    if not router_type:
        return jsonify({'status':'error','message':'Select Access or Core'}), 400

    device = {
        "name": request.form.get('deviceName','').strip(),
        "vendor": request.form.get('vendor','').strip(),
        "mgmt_ip": request.form.get('wanIp','').strip(),
        "site": clean_empty_fields(request.form.get('site'))
    }

    if router_type == 'Access':
        device.update({
            'vlans': [
                {
                    'id': request.form.getlist('vlanId[]')[i],
                    'name': clean_empty_fields(request.form.getlist('vlanName[]')[i]),
                    'ipv4_subnet': clean_empty_fields(request.form.getlist('ipv4Subnet[]')[i]),
                    'ipv6_subnet': clean_empty_fields(request.form.getlist('ipv6Subnet[]')[i]),
                    'ospfv3': {'area': clean_empty_fields(request.form.getlist('ospfv3Area[]')[i])},
                    'dhcp_enabled': request.form.getlist('dhcpEnabled[]')[i] == 'true',
                    'dhcp_range_start': clean_empty_fields(request.form.getlist('dhcpRangeStart[]')[i]),
                    'dhcp_range_end': clean_empty_fields(request.form.getlist('dhcpRangeEnd[]')[i]),
                    'default_gateway': clean_empty_fields(request.form.getlist('defaultGateway[]')[i]),
                    'dhcpv6_range_start': clean_empty_fields(request.form.getlist('dhcpv6RangeStart[]')[i]),
                    'dhcpv6_range_end': clean_empty_fields(request.form.getlist('dhcpv6RangeEnd[]')[i]),
                    'ipv4_virtual_router_address': clean_empty_fields(request.form.getlist('ipv4VRouter[]')[i]),
                    'ipv6_virtual_router_address': clean_empty_fields(request.form.getlist('ipv6VRouter[]')[i])
                } for i in range(len(request.form.getlist('vlanId[]')))
            ],
            'interfaces': [
                {
                    'name': request.form.getlist('interfaceName[]')[i],
                    'ipv4': clean_empty_fields(request.form.getlist('ipv4[]')[i]),
                    'ipv6': clean_empty_fields(request.form.getlist('ipv6[]')[i]),
                    'mtu': clean_empty_fields(request.form.getlist('mtu[]')[i]) if 'mtu[]' in request.form else None,
                    'switchport_mode': clean_empty_fields(request.form.getlist('switchportMode[]')[i])
                } for i in range(len(request.form.getlist('interfaceName[]')))
            ],
            'routes': {
                'static': [
                    {'prefix': clean_empty_fields(request.form.getlist('staticPrefix[]')[i]),
                     'next_hop': clean_empty_fields(request.form.getlist('staticNextHop[]')[i])}
                    for i in range(len(request.form.getlist('staticPrefix[]')))
                ],
                'ipv6_static': [
                    {'prefix': clean_empty_fields(request.form.getlist('ipv6StaticPrefix[]')[i]),
                     'next_hop': clean_empty_fields(request.form.getlist('ipv6StaticNextHop[]')[i])}
                    for i in range(len(request.form.getlist('ipv6StaticPrefix[]')))
                ]
            },
            'routing_protocols': {
                'ospf': {
                    'id': clean_empty_fields(request.form.get('ospfId')),
                    'networks': [
                        {'prefix': clean_empty_fields(request.form.getlist('ospfNetwork[]')[i]),
                         'area': clean_empty_fields(request.form.getlist('ospfArea[]')[i])}
                        for i in range(len(request.form.getlist('ospfNetwork[]')))
                    ]
                },
                'rip': {
                    'networks': [
                        {'prefix': clean_empty_fields(request.form.getlist('ripNetwork[]')[i])}
                        for i in range(len(request.form.getlist('ripNetwork[]')))
                    ]
                }
            }
        })
        yaml_path = os.path.join(DATA_DEVICES_DIR, f"{device['name']}_access.yaml")

    elif router_type == 'Core':
        device.update({
            'vlans': [
                {
                    'id': request.form.getlist('vlanIdCore[]')[i],
                    'name': clean_empty_fields(request.form.getlist('vlanNameCore[]')[i]),
                    'ipv4_subnet': clean_empty_fields(request.form.getlist('ipv4SubnetCore[]')[i]),
                    'ipv6_subnet': clean_empty_fields(request.form.getlist('ipv6SubnetCore[]')[i]),
                    'ospfv3': {'area': clean_empty_fields(request.form.getlist('ospfv3AreaCore[]')[i])}
                } for i in range(len(request.form.getlist('vlanIdCore[]')))
            ],
            'interfaces': [
                {
                    'name': request.form.getlist('interfaceNameCore[]')[i],
                    'ipv4': clean_empty_fields(request.form.getlist('ipv4Core[]')[i]),
                    'ipv6': clean_empty_fields(request.form.getlist('ipv6Core[]')[i]),
                    'switchport_mode': clean_empty_fields(request.form.getlist('switchportModeCore[]')[i]),
                    'ospfv3_area': clean_empty_fields(request.form.getlist('ospfv3AreaInterfaceCore[]')[i])
                } for i in range(len(request.form.getlist('interfaceNameCore[]')))
            ],
            'routes': {
                'static': [
                    {'prefix': clean_empty_fields(request.form.getlist('staticPrefixCore[]')[i]),
                     'next_hop': clean_empty_fields(request.form.getlist('staticNextHopCore[]')[i])}
                    for i in range(len(request.form.getlist('staticPrefixCore[]')))
                ],
                'ipv6_static': [
                    {'prefix': clean_empty_fields(request.form.getlist('ipv6StaticPrefixCore[]')[i]),
                     'next_hop': clean_empty_fields(request.form.getlist('ipv6StaticNextHopCore[]')[i])}
                    for i in range(len(request.form.getlist('ipv6StaticPrefixCore[]')))
                ]
            },
            'routing_protocols': {
                'ospf': {
                    'id': clean_empty_fields(request.form.get('ospfId')),
                    'networks': [
                        {'prefix': clean_empty_fields(request.form.getlist('ospfNetworkCore[]')[i]),
                         'area': clean_empty_fields(request.form.getlist('ospfAreaCore[]')[i])}
                        for i in range(len(request.form.getlist('ospfNetworkCore[]')))
                    ]
                },
                'ospfv3': {'address_family': 'ipv6', 'redistribute_bgp': 'true'},
                'bgp': {
                    'as': clean_empty_fields(request.form.get('bgpAsCore')),
                    'neighbors': [
                        {'ip': clean_empty_fields(request.form.getlist('neighborIpCore[]')[i]),
                         'remote_as': clean_empty_fields(request.form.getlist('remoteAsCore[]')[i])}
                        for i in range(len(request.form.getlist('neighborIpCore[]')))
                    ],
                    'networks': [
                        clean_empty_fields(request.form.getlist('bgpNetworkPrefixCore[]')[i])
                        for i in range(len(request.form.getlist('bgpNetworkPrefixCore[]')))
                    ]
                }
            }
        })
        yaml_path = os.path.join(DATA_DEVICES_DIR, f"{device['name']}_core.yaml")

    # Save YAML
    with open(yaml_path, "w") as f:
        yaml.dump({'device': device}, f, sort_keys=False)

    # Render .cfg via generator
    try:
        subprocess.run(["python3", SCRIPT_PATH, "--config", yaml_path], cwd=REPO_ROOT, check=True)
    except subprocess.CalledProcessError as e:
        return jsonify({'status':'error','message':f'Generator failed: {e}'}), 500

    # Commit & push (best effort; will silently no-op if nothing to commit)
    subprocess.run(["git", "add", "."], cwd=REPO_ROOT)
    subprocess.run(["git", "commit", "-m", f"add: {device['name']} {router_type} yaml+cfg"], cwd=REPO_ROOT)
    subprocess.run(["git", "push"], cwd=REPO_ROOT)

    return jsonify({"status":"ok","yaml":os.path.basename(yaml_path)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
