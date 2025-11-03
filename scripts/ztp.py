#!/usr/bin/env python3
"""
Dynamic Zero-Touch Provisioning (ZTP)
------------------------------------
Discovers all generated configs in folder,
pings devices until reachable, pushes configs,
and handles R8 special initialization.
"""

import os
import time
import threading
from netmiko import ConnectHandler
from loguru import logger
import glob

# === PATHS ===
BASE_DIR = "/home/student/advanced-netman"
CONFIG_FOLDER = f"{BASE_DIR}/generated-configs"      # or "startup_configs" if that’s your GUI output
LOG_FILE = f"{BASE_DIR}/logs/ztp_dynamic.log"

# === CREDS ===
USERNAME = "admin"
PASSWORD = "admin"
DEVICE_TYPE = "arista_eos"
PING_INTERVAL = 3

# === LOGGER ===
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logger.add(LOG_FILE, rotation="10 MB", level="INFO", format="{time} | {level} | {message}")

# ----------------------------------------------------------------------

def discover_devices():
    """
    Auto-discover .cfg files in CONFIG_FOLDER
    and build a device map.
    Filename should match device name (R6.cfg, R7.cfg, R8.cfg, etc.)
    """
    device_map = {}
    cfg_files = glob.glob(f"{CONFIG_FOLDER}/*.cfg")
    if not cfg_files:
        logger.warning(f"No config files found in {CONFIG_FOLDER}")
        return device_map

    for cfg in cfg_files:
        name = os.path.basename(cfg).split(".")[0]
        device_map[name] = {
            "device_type": DEVICE_TYPE,
            "username": USERNAME,
            "password": PASSWORD,
            "host": None,         # to be discovered dynamically
            "config_file": cfg
        }
    logger.info(f"Discovered {len(device_map)} config files: {list(device_map.keys())}")
    return device_map

# ----------------------------------------------------------------------

def is_reachable(ip):
    """Check if IP responds to ping."""
    return os.system(f"ping -c 1 -W 2 {ip} > /dev/null 2>&1") == 0

# ----------------------------------------------------------------------

def push_config(device_info, config_commands):
    """Connect and push configuration."""
    conn_info = {k: v for k, v in device_info.items() if k != "config_file"}
    connection = ConnectHandler(**conn_info)
    connection.enable()
    try:
        connection.send_config_set(config_commands)
        connection.save_config()
        logger.success(f"[{device_info['host']}] ✅ Configuration applied successfully.")
    except Exception as e:
        logger.error(f"[{device_info['host']}] ❌ Error applying config: {e}")
    finally:
        connection.disconnect()
        logger.info(f"Disconnected from {device_info['host']}.")

# ----------------------------------------------------------------------

def setup_r8(device_info):
    """Special setup for R8: assign IP to Ethernet1 before config push."""
    try:
        conn_info = {k: v for k, v in device_info.items() if k != "config_file"}
        connection = ConnectHandler(**conn_info)
        connection.enable()
        logger.info("[R8] Performing Ethernet1 setup...")
        connection.send_config_set([
            "interface Ethernet1",
            "no switchport",
            "ip address 192.51.0.10/30",
            "no shutdown"
        ])
        connection.save_config()
        connection.disconnect()
        logger.success("[R8] Initial interface configuration complete.")
    except Exception as e:
        logger.error(f"[R8] Setup failed: {e}")

# ----------------------------------------------------------------------

def ping_until_reachable(device_name, device_info):
    """Ping until reachable, then push config."""
    cfg_path = device_info["config_file"]
    with open(cfg_path) as f:
        config_commands = f.read().splitlines()

    # Define scan range (management subnet)
    mgmt_prefix = "10.100.0."
    possible_ips = [f"{mgmt_prefix}{i}" for i in range(10, 51)]

    while True:
        for ip in possible_ips:
            if is_reachable(ip):
                logger.info(f"{ip} responded — testing connection for {device_name}...")
                try:
                    # Try connecting; check hostname to verify
                    conn = ConnectHandler(
                        device_type=DEVICE_TYPE,
                        host=ip,
                        username=USERNAME,
                        password=PASSWORD
                    )
                    hostname_out = conn.send_command("show hostname").strip()
                    conn.disconnect()

                    if device_name.lower() in hostname_out.lower():
                        logger.info(f"Verified {device_name} at {ip}")
                        device_info["host"] = ip
                        if device_name == "R8":
                            setup_r8(device_info)
                        push_config(device_info, config_commands)
                        return
                    else:
                        logger.info(f"{ip} is {hostname_out}, not {device_name} — skipping.")
                except Exception as e:
                    logger.debug(f"SSH failed for {ip}: {e}")
        logger.info(f"{device_name} not found yet — retrying in {PING_INTERVAL}s...")
        time.sleep(PING_INTERVAL)

# ----------------------------------------------------------------------

def main():
    logger.info("========== ZTP SERVICE STARTED ==========")
    devices = discover_devices()
    if not devices:
        return

    threads = []
    for name, info in devices.items():
        t = threading.Thread(target=ping_until_reachable, args=(name, info))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    logger.success("========== ZTP CONFIGURATION COMPLETE ==========")

# ----------------------------------------------------------------------

if __name__ == "__main__":
    main()
