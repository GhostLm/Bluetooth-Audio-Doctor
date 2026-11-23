# Bluetooth Audio Doctor — prototipo 0.3

Pequeña interfaz gráfica para diagnosticar la ausencia de A2DP y aplicar el ajuste **global** de roles Bluetooth que funcionó con unos Soundcore AeroFit 2 en WirePlumber 0.4.17.

## Interfaz con alcance global explícito (v0.3)

- El estado principal aparece arriba, dentro de una única tarjeta: **«AJUSTE GENERAL DEL ORDENADOR»** y **«✓ Corrección activa en todo el equipo»** o **«Corrección sin aplicar»**.
- La explicación dentro de la tarjeta aclara que afecta a **todos los auriculares y altavoces Bluetooth**, nunca solamente al seleccionado.
- La lista se titula **«Revisar tus dispositivos Bluetooth»** e indica que seleccionar uno solo sirve para comprobar el sonido; no cambia a quién se aplica el ajuste.
- Las confirmaciones de aplicar y quitar mencionan expresamente **todos los dispositivos** antes de modificar archivos.
- Si el parche está aplicado, se muestra un botón **«Quitar corrección»**. Al quitarlo se solicita confirmación y se reinicia solo WirePlumber.
- Si está sin aplicar, se muestra exclusivamente el botón **«Aplicar corrección»**.
- La aplicación reconoce el parche manual conocido en `90-a2dp-unidireccional.lua` y lo respalda al retirarlo, sin borrar ni desemparejar auriculares.
- Si encuentra otra configuración o un archivo modificado, no ofrece borrar ni sobrescribir ese ajuste.
- El estado superior indica si el **archivo de configuración** está instalado, no confirma por sí solo la reproducción de audio: para ello hay que seleccionar un dispositivo y pulsar **«Comprobar sonido»**.

## Alcance

- Muestra dispositivos **emparejados** reconocidos por BlueZ (filtro de audio opcional).
- Distingue dispositivos que anuncian A2DP Audio Source y Audio Sink; es una **pista**, no prueba de incompatibilidad.
- Consulta perfiles en PipeWire usando la salida JSON de `pactl` (sin depender del idioma).
- Identifica si falta el perfil `a2dp-sink` o está disponible.
- En WirePlumber **0.4** crea un archivo Lua; en WirePlumber **0.5** crea un fragmento de configuración.
- Detecta y respeta archivos existentes de asignación `bluez5.roles` en el directorio del usuario.
- Reconoce exactamente `90-a2dp-unidireccional.lua`, el parche probado anteriormente. No lo modifica ni duplica. Se puede desactivar con respaldo y confirmación expresa.
- Reinicia únicamente WirePlumber después de aplicar o revertir.
- **Nunca** cambia el emparejamiento Bluetooth, toca `/etc`, ejecuta `sudo` ni reinicia `bluetooth.service`.

## Ejecución como código fuente (Zorin / Ubuntu)

```bash
sudo apt install python3 python3-tk pulseaudio-utils bluez
git clone https://github.com/GhostLm/Bluetooth-Audio-Doctor.git
cd Bluetooth-Audio-Doctor
sh iniciar.sh
```

Requiere sesión gráfica, BlueZ, WirePlumber y PipeWire/Pulse (`pactl`).

## Crear AppImage

La primera versión **no incluye un runtime de Python/Tk**: el AppImage se puede crear, pero requiere `python3` y `python3-tk` instalados en el sistema destino. Para un AppImage completamente independiente habría que empaquetar Python, Tcl/Tk y sus librerías, o reescribir la GUI en Rust/Slint.

Descarga `appimagetool` desde [AppImage/appimagetool](https://github.com/AppImage/appimagetool/releases) y ejecuta:

```bash
APPIMAGETOOL="$HOME/Descargas/appimagetool-x86_64.AppImage" bash build-appimage.sh
```

Se generará `Bluetooth-Audio-Doctor-x86_64.AppImage`.

## Ejecutar las pruebas

```bash
python3 -m unittest discover -s tests -v
```

Para ejecutar las pruebas gráficas sin pantalla física, instala `xvfb` y usa:

```bash
env -u DISPLAY xvfb-run -a python3 -m unittest discover -s tests -v
```

Las pruebas usan un simulador para comandos Bluetooth y WirePlumber; no modifican la configuración Bluetooth real.

## Por qué no aplica la corrección a un dispositivo solamente

`bluez5.roles` es una propiedad del monitor BlueZ de WirePlumber, por lo que influye en toda la sesión de audio Bluetooth. El ajuste elimina el rol **local** `a2dp_sink` (recibir música de otro equipo) y mantiene `a2dp_source` (enviar música a auriculares), además de los roles de manos libres. En WirePlumber 0.5 se preservan los roles BAP/LE Audio habituales. No hay garantía de que resuelva todos los problemas A2DP.

## Seguridad y limitaciones

1. La aplicación **no ejecuta automáticamente** una conexión fallida para provocar el error. El usuario decide si aplicar la corrección.
2. Solo modifica archivos **propios**, salvo la opción de desactivar con respaldo el archivo anterior que coincide exactamente con el parche probado.
3. No modifica archivos de sistema ni configuraciones de terceros que ya definan `bluez5.roles`.
4. Si `systemctl --user restart wireplumber` falla al aplicar, retira el fragmento nuevo e intenta restaurar WirePlumber.
5. La detección de perfiles depende de `pactl --format=json list cards`. No permite controlar arbitrariamente codecs, actualizar firmware ni solucionar fallos de radio.
6. El soporte de WirePlumber 0.5 está basado en su documentación; la prueba real de este proyecto es WirePlumber 0.4.17 con AeroFit 2. Hay que probarlo en 0.5 antes de distribuir ampliamente.
7. No instalar encima de un parche manual distinto sin revisarlo: podría haber reglas superpuestas que alteren el resultado.

## Referencias

- [WirePlumber 0.4 - Bluetooth](https://fdanis.pages.freedesktop.org/wireplumber/configuration/bluetooth.html)
- [WirePlumber 0.5 - Bluetooth](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html)
- [BlueZ #2494](https://github.com/bluez/bluez/issues/2494)
- [BlueZ #2671](https://github.com/bluez/bluez/issues/2671)
