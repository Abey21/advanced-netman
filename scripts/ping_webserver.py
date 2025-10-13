#!/usr/bin/env python3
import argparse
import csv
import os
from loguru import logger
from netmiko import ConnectHandler
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException

def read_devices(csv_path):
    devices = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            devices.append({
                "name": row["Device"].strip(),
                "ip": row["IP"].strip(),
                "username": row["Username"].strip(),
                "password": row["Password"].strip(),
                "device_type": row.get("Device_Type", "arista_eos").strip() or "arista_eos",
            })
    return devices

def send_eos_ping(conn, dst, vrf=None, count=3):
    """
    Try EOS ping syntax. Prefer `ping vrf <vrf> <dst> count <n>` if vrf provided,
    else `ping <dst> count <n>`. Returns (ok: bool, output: str).
    """
    cmds = []
    if vrf:
        cmds.append(f"ping vrf {vrf} {dst}")
    cmds.append(f"ping {dst}")  # fallback without VRF

    last_out = ""
    for cmd in cmds:
        try:
            out = conn.send_command(cmd, expect_string=r"#", strip_prompt=False, strip_command=False)
            last_out = out or ""
            # consider success if we see any echo replies or 0% packet loss or "bytes from"
            text = out.lower()
            if " 0% packet loss" in text or "bytes from" in text or " 0.0% packet loss" in text:
                return True, out
            # Some EOS prints success lines like "5 packets transmitted, 5 received"
            if " packets transmitted" in text and " received" in text and "0% packet loss" in text:
                return True, out
            # If command itself was invalid, try next syntax
            if "% invalid input" in text or "usage:" in text:
                continue
            # If we got proper output but not success, treat as failure
            return False, out
        except Exception as e:
            last_out = str(e)

    return False, last_out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to sshInfo.csv")
    ap.add_argument("--dst", default="1.1.1.2", help="Destination to ping")
    ap.add_argument("--count", type=int, default=3, help="Ping count")
    ap.add_argument("--vrf", default=os.environ.get("JENKINS_PING_VRF", ""), help="VRF name (e.g., mgmt)")
    args = ap.parse_args()

    devices = read_devices(args.csv)
    print(f"\nPing destination: {args.dst}")
    print(f"Devices found: {len(devices)}\n")

    any_fail = False

    for d in devices:
        name = d["name"]
        ip   = d["ip"]
        print(f"--- {name} ({ip}) ---")
        dev = {
            "device_type": d["device_type"],
            "ip": ip,
            "username": d["username"],
            "password": d["password"],
        }
        try:
            conn = ConnectHandler(**dev)
            conn.enable()
            ok, out = send_eos_ping(conn, args.dst, vrf=(args.vrf or None), count=args.count)
            print(out.strip() if out else "(no output)")
            if ok:
                print("RESULT: PASS\n")
            else:
                print("RESULT: FAIL\n")
                any_fail = True
            conn.disconnect()
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
            print(f"RESULT: FAIL (SSH error: {e})\n")
            any_fail = True
        except Exception as e:
            print(f"RESULT: FAIL (Unexpected error: {e})\n")
            any_fail = True

    # Non-zero exit if any device failed (so Jenkins marks build red)
    if any_fail:
        exit(1)

if __name__ == "__main__":
    main()
