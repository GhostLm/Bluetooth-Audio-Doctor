import os
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

from app import Window, presentation
from core import BluetoothDoctor, KNOWN_LEGACY
from test_core import FakeRunner


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.doc = BluetoothDoctor(FakeRunner(), self.home)

    def tearDown(self):
        self.temp.cleanup()

    def test_clear_uninstalled_state(self):
        title, _, _, _, action = presentation(self.doc.config_state())
        self.assertEqual(title, 'Corrección sin aplicar')
        self.assertIn('todos los dispositivos', presentation(self.doc.config_state())[1])
        self.assertEqual(action, 'apply')

    def test_clear_installed_state_from_existing_legacy_patch(self):
        legacy = self.home / 'wireplumber' / 'bluetooth.lua.d' / '90-a2dp-unidireccional.lua'
        legacy.parent.mkdir(parents=True)
        legacy.write_text(KNOWN_LEGACY)
        title, _, _, _, action = presentation(self.doc.config_state())
        self.assertIn('todo el equipo', title)
        self.assertEqual(action, 'remove')

    def test_external_configuration_cannot_be_removed(self):
        other = self.home / 'wireplumber' / 'bluetooth.lua.d' / 'other.lua'
        other.parent.mkdir(parents=True)
        other.write_text('bluez_monitor.properties["bluez5.roles"] = "[ a2dp_sink ]"')
        title, _, _, _, action = presentation(self.doc.config_state())
        self.assertEqual(action, 'none')
        self.assertIn('otra configuración', title)

    def test_modified_managed_file_not_misreported_as_applied(self):
        target = self.doc.target('0.4')
        target.parent.mkdir(parents=True)
        target.write_text('# Bluetooth Audio Doctor - archivo generado automáticamente\n# modificado\n')
        title, _, _, _, action = presentation(self.doc.config_state())
        self.assertEqual(action, 'none')
        self.assertNotIn('aplicada', title)


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Se requiere una sesión gráfica/Xvfb')
class WindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.doc = BluetoothDoctor(FakeRunner(), Path(self.temp.name))
        self.root = tk.Tk()
        self.window = Window(self.root, doctor=self.doc)
        self.wait_idle()

    def tearDown(self):
        self.root.destroy()
        self.temp.cleanup()

    def wait_idle(self):
        deadline = time.monotonic() + 3
        while (self.window.busy or not self.window.devices) and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.root.update()
        self.assertFalse(self.window.busy)

    def test_remove_button_only_shown_when_applied_and_reverts_legacy(self):
        self.assertFalse(self.window.remove_btn.winfo_ismapped())
        self.assertTrue(self.window.apply_btn.winfo_ismapped())
        legacy = self.doc.base / 'bluetooth.lua.d' / '90-a2dp-unidireccional.lua'
        legacy.parent.mkdir(parents=True)
        legacy.write_text(KNOWN_LEGACY)
        self.window._config_state()
        self.root.update()
        self.assertIn('todo el equipo', self.window.summary_title.get())
        self.assertEqual(self.window.scope_label.cget('text'), 'AJUSTE GENERAL DEL ORDENADOR')
        self.assertIn('todos los auriculares', self.window.summary_detail.get())
        self.assertTrue(self.window.remove_btn.winfo_ismapped())
        self.assertFalse(self.window.apply_btn.winfo_ismapped())
        with patch('app.messagebox.askyesno', return_value=True), patch('app.messagebox.showinfo'):
            self.window.restore()
            self.wait_idle()
        self.assertFalse(legacy.exists())
        self.assertTrue(legacy.with_name(legacy.name + '.audio-doctor.bak').exists())
        self.assertEqual(self.window.summary_title.get(), 'Corrección sin aplicar')
        self.assertTrue(self.window.apply_btn.winfo_ismapped())
        self.assertFalse(self.window.remove_btn.winfo_ismapped())

    def test_selection_does_not_change_global_status(self):
        title = self.window.summary_title.get()
        description = self.window.summary_detail.get()
        self.window.tree.selection_set('7C:FE:62:4F:DB:5E')
        self.window._selected()
        self.assertEqual(self.window.summary_title.get(), title)
        self.assertEqual(self.window.summary_detail.get(), description)

    def test_confirmations_explicitly_mention_all_devices(self):
        legacy = self.doc.base / 'bluetooth.lua.d' / '90-a2dp-unidireccional.lua'
        legacy.parent.mkdir(parents=True)
        legacy.write_text(KNOWN_LEGACY)
        self.window._config_state()
        with patch('app.messagebox.askyesno', return_value=False) as confirm:
            self.window.restore()
        self.assertIn('TODOS', confirm.call_args.args[1])
        self.assertIn('todo el equipo', confirm.call_args.args[0])
        legacy.unlink()
        self.window._config_state()
        with patch('app.messagebox.askyesno', return_value=False) as confirm:
            self.window.apply()
        self.assertIn('TODOS', confirm.call_args.args[1])
        self.assertIn('todo el equipo', confirm.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
