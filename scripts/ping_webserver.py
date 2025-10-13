#!/usr/bin/env python3
"""
Ping a destination from each device listed in a CSV (sshInfo.csv), via SSH to Arista EOS.
- Prints per-device results
- Writes a summary report to artifacts/ping_report.txt
- Exits 0 if all pass; exits 1 if any fail (so Jenkins can mark UNSTABLE instead of FAIL)

CSV headers expected:
Device,IP,Username,Password,Device_Type

Example run:
  python3 scripts/ping_webserver.py --csv data/ssh/sshInfo.csv --dst 1.1.1.2 --count 5 --exclude S1,S2
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import List, Dict

from loguru import logger
from netmiko import ConnectHandler
from netmiko.ssh_exception import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
)

def read_devices(csv_path: str) -> List[Dict[str, str]]:
    devices = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            devices.append({
                "name": row["Device"].strip(),
                "ip": row["IP"].strip(),
                "username": row["Username"].strip(),
                "password": row["Password"].strip(),
                "device_type": (row.get("Device_Type") or "arista_eos").strip() or "arista_eos",
            })
    return devices

def filter_devices(devices, include_list: str = "", exclude_list: str = ""):
    if include_list:
        inc = {d.strip() for d in include_list.split(",") if d.strip()}
        devices = [d for d in devices if d["name"] in inc]
    if exclude_list:
        exc = {d.strip() for d in exclude_list.split(",") if d.strip()}
        devices = [d for d in devices if d["name"] not in exc]
    return devices

def eos_ping(net_connect: ConnectHandler, dst: str, count: int) -> str:
    """
    Use EOS bash ping for consistent output (works on vEOS).
    """
    cmd = f"bash ping -c {count} {dst}"
    # Enter enable first (safe even if not needed)
    net_connect.enable()
    output = net_connect.send_command(cmd, expect_string=r"#", read_timeout=60)
    return output.strip()

def ping_from_device(dev: Dict[str, str], dst: str, count: int, logs_dir: Path) -> bool:
    """
    SSH to the device, run ping, log output, return True/False.
    """
    session_log = logs_dir / f"{dev['name']}.log"
    device = {
        "device_type": dev["device_type"],
        "ip": dev["ip"],
        "username": dev["username"],
        "password": dev["password"],
        "session_log": str(session_log),
        # Conservative delays to avoid prompt timing issues
        "fast_cli": False,
        "global_delay_factor": 1.0,
        "conn_timeout": 20,
    }
    try:
        logger.info(f"Connecting to {dev['name']} ({dev['ip']}) as {dev['username']}")
        with ConnectHandler(**device) as nc:
            out = eos_ping(nc, dst=dst, count=count)
    except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
        print(f"--- {dev['name']} ({dev['ip']}) ---")
        print(f"{type(e).__name__}: {e}")
        print("RESULT: FAIL\n")
        return False
    except Exception as e:
        print(f"--- {dev['name']} ({dev['ip']}) ---")
        print(f"ERROR: {e}")
        print("RESULT: FAIL\n")
        return False

    # Print raw output and a quick verdict based on “packet loss”
    print(f"--- {dev['name']} ({dev['ip']}) ---")
    print(out)
    ok = " 0% packet loss" in out or " 0% packet loss," in out
    print(f"RESULT: {'SUCCESS' if ok else 'FAIL'}\n")
    return ok

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to sshInfo.csv")
    ap.add_argument("--dst", default="1.1.1.2", help="Destination to ping")
    ap.add_argument("--count", type=int, default=5, help="Ping count per device")
    ap.add_argument("--include", default="", help="Comma-separated device names to include")
    ap.add_argument("--exclude", default=os.environ.get("PING_EXCLUDE", ""), help="Comma-separated device names to exclude")
    args = ap.parse_args()

    # prepare artifacts directory for report + logs
    artifacts_dir = Path("artifacts")
    logs_dir = artifacts_dir / "netmiko"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    devices = read_devices(args.csv)
    devices = filter_devices(devices, include_list=args.include, exclude_list=args.exclude)

    print(f"\nPing destination: {args.dst}")
    print(f"Devices found: {len(devices)}\n")

    results = []
    for dev in devices:
        ok = ping_from_device(dev, dst=args.dst, count=args.count, logs_dir=logs_dir)
        results.append((dev["name"], dev["ip"], ok))

    # Summary + exit code
    passed = sum(1 for _, _, ok in results if ok)
    failed = sum(1 for _, _, ok in results if not ok)
    summary_lines = [
        f"Destination: {args.dst}",
        f"Devices tested: {len(results)}",
        f"Passed: {passed}",
        f"Failed: {failed}",
        "",
        "Failures:" if failed else "All devices passed.",
    ]
    if failed:
        for name, ip, ok in results:
            if not ok:
                summary_lines.append(f"- {name} ({ip})")

    report_path = artifacts_dir / "ping_report.txt"
    report_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print("\n=== Summary ===")
    print("\n".join(summary_lines))

    # Exit 0 if all success, 1 if any failure (Jenkins will mark UNSTABLE instead of FAIL)
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
