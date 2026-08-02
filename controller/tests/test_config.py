import tempfile
import unittest
from pathlib import Path

from pki_controller.config import load_config


class ConfigTests(unittest.TestCase):
    def test_loads_target(self) -> None:
        content = b'''[controller]
interval_seconds = 60
[[certificate]]
id = "test"
hostname = "test.lab.local"
csr = "/certs/test.csr"
certificate = "/certs/test.crt"
account_state = "/state/test"
webroot = "/webroot"
ca_url = "https://ca.lab.local:9000"
root = "/trust/root.crt"
verify_url = "https://test.lab.local"
'''
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as stream:
            stream.write(content)
            path = Path(stream.name)
        try:
            config = load_config(path)
            self.assertEqual(config.interval_seconds, 60)
            self.assertEqual(config.targets[0].target_id, "test")
            self.assertEqual(config.targets[0].renew_before, "4h")
            self.assertEqual(config.targets[0].operation_timeout_seconds, 120)
            self.assertEqual(config.targets[0].warning_before_seconds, 14400)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
