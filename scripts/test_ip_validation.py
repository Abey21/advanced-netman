import os, ipaddress, unittest
from scripts.health_check import load_ssh_info, CSV_PATH

class TestIpValidation(unittest.TestCase):
    def test_device_ips_are_valid(self):
        csv_path = os.environ.get("SSHINFO_CSV", str(CSV_PATH))
        devices = load_ssh_info(csv_path)
        self.assertGreater(len(devices), 0, "No devices loaded from CSV")
        for name, meta in devices.items():
            ipaddress.ip_address(meta["IP"])  # raises ValueError if invalid
