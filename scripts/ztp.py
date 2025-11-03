#!/usr/bin/env python3
"""
Zero Touch Provisioning (ZTP) Auto-Push Script
----------------------------------------------
Triggered automatically when a new device is added through the GUI.

Reads device details (name, mgmt_ip, vendor, credentials) from YAMLs
inside /data/devices, waits for each device to become reachable via ping,
then SSHs into it and pushes the generated .cfg from /startup_configs.
"""

import os
import time
import threading
import yaml
import glob
from netmiko import ConnectHandler
from loguru import logger

# === PATH CONFIGURATION ===
BASE_DIR = "/home/student/advanced-netman"
DEVICE_YAML_DIR = f"{BASE_DIR}/data/devices"
CONFIG_DIR = f"{BASE_DIR}/startup_configs"
LOG_FILE = f"{BASE_DIR}/logs/ztp_autopush.log"

PING_INTERVAL = 3  # seconds between ping retries

# === Ensure logs folder exists ===
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logger.add(LOG_FILE, rotation="10 MB", level="INFO", format="{time} | {level} | {message}")

# ---------------------------------------------------------------------

def discover_new_devices():
    """
    Discover all device YAMLs and map them to their generated .cfg files.
    Each YAML is expected to have fields:
      device.name, device.mgmt_ip, device.vendor, device.username, device.password
    """
    devices = {}
    for yaml_file in glob.glob(f"{DEVICE_YAML_DIR}/*.yaml"):
        with open(yaml_file) as f:
            try:
                data = yaml.safe_load(f)
                dev = data.get("device", {})
                name = dev.get("name")
                if not name:
                    continue

                cfg_file = os.path.join(CONFIG_DIR, f"{name}.cfg")
                if not os.path.exists(cfg_file):
                    logger.warning(f"[{name}] Config file not found yet: {cfg_file}")
                    continue

                devices[name] = {
                    "device_type": dev.get("vendor", "arista_eos"),
                    "host": dev.get("mgmt_ip"),
                    "username": dev.get("username", "admin"),
                    "password": dev.get("password", "admin"),
                    "config_file": cfg_file
                }

            except Exception as e:
                logger.error(f"Error reading {yaml_file}: {e}")
    return devices

# ---------------------------------------------------------------------

def is_reachable(ip):
    """Check ping reachability (returns True if host responds)."""
    return os.system(f"ping -c 1 -W 2 {ip} > /dev/null 2>&1") == 0

# ---------------------------------------------------------------------

def push_config(device_name, device_info):
    """SSH into the device and push its generated configuration."""
    cfg_file = device_info["config_file"]
    with open(cfg_file) as f:
        cfg_lines = f.read().splitlines()

    conn_info = {k: v for k, v in device_info.items() if k != "config_file"}
    try:
        logger.info(f"[{device_name}] Connecting to {device_info['host']} ...")
        conn = ConnectHandler(**conn_info)
        conn.enable()
        conn.send_config_set(cfg_lines)
        conn.save_config()
        conn.disconnect()
        logger.success(f"[{device_name}] ✅ Config applied successfully.")
    except Exception as e:
        logger.error(f"[{device_name}] ❌ Failed to push config: {e}")

# ---------------------------------------------------------------------

def ping_and_push(device_name, device_info):
    """Wait until device is reachable, then push configuration."""
    ip = device_info["host"]
    if not ip:
        logger.warning(f"[{device_name}] No management IP found in YAML. Skipping.")
        return

    logger.info(f"[{device_name}] Waiting for {ip} to become reachable...")
    while True:
        if is_reachable(ip):
            logger.info(f"[{device_name}] {ip} is reachable. Beginning config push.")
            push_config(device_name, device_info)
            break
        else:
            logger.info(f"[{device_name}] Not reachable yet. Retrying in {PING_INTERVAL}s...")
            time.sleep(PING_INTERVAL)

# ---------------------------------------------------------------------

def main():
    logger.info("========== ZTP AUTOPUSH STARTED ==========")
    devices = discover_new_devices()

    if not devices:
        logger.warning("No devices found in data/devices.")
        return

    threads = []
    for name, info in devices.items():
        t = threading.Thread(target=ping_and_push, args=(name, info))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    logger.success("========== ZTP CONFIGURATION COMPLETE ==========")

# ---------------------------------------------------------------------

if __name__ == "__main__":
    main()
