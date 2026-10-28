import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("manager", Path(__file__).parents[1] / "manager.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.s = m.new_state("8.8.8.8", 443, 8443, "www.cloudflare.com",
                             "PrivateKey: private-test-key\nPassword (PublicKey): public-test-key\nHash32: unused\n")

    def test_client_and_server_agree(self):
        inbound = m.xray_config(self.s)["inbounds"][0]
        node = m.mihomo_config(self.s)["proxies"][0]
        self.assertEqual(node["uuid"], inbound["settings"]["clients"][0]["id"])
        self.assertEqual(node["port"], inbound["port"])
        self.assertEqual(node["flow"], inbound["settings"]["clients"][0]["flow"])
        self.assertTrue(node["reality-opts"]["support-x25519mlkem768"])
        self.assertIn(node["reality-opts"]["short-id"], inbound["streamSettings"]["realitySettings"]["shortIds"])
        self.assertNotIn("private-test-key", m.dump(m.mihomo_config(self.s)))
        self.assertIn("pbk=public-test-key", m.vless_url(self.s))

    def test_fresh_credentials(self):
        other = m.new_state("8.8.8.8", 443, 8443, "www.cloudflare.com",
                            "Private key: private\nPublic key: public\n")
        self.assertNotEqual(self.s["uuid"], other["uuid"])
        self.assertNotEqual(self.s["token"], other["token"])
        self.assertEqual(len(self.s["token"]), 64)
        self.assertEqual(len(self.s["short_id"]), 16)

    def test_invalid_inputs_rejected(self):
        for values in [("127.0.0.1", 443, 8443, "example.com"),
                       ("8.8.8.8", 80, 8443, "example.com"),
                       ("8.8.8.8", 443, 443, "example.com"),
                       ("8.8.8.8", -1, 8443, "example.com"),
                       ("8.8.8.8", 443, 8443, "x; return 200;")]:
            with self.assertRaises(ValueError):
                m.validate(*values)

    def test_subscription_exact_path_only(self):
        config = m.nginx_config(self.s)
        self.assertIn(f'location = /{self.s["token"]}/mihomo.yaml', config)
        self.assertIn("location / { return 404; }", config)
        self.assertIn("access_log off", config)
        self.assertNotIn(self.s["token"], m.nginx_config(self.s, tls=False))
        self.assertTrue(m.subscription_url(self.s).startswith("https://"))

    def test_atomic_write_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "state.json"
            m.write(p, m.dump(self.s))
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(p.read_text()), self.s)


if __name__ == "__main__":
    unittest.main()
