#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from art import text2art
from loguru import logger
from InquirerPy import prompt
from rich.console import Console
from rich.table import Table
from termcolor import colored
from netmiko import ConnectHandler
import csv
import re
import os
import sys
from typing import Dict, Any

console = Console()

CSV_PATH = os.environ.get(
    "SSHINFO_CSV",
    os.path.expanduser("~/advanced-netman/data/ssh/sshInfo.csv")
)

def load_ssh_info(csv_file: str) -> Dict[str, Dict[str, str]]:
    """
    Reads CSV with header: Device,IP,Username,Password,Device_Type
    Returns dict keyed by Device.
    """
    data: Dict[str, Dict[str, str]] = {}
    try:
        with open(csv_file, "r", newline="") as f:
            reader = csv.DictReader(f)
            required = {"Device", "IP", "Username", "Password", "Device_Type"}
            if set(reader.fieldnames or []) != required:
                console.print(
                    f"[bold red]CSV header must be exactly: {','.join(sorted(required))}[/bold red]"
                )
                sys.exit(2)
            for row in reader:
                dev = row["Device"].strip()
                if not dev:
                    continue
                data[dev] = {
                    "IP": row["IP"].strip(),
                    "Username": row["Username"].strip(),
                    "Password": row["Password"].strip(),
                    "Device_Type": row["Device_Type"].strip() or "arista_eos",
                }
        if not data:
            console.print("[bold red]No rows found in CSV.[/bold red]")
            sys.exit(2)
        return data
    except FileNotFoundError:
        console.print(f"[bold red]CSV not found: {csv_file}[/bold red]")
        sys.exit(2)
    except Exception as e:
        console.print(f"[bold red]Failed reading CSV: {e}[/bold red]")
        sys.exit(2)

def connect(ip: str, username: str, password: str, device_type: str) -> Any:
    """
    Establish Netmiko connection. For EOS, device_type='arista_eos'.
    """
    params = {
        "device_type": device_type,
        "ip": ip,
        "username": username,
        "password": password,
        # EOS usually doesn’t need separate secret; enable() works with login creds
        "fast_cli": False,
        "global_delay_factor": 1,
        "session_log": os.path.expanduser(
            f"~/advanced-netman/logs/netmiko/health_{ip}.log"
        ),
    }
    os.makedirs(os.path.dirname(params["session_log"]), exist_ok=True)
    return ConnectHandler(**params)

def run_cmd(nc, cmd: str) -> str:
    try:
        # EOS: many commands okay with send_command; use enable() first for show
        nc.enable()
    except Exception:
        pass
    return nc.send_command(cmd, strip_prompt=False, strip_command=False)

def extract_cpu_sy(cpu_line: str) -> str:
    """
    Expects something like:
    %Cpu(s):  3.2 us,  5.6 sy,  ...
    Returns '5.6%' if found else 'N/A'.
    """
    m = re.search(r'(\d+(?:\.\d+)?)\s+sy', cpu_line)
    return f"{m.group(1)}%" if m else "N/A"

def health_check_one(dev_name: str, meta: Dict[str, str]) -> None:
    ip = meta["IP"]; user = meta["Username"]; pw = meta["Password"]; dtype = meta["Device_Type"] or "arista_eos"
    console.rule(f"[bold cyan]Health Check for {dev_name} ({ip})[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check")
    table.add_column("Result")

    try:
        logger.info(f"Connecting to {dev_name} {ip} as {user}")
        nc = connect(ip, user, pw, dtype)

        # CPU
        # Works on EOS: 'show processes top once' shows CPU line
        cpu_raw = run_cmd(nc, "show processes top once | grep Cpu")
        cpu_sy = extract_cpu_sy(cpu_raw)
        table.add_row("CPU (sy%)", cpu_sy)

        # OSPF neighbors (EOS classic)
        ospf = run_cmd(nc, "show ip ospf neighbor")
        # Quick parse: Neighbor ID + State + Interface lines
        neigh_lines = []
        for line in ospf.splitlines():
            m = re.search(r'(\d+\.\d+\.\d+\.\d+).+?\s+(\S+)\s+(\S+)$', line.strip())
            # fallback to simple include of FULL lines
            if "FULL" in line or "2WAY" in line or "DOWN" in line:
                neigh_lines.append(line.strip())
            elif m:
                neigh_lines.append(f"{m.group(1)}  {m.group(2)}  {m.group(3)}")
        table.add_row("OSPF Neighborships", "\n".join(neigh_lines) or "None")

        # BGP summary (if used)
        bgp = run_cmd(nc, "show ip bgp summary")
        table.add_row("BGP Summary", bgp.strip() or "None")

        # Route table (show a slice to keep output compact)
        routes = run_cmd(nc, "show ip route")
        if "Gateway of last resort" in routes:
            start = routes.find("Gateway of last resort")
            routes = routes[start:]
        table.add_row("Route Table (tail)", routes.strip()[:1500] or "None")

        # Ping mgmt gateway-ish (adjust as needed)
        ping = run_cmd(nc, "ping 1.1.1.2")
        table.add_row("IP Connectivity (ping 8.8.8.8)", ping.strip() or "No output")

        console.print(table)

        try:
            nc.disconnect()
        except Exception:
            pass

    except Exception as e:
        table.add_row("ERROR", str(e))
        console.print(table)

def main():
    # Title
    title = text2art("NetHealth", font="doom")
    print(title)
    print(colored("Health checks for EOS devices\n", "cyan"))

    ssh = load_ssh_info(CSV_PATH)
    devices = list(ssh.keys()) + ["Quit"]

    while True:
        answers = prompt([
            {
                "type": "list",
                "name": "choice",
                "message": "Choose device to check (or Quit):",
                "choices": devices
            }
        ])
        choice = answers["choice"]
        if choice == "Quit":
            console.print("\n[bold yellow]Bye![/bold yellow]\n")
            break
        health_check_one(choice, ssh[choice])

if __name__ == "__main__":
    main()
