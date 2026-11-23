#!/usr/bin/env bash
# Empaqueta la GUI en AppImage. Python 3 + tkinter son dependencias del equipo destino.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
if [[ "$(uname -m)" != "x86_64" ]]; then
  echo 'Esta receta de empaquetado ha sido preparada para x86_64.' >&2; exit 1
fi
if [[ -n "${APPIMAGETOOL:-}" ]]; then
  TOOL="$APPIMAGETOOL"
else
  TOOL="$(command -v appimagetool || true)"
fi
if [[ -z "$TOOL" || ! -f "$TOOL" && ! -x "$TOOL" ]]; then
  cat >&2 <<'EOF'
No se encontró appimagetool.
Descárgalo del proyecto oficial:
  https://github.com/AppImage/appimagetool/releases
Luego ejecuta:
  APPIMAGETOOL=/ruta/al/appimagetool-x86_64.AppImage bash build-appimage.sh
Nota: este empaquetado usa Python 3 + tkinter instalados en la máquina destino.
EOF
  exit 2
fi
rm -rf build/AppDir
mkdir -p build/AppDir/usr/share/bluetooth-audio-doctor build/AppDir/usr/share/icons/hicolor/scalable/apps
cp src/app.py src/core.py build/AppDir/usr/share/bluetooth-audio-doctor/
cp assets/bluetooth-audio-doctor.svg build/AppDir/bluetooth-audio-doctor.svg
cp assets/bluetooth-audio-doctor.svg build/AppDir/usr/share/icons/hicolor/scalable/apps/bluetooth-audio-doctor.svg
cat > build/AppDir/bluetooth-audio-doctor.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Bluetooth Audio Doctor
Comment=Diagnóstico y corrección reversible de perfiles A2DP
Exec=AppRun
Icon=bluetooth-audio-doctor
Terminal=false
Categories=Settings;Utility;
EOF
cat > build/AppDir/AppRun <<'EOF'
#!/bin/sh
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Se necesita Python 3 en el equipo.' >&2
  exit 1
fi
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  echo 'Falta tkinter: en Ubuntu/Zorin instala python3-tk.' >&2
  exit 1
fi
exec python3 "$HERE/usr/share/bluetooth-audio-doctor/app.py" "$@"
EOF
chmod +x build/AppDir/AppRun
ln -s bluetooth-audio-doctor.svg build/AppDir/.DirIcon
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" build/AppDir "$(pwd)/Bluetooth-Audio-Doctor-x86_64.AppImage"
echo "Creado: $(pwd)/Bluetooth-Audio-Doctor-x86_64.AppImage"
