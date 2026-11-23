#!/bin/sh
set -eu
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'No se encontró Python 3.' >&2; exit 1
fi
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  echo 'Falta tkinter. En Zorin/Ubuntu ejecuta: sudo apt install python3-tk' >&2; exit 1
fi
exec python3 src/app.py "$@"
