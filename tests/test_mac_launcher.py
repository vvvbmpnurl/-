import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import mac_launcher as mac

class MacLauncherTests(unittest.TestCase):
    def test_local_mode_overrides_cloud_environment(self):
        with patch.dict(os.environ,{'FACTORY_PUBLIC_ORIGIN':'https://example.com','FACTORY_PROXY_TOKEN':'old','FACTORY_BIND':'0.0.0.0'}):
            env=mac.local_environment({'SHANJIAN_API_KEY':'private'},8766)
        self.assertEqual(env['FACTORY_BIND'],'127.0.0.1')
        self.assertEqual(env['FACTORY_PORT'],'8766')
        self.assertNotIn('FACTORY_PUBLIC_ORIGIN',env)
        self.assertNotIn('FACTORY_PROXY_TOKEN',env)

    def test_mac_system_certificate_fallback_preserves_explicit_setting(self):
        with patch.object(mac.sys,'platform','darwin'), patch.object(mac.Path,'is_file',return_value=True), patch.dict(os.environ,{},clear=True):
            self.assertEqual(mac.local_environment({},8765)['SSL_CERT_FILE'],'/etc/ssl/cert.pem')
            with patch.dict(os.environ,{'SSL_CERT_FILE':'/custom/ca.pem'}):
                self.assertEqual(mac.local_environment({},8765)['SSL_CERT_FILE'],'/custom/ca.pem')

    def test_config_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'config.json'
            self.assertEqual(mac.read_config(p),{})
            p.write_text('{"SHANJIAN_API_KEY":"value"}')
            self.assertEqual(mac.read_config(p)['SHANJIAN_API_KEY'],'value')
            p.write_text('{"FACTORY_BIND":"0.0.0.0"}')
            with self.assertRaises(RuntimeError):mac.read_config(p)

    def test_installer_newlines_and_idempotency(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            (d/'index.html').write_text('<html><head></head><body>内容工厂 · 成稿线</body></html>')
            (d/'install.py').write_text((mac.ROOT/'install.py').read_text())
            subprocess.run([sys.executable,str(d/'install.py')],check=True,capture_output=True)
            one=(d/'index.html').read_text()
            self.assertNotIn(chr(92)+'n',one)
            self.assertIn('<script src="factory.js"></script>\n</body>',one)
            subprocess.run([sys.executable,str(d/'install.py')],check=True,capture_output=True)
            self.assertEqual((d/'index.html').read_text(),one)
