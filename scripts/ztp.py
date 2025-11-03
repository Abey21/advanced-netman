#!/usr/bin/env python3
"""
ZTP (Zero Touch Provisioning) – Safe Preview Version
----------------------------------------------------
Pushes configs from generated-configs to Arista devices.

✅ Only merges configuration (does NOT erase).
✅ Shows full CLI output for each command pushed.
✅ Waits until device is reachable before connecting.
"""

import os
import time
import threading
from netmiko import ConnectHandler
from loguru import logger

# === Paths ===
BASE_DIR = "/home/student/advanced-netman"
CONFIG_DIR = f"{BASE_DIR}/generated-configs"
LOG_FILE = f"{BASE_DIR}/logs/ztp_preview.log"
PING_INTERVAL = 3  # seconds

# === Logging Setup ===
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logger.add(LOG_FILE, rotation="10 MB", level="INFO", format="{time} | {level} | {message}")

# === Manual Device Definitions ===
DEVICES = {
    "R8": {
        "device_type": "arista_eos",
        "host": "10.100.0.17",          # Management IP of R8
        "username": "admin",
        "password": "admin",
        "config_file": f"{CONFIG_DIR}/R8.cfg"
    },
    # Example for future:
    # "R9": {
    #     "device_type": "arista_eos",
    #     "host": "10.100.0.18",
    #     "username": "admin",
    #     "password": "admin",
    #     "config_file": f"{CONFIG_DIR}/R9.cfg"
    # }
}

# ------------------------------------------------------------
def is_reachable(ip):
    """Check if device responds to ping."""
    return os.system(f"ping -c 1 -W 2 {ip} > /dev/null 2>&1") == 0

# ------------------------------------------------------------
def push_config(device_name, device_info):
    """SSH into device and safely apply config while printing output."""
    ip = device_info["host"]
    cfg_file = device_info["config_file"]

    if not os.path.exists(cfg_file):
        logger.error(f"[{device_name}] Config file not found: {cfg_file}")
        return

    try:
        logger.info(f"[{device_name}] Connecting to {ip} ...")
        conn = ConnectHandler(
            device_type=device_info["device_type"],
            host=ip,
            username=device_info["username"],
            password=device_info["password"]
        )
        conn.enable()

        # Read the config file
        with open(cfg_file) as f:
            cfg_lines = f.read().splitlines()

        logger.info(f"[{device_name}] Sending configuration lines...")
        output = conn.send_config_set(cfg_lines, exit_config_mode=False)
        print(f"\n=== CLI Output for {device_name} ({ip}) ===\n")
        print(output)
        print("==========================================\n")

        conn.exit_config_mode()
        conn.save_config()
        conn.disconnect()

        logger.success(f"[{device_name}] ✅ Config applied successfully (check console for details).")

    except Exception as e:
        logger.error(f"[{device_name}] ❌ Failed to push config: {e}")

# ------------------------------------------------------------
def ztp_worker(device_name, device_info):
    """Wait for device reachability and push config."""
    ip = device_info["host"]
    logger.info(f"[{device_name}] Waiting for {ip} to become reachable...")

    while True:
        if is_reachable(ip):
            logger.info(f"[{device_name}] {ip} is reachable. Starting config push.")
            push_config(device_name, device_info)
            break
        else:
            logger.info(f"[{device_name}] Not reachable yet. Retrying in {PING_INTERVAL}s...")
            time.sleep(PING_INTERVAL)

# ------------------------------------------------------------
def main():
    logger.info("========== ZTP SAFE PREVIEW STARTED ==========")

    threads = []
    for name, info in DEVICES.items():
        t = threading.Thread(target=ztp_worker, args=(name, info))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    logger.success("========== ZTP CONFIGURATION COMPLETE ==========")

# ------------------------------------------------------------
if __name__ == "__main__":
    main()
