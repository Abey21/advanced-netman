# scripts/test_netman.py
import unittest
from netmiko import ConnectHandler
from scripts.health_check import CSV_PATH, load_ssh_info, extract_cpu_sy

class TestDeviceHealthChecks(unittest.TestCase):
    def setUp(self):
        # Load device info from CSV via your existing loader
        self.devices = load_ssh_info(str(CSV_PATH))
        self.assertIsNotNone(self.devices, "Device information could not be loaded")
        self.assertGreater(len(self.devices), 0, "No devices found in sshInfo.csv")

    # Optional: CPU usage test
    def test_cpu_usage(self):
        for name, info in self.devices.items():
            with self.subTest(device=name):
                conn = ConnectHandler(                     device_type=info["Device_Type"],
                     ip=info["IP"],
                     username=info["Username"],
                     password=info["Password"],
                 )
                output = conn.send_command("show processes top once | grep Cpu")
                cpu = extract_cpu_sy(output)
                conn.disconnect()
                self.assertTrue(cpu.endswith("%") or cpu == "N/A")

    def test_ospf_neighbors(self):
        for name, info in self.devices.items():
            with self.subTest(device=name):
                conn = ConnectHandler(
                    device_type=info["Device_Type"],
                    ip=info["IP"],
                    username=info["Username"],
                    password=info["Password"],
                    timeout=10,
                )
                ospf_output = conn.send_command("show ip ospf neighbor")
                conn.disconnect()
                # simple check: should contain expected words if neighbors exist
                if ospf_output.strip():
                    self.assertTrue(
                        "FULL" in ospf_output or "2WAY" in ospf_output or "Neighbor" in ospf_output,
                        "OSPF neighbors output format unexpected",
                    )

    def test_bgp_neighbors(self):
        for name, info in self.devices.items():
            with self.subTest(device=name):
                conn = ConnectHandler(
                    device_type=info["Device_Type"],
                    ip=info["IP"],
                    username=info["Username"],
                    password=info["Password"],
                    timeout=10,
                )
                bgp_output = conn.send_command("show ip bgp summary")
                conn.disconnect()
                self.assertTrue(len(bgp_output) > 0, "BGP neighbors command returned empty output")

if __name__ == "__main__":
    unittest.main()
