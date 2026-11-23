"""Bluetooth Audio Doctor: diagnóstico conservador de A2DP en Linux.

Solo escribe un archivo propio en la configuración del usuario; nunca modifica
BlueZ ni los emparejamientos. El ajuste de roles es GLOBAL por sesión.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile
from typing import Optional

MAC_RE = re.compile(r"\b([0-9A-F]{2}(?::[0-9A-F]{2}){5})\b", re.I)
DEVICE_RE = re.compile(r"^Device\s+([0-9A-F:]{17})\s+(.+)$", re.I)
UUID_SINK = "0000110b-0000-1000-8000-00805f9b34fb"
UUID_SOURCE = "0000110a-0000-1000-8000-00805f9b34fb"
MARKER = "# Bluetooth Audio Doctor - archivo generado automáticamente"
ROLES_04 = "[ a2dp_source hsp_hs hsp_ag hfp_hf hfp_ag ]"
ROLES_05 = "[ a2dp_source bap_sink bap_source hsp_hs hsp_ag hfp_hf hfp_ag ]"
CONTENT_04 = f'{MARKER}\nbluez_monitor.properties["bluez5.roles"] = "{ROLES_04}"\n'
CONTENT_05 = f'{MARKER}\nmonitor.bluez.properties = {{\n  bluez5.roles = {ROLES_05}\n}}\n'
KNOWN_LEGACY = 'bluez_monitor.properties["bluez5.roles"] = "[ a2dp_source hsp_hs hsp_ag hfp_hf hfp_ag ]"\n'


class DoctorError(RuntimeError):
    pass


class Runner:
    def run(self, *args: str, timeout: int = 12) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(args, capture_output=True, text=True,
                                  errors="replace", timeout=timeout, check=False)
        except FileNotFoundError as exc:
            raise DoctorError(f"Falta la herramienta del sistema: {args[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise DoctorError(f"Tiempo agotado al ejecutar: {args[0]}") from exc


@dataclass(frozen=True)
class Device:
    mac: str
    name: str
    connected: bool
    paired: bool
    audio_sink: bool
    audio_source: bool
    handsfree: bool

    @property
    def dual_role(self) -> bool:
        return self.audio_sink and self.audio_source

    @property
    def is_audio(self) -> bool:
        return self.audio_sink or self.audio_source or self.handsfree


@dataclass(frozen=True)
class Diagnosis:
    detail: str
    a2dp_available: bool
    active_profile: str
    profiles: tuple[str, ...]
    flag: str


@dataclass(frozen=True)
class ConfigState:
    version: Optional[str]
    major_minor: Optional[str]
    managed_file: Path | None
    existing_configs: tuple[Path, ...]
    mode: str
    note: str


class BluetoothDoctor:
    def __init__(self, runner: Runner | None = None, config_home: Path | None = None):
        self.runner = runner or Runner()
        self.config_home = config_home or Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        self.base = self.config_home / "wireplumber"

    def version(self) -> tuple[Optional[str], Optional[str]]:
        r = self.runner.run("wireplumber", "--version")
        if r.returncode:
            raise DoctorError("No se pudo obtener la versión de WirePlumber.")
        m = re.search(r"(?:libwireplumber|WirePlumber)\s+(\d+)\.(\d+)\.(\d+)", r.stdout, re.I)
        if not m:
            m = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", r.stdout)
        if not m:
            return None, None
        return m.group(0).split()[-1], f"{m.group(1)}.{m.group(2)}"

    def target(self, major_minor: str) -> Path:
        if major_minor == "0.4":
            return self.base / "bluetooth.lua.d" / "95-bluetooth-audio-doctor.lua"
        if major_minor == "0.5":
            return self.base / "wireplumber.conf.d" / "95-bluetooth-audio-doctor.conf"
        raise DoctorError("WirePlumber no es 0.4 ni 0.5; aplicación del ajuste no admitida.")

    def _all_role_files(self) -> list[Path]:
        result = []
        for dirname, suffix in (("bluetooth.lua.d", "*.lua"), ("wireplumber.conf.d", "*.conf")):
            result.extend(sorted((self.base / dirname).glob(suffix)))
        return result

    def config_state(self) -> ConfigState:
        version, mm = self.version()
        managed = self.target(mm) if mm in ("0.4", "0.5") else None
        external = []
        for path in self._all_role_files():
            if path == managed:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            # Detectar asignaciones, no menciones en comentarios.
            if re.search(r'(?m)^\s*(?:bluez_monitor\.properties\["bluez5\.roles"\]|bluez5\.roles)\s*=', content):
                external.append(path)
        if managed and managed.is_file():
            try:
                actual = managed.read_text(encoding="utf-8")
            except OSError:
                actual = ""
            expected = CONTENT_04 if mm == "0.4" else CONTENT_05
            # Nunca presentar como aplicada una configuración alterada o superpuesta.
            if actual == expected and not external:
                return ConfigState(version, mm, managed, (), "managed",
                                   "Corrección instalada por Bluetooth Audio Doctor.")
            return ConfigState(version, mm, managed, tuple(external), "foreign_target",
                               "Hay archivos adicionales o una configuración modificada. No se cambiará automáticamente.")
        if external:
            legacy = self.base / "bluetooth.lua.d" / "90-a2dp-unidireccional.lua"
            if mm == "0.4" and external == [legacy]:
                try:
                    legacy_text = legacy.read_text(encoding="utf-8")
                except OSError:
                    legacy_text = ""
                if legacy_text == KNOWN_LEGACY:
                    return ConfigState(version, mm, legacy, tuple(external), "legacy",
                                       "Parche anterior conocido detectado. No se duplicará. Se puede revertir con respaldo.")
            return ConfigState(version, mm, managed, tuple(external), "external",
                               "Hay una configuración de roles existente. No se duplicará ni modificará.")
        if not managed:
            return ConfigState(version, mm, None, (), "unsupported",
                               "Versión no admitida. Diagnóstico disponible; no se modificará la configuración.")
        return ConfigState(version, mm, managed, (), "none",
                           "Sin corrección de roles detectada en los archivos del usuario.")

    def devices(self) -> list[Device]:
        r = self.runner.run("bluetoothctl", "devices", timeout=15)
        if r.returncode != 0:
            raise DoctorError((r.stderr or "No se pudo consultar Bluetooth").strip())
        found: list[Device] = []
        seen = set()
        for line in r.stdout.splitlines():
            m = DEVICE_RE.match(line.strip())
            if not m:
                continue
            mac, fallback = m.group(1).upper(), m.group(2).strip()
            if mac in seen:
                continue
            seen.add(mac)
            info = self.runner.run("bluetoothctl", "info", mac, timeout=10)
            if info.returncode:
                continue
            txt = info.stdout
            paired = bool(re.search(r"(?m)^\s*Paired:\s*yes\b", txt, re.I))
            if not paired:
                continue
            connected = bool(re.search(r"(?m)^\s*Connected:\s*yes\b", txt, re.I))
            name = re.search(r"(?m)^\s*(?:Alias|Name):\s*(.+)$", txt)
            found.append(Device(mac, name.group(1).strip() if name else fallback,
                                connected, paired,
                                UUID_SINK in txt.lower(), UUID_SOURCE in txt.lower(),
                                "0000111e-" in txt.lower() or "00001108-" in txt.lower()))
        return sorted(found, key=lambda d: (not d.connected, d.name.lower()))

    def diagnose(self, device: Device) -> Diagnosis:
        if not device.connected:
            return Diagnosis("El dispositivo no está conectado. Conéctalo desde Bluetooth y actualiza.",
                             False, "—", (), "disconnected")
        r = self.runner.run("pactl", "--format=json", "list", "cards", timeout=12)
        if r.returncode:
            return Diagnosis("No se pudo consultar PipeWire con pactl. Comprueba que pipewire-pulse esté activo.",
                             False, "—", (), "unavailable")
        try:
            cards = json.loads(r.stdout)
        except (ValueError, TypeError):
            return Diagnosis("pactl no devolvió un JSON válido.", False, "—", (), "unavailable")
        if not isinstance(cards, list):
            return Diagnosis("Formato inesperado de las tarjetas de audio.", False, "—", (), "unavailable")
        key = "bluez_card." + device.mac.replace(":", "_")
        card = next((c for c in cards if isinstance(c, dict) and (
            c.get("name") == key or c.get("properties", {}).get("device.name") == key)), None)
        if card is None:
            return Diagnosis("BlueZ está conectado, pero PipeWire no publica una tarjeta de audio para este dispositivo.",
                             False, "—", (), "missing_card")
        raw = card.get("profiles") or {}
        if isinstance(raw, dict):
            names = tuple(str(k) for k in raw)
        elif isinstance(raw, list):
            names = tuple(p.get("name", "") for p in raw if isinstance(p, dict))
        else:
            names = ()
        active = card.get("active_profile") or "—"
        if isinstance(active, dict):
            active = active.get("name", "—")
        if not isinstance(active, str):
            active = str(active)
        available = any(p.startswith("a2dp-sink") for p in names)
        if available:
            msg = ("A2DP está disponible" + (" y seleccionado." if active.startswith("a2dp-sink")
                   else f", aunque el perfil activo es {active}."))
            return Diagnosis(msg, True, active, names, "ok")
        if device.dual_role:
            msg = ("Falta A2DP en PipeWire y el dispositivo anuncia Audio Source y Audio Sink. "
                   "El conflicto de doble rol es una posibilidad; no está confirmado.")
        else:
            msg = ("Falta A2DP, pero no se detectó el doble rol Audio Source/Audio Sink. "
                   "La corrección puede no ser apropiada para este equipo.")
        return Diagnosis(msg, False, active, names, "missing_a2dp")

    def apply(self) -> str:
        state = self.config_state()
        if state.mode != "none" or not state.managed_file:
            raise DoctorError(state.note + " Revisa primero la configuración existente.")
        path = state.managed_file
        content = CONTENT_04 if state.major_minor == "0.4" else CONTENT_05
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise DoctorError("El archivo apareció después de comprobarlo. No se sobrescribirá.")
        tmp_name = ""
        try:
            fd, tmp_name = tempfile.mkstemp(prefix=".audio-doctor-", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                os.fchmod(fp.fileno(), 0o600)
                fp.write(content)
                fp.flush()
                os.fsync(fp.fileno())
            # Evita una sobreescritura accidental si otra instancia creó el destino.
            os.link(tmp_name, path)
        except FileExistsError as exc:
            raise DoctorError("El archivo ya existe. No se sobrescribió.") from exc
        finally:
            if tmp_name and Path(tmp_name).exists():
                Path(tmp_name).unlink()
        r = self.runner.run("systemctl", "--user", "restart", "wireplumber", timeout=25)
        if r.returncode:
            # Reversión automática: nunca dejar un archivo nuevo si el reinicio falló.
            try:
                path.unlink()
            except OSError:
                pass
            self.runner.run("systemctl", "--user", "restart", "wireplumber", timeout=25)
            raise DoctorError("WirePlumber no reinició correctamente. Se retiró el ajuste nuevo. "
                              + (r.stderr or "").strip())
        return f"Corrección guardada en {path}. WirePlumber reiniciado. Comprueba nuevamente A2DP."

    def restore(self) -> str:
        state = self.config_state()
        if state.mode not in ("managed", "legacy") or not state.managed_file:
            raise DoctorError("No hay ningún parche conocido que se pueda retirar de forma segura.")
        path = state.managed_file
        current = path.read_text(encoding="utf-8")
        expected = (KNOWN_LEGACY,) if state.mode == "legacy" else (CONTENT_04, CONTENT_05)
        if current not in expected:
            raise DoctorError("El archivo fue modificado. No se eliminará automáticamente.")
        if state.mode == "legacy":
            backup = path.with_name(path.name + ".audio-doctor.bak")
            if backup.exists():
                raise DoctorError("Ya existe el respaldo del parche anterior. No se sobrescribirá.")
            path.rename(backup)
        else:
            # El archivo es idéntico al generado por esta app.
            path.unlink()
        r = self.runner.run("systemctl", "--user", "restart", "wireplumber", timeout=25)
        if r.returncode:
            if state.mode == "legacy":
                backup.rename(path)
            else:
                path.write_text(current, encoding="utf-8")
            self.runner.run("systemctl", "--user", "restart", "wireplumber", timeout=25)
            raise DoctorError("Falló el reinicio; se restauró el parche anterior. " + (r.stderr or "").strip())
        if state.mode == "legacy":
            return f"Se desactivó el parche anterior. Respaldo conservado en {backup}."
        return "Se retiró el ajuste de la aplicación y se reinició WirePlumber."
