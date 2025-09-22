#!/usr/bin/env python3
import yaml
from jinja2 import Environment, FileSystemLoader
import argparse, os, sys, ipaddress

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Device configuration templates (NOT Flask HTML):
DEVICE_TPL_DIR = os.path.join(REPO_ROOT, "gui", "jinja")

# Where rendered device configs will be written:
OUTPUT_DIR = os.path.join(REPO_ROOT, "generated-configs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def cidr_to_net_wild(s: str):
    """
    Accepts either CIDR ('10.0.0.0/8') or 'ip wildcard' ('10.0.0.0 0.255.255.255').
    Returns (network, wildcard) or ("", None) if input was empty.
    """
    if not s:
        return "", None
    if " " in s and "/" not in s:
        net, wild = s.split()
        return net, wild
    try:
        net = ipaddress.IPv4Network(s, strict=False)
        inv = ipaddress.IPv4Address(int(net.hostmask))
        return str(net.network_address), str(inv)
    except Exception:
        # If input is IPv6 or malformed, return raw and let template handle it.
        return s, None

def add_helpers(env: Environment):
    def ospf_net(stmt):
        """Jinja filter to normalize OSPF network statements safely."""
        if not stmt:
            return ""
        n, w = cidr_to_net_wild(stmt)
        return f"{n} {w}" if w else n
    env.filters["ospf_net"] = ospf_net
    return env

def normalize_vendor(v):
    v = (v or "").lower()
    if "arista" in v or "eos" in v:
        return "eos"
    if "cisco" in v or "ios" in v:
        return "ios"
    if "juniper" in v or "junos" in v:
        return "junos"
    return None  # falls back to generic templates

def choose_template(env, vendor, dev_type):
    """
    Try vendorized name first (e.g., eos_access.j2), then generic (access.j2/core.j2).
    """
    candidates = []
    if vendor:
        candidates.append(f"{vendor}_{dev_type}.j2")
    candidates.append(f"{dev_type}.j2")

    last_err = None
    for name in candidates:
        try:
            return env.get_template(name), name
        except Exception as e:
            last_err = e
    raise SystemExit(
        f"No matching template found. Tried: {', '.join(candidates)} in {DEVICE_TPL_DIR}\n"
        f"Last error: {last_err}"
    )

def main():
    ap = argparse.ArgumentParser(description="Render device config from YAML + Jinja2.")
    ap.add_argument("--config", required=True,
                    help="Path to YAML (e.g., data/devices/R1_access.yaml)")
    args = ap.parse_args()

    yaml_path = os.path.abspath(args.config)
    if not os.path.exists(yaml_path):
        sys.exit(f"YAML not found: {yaml_path}")

    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}

    device = data.get("device", {})
    base = os.path.splitext(os.path.basename(yaml_path))[0]
    if "_" not in base:
        sys.exit("YAML filename must be <name>_<type>.yaml (e.g., R1_access.yaml)")
    name, dev_type = base.split("_", 1)
    dev_type = dev_type.lower()
    vendor = normalize_vendor(device.get("vendor"))

    env = Environment(loader=FileSystemLoader(DEVICE_TPL_DIR),
                      trim_blocks=True, lstrip_blocks=True)
    env = add_helpers(env)

    tpl, tpl_name = choose_template(env, vendor, dev_type)
    rendered = tpl.render(data)

    out_name = f"{device.get('name', name)}.cfg"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    with open(out_path, "w") as f:
        f.write(rendered)

    print(f"[ok] wrote {out_path} using {tpl_name}")

if __name__ == "__main__":
    main()
