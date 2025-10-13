# scripts/ping_webserver.py
#!/usr/bin/env python3
import argparse, csv, sys
from netmiko import ConnectHandler

def read_csv(csv_path):
    devices = []
    with open(csv_path) as f:
        r = csv.DictReader(f)
        # Accept either "Device" or "Routers" as the device name column
        name_col = "Device" if "Device" in r.fieldnames else ("Routers" if "Routers" in r.fieldnames else None)
        if not name_col:
            print("CSV must have a 'Device' or 'Routers' header.", file=sys.stderr); sys.exit(2)

        for row in r:
            devices.append({
                "name": row[name_col],
                "device_type": row.get("Device_Type","arista_eos").strip() or "arista_eos",
                "ip": row["IP"].strip(),
                "username": row["Username"].strip(),
                "password": row["Password"].strip(),
            })
    return devices

def ping_eos(net_connect, dst):
    # EOS: 'ping <ip> count 2'
    out = net_connect.send_command(f"ping {dst}", expect_string=r"#")
    ok = (" 0% packet loss" in out) or (" 0% loss" in out) or (" 2 received" in out)
    return ok, out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to sshInfo.csv")
    ap.add_argument("--dst", default="1.1.1.2", help="Destination IP to ping (default 1.1.1.2)")
    args = ap.parse_args()

    devs = read_csv(args.csv)
    print(f"Ping destination: {args.dst}\nDevices found: {len(devs)}\n")

    all_ok = True
    for d in devs:
        print(f"--- {d['name']} ({d['ip']}) ---")
        device = {
            "device_type": d["device_type"],
            "ip": d["ip"],
            "username": d["username"],
            "password": d["password"],
        }
        try:
            nc = ConnectHandler(**device)
            nc.enable()
            ok, output = ping_eos(nc, args.dst)
            nc.disconnect()
            print(output.strip())
            print(f"RESULT: {'SUCCESS' if ok else 'FAIL'}\n")
            all_ok = all_ok and ok
        except Exception as e:
            print(f"ERROR: {e}\n")
            all_ok = False

    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
