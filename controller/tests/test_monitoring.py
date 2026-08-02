import unittest

from pki_controller.monitoring import classify_status, prometheus


class MonitoringTests(unittest.TestCase):
    def test_status_thresholds(self) -> None:
        self.assertEqual(classify_status(20000, True, True, True, 14400, 3600), "OK")
        self.assertEqual(classify_status(10000, True, True, True, 14400, 3600), "WARNING")
        self.assertEqual(classify_status(1000, True, True, True, 14400, 3600), "CRITICAL")
        self.assertEqual(classify_status(-1, True, True, True, 14400, 3600), "EXPIRED")
        self.assertEqual(classify_status(20000, False, True, True, 14400, 3600), "ERROR")

    def test_prometheus_output(self) -> None:
        output = prometheus(
            [{
                "id": "app1", "hostname": "app1.lab.local",
                "seconds_remaining": 42, "connectivity": True,
                "chain_valid": True, "hostname_valid": True, "deployed": True,
            }],
            123.0,
        )
        self.assertIn('pki_certificate_seconds_remaining{id="app1",hostname="app1.lab.local"} 42', output)
        self.assertIn("pki_controller_last_cycle_timestamp_seconds 123.0", output)


if __name__ == "__main__":
    unittest.main()
