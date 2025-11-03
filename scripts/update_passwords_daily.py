#!/usr/bin/env python3

import csv
import time
import secrets
from pathlib import Path
from loguru import logger
from netmiko import ConnectHandler

CSV_PATH = Path("/home/student/advanced-netman/data/ssh/sshInfo.csv")

def generatePassword():
    # ~16 chars, URL-safe
    return secrets.token_urlsafe(12)

def load_credentials(csv_path: Path):
    """Return a list of device rows from the CSV."""
    devices = []
    with csv_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"Device","IP","Username","Password","Device_Type"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise RuntimeError(f"CSV must have headers: {sorted(required)}")
        for row in reader:
            devices.append(row)
    return devices

def updatePasswordFile(csv_path: Path, ip: str, new_password: str):
    """Update the password for matching IP in the CSV."""
    with csv_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    for r in rows:
        if r["IP"] == ip:
            r["Password"] = new_password

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def connectRouter(eos):
    """Connect to a router and return the connection object."""
    try:
        # Netmiko will detect the prompt; no custom expect pattern needed.
        net_connect = ConnectHandler(**eos)
        logger.info(f"Connected to {eos['host']} as {eos['username']}")
        return net_connect
    except Exception as e:
        logger.error(f"Unable to connect to {eos['host']} as {eos['username']}: {e}")
        return None

def updatePassword(net_connect, ip, username, password):
    """Send the EOS command to update the password, then save config."""
    try:
        net_connect.enable()
        # EOS syntax (no 'secret 0'):
        cmds = [f"username {username} secret {password}"]
        out = net_connect.send_config_set(cmds)
        logger.info(f"{ip}: config response:\n{out}")

        # Save config (EOS supports save_config in Netmiko; fallback if needed)
        try:
            save_out = net_connect.save_config()
        except Exception:
            save_out = net_connect.send_command_timing("write memory")
        logger.info(f"{ip}: saved config:\n{save_out}")

        return True
    except Exception as e:
        logger.error(f"Unable to configure password on {ip}: {e}")
        return False
    finally:
        try:
            net_connect.disconnect()
        except Exception:
            pass

def main():
    logger.add(
        "/home/student/advanced-netman/data/ssh/update_passwords.log",
        level="INFO", rotation="10 MB", retention=5, enqueue=True
    )

    if not CSV_PATH.exists():
        logger.error(f"CSV not found: {CSV_PATH}")
        return

    while True:
        devices = load_credentials(CSV_PATH)

        for row in devices:
            ip = row["IP"]
            username = row["Username"]
            current_pw = row["Password"]
            device_type = (row.get("Device_Type") or "arista_eos").strip()

            eos = {
                "device_type": device_type,   # arista_eos
                "host": ip,
                "username": username,
                "password": current_pw,
                # If devices are slow, you can bump this:
                "global_delay_factor": 1.0,
            }

            net_connect = connectRouter(eos)
            if not net_connect:
                continue

            new_password = generatePassword()
            if updatePassword(net_connect, ip, username, new_password):
                updatePasswordFile(CSV_PATH, ip, new_password)
                logger.success(f"Password updated on {ip} and CSV refreshed.")
            else:
                logger.error(f"Password update failed on {ip}.")

        logger.info("\nWaiting 1 day before the next update...\n")
        time.sleep(86400)  # 24 hours

if __name__ == "__main__":
    main()
