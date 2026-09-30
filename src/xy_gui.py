# xy_gui.py

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.xy_backend import XyclopsBackend
from src.firmware_library import FirmwareLibrary
from src.settings import Settings
from src.lang import Lang
from src.theme import apply_theme
from src.utils import format_digests, md5, save_file, timestamped_path
from src.about import AboutDialog
from src import version

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DUMPS_DIR = os.path.join(_REPO_ROOT, "output", "dumps")

GRID_BIOS = {"cells": 1024, "per_cell": 4, "columns": 64}
GRID_SMC  = {"cells":   64, "per_cell": 4, "columns": 64}


class XyclopsGUI:
    def __init__(self, root):
        self.root = root

        self.settings = Settings()
        self.lang = Lang()
        self.lang.set_language(self.settings.get("language"))

        self.backend = XyclopsBackend(self.settings)
        self.library = FirmwareLibrary()
        self.library.set_root(self.settings.get("library_root"))

        self.current_cells = []
        self.cell_state = []
        self._grid_spec = None
        self._effective_theme = "light"

        self.busy = False
        self._port_map = {}
        self._bios_files = {}
        self._smc_files = {}

        self._apply_title()
        self._effective_theme = apply_theme(self.root,
                                            self.settings.get("appearance"))

        self._build_ui()
        self._apply_language_to_widgets()

        self.refresh_ports()
        self.refresh_library()

        if self.settings.get("auto_detect_on_startup"):
            self.root.after(150, self._startup_auto_detect)

    # =====================================================================
    # Language helpers
    # =====================================================================
    def t(self, key, **fmt):
        return self.lang(key, **fmt)

    def _apply_title(self):
        self.root.title(version.version_string())

    # =====================================================================
    # UI construction
    # =====================================================================
    def _build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=(8, 4))

        self.port_label = ttk.Label(top, text=self.t("top.port"))
        self.port_label.pack(side="left")

        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var,
                                       state="readonly", width=40)
        self.port_combo.pack(side="left", padx=4)

        self.refresh_btn = ttk.Button(top, text=self.t("top.refresh"),
                                      command=self.refresh_ports)
        self.refresh_btn.pack(side="left", padx=2)

        self.connect_btn = ttk.Button(top, text=self.t("top.connect"),
                                      command=self.on_connect)
        self.connect_btn.pack(side="left", padx=2)

        self.settings_btn = ttk.Button(top, text="\u2699",
                                       width=3,
                                       command=self.open_settings)
        self.settings_btn.pack(side="right", padx=2)

        # Status = neutral prefix + colored value.
        # pack(side="right") stacks right-to-left, so value packs first.
        self.status_value_label = ttk.Label(
            top, text=self.t("top.status_not_connected"))
        self.status_value_label.pack(side="right", padx=(0, 8))

        self.status_prefix_label = ttk.Label(
            top, text=self.t("top.status_prefix"))
        self.status_prefix_label.pack(side="right")

        self._set_status_color("idle")

        prog_outer = ttk.LabelFrame(self.root, text=" ")
        prog_outer.pack(fill="x", padx=8, pady=(2, 4))

        prog_inner = tk.Frame(prog_outer, bd=1, relief="sunken",
                              highlightthickness=0)
        prog_inner.pack(fill="x", padx=6, pady=(4, 6))

        self.progress_canvas = tk.Canvas(prog_inner, height=180,
                                         highlightthickness=0, bd=0)
        self.progress_canvas.pack(fill="x", padx=1, pady=1)
        self.progress_canvas.bind("<Configure>", self._on_canvas_resize)

        legend = ttk.Frame(prog_outer)
        legend.pack(fill="x", padx=8, pady=(0, 6))
        self.legend_labels = {}
        self._legend_dot(legend, "pending",
                         lambda: self.t("legend.pending"))
        self._legend_dot(legend, "ok",
                         lambda: self.t("legend.ok"))
        self._legend_dot(legend, "error",
                         lambda: self.t("legend.error"))
        self._legend_dot(legend, "retry",
                         lambda: self.t("legend.retry"))

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.tab_dump = ttk.Frame(self.nb)
        self.tab_flash = ttk.Frame(self.nb)
        self.tab_log = ttk.Frame(self.nb)

        self.nb.add(self.tab_dump, text=self.t("tabs.dump"))
        self.nb.add(self.tab_flash, text=self.t("tabs.flash"))
        self.nb.add(self.tab_log, text=self.t("tabs.log"))

        self._build_dump_tab()
        self._build_flash_tab()
        self._build_log_tab()

        status_strip = ttk.Frame(self.root)
        status_strip.pack(fill="x", side="bottom")
        self.operation_label = ttk.Label(status_strip,
                                         text=self.t("status.idle"),
                                         anchor="w")
        self.operation_label.pack(fill="x", padx=8, pady=2)

        self._draw_grid(GRID_BIOS)

    def _legend_dot(self, parent, key, get_text):
        f = ttk.Frame(parent)
        f.pack(side="left", padx=(0, 12))
        c = tk.Canvas(f, width=12, height=12, highlightthickness=0, bd=0)
        fill = self._color_for_state(key)
        c.create_rectangle(0, 0, 11, 11,
                           outline=self._border_color(),
                           fill=fill)
        c.pack(side="left")
        lbl = ttk.Label(f, text=get_text())
        lbl.pack(side="left", padx=(4, 0))
        self.legend_labels[key] = (lbl, get_text)

    def _build_dump_tab(self):
        f = self.tab_dump

        row = ttk.Frame(f)
        row.pack(fill="x", padx=4, pady=(8, 4))
        self.dump_bios_btn = ttk.Button(row, text=self.t("dump.title_bios"),
                                        command=self.on_dump_bios)
        self.dump_bios_btn.pack(side="left", padx=4)
        self.dump_smc_btn = ttk.Button(row, text=self.t("dump.title_smc"),
                                       command=self.on_dump_smc)
        self.dump_smc_btn.pack(side="left", padx=4)

        self.dump_info_header = ttk.Label(f, text=self.t("dump.info_header"))
        self.dump_info_header.pack(anchor="w", padx=4, pady=(12, 0))

        self.dump_info = tk.Text(f, height=8, wrap="none")
        self.dump_info.pack(fill="both", expand=True, padx=4, pady=4)
        self.dump_info.configure(state="disabled")

    def _build_flash_tab(self):
        f = self.tab_flash

        LABEL_MIN = 100

        def make_group(title):
            g = ttk.LabelFrame(f, text=title)
            g.pack(fill="x", padx=4, pady=6)
            g.grid_columnconfigure(0, minsize=LABEL_MIN, weight=0)
            g.grid_columnconfigure(1, weight=1)
            g.grid_columnconfigure(2, weight=0)
            return g

        def add_row(parent, row_idx, label_text, input_widget, btn_frame):
            lbl = ttk.Label(parent, text=label_text)
            lbl.grid(row=row_idx, column=0, sticky="w",
                     padx=(8, 4), pady=4)
            input_widget.grid(row=row_idx, column=1, sticky="ew",
                              padx=4, pady=4)
            btn_frame.grid(row=row_idx, column=2, sticky="e",
                           padx=(4, 8), pady=4)
            return lbl

        self.bios_group = make_group(self.t("flash.bios_group"))

        self.bios_combo_var = tk.StringVar()
        self.bios_combo = ttk.Combobox(self.bios_group,
                                       textvariable=self.bios_combo_var,
                                       state="readonly")
        self.bios_combo.bind("<<ComboboxSelected>>",
                             self._on_bios_combo_selected)

        self.bios_lib_label = add_row(
            self.bios_group, 0,
            self.t("flash.from_library"),
            self.bios_combo,
            ttk.Frame(self.bios_group))

        self.bios_path_var = tk.StringVar()
        self.bios_entry = ttk.Entry(self.bios_group,
                                    textvariable=self.bios_path_var)

        self.bios_btn_frame = ttk.Frame(self.bios_group)
        self.bios_browse_btn = ttk.Button(self.bios_btn_frame,
                                          text=self.t("flash.browse"),
                                          command=self.on_browse_bios)
        self.bios_browse_btn.pack(side="left", padx=2)
        self.bios_flash_btn = ttk.Button(self.bios_btn_frame,
                                         text=self.t("flash.flash_bios"),
                                         command=self.on_flash_bios)
        self.bios_flash_btn.pack(side="left", padx=2)
        self.bios_verify_btn = ttk.Button(self.bios_btn_frame,
                                          text=self.t("flash.verify_bios"),
                                          command=self.on_verify_bios)
        self.bios_verify_btn.pack(side="left", padx=2)

        self.bios_sel_label = add_row(
            self.bios_group, 1,
            self.t("flash.selected_file"),
            self.bios_entry,
            self.bios_btn_frame)

        self.smc_group = make_group(self.t("flash.smc_group"))

        self.smc_combo_var = tk.StringVar()
        self.smc_combo = ttk.Combobox(self.smc_group,
                                      textvariable=self.smc_combo_var,
                                      state="readonly")
        self.smc_combo.bind("<<ComboboxSelected>>",
                            self._on_smc_combo_selected)

        self.smc_lib_label = add_row(
            self.smc_group, 0,
            self.t("flash.from_library"),
            self.smc_combo,
            ttk.Frame(self.smc_group))

        self.smc_path_var = tk.StringVar()
        self.smc_entry = ttk.Entry(self.smc_group,
                                   textvariable=self.smc_path_var)

        self.smc_btn_frame = ttk.Frame(self.smc_group)
        self.smc_browse_btn = ttk.Button(self.smc_btn_frame,
                                         text=self.t("flash.browse"),
                                         command=self.on_browse_smc)
        self.smc_browse_btn.pack(side="left", padx=2)
        self.smc_flash_btn = ttk.Button(self.smc_btn_frame,
                                        text=self.t("flash.flash_smc"),
                                        command=self.on_flash_smc)
        self.smc_flash_btn.pack(side="left", padx=2)
        self.smc_verify_btn = ttk.Button(self.smc_btn_frame,
                                         text=self.t("flash.verify_smc"),
                                         command=self.on_verify_smc)
        self.smc_verify_btn.pack(side="left", padx=2)

        self.smc_sel_label = add_row(
            self.smc_group, 1,
            self.t("flash.selected_file"),
            self.smc_entry,
            self.smc_btn_frame)

        self.flash_info_header = ttk.Label(f,
                                           text=self.t("flash.info_header"))
        self.flash_info_header.pack(anchor="w", padx=4, pady=(12, 0))
        self.flash_info = tk.Text(f, height=8, wrap="none")
        self.flash_info.pack(fill="both", expand=True, padx=4, pady=4)
        self.flash_info.configure(state="disabled")

    def _build_log_tab(self):
        f = self.tab_log
        self.log_text = tk.Text(f, height=15)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_refresh_btn = ttk.Button(f, text=self.t("log.refresh"),
                                          command=self.refresh_log)
        self.log_refresh_btn.pack(pady=4)

    # =====================================================================
    # Language application
    # =====================================================================
    def _apply_language_to_widgets(self):
        self._apply_title()

        self.port_label.configure(text=self.t("top.port"))
        self.refresh_btn.configure(text=self.t("top.refresh"))
        self.connect_btn.configure(text=self.t("top.connect"))
        self.status_prefix_label.configure(text=self.t("top.status_prefix"))

        self.nb.tab(self.tab_dump, text=self.t("tabs.dump"))
        self.nb.tab(self.tab_flash, text=self.t("tabs.flash"))
        self.nb.tab(self.tab_log, text=self.t("tabs.log"))

        self.dump_bios_btn.configure(text=self.t("dump.title_bios"))
        self.dump_smc_btn.configure(text=self.t("dump.title_smc"))
        self.dump_info_header.configure(text=self.t("dump.info_header"))

        self.bios_group.configure(text=self.t("flash.bios_group"))
        self.smc_group.configure(text=self.t("flash.smc_group"))
        self.bios_lib_label.configure(text=self.t("flash.from_library"))
        self.smc_lib_label.configure(text=self.t("flash.from_library"))
        self.bios_sel_label.configure(text=self.t("flash.selected_file"))
        self.smc_sel_label.configure(text=self.t("flash.selected_file"))
        self.bios_browse_btn.configure(text=self.t("flash.browse"))
        self.smc_browse_btn.configure(text=self.t("flash.browse"))
        self.bios_flash_btn.configure(text=self.t("flash.flash_bios"))
        self.smc_flash_btn.configure(text=self.t("flash.flash_smc"))
        self.bios_verify_btn.configure(text=self.t("flash.verify_bios"))
        self.smc_verify_btn.configure(text=self.t("flash.verify_smc"))
        self.flash_info_header.configure(text=self.t("flash.info_header"))

        self.log_refresh_btn.configure(text=self.t("log.refresh"))

        for key, (lbl, get_text) in self.legend_labels.items():
            lbl.configure(text=get_text())

        self._refresh_status_label()

    def _refresh_status_label(self):
        if self.busy:
            return
        if self.backend.is_connected():
            cur = self.status_value_label.cget("text")
            prefix = self.t("top.status_connected", device="").split("?")[0]
            if not cur.startswith(prefix):
                self.status_value_label.config(
                    text=self.t("top.status_connected", device="?"))
            self._set_status_color("connected")
        else:
            self.status_value_label.config(
                text=self.t("top.status_not_connected"))
            self._set_status_color("error")

    # =====================================================================
    # Status value colour
    # =====================================================================
    def _set_status_color(self, state):
        color = {
            "idle":      "#888888",
            "busy":      "#C9A227",
            "connected": "#2E9E4F",
            "error":     "#C0392B",
        }.get(state, "#888888")
        try:
            self.status_value_label.configure(foreground=color)
        except tk.TclError:
            pass

    # =====================================================================
    # Grid drawing
    # =====================================================================
    def _color_for_state(self, state):
        dark = self._effective_theme == "dark"
        if state == "ok":
            return "#2E9E4F"
        if state == "error":
            return "#C0392B"
        if state == "retry":
            return "#C9A227"
        return "#2A2A2A" if dark else "#E8E8E8"

    def _border_color(self):
        return "#3A3A3A" if self._effective_theme == "dark" else "#B8B8B8"

    def _canvas_bg(self):
        return "#1E1E1E" if self._effective_theme == "dark" else "#F4F4F4"

    def _on_canvas_resize(self, _event=None):
        if self._grid_spec is not None:
            self._draw_grid(self._grid_spec, preserve_state=True)

    def _draw_grid(self, grid_spec, preserve_state=False):
        canvas = self.progress_canvas
        prev_state = list(self.cell_state) if preserve_state else []
        self._grid_spec = grid_spec
        canvas.delete("all")
        canvas.configure(bg=self._canvas_bg())
        self.current_cells = []

        cells = grid_spec["cells"]
        cols = grid_spec.get("columns", 64)
        rows = max(1, (cells + cols - 1) // cols)

        canvas.update_idletasks()
        w = canvas.winfo_width()
        if w <= 1:
            w = 720
        h = canvas.winfo_height()
        if h <= 1:
            h = 180

        gap = 1
        cell_w = max(1, (w - gap * (cols + 1)) / cols)
        cell_h = max(1, (h - gap * (rows + 1)) / rows)

        border = self._border_color()
        for i in range(cells):
            col = i % cols
            row = i // cols
            x0 = gap + col * (cell_w + gap)
            y0 = gap + row * (cell_h + gap)
            x1 = x0 + cell_w
            y1 = y0 + cell_h

            if preserve_state and i < len(prev_state):
                state = prev_state[i]
            else:
                state = "pending"

            rect = canvas.create_rectangle(x0, y0, x1, y1,
                                           outline=border,
                                           fill=self._color_for_state(state))
            self.current_cells.append(rect)

        if preserve_state and prev_state:
            self.cell_state = prev_state[:cells]
            while len(self.cell_state) < cells:
                self.cell_state.append("pending")
        else:
            self.cell_state = ["pending"] * cells

    def _init_grid(self, grid_spec):
        self._draw_grid(grid_spec, preserve_state=False)

    def _progress_cb_threadsafe(self, idx, total, status):
        self.root.after(0, self._progress_cb, idx, total, status)

    def _progress_cb(self, idx, total, status):
        if self._grid_spec is None or not self.current_cells:
            return
        per_cell = self._grid_spec["per_cell"]
        cell_idx = idx // per_cell
        if cell_idx < 0 or cell_idx >= len(self.current_cells):
            return

        cur = self.cell_state[cell_idx]
        new = cur
        if status == "error":
            new = "error"
        elif status == "retry" and cur != "error":
            new = "retry"
        elif status == "ok" and cur not in ("error", "retry"):
            new = "ok"

        if new != cur:
            self.cell_state[cell_idx] = new
            self.progress_canvas.itemconfig(
                self.current_cells[cell_idx],
                fill=self._color_for_state(new))

        if total > 0:
            pct = int(((idx + 1) / total) * 100)
            base = self.operation_label.cget("text").rsplit(":", 1)[0]
            self.operation_label.config(text=f"{base}: {pct}%")

    # =====================================================================
    # Firmware library
    # =====================================================================
    def refresh_library(self):
        bios = self.library.list_files("bios")
        smc = self.library.list_files("smc")

        self._bios_files = {self._short_label(p): p for p in bios}
        self._smc_files = {self._short_label(p): p for p in smc}

        self.bios_combo["values"] = list(self._bios_files.keys())
        self.smc_combo["values"] = list(self._smc_files.keys())

        if not self._bios_files:
            self.bios_combo_var.set("")
        if not self._smc_files:
            self.smc_combo_var.set("")

    def _short_label(self, path):
        parent = os.path.basename(os.path.dirname(path)) or "."
        return f"{os.path.basename(path)}  ({parent})"

    def _on_bios_combo_selected(self, _event=None):
        label = self.bios_combo_var.get()
        path = self._bios_files.get(label)
        if path:
            self.bios_path_var.set(path)

    def _on_smc_combo_selected(self, _event=None):
        label = self.smc_combo_var.get()
        path = self._smc_files.get(label)
        if path:
            self.smc_path_var.set(path)

    def _sync_combo_to_path(self, kind, path):
        table = self._bios_files if kind == "bios" else self._smc_files
        combo_var = (self.bios_combo_var if kind == "bios"
                     else self.smc_combo_var)
        for label, p in table.items():
            if os.path.normcase(os.path.abspath(p)) == \
               os.path.normcase(os.path.abspath(path)):
                combo_var.set(label)
                return
        combo_var.set("")

    # =====================================================================
    # Port handling
    # =====================================================================
    def refresh_ports(self):
        ports = self.backend.list_ports()
        if not ports:
            self.port_combo["values"] = [self.t("top.no_ports")]
            self.port_var.set(self.t("top.no_ports"))
            self._port_map = {}
            return
        labels = [label for (_, label, _) in ports]
        self._port_map = {label: device for (device, label, _) in ports}
        self.port_combo["values"] = labels
        if self.port_var.get() not in labels:
            self.port_var.set(labels[0])

    def _startup_auto_detect(self):
        if self.busy:
            return
        self.set_busy(True, self.t("conn.detecting"))
        self.log("INFO_HIGH", self.t("conn.detecting_log"))

        def work():
            try:
                device = self.backend.auto_detect()
                self.root.after(0, self._on_detect_done, device, None, True)
            except Exception as e:
                self.root.after(0, self._on_detect_done, None, str(e), True)

        threading.Thread(target=work, daemon=True).start()

    def _on_detect_done(self, device, err, quiet):
        self.set_busy(False)
        if err:
            self.log("ERROR", self.t("conn.detect_error", err=err))
            if not quiet:
                messagebox.showerror(self.t("dump.failed_title"),
                                     self.t("conn.detect_error", err=err))
            self.refresh_log()
            return
        if device is None:
            self.log("WARNING", self.t("conn.not_found_title"))
            if not quiet:
                messagebox.showwarning(self.t("conn.not_found_title"),
                                       self.t("conn.not_found_body"))
            self.refresh_log()
            return
        for label, dev in self._port_map.items():
            if dev == device:
                self.port_var.set(label)
                break
        self.log("INFO_HIGH", self.t("conn.detected_log", device=device))
        self.refresh_log()

    def on_connect(self):
        if self.busy:
            return
        label = self.port_var.get()
        if label not in self._port_map:
            messagebox.showwarning(self.t("conn.no_port_title"),
                                   self.t("conn.no_port_body"))
            return
        device = self._port_map[label]
        self.set_busy(True, self.t("status.connecting"))

        def work():
            ok = self.backend.connect(device)
            self.root.after(0, self._on_connect_done, ok, device)

        threading.Thread(target=work, daemon=True).start()

    def _on_connect_done(self, ok, device):
        self.set_busy(False)
        if ok:
            self.status_value_label.config(
                text=self.t("top.status_connected", device=device))
            self._set_status_color("connected")
        else:
            self.status_value_label.config(
                text=self.t("top.status_not_connected"))
            self._set_status_color("error")
            messagebox.showerror(
                self.t("conn.failed_title"),
                self.t("conn.failed_body", device=device))
        self.refresh_log()

    # =====================================================================
    # Dump handlers
    # =====================================================================
    def on_dump_bios(self):
        self._run_dump("BIOS", self.backend.dump_bios,
                       GRID_BIOS, 0x40000, "bios_dump")

    def on_dump_smc(self):
        self._run_dump("SMC", self.backend.dump_smc,
                       GRID_SMC, 0x4000, "smc_dump")

    def _run_dump(self, label, fn, grid_spec, size, base_name):
        if self.busy:
            return
        if not self.backend.is_connected():
            messagebox.showwarning(self.t("conn.not_connected_title"),
                                   self.t("conn.not_connected_body"))
            return

        double_read = self.settings.get("double_read_on_dump")

        self.set_busy(True, self.t("status.dumping", label=label, percent=0))
        self._init_grid(grid_spec)

        def work():
            try:
                result = fn(size=size, double_read=double_read,
                            progress_cb=self._progress_cb_threadsafe)
            except Exception as e:
                self.root.after(0, self._on_dump_done, label, base_name,
                                None, str(e))
                return
            self.root.after(0, self._on_dump_done, label, base_name,
                            result, None)

        threading.Thread(target=work, daemon=True).start()

    def _on_dump_done(self, label, base_name, result, err):
        self.set_busy(False)
        if err:
            self.log("ERROR", self.t("dump.error_body", label=label, err=err))
            messagebox.showerror(self.t("dump.failed_title"),
                                 self.t("dump.error_body", label=label,
                                        err=err))
            self.refresh_log()
            return
        if result is None:
            messagebox.showerror(self.t("dump.failed_title"),
                                 self.t("dump.failed_body", label=label))
            self.refresh_log()
            return

        status = result.get("status")
        if status == "ok":
            data = result["dump"]
            path = timestamped_path(_DUMPS_DIR, f"{base_name}_verified")
            save_file(path, data)
            info = f"{self.t('flash.file_line', path=path)}\n{format_digests(data)}"
            self._set_info(self.dump_info, info)
            messagebox.showinfo(self.t("dump.done_title"),
                                self.t("dump.done_body", label=label,
                                       info=info))
        elif status == "mismatch":
            p1 = timestamped_path(_DUMPS_DIR, f"{base_name}_1")
            p2 = timestamped_path(_DUMPS_DIR, f"{base_name}_2")
            save_file(p1, result["dump1"])
            save_file(p2, result["dump2"])
            info = (f"Double-read MISMATCH\n"
                    f"{p1}: MD5 {md5(result['dump1'])}\n"
                    f"{p2}: MD5 {md5(result['dump2'])}")
            self._set_info(self.dump_info, info)
            messagebox.showwarning(self.t("dump.mismatch_title"), info)
        else:
            messagebox.showerror(self.t("dump.failed_title"),
                                 self.t("dump.unexpected", status=status))
        self.refresh_log()

    # =====================================================================
    # Flash handlers
    # =====================================================================
    def on_browse_bios(self):
        initial = (self.library.root
                   if os.path.isdir(self.library.root) else os.getcwd())
        path = filedialog.askopenfilename(title=self.t("flash.flash_bios"),
                                          initialdir=initial)
        if path:
            self.bios_path_var.set(path)
            self._sync_combo_to_path("bios", path)

    def on_browse_smc(self):
        initial = (self.library.root
                   if os.path.isdir(self.library.root) else os.getcwd())
        path = filedialog.askopenfilename(title=self.t("flash.flash_smc"),
                                          initialdir=initial)
        if path:
            self.smc_path_var.set(path)
            self._sync_combo_to_path("smc", path)

    def on_flash_bios(self):
        self._run_flash("BIOS", self.bios_path_var.get(),
                        self.backend.flash_bios, GRID_BIOS, 0x40000)

    def on_flash_smc(self):
        self._run_flash("SMC", self.smc_path_var.get(),
                        self.backend.flash_smc, GRID_SMC, 0x4000)

    def _run_flash(self, label, path, fn, grid_spec, size):
        if self.busy:
            return
        if not self.backend.is_connected():
            messagebox.showwarning(self.t("conn.not_connected_title"),
                                   self.t("conn.not_connected_body"))
            return
        if not path:
            messagebox.showwarning(self.t("flash.no_file_title"),
                                   self.t("flash.no_file_body", label=label))
            return
        if not os.path.isfile(path):
            messagebox.showerror(self.t("flash.file_missing_title"),
                                 self.t("flash.file_missing_body", path=path))
            return
        if not messagebox.askyesno(
                self.t("flash.confirm_title"),
                self.t("flash.confirm_body", label=label, path=path)):
            return

        with open(path, "rb") as f:
            src = f.read()

        verify = self.settings.get("verify_after_flash")
        backup = self.settings.get("backup_before_flash")
        fast = self.settings.get("fast_mode")

        self.set_busy(True, self.t("status.flashing", label=label, percent=0))
        self._init_grid(grid_spec)

        def work():
            try:
                ok = fn(path, override=False, verify=verify, fast=fast,
                        progress_cb=self._progress_cb_threadsafe,
                        backup=backup)
            except Exception as e:
                self.root.after(0, self._on_flash_done, label, path, src,
                                False, str(e))
                return
            self.root.after(0, self._on_flash_done, label, path, src,
                            ok, None)

        threading.Thread(target=work, daemon=True).start()

    def _on_flash_done(self, label, path, src, ok, err):
        self.set_busy(False)
        if err:
            self.log("ERROR", self.t("flash.error_body", label=label, err=err))
            messagebox.showerror(self.t("dump.failed_title"),
                                 self.t("flash.error_body", label=label,
                                        err=err))
            self.refresh_log()
            return

        result_str = (self.t("flash.result_ok") if ok
                      else self.t("flash.result_failed"))
        info = (f"{self.t('flash.file_line', path=path)}\n"
                f"{self.t('flash.source_digest')}\n"
                f"{format_digests(src)}\n"
                f"Result: {result_str}")
        self._set_info(self.flash_info, info)

        if ok:
            messagebox.showinfo(self.t("flash.done_title"),
                                self.t("flash.done_body", label=label,
                                       info=info))
        else:
            messagebox.showerror(self.t("flash.failed_title"),
                                 self.t("flash.failed_body", label=label,
                                        info=info))
        self.refresh_log()

    # =====================================================================
    # Verify-only handlers
    # =====================================================================
    def on_verify_bios(self):
        self._run_verify("BIOS", self.bios_path_var.get(),
                         self.backend.verify_bios, GRID_BIOS, 0x40000)

    def on_verify_smc(self):
        self._run_verify("SMC", self.smc_path_var.get(),
                         self.backend.verify_smc, GRID_SMC, 0x4000)

    def _run_verify(self, label, path, fn, grid_spec, size):
        if self.busy:
            return
        if not self.backend.is_connected():
            messagebox.showwarning(self.t("conn.not_connected_title"),
                                   self.t("conn.not_connected_body"))
            return
        if not path:
            messagebox.showwarning(self.t("flash.no_file_title"),
                                   self.t("flash.no_file_body", label=label))
            return
        if not os.path.isfile(path):
            messagebox.showerror(self.t("flash.file_missing_title"),
                                 self.t("flash.file_missing_body", path=path))
            return

        with open(path, "rb") as f:
            src = f.read()

        fast = self.settings.get("fast_mode")

        self.set_busy(True, self.t("status.verifying", label=label, percent=0))
        self._init_grid(grid_spec)

        def work():
            try:
                ok = fn(path, fast=fast,
                        progress_cb=self._progress_cb_threadsafe)
            except Exception as e:
                self.root.after(0, self._on_verify_done, label, path, src,
                                False, str(e))
                return
            self.root.after(0, self._on_verify_done, label, path, src,
                            ok, None)

        threading.Thread(target=work, daemon=True).start()

    def _on_verify_done(self, label, path, src, ok, err):
        self.set_busy(False)
        if err:
            self.log("ERROR", self.t("flash.verify_error_body",
                                     label=label, err=err))
            messagebox.showerror(self.t("dump.failed_title"),
                                 self.t("flash.verify_error_body",
                                        label=label, err=err))
            self.refresh_log()
            return

        result_str = (self.t("flash.result_pass") if ok
                      else self.t("flash.result_fail"))
        info = (f"{self.t('flash.file_line', path=path)}\n"
                f"{format_digests(src)}\n"
                f"Result: {result_str}")
        self._set_info(self.flash_info, info)

        if ok:
            messagebox.showinfo(self.t("flash.verify_passed_title"),
                                self.t("flash.verify_passed_body",
                                       label=label, info=info))
        else:
            messagebox.showerror(self.t("flash.verify_failed_title"),
                                 self.t("flash.verify_failed_body",
                                        label=label, info=info))
        self.refresh_log()

    # =====================================================================
    # Settings dialog
    # =====================================================================
    def open_settings(self):
        SettingsDialog(self.root, self, self.settings, self.lang)
        self._apply_language_to_widgets()
        self.library.set_root(self.settings.get("library_root"))
        self.refresh_library()
        self._effective_theme = apply_theme(
            self.root, self.settings.get("appearance"))
        if self._grid_spec is not None:
            self._draw_grid(self._grid_spec, preserve_state=True)

    # =====================================================================
    # Helpers
    # =====================================================================
    def _set_info(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state="disabled")

    def set_busy(self, busy, status=None):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for w in (self.connect_btn, self.refresh_btn,
                  self.dump_bios_btn, self.dump_smc_btn,
                  self.bios_flash_btn, self.bios_verify_btn,
                  self.smc_flash_btn, self.smc_verify_btn,
                  self.bios_browse_btn, self.smc_browse_btn,
                  self.settings_btn):
            try:
                w.configure(state=state)
            except tk.TclError:
                pass

        if status:
            self.status_value_label.config(
                text=self.t("top.status_busy", status=status))
            self.operation_label.config(text=status)
            if self.backend.is_connected():
                self._set_status_color("connected")
            else:
                self._set_status_color("busy")
        elif not self.backend.is_connected():
            self.status_value_label.config(
                text=self.t("top.status_not_connected"))
            self.operation_label.config(text=self.t("status.idle"))
            self._set_status_color("error")
        else:
            cur = self.status_value_label.cget("text")
            if not cur.startswith("Connected"):
                self.status_value_label.config(
                    text=self.t("top.status_connected", device="?"))
            self.operation_label.config(text=self.t("status.idle"))
            self._set_status_color("connected")

    def log(self, level, msg):
        self.backend.log.log(msg, level)

    def refresh_log(self):
        self.log_text.delete("1.0", tk.END)
        for level, msg in self.backend.get_gui_log():
            self.log_text.insert(tk.END, f"[{level}] {msg}\n")


# =========================================================================
# Settings dialog
# =========================================================================
class SettingsDialog:
    def __init__(self, parent, gui, settings, lang):
        self.gui = gui
        self.settings = settings
        self.lang = lang
        self.lang.reload()

        self.top = tk.Toplevel(parent)
        self.top.title(self.lang("settings.title"))
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)

        self._build()
        self.top.wait_window()

    def t(self, key, **fmt):
        return self.lang(key, **fmt)

    def _build(self):
        pad = {"padx": 8, "pady": 4}

        app_frame = ttk.LabelFrame(self.top,
                                   text=self.t("settings.appearance"))
        app_frame.pack(fill="x", **pad)

        self.appearance_var = tk.StringVar(
            value=self.settings.get("appearance"))
        for value in ("system", "light", "dark"):
            ttk.Radiobutton(
                app_frame,
                text=self.t(f"settings.appearance_{value}"),
                value=value,
                variable=self.appearance_var
            ).pack(anchor="w", padx=8, pady=2)

        lang_frame = ttk.LabelFrame(self.top, text=self.t("settings.language"))
        lang_frame.pack(fill="x", **pad)

        self.lang_var = tk.StringVar()
        options = self.lang.available()
        self._lang_options = {display: code for (code, display) in options}
        current_code = self.settings.get("language")
        current_display = None
        for code, display in options:
            if code == current_code:
                current_display = display
                break
        if current_display is None:
            current_display = options[0][1] if options else "English"
        self.lang_var.set(current_display)

        combo = ttk.Combobox(lang_frame, textvariable=self.lang_var,
                             state="readonly",
                             values=[d for (_, d) in options],
                             width=30)
        combo.pack(anchor="w", padx=8, pady=4)

        lib_frame = ttk.LabelFrame(self.top, text=self.t("settings.library"))
        lib_frame.pack(fill="x", **pad)

        self.lib_var = tk.StringVar(value=self.settings.get("library_root"))
        row = ttk.Frame(lib_frame)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Entry(row, textvariable=self.lib_var,
                  width=40).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=self.t("library.change"),
                   command=self._pick_library).pack(side="left", padx=4)

        adv_frame = ttk.LabelFrame(self.top, text=self.t("settings.advanced"))
        adv_frame.pack(fill="x", **pad)

        self.auto_detect_var = tk.BooleanVar(
            value=self.settings.get("auto_detect_on_startup"))
        self.double_read_var = tk.BooleanVar(
            value=self.settings.get("double_read_on_dump"))
        self.verify_after_var = tk.BooleanVar(
            value=self.settings.get("verify_after_flash"))
        self.backup_var = tk.BooleanVar(
            value=self.settings.get("backup_before_flash"))
        self.fast_var = tk.BooleanVar(
            value=self.settings.get("fast_mode"))

        ttk.Checkbutton(adv_frame, text=self.t("settings.auto_detect"),
                        variable=self.auto_detect_var).pack(anchor="w",
                                                            padx=8, pady=2)
        ttk.Checkbutton(adv_frame, text=self.t("settings.double_read"),
                        variable=self.double_read_var).pack(anchor="w",
                                                            padx=8, pady=2)
        ttk.Checkbutton(adv_frame, text=self.t("settings.verify_after"),
                        variable=self.verify_after_var).pack(anchor="w",
                                                             padx=8, pady=2)
        ttk.Checkbutton(adv_frame, text=self.t("settings.backup_before"),
                        variable=self.backup_var).pack(anchor="w",
                                                       padx=8, pady=2)
        ttk.Checkbutton(adv_frame, text=self.t("settings.fast_mode"),
                        variable=self.fast_var).pack(anchor="w",
                                                     padx=8, pady=2)

        btns = ttk.Frame(self.top)
        btns.pack(fill="x", padx=8, pady=8)

        ttk.Button(btns, text=self.t("settings.about_button"),
                   command=self._open_about).pack(side="left", padx=4)
        ttk.Label(btns, text=f"v{version.VERSION}",
                  foreground="#888").pack(side="left", padx=4)

        ttk.Button(btns, text=self.t("settings.cancel"),
                   command=self.top.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text=self.t("settings.save"),
                   command=self._save).pack(side="right", padx=4)

    def _pick_library(self):
        folder = filedialog.askdirectory(
            title=self.t("library.choose_title"),
            initialdir=self.lib_var.get() or os.getcwd())
        if folder:
            self.lib_var.set(folder)

    def _open_about(self):
        AboutDialog(self.top, self.lang)

    def _save(self):
        self.settings.set("appearance", self.appearance_var.get())

        display = self.lang_var.get()
        code = self._lang_options.get(display, "en")
        self.settings.set("language", code)
        self.lang.set_language(code)

        self.settings.set("library_root", self.lib_var.get())

        self.settings.set("auto_detect_on_startup", self.auto_detect_var.get())
        self.settings.set("double_read_on_dump", self.double_read_var.get())
        self.settings.set("verify_after_flash", self.verify_after_var.get())
        self.settings.set("backup_before_flash", self.backup_var.get())
        self.settings.set("fast_mode", self.fast_var.get())

        self.top.destroy()


def main():
    root = tk.Tk()
    app = XyclopsGUI(root)
    root.mainloop()