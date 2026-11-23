#!/usr/bin/env bash
# Construye AppImage x86_64 con Python y Tcl/Tk incorporados mediante PyInstaller.
set -Eeuo pipefail
cd "$(dirname "$0")"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || { echo "Solo Linux x86_64" >&2; exit 1; }
python3 -c 'import tkinter, _tkinter' || { echo "Instala python3-tk en el equipo compilador" >&2; exit 1; }
mkdir -p build
if [[ ! -x build/venv-appimage/bin/python ]]; then
  python3 -m venv build/venv-appimage || { echo "Instala python3-venv" >&2; exit 1; }
fi
echo "[1/4] Instalando PyInstaller para compilar..."
build/venv-appimage/bin/python -m pip install --disable-pip-version-check --quiet 'pyinstaller==6.16.0'
echo "[2/4] Incorporando Python y Tkinter al ejecutable..."
build/venv-appimage/bin/python -m PyInstaller --noconfirm --clean --onedir \
  --name BluetoothAudioDoctor \
  --distpath "$(pwd)/build/pyinstaller-dist" \
  --workpath "$(pwd)/build/pyinstaller-work" \
  --specpath "$(pwd)/build/pyinstaller-spec" src/app.py
test -x build/pyinstaller-dist/BluetoothAudioDoctor/BluetoothAudioDoctor
echo "[3/4] Preparando AppDir..."
rm -rf build/AppDir
mkdir -p build/AppDir/usr/lib build/AppDir/usr/share/icons/hicolor/scalable/apps
cp -a build/pyinstaller-dist/BluetoothAudioDoctor build/AppDir/usr/lib/bluetooth-audio-doctor
cp assets/bluetooth-audio-doctor.svg build/AppDir/bluetooth-audio-doctor.svg
cp assets/bluetooth-audio-doctor.svg build/AppDir/usr/share/icons/hicolor/scalable/apps/bluetooth-audio-doctor.svg
ln -s bluetooth-audio-doctor.svg build/AppDir/.DirIcon
cat > build/AppDir/bluetooth-audio-doctor.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Bluetooth Audio Doctor
Comment=Diagnóstico y corrección reversible de perfiles A2DP
Exec=AppRun
Icon=bluetooth-audio-doctor
Terminal=false
Categories=Settings;Utility;
DESKTOP
cat > build/AppDir/AppRun <<'APPRUN'
#!/bin/sh
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$HERE/usr/lib/bluetooth-audio-doctor/BluetoothAudioDoctor" "$@"
APPRUN
chmod +x build/AppDir/AppRun
echo "[4/4] Creando AppImage..."
if [[ -v APPIMAGETOOL && -n "$APPIMAGETOOL" ]]; then
  TOOL="$APPIMAGETOOL"
elif command -v appimagetool >/dev/null 2>&1; then
  TOOL="$(command -v appimagetool)"
else
  TOOL="$(pwd)/build/appimagetool-x86_64.AppImage"
  if [[ ! -s "$TOOL" ]]; then
    curl -fL --retry 3 \
      'https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage' \
      -o "$TOOL"
  fi
  chmod +x "$TOOL"
fi
[[ -x "$TOOL" ]] || { echo "appimagetool no es ejecutable: $TOOL" >&2; exit 1; }
OUTPUT="$(pwd)/Bluetooth-Audio-Doctor-x86_64.AppImage"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$(pwd)/build/AppDir" "$OUTPUT"
chmod +x "$OUTPUT"
printf 'AppImage creada: %s\n' "$OUTPUT"
