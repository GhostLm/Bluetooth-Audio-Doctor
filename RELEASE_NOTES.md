# Bluetooth Audio Doctor 0.3.0 — primera versión pública

Aplicación gráfica para Linux que ayuda a diagnosticar problemas donde unos auriculares Bluetooth se conectan en modo manos libres y desaparece la reproducción estéreo A2DP.

### Qué incluye

- Interfaz sencilla en español, con el estado de la corrección claramente visible.
- Detección de dispositivos Bluetooth emparejados y comprobación de perfiles A2DP.
- Ajuste reversible para WirePlumber 0.4 y 0.5.
- Reconocimiento del parche manual anterior de WirePlumber 0.4, con copia de seguridad al retirarlo.
- Botones **Aplicar corrección** y **Quitar corrección**, con confirmación previa.
- AppImage x86_64 que **incluye Python y Tkinter**: no hace falta instalarlos por separado.

### Instalación

1. Descarga `Bluetooth-Audio-Doctor-x86_64.AppImage` en los archivos de esta versión.
2. Marca el archivo como ejecutable (Propiedades → Permitir ejecutar como programa).
3. Haz doble clic para abrirlo.

Si tu distribución requiere ejecutar la AppImage sin FUSE, usa desde terminal:
```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./Bluetooth-Audio-Doctor-x86_64.AppImage
```

### Importante: la corrección es global

El ajuste modifica los roles del monitor BlueZ de WirePlumber y afecta a **todos los dispositivos de audio Bluetooth del ordenador**, no solamente al seleccionado. Deshabilita la recepción A2DP en el ordenador, pero mantiene la salida A2DP hacia auriculares y los roles de manos libres. Es una solución alternativa a ciertos fallos de perfiles, no un arreglo universal.

La AppImage incluye la interfaz, pero usa los servicios Bluetooth/audio del sistema: BlueZ, WirePlumber y PipeWire (con `pactl`). No elimina emparejamientos ni necesita modificar archivos de sistema.

### Compatibilidad

- Linux x86_64.
- Probado por el usuario en Zorin con WirePlumber 0.4.17, BlueZ 5.72 y Soundcore AeroFit 2.
- El formato de configuración de WirePlumber 0.5 está implementado, pero todavía requiere validación en equipos reales con esa versión.

Código fuente y documentación: https://github.com/GhostLm/Bluetooth-Audio-Doctor

Seguimiento de fallos relacionados: https://github.com/bluez/bluez/issues/2494 y https://github.com/bluez/bluez/issues/2671
