#!/usr/bin/env python3
"""Interfaz sencilla para una corrección global de perfiles de audio Bluetooth."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import BluetoothDoctor, ConfigState, Device, DoctorError  # noqa: E402


BACKGROUND = "#F7F8FC"
PRIMARY = "#24304B"
MUTED = "#5E6A83"
GOOD = "#17683E"
GOOD_BG = "#E8F5EC"
NEUTRAL_BG = "#EDF1FB"
WARNING_BG = "#FFF4E5"
WARNING_FG = "#8F5414"
DANGER = "#A42736"
DANGER_BG = "#FFF0F1"


def presentation(state: ConfigState) -> tuple[str, str, str, str, str]:
    """(título, texto, color del texto, fondo, acción). Sin confundir fichero con audio real."""
    managed_only = state.mode == "managed" and not state.existing_configs
    known_old_patch = (state.mode == "legacy" and len(state.existing_configs) == 1
                       and state.existing_configs[0] == state.managed_file)
    if managed_only or known_old_patch:
        return (
            "✓  Corrección activa en todo el equipo",
            "Afecta a todos los auriculares y altavoces Bluetooth, no solo al seleccionado.",
            GOOD, GOOD_BG, "remove",
        )
    if state.mode == "none":
        return (
            "Corrección sin aplicar",
            "Si la activas, se aplicará a todos los dispositivos de audio Bluetooth del equipo.",
            PRIMARY, NEUTRAL_BG, "apply",
        )
    if state.mode == "unsupported":
        return (
            "Esta versión no admite la corrección",
            "Puedes comprobar el sonido, pero esta aplicación no puede cambiar el ajuste general.",
            WARNING_FG, WARNING_BG, "none",
        )
    return (
        "Hay otra configuración de Bluetooth",
        "Para proteger tus ajustes actuales, esta aplicación no los cambiará ni eliminará.",
        WARNING_FG, WARNING_BG, "none",
    )


class Window:
    def __init__(self, root: tk.Tk, doctor: BluetoothDoctor | None = None):
        self.root = root
        self.root.title("Bluetooth Audio Doctor")
        self.root.geometry("820x700")
        self.root.minsize(700, 640)
        self.doc = doctor or BluetoothDoctor()
        self.devices: dict[str, Device] = {}
        self.messages: queue.Queue = queue.Queue()
        self.busy = False
        self.all_devices = tk.BooleanVar(value=False)
        self.summary_title = tk.StringVar(value="Comprobando configuración…")
        self.summary_detail = tk.StringVar(value="Estamos revisando los ajustes de audio Bluetooth.")
        self.version_text = tk.StringVar(value="")
        self.detail_text = tk.StringVar(value="Selecciona unos auriculares y pulsa «Comprobar sonido».")
        self.status_text = tk.StringVar(value="Preparado")
        self._styles()
        self._build()
        self.root.after(120, self._poll)
        self.refresh()

    def _styles(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        self.root.configure(bg=BACKGROUND)
        style.configure("TFrame", background=BACKGROUND)
        style.configure("TLabelframe", background="#FFFFFF")
        style.configure("TLabelframe.Label", background=BACKGROUND, foreground=PRIMARY, font=("Sans", 10, "bold"))
        style.configure("Detail.TLabel", background="#FFFFFF", foreground=PRIMARY, font=("Sans", 10))
        style.configure("Header.TLabel", background=BACKGROUND, foreground=PRIMARY, font=("Sans", 17, "bold"))
        style.configure("Section.TLabel", background=BACKGROUND, foreground=PRIMARY, font=("Sans", 11, "bold"))
        style.configure("TLabel", background=BACKGROUND, foreground=PRIMARY, font=("Sans", 10))
        style.configure("Info.TLabel", background=BACKGROUND, foreground=MUTED, font=("Sans", 9))
        style.configure("TButton", font=("Sans", 10), padding=(12, 8))
        style.configure("TCheckbutton", background=BACKGROUND, font=("Sans", 10))
        style.configure("Treeview", font=("Sans", 10), rowheight=32, background="#FFFFFF", fieldbackground="#FFFFFF")
        style.configure("Treeview.Heading", font=("Sans", 10, "bold"))
        style.map("Treeview", background=[("selected", "#E5EBFF")], foreground=[("selected", "#17254A")])
        style.configure("SafeApply.TButton", font=("Sans", 10, "bold"), padding=(15, 10),
                        background="#245FC5", foreground="#FFFFFF", borderwidth=0)
        style.map("SafeApply.TButton", background=[("active", "#194FA8"), ("disabled", "#BEC6D8")],
                  foreground=[("disabled", "#FFFFFF")])
        style.configure("Remove.TButton", font=("Sans", 10, "bold"), padding=(15, 10),
                        background=DANGER_BG, foreground=DANGER, borderwidth=1)
        style.map("Remove.TButton", background=[("active", "#FAD9DD"), ("disabled", "#F4E9EA")],
                  foreground=[("disabled", "#BA969A")])

    def _build(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Bluetooth Audio Doctor", style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Ayuda a recuperar el sonido de alta calidad en tus auriculares.",
                  style="Info.TLabel").pack(anchor="w", pady=(4, 11))

        # Estado principal visible incluso si no se selecciona un dispositivo.
        self.banner = tk.Frame(outer, bg=NEUTRAL_BG, padx=16, pady=13, highlightthickness=0)
        self.banner.pack(fill="x", pady=(0, 12))
        self.banner_text = tk.Frame(self.banner, bg=NEUTRAL_BG)
        self.banner_text.pack(side="left", fill="both", expand=True)
        # El alcance se presenta dentro del mismo estado, no como una nota fácil de ignorar.
        self.scope_label = tk.Label(
            self.banner_text, text="AJUSTE GENERAL DEL ORDENADOR", bg=NEUTRAL_BG,
            fg=MUTED, font=("Sans", 9, "bold"), anchor="w"
        )
        self.scope_label.pack(fill="x", anchor="w", pady=(0, 5))
        self.title_label = tk.Label(self.banner_text, textvariable=self.summary_title,
                                    bg=NEUTRAL_BG, fg=PRIMARY, font=("Sans", 12, "bold"), anchor="w")
        self.title_label.pack(fill="x", anchor="w")
        self.desc_label = tk.Label(self.banner_text, textvariable=self.summary_detail, justify="left",
                                   bg=NEUTRAL_BG, fg=PRIMARY, font=("Sans", 10), anchor="w", wraplength=475)
        self.desc_label.pack(fill="x", anchor="w", pady=(6, 0))
        self.action_area = tk.Frame(self.banner, bg=NEUTRAL_BG)
        self.action_area.pack(side="right", padx=(14, 0))
        self.apply_btn = ttk.Button(self.action_area, text="Aplicar corrección", style="SafeApply.TButton", command=self.apply)
        self.remove_btn = ttk.Button(self.action_area, text="Quitar corrección", style="Remove.TButton", command=self.restore)
        self.remove_btn.pack_forget()
        self.apply_btn.pack_forget()

        tools = ttk.Frame(outer)
        tools.pack(fill="x", pady=(0, 6))
        ttk.Label(tools, text="Revisar tus dispositivos Bluetooth", style="Section.TLabel").pack(side="left")
        ttk.Button(tools, text="Actualizar lista", command=self.refresh).pack(side="right")
        self.refresh_btn = tools.winfo_children()[-1]
        ttk.Label(outer, text="Seleccionar un dispositivo solo sirve para comprobar su sonido.",
                  style="Info.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(outer, text="Mostrar también otros dispositivos",
                        variable=self.all_devices, command=self._populate).pack(anchor="w", pady=(0, 5))

        list_frame = ttk.Frame(outer)
        list_frame.pack(fill="both", expand=True)
        columns = ("name", "connection", "kind")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=4, selectmode="browse")
        for col, label, width in (("name", "Dispositivo", 310), ("connection", "Estado", 120), ("kind", "Tipo de audio", 250)):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w", stretch=True)
        bar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._selected)

        detail_frame = ttk.LabelFrame(outer, text="Estado del sonido", padding=(12, 10))
        detail_frame.pack(fill="x", pady=(8, 5))
        ttk.Label(detail_frame, textvariable=self.detail_text, wraplength=720, justify="left", style="Detail.TLabel").pack(anchor="w")
        self.diagnose_btn = ttk.Button(detail_frame, text="Comprobar sonido", command=self.diagnose)
        self.diagnose_btn.pack(anchor="e", pady=(6, 0))

        ttk.Label(outer, textvariable=self.version_text, style="Info.TLabel").pack(anchor="w", pady=(1, 0))
        ttk.Label(outer, textvariable=self.status_text, style="Info.TLabel").pack(anchor="w", pady=(3, 0))

    def _show_state(self, mode: str):
        for button in (self.apply_btn, self.remove_btn):
            button.pack_forget()
        if mode == "apply":
            self.apply_btn.pack()
        elif mode == "remove":
            self.remove_btn.pack()
        self._set_button_state()

    def _set_button_state(self):
        value = "disabled" if self.busy else "normal"
        for button in (self.apply_btn, self.remove_btn, self.refresh_btn, self.diagnose_btn):
            button.configure(state=value)

    def _job(self, job, callback):
        if self.busy:
            return
        self.busy = True
        self._set_button_state()
        self.status_text.set("Consultando el sistema…")

        def work():
            try:
                result = job()
                self.messages.put((True, callback, result))
            except Exception as exc:
                self.messages.put((False, callback, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                ok, callback, value = self.messages.get_nowait()
                self.busy = False
                self._set_button_state()
                if ok:
                    callback(value)
                else:
                    self.status_text.set("No se pudo completar la operación.")
                    messagebox.showerror("No se pudo completar", value)
                    self._config_state()
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def _config_state(self):
        try:
            state = self.doc.config_state()
            title, description, fg, bg, action = presentation(state)
            self.version_text.set(f"WirePlumber {state.version or 'desconocido'}")
        except DoctorError as exc:
            title, description, fg, bg, action = (
                "No se pudo revisar la corrección", str(exc), WARNING_FG, WARNING_BG, "none"
            )
            self.version_text.set("")
        self.summary_title.set(title)
        self.summary_detail.set(description)
        self.banner.configure(bg=bg)
        self.banner_text.configure(bg=bg)
        self.action_area.configure(bg=bg)
        self.scope_label.configure(bg=bg, fg=GOOD if action == "remove" else MUTED)
        self.title_label.configure(bg=bg, fg=fg)
        self.desc_label.configure(bg=bg, fg=PRIMARY)
        self._show_state(action)

    def refresh(self):
        self._job(self.doc.devices, self._loaded)

    def _loaded(self, devices):
        self.devices = {x.mac: x for x in devices}
        self._populate()
        self._config_state()
        self.status_text.set(f"{len(devices)} dispositivos emparejados encontrados.")

    def _populate(self):
        prev = self.tree.selection()[0] if self.tree.selection() else None
        for item in self.tree.get_children():
            self.tree.delete(item)
        for d in self.devices.values():
            if not self.all_devices.get() and not d.is_audio:
                continue
            kind = "Audio estéreo y doble función" if d.dual_role else ("Música estéreo" if d.audio_sink else ("Manos libres" if d.handsfree else "Otro"))
            self.tree.insert("", "end", iid=d.mac,
                             values=(d.name, "Conectado" if d.connected else "Desconectado", kind))
        if prev and self.tree.exists(prev):
            self.tree.selection_set(prev)
        else:
            self.detail_text.set("Selecciona unos auriculares y pulsa «Comprobar sonido».")

    def _selected(self, _evt=None):
        if not self.tree.selection():
            return
        d = self.devices.get(self.tree.selection()[0])
        if d:
            self.detail_text.set(
                f"{d.name}\n"
                + ("Es compatible con música estéreo. Puedes comprobar si está disponible."
                   if d.audio_sink else "No anuncia música estéreo Bluetooth; este ajuste quizá no sea útil.")
            )

    def diagnose(self):
        if not self.tree.selection():
            messagebox.showinfo("Selecciona unos auriculares", "Primero elige un dispositivo de la lista.")
            return
        d = self.devices[self.tree.selection()[0]]

        def on_result(res):
            if res.flag == "ok":
                text = "✓  Música en alta calidad disponible."
                if not res.active_profile.startswith("a2dp-sink"):
                    text += " Ahora mismo está seleccionado otro modo de sonido."
            elif res.flag == "disconnected":
                text = "El dispositivo está desconectado. Conéctalo y actualiza la lista."
            elif res.flag in ("missing_a2dp", "missing_card"):
                text = "La música en alta calidad no está disponible en este momento. " + res.detail
            else:
                text = res.detail
            self.detail_text.set(f"{d.name}\n{text}")
            self.status_text.set("Comprobación terminada.")
            self._config_state()
        self._job(lambda: self.doc.diagnose(d), on_result)

    def apply(self):
        warning = (
            "Este cambio se aplicará a TODOS los auriculares y altavoces Bluetooth "
            "de este ordenador, no solo al dispositivo seleccionado.\n\n"
            "Podrás seguir escuchando música y utilizando manos libres, pero "
            "el ordenador dejará de recibir música por Bluetooth desde otros equipos.\n\n"
            "El sonido podría interrumpirse brevemente. Puedes quitar la corrección "
            "cuando quieras.\n\n¿Aplicar en todo el equipo?"
        )
        if not messagebox.askyesno("Aplicar a todo el equipo", warning, icon="warning"):
            return

        def on_result(msg):
            self._config_state()
            self.status_text.set("Corrección instalada correctamente.")
            messagebox.showinfo("Corrección aplicada", "El ajuste quedó guardado.\n\n" + msg)
        self._job(self.doc.apply, on_result)

    def restore(self):
        warning = (
            "Se quitará la corrección para TODOS los dispositivos de audio Bluetooth "
            "de este ordenador.\n\n"
            "No se borrará ningún auricular ni su emparejamiento. El sonido puede "
            "interrumpirse unos segundos y podría volver el problema de manos libres.\n\n"
            "Si es tu parche anterior, guardaremos una copia de seguridad.\n\n"
            "¿Quitar la corrección de todo el equipo?"
        )
        if not messagebox.askyesno("Quitar de todo el equipo", warning, icon="warning"):
            return

        def on_result(msg):
            self._config_state()
            self.status_text.set("Corrección quitada correctamente.")
            messagebox.showinfo("Corrección quitada", "Ya no está aplicada la corrección.\n\n" + msg)
        self._job(self.doc.restore, on_result)


def main():
    # Prueba de arranque del ejecutable: valida Tk sin acceder a Bluetooth.
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        print("Bluetooth Audio Doctor: self-test OK")
        return
    root = tk.Tk()
    Window(root)
    root.mainloop()


if __name__ == "__main__":
    main()
