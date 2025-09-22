#!/usr/bin/env python3
"""
Save Golden Configs with timestamped filenames.

Reads device credentials from CSV (supports 'Device' or 'Routers' for the name column):
  ~/advanced-netman/data/ssh/sshInfo.csv

Columns accepted (synonyms in parentheses):
  - Device (Routers, Name)
  - IP
  - Username (User)
  - Password (Passwd)
  - Device_Type (Platform, Vendor)

Netmiko device_type examples:
  arista_eos, cisco_ios, juniper, juniper_junos
"""

import csv
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from netmiko import ConnectHandler
except Exception as e:
    raise SystemExit(
        "Netmiko is not installed in this Python environment.\n"
        "Activate your venv and install it:\n"
        "  source ~/advanced-netman/gui/.venv/bin/activate\n"
        "  pip install netmiko paramiko scp\n"
    ) from e

# ---------- paths ----------
REPO_ROOT = Path.home() / "advanced-netman"
CSV_PATH  = REPO_ROOT / "data" / "ssh" / "sshInfo.csv"
OUT_ROOT  = REPO_ROOT / "golden-configs"

# ---------- logging ----------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("golden")

# ---------- per-vendor commands ----------
SHOW_CMDS = {
    "arista_eos": {
        "prep": ["terminal length 0"],
        "run":  "show running-config",
    },
    "cisco_ios": {
        "prep": ["terminal length 0"],
        "run":  "show running-config",
    },
    "juniper": {
        "prep": ["set cli screen-length 0"],
        "run":  "show configuration | display set",
    },
    "juniper_junos": {
        "prep": ["set cli screen-length 0"],
        "run":  "show configuration | display set",
    },
}

# ---------- header normalization ----------
HEADER_MAP = {
    "device": "Device",
    "routers": "Device",
    "name": "Device",

    "ip": "IP",

    "username": "Username",
    "user": "Username",

    "password": "Password",
    "passwd": "Password",

    "device_type": "Device_Type",
    "platform": "Device_Type",
    "vendor": "Device_Type",
}

REQUIRED = {"Device", "IP", "Username", "Password", "Device_Type"}


def normalize_headers(headers: List[str]) -> List[str]:
    out: List[str] = []
    for h in headers:
        key = h.strip().lower()
        out.append(HEADER_MAP.get(key, h.strip()))
    return out


def load_devices(csv_path: Path) -> Dict[str, Dict[str, str]]:
    """
    Read CSV safely in text mode, normalize headers, and build a device dict:
      { "R1": {"IP": "...", "Username": "...", "Password": "...", "Device_Type": "..."} }
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    devices: Dict[str, Dict[str, str]] = {}

    # Read file as text and parse with csv.reader (returns lists of strings)
    with csv_path.open("r", newline="") as f:
        reader = csv.reader(f)
        rows = [row for row in reader if any(col.strip() for col in row)]  # skip empty lines

    if not rows:
        log.warning("CSV is empty.")
        return devices

    headers = normalize_headers(rows[0])

    # Validate headers
    present = set(headers)
    missing = REQUIRED - present
    if missing:
        log.warning(f"CSV missing expected columns: {missing}. Will try to proceed.")

    # Build row dicts by zipping normalized headers with each row
    for raw in rows[1:]:
        row = {headers[i]: (raw[i].strip() if i < len(raw) else "") for i in range(len(headers))}

        name = row.get("Device", "").strip() or row.get("Routers", "").strip()
        if not name:
            continue

        devices[name] = {
            "IP":          row.get("IP", ""),
            "Username":    row.get("Username", ""),
            "Password":    row.get("Password", ""),
            "Device_Type": row.get("Device_Type", ""),
        }

    return devices


def fetch_running_config(name: str, meta: Dict[str, str]) -> str:
    dtype = meta["Device_Type"]
    ip    = meta["IP"]
    user  = meta["Username"]
    pwd   = meta["Password"]

    if not dtype or not ip or not user:
        raise ValueError(f"{name}: missing critical fields (Device_Type/IP/Username).")

    cmds = SHOW_CMDS.get(dtype)
    if not cmds:
        raise ValueError(f"{name}: unsupported device_type '{dtype}'")

    device = {
        "device_type": dtype,
        "host": ip,
        "username": user,
        "password": pwd,
        "fast_cli": False,
        "timeout": 60,
    }

    log.info(f"[{name}] connecting to {ip} ({dtype})")
    with ConnectHandler(**device) as conn:
        try:
            conn.enable()
        except Exception:
            pass

        for p in cmds["prep"]:
            try:
                conn.send_command_timing(p)
            except Exception:
                pass

        output = conn.send_command(cmds["run"], read_timeout=90)

    if not output or not output.strip():
        raise RuntimeError(f"{name}: empty configuration received")
    return output


def save_config(device: str, text: str, out_root: Path) -> Path:
    now = datetime.now(timezone.utc)
    day_dir = out_root / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    stamp = now.strftime("%Y%m%d-%H%M%SZ")
    path  = day_dir / f"{device}_{stamp}.cfg"
    path.write_text(text, encoding="utf-8")
    return path


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Golden Config backup with timestamped filenames.")
    ap.add_argument("--csv", default=str(CSV_PATH), help="Path to sshInfo.csv")
    ap.add_argument("--outdir", default=str(OUT_ROOT), help="Output root directory")
    ap.add_argument("--only", nargs="*", help="Only these device names (space-separated)")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    out_root = Path(args.outdir)

    try:
        devices = load_devices(csv_path)
    except Exception as e:
        log.error(e)
        return

    if not devices:
        log.error("No devices loaded. Check your CSV path and contents.")
        return

    target = set(args.only or devices.keys())

    for name, meta in devices.items():
        if name not in target:
            continue
        try:
            cfg = fetch_running_config(name, meta)
            out = save_config(name, cfg, out_root)
            log.info(f"[{name}] saved -> {out}")
        except Exception as e:
            log.error(f"[{name}] failed: {e}")


if __name__ == "__main__":
    main()
