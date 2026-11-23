import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from core import BluetoothDoctor, DoctorError, KNOWN_LEGACY, CONTENT_04, CONTENT_05, Device


class FakeRunner:
    def __init__(self, version='0.4.17', profiles=None, fail_restart=False):
        self.version_value = version
        self.calls = []
        self.profiles = profiles or {}
        self.fail_restart = fail_restart

    def run(self, *args, timeout=12):
        self.calls.append(args)
        if args[:2] == ('wireplumber', '--version'):
            return subprocess.CompletedProcess(args, 0, f'wireplumber\nCompiled with libwireplumber {self.version_value}\n', '')
        if args[:2] == ('bluetoothctl', 'devices'):
            return subprocess.CompletedProcess(args, 0, 'Device 7C:FE:62:4F:DB:5E soundcore AeroFit 2\nDevice 11:22:33:44:55:66 mouse\n', '')
        if args[:2] == ('bluetoothctl', 'info'):
            if args[-1] == '7C:FE:62:4F:DB:5E':
                return subprocess.CompletedProcess(args, 0,
                    'Name: soundcore AeroFit 2\nPaired: yes\nConnected: yes\n'
                    'UUID: Audio Source (0000110a-0000-1000-8000-00805f9b34fb)\n'
                    'UUID: Audio Sink (0000110b-0000-1000-8000-00805f9b34fb)\n', '')
            return subprocess.CompletedProcess(args, 0, 'Paired: yes\nConnected: no\n', '')
        if args[0] == 'pactl':
            card = {'name': 'bluez_card.7C_FE_62_4F_DB_5E',
                    'profiles': self.profiles, 'active_profile': {'name': 'audio-gateway'}}
            return subprocess.CompletedProcess(args, 0, json.dumps([card]), '')
        if args[0] == 'systemctl':
            return subprocess.CompletedProcess(args, 1 if self.fail_restart else 0,
                                               '', 'restart failed' if self.fail_restart else '')
        raise AssertionError(args)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.home = Path(self.dir.name)
        self.fake = FakeRunner()
        self.doc = BluetoothDoctor(self.fake, self.home)

    def tearDown(self):
        self.dir.cleanup()

    def test_scans_paired_and_detects_dual_role(self):
        d = self.doc.devices()
        self.assertEqual(len(d), 2)
        self.assertTrue(d[0].dual_role)
        self.assertTrue(d[0].connected)
        self.assertFalse(d[1].is_audio)

    def test_missing_profile(self):
        d = self.doc.devices()[0]
        diagnostic = self.doc.diagnose(d)
        self.assertEqual(diagnostic.flag, 'missing_a2dp')
        self.assertFalse(diagnostic.a2dp_available)

    def test_available_profile(self):
        self.fake.profiles = {'off': {}, 'a2dp-sink': {}}
        self.assertTrue(self.doc.diagnose(self.doc.devices()[0]).a2dp_available)

    def test_apply_and_restore_04(self):
        self.doc.apply()
        dest = self.doc.target('0.4')
        self.assertEqual(dest.read_text(), CONTENT_04)
        self.assertEqual(self.doc.config_state().mode, 'managed')
        self.doc.restore()
        self.assertFalse(dest.exists())

    def test_apply_05(self):
        self.fake.version_value = '0.5.17'
        self.doc.apply()
        dest = self.doc.target('0.5')
        self.assertEqual(dest.read_text(), CONTENT_05)

    def test_never_overwrite_external_config(self):
        directory = self.home / 'wireplumber' / 'bluetooth.lua.d'
        directory.mkdir(parents=True)
        path = directory / '61-other.lua'
        path.write_text('bluez_monitor.properties["bluez5.roles"] = "[ a2dp_sink a2dp_source ]"\n')
        self.assertEqual(self.doc.config_state().mode, 'external')
        with self.assertRaises(DoctorError):
            self.doc.apply()
        self.assertIn('a2dp_sink', path.read_text())

    def test_recognizes_known_legacy_and_backs_up_on_restore(self):
        p = self.home / 'wireplumber' / 'bluetooth.lua.d' / '90-a2dp-unidireccional.lua'
        p.parent.mkdir(parents=True)
        p.write_text(KNOWN_LEGACY)
        self.assertEqual(self.doc.config_state().mode, 'legacy')
        with self.assertRaises(DoctorError):
            self.doc.apply()
        self.doc.restore()
        self.assertFalse(p.exists())
        self.assertEqual(p.with_name(p.name + '.audio-doctor.bak').read_text(), KNOWN_LEGACY)

    def test_failed_restart_rolls_back_new_file(self):
        self.fake.fail_restart = True
        with self.assertRaises(DoctorError):
            self.doc.apply()
        self.assertFalse(self.doc.target('0.4').exists())

    def test_unknown_version_diagnosis_only(self):
        self.fake.version_value = '0.6.1'
        self.assertEqual(self.doc.config_state().mode, 'unsupported')
        with self.assertRaises(DoctorError):
            self.doc.apply()


if __name__ == '__main__':
    unittest.main()
