import unittest
from unittest.mock import patch, MagicMock
from scripts.health_check import health_check_one, extract_cpu_sy

class TestConnectivityMock(unittest.TestCase):
    @patch("scripts.health_check.ConnectHandler")
    def test_health_flow_invokes_expected_commands(self, mock_ch):
        conn = MagicMock()
        conn.send_command.side_effect = [
            "CPU %Cpu(s): 1.0 us, 2.0 sy, 97.0 id",  # CPU
            "Neighbor ID ... FULL/DR ...",          # OSPF
            "BGP summary ...",                      # BGP
            "Gateway of last resort is 1.1.1.1",    # Routes
            "PING OK",                               # Ping
        ]
        mock_ch.return_value = conn

        meta = {"IP": "10.0.0.1", "Username": "u", "Password": "p", "Device_Type": "arista_eos"}
        # Should run without exceptions and call commands:
        health_check_one("R1", meta)

        self.assertGreaterEqual(conn.send_command.call_count, 5)

    def test_extract_cpu_sy_parses_percent(self):
        self.assertEqual(extract_cpu_sy("%Cpu(s):  3.2 us,  5.6 sy,  91.3 id"), "5.6%")
        self.assertEqual(extract_cpu_sy("garbage line"), "N/A")
